# ruff: noqa: F401, F811 - imported fixture names are required by pytest
from __future__ import annotations

import multiprocessing
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
from typing import Literal

import pytest
import redis
from bluetape.leader import (
    ActionFailed,
    Elected,
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderLeaseLostError,
    LeaderReleaseError,
    NotHeld,
    Renewed,
)
from bluetape.leader.redis import RedisDistributedLock, RedisLeaderElector
from leader_redis_test_support import (
    TESTCONTAINERS_MARK,
    RedisEndpoint,
    assert_database_clean,
    borrowed_sync_client,
    clean_redis_database,
    clean_sync_keys,
    leader_keys,
    new_sync_client,
    observed_timing,
    redis_endpoint,
    unique_logical_name,
)

pytestmark = TESTCONTAINERS_MARK

_SHORT_LEASE = 0.20
_POLL_INTERVAL = 0.01
_ACL_SHAPES = [
    (auth, protocol, client_name, database)
    for auth in ("none", "password", "username-password")
    for protocol in (2, 3)
    for client_name in (None, "leader-test")
    for database in (0, 1)
]


@dataclass(frozen=True, slots=True)
class ChildResult:
    scenario_id: Literal["sync-lifecycle", "sync-contention", "sync-renewal-loss"]
    status: Literal["passed", "failed"]
    public_outcome: Literal[
        "elected",
        "skipped",
        "action-failed",
        "backend-error",
        "lease-lost",
        "release-error",
        "execution-error",
    ]
    action_count: int
    fencing_relation: Literal["strictly-increasing", "not-applicable"]
    lease_cleanup: Literal["released", "ttl-only", "not-applicable"]
    worker_delta: int
    task_delta: int
    borrowed_client_usable: bool
    failure_kind: Literal["none", "assertion", "unexpected-public-outcome"]


def _options(
    *,
    wait: float = 0.0,
    lease: float = 1.0,
    minimum: float = 0.0,
    auto_renew: bool = False,
    renew_interval: float | None = None,
) -> LeaderElectionOptions:
    return LeaderElectionOptions(
        wait_time=timedelta(seconds=wait),
        lease_time=timedelta(seconds=lease),
        min_lease_time=timedelta(seconds=minimum),
        auto_renew=auto_renew,
        renew_interval=(None if renew_interval is None else timedelta(seconds=renew_interval)),
    )


def _wait_until_absent(client: redis.Redis, key: bytes, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while client.exists(key):
        if time.monotonic() >= deadline:
            pytest.fail("Redis expiry deadline exceeded", pytrace=False)
        time.sleep(_POLL_INTERVAL)


def _renew_worker_count() -> int:
    return sum(thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate())


def _command_calls(commandstats: dict[str, object], command: str) -> int:
    details = commandstats.get(f"cmdstat_{command}", {})
    assert isinstance(details, dict)
    return int(details.get("calls", 0))


def _sync_lifecycle_child(
    endpoint: RedisEndpoint,
    logical_name: str,
    terminal: multiprocessing.Queue[ChildResult],
) -> None:
    client = new_sync_client(endpoint)
    keys = leader_keys(logical_name)
    baseline = _renew_worker_count()
    action_count = 0
    tokens: list[int] = []
    try:
        timing = observed_timing(client)
        renew_interval = timing.renew + 0.05
        assert timing.renew + renew_interval < 2.0
        lock = RedisDistributedLock(client)
        elector = RedisLeaderElector(client)
        first = lock.try_acquire(logical_name, _options(lease=1.0))
        assert first is not None
        tokens.append(first.lease.fencing_token)
        assert isinstance(first.renew(), Renewed)
        first.release()

        second = lock.try_acquire(logical_name, _options(lease=1.0))
        assert second is not None
        tokens.append(second.lease.fencing_token)
        second.release()

        def action(_lease: object) -> str:
            nonlocal action_count
            action_count += 1
            time.sleep(6.1)
            return "completed"

        result = elector.run_if_leader_result(
            logical_name,
            action,
            _options(lease=2.0, auto_renew=True, renew_interval=renew_interval),
        )
        assert isinstance(result, Elected)
        assert result.value == "completed"
        tokens.append(result.lease.fencing_token)
        assert client.exists(keys[0]) == 0
        usable = client.ping() is True
        worker_delta = _renew_worker_count() - baseline
        terminal.put(
            ChildResult(
                scenario_id="sync-lifecycle",
                status="passed",
                public_outcome="elected",
                action_count=action_count,
                fencing_relation=(
                    "strictly-increasing"
                    if all(left < right for left, right in pairwise(tokens))
                    else "not-applicable"
                ),
                lease_cleanup="released",
                worker_delta=worker_delta,
                task_delta=0,
                borrowed_client_usable=usable,
                failure_kind="none",
            )
        )
    except AssertionError:
        terminal.put(
            ChildResult(
                scenario_id="sync-lifecycle",
                status="failed",
                public_outcome="execution-error",
                action_count=action_count,
                fencing_relation="not-applicable",
                lease_cleanup="not-applicable",
                worker_delta=_renew_worker_count() - baseline,
                task_delta=0,
                borrowed_client_usable=False,
                failure_kind="assertion",
            )
        )
        raise SystemExit(1) from None
    except BaseException:
        raise SystemExit(2) from None
    finally:
        clean_sync_keys(client, keys)
        client.close()


def _sync_renewal_loss_child(
    endpoint: RedisEndpoint,
    logical_name: str,
    terminal: multiprocessing.Queue[ChildResult],
) -> None:
    client = new_sync_client(endpoint)
    keys = leader_keys(logical_name)
    baseline = _renew_worker_count()
    action_count = 0
    try:
        timing = observed_timing(client)
        renew_interval = timing.renew + 0.05

        def invalidate(_lease: object) -> str:
            nonlocal action_count
            action_count += 1
            client.delete(keys[0])
            time.sleep(renew_interval + 0.20)
            return "must-not-complete"

        with pytest.raises(LeaderLeaseLostError):
            RedisLeaderElector(client).run_if_leader_result(
                logical_name,
                invalidate,
                _options(lease=2.0, auto_renew=True, renew_interval=renew_interval),
            )
        assert client.exists(keys[0]) == 0
        terminal.put(
            ChildResult(
                scenario_id="sync-renewal-loss",
                status="passed",
                public_outcome="lease-lost",
                action_count=action_count,
                fencing_relation="not-applicable",
                lease_cleanup="not-applicable",
                worker_delta=_renew_worker_count() - baseline,
                task_delta=0,
                borrowed_client_usable=client.ping() is True,
                failure_kind="none",
            )
        )
    except AssertionError:
        terminal.put(
            ChildResult(
                scenario_id="sync-renewal-loss",
                status="failed",
                public_outcome="execution-error",
                action_count=action_count,
                fencing_relation="not-applicable",
                lease_cleanup="not-applicable",
                worker_delta=_renew_worker_count() - baseline,
                task_delta=0,
                borrowed_client_usable=False,
                failure_kind="assertion",
            )
        )
        raise SystemExit(1) from None
    except BaseException:
        raise SystemExit(2) from None
    finally:
        clean_sync_keys(client, keys)
        client.close()


def test_spawned_sync_lifecycle_crosses_three_ttls_without_leaks(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    context = multiprocessing.get_context("spawn")
    terminal: multiprocessing.Queue[ChildResult] = context.Queue()
    process = context.Process(
        target=_sync_lifecycle_child,
        args=(redis_endpoint, unique_logical_name("spawned-lifecycle"), terminal),
    )
    process.start()
    try:
        process.join(8.0)
        if process.is_alive():
            process.terminate()
            process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join(1.0)
            assert not process.is_alive()
            pytest.fail("sync lifecycle deadline exceeded", pytrace=False)
        assert process.exitcode == 0
        record = terminal.get(timeout=0.5)
        with pytest.raises(queue.Empty):
            terminal.get_nowait()
        assert record == ChildResult(
            scenario_id="sync-lifecycle",
            status="passed",
            public_outcome="elected",
            action_count=1,
            fencing_relation="strictly-increasing",
            lease_cleanup="released",
            worker_delta=0,
            task_delta=0,
            borrowed_client_usable=True,
            failure_kind="none",
        )
    finally:
        if process.is_alive():
            process.terminate()
        process.join(1.0)
        terminal.close()
        terminal.join_thread()
        with borrowed_sync_client(redis_endpoint) as client:
            client.flushdb()
            assert_database_clean(client)


def test_spawned_sync_renewal_loss_prevents_successful_scoped_completion(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as timing_client:
        timing = observed_timing(timing_client)
    deadline = timing.acquire + timing.renew + timing.release + 2.0
    context = multiprocessing.get_context("spawn")
    terminal: multiprocessing.Queue[ChildResult] = context.Queue()
    process = context.Process(
        target=_sync_renewal_loss_child,
        args=(redis_endpoint, unique_logical_name("spawned-renewal-loss"), terminal),
    )
    process.start()
    try:
        process.join(deadline)
        if process.is_alive():
            process.terminate()
            process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join(1.0)
            assert not process.is_alive()
            pytest.fail("sync renewal-loss deadline exceeded", pytrace=False)
        assert process.exitcode == 0
        record = terminal.get(timeout=0.5)
        with pytest.raises(queue.Empty):
            terminal.get_nowait()
        assert record == ChildResult(
            scenario_id="sync-renewal-loss",
            status="passed",
            public_outcome="lease-lost",
            action_count=1,
            fencing_relation="not-applicable",
            lease_cleanup="not-applicable",
            worker_delta=0,
            task_delta=0,
            borrowed_client_usable=True,
            failure_kind="none",
        )
    finally:
        if process.is_alive():
            process.terminate()
            process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join(1.0)
        terminal.close()
        terminal.join_thread()
        with borrowed_sync_client(redis_endpoint) as client:
            client.flushdb()
            assert_database_clean(client)


def test_real_acquire_renew_release_reacquire_and_owner_mismatch(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as client:
        logical_name = unique_logical_name("lifecycle")
        lock = RedisDistributedLock(client)
        first = lock.try_acquire(logical_name, _options(lease=1.0))
        assert first is not None
        assert isinstance(first.renew(), Renewed)
        assert lock.try_acquire(logical_name, _options(lease=1.0)) is None
        first_token = first.lease.fencing_token
        first.release()

        successor = lock.try_acquire(logical_name, _options(lease=1.0))
        assert successor is not None
        assert successor.lease.fencing_token > first_token
        successor.release()
        assert client.ping() is True


def test_expired_owner_cannot_change_successor_record_or_ttl(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as client:
        logical_name = unique_logical_name("stale-owner")
        lease_key, _ = leader_keys(logical_name)
        lock = RedisDistributedLock(client)
        old = lock.try_acquire(logical_name, _options(lease=_SHORT_LEASE))
        assert old is not None
        _wait_until_absent(client, lease_key)

        successor = lock.try_acquire(logical_name, _options(lease=1.0))
        assert successor is not None
        record_before = client.get(lease_key)
        ttl_before = client.pttl(lease_key)
        assert record_before is not None and ttl_before > 0
        commands_before = client.info("commandstats")
        assert isinstance(old.renew(), NotHeld)
        with pytest.raises(LeaderReleaseError):
            old.release()
        commands_after = client.info("commandstats")
        record_after = client.get(lease_key)
        ttl_after = client.pttl(lease_key)

        assert record_after == record_before
        assert 0 < ttl_after <= ttl_before
        assert _command_calls(commands_after, "pexpire") == _command_calls(
            commands_before, "pexpire"
        )
        assert _command_calls(commands_after, "del") == _command_calls(commands_before, "del")
        successor.release()


def test_minimum_lease_survives_release_then_expires_naturally(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as client:
        logical_name = unique_logical_name("minimum-lease")
        lease_key, _ = leader_keys(logical_name)
        lock = RedisDistributedLock(client)
        handle = lock.try_acquire(logical_name, _options(lease=1.0, minimum=0.30))
        assert handle is not None
        handle.release()
        remaining = client.pttl(lease_key)
        assert 0 < remaining <= 300
        assert lock.try_acquire(logical_name, _options(lease=1.0)) is None
        _wait_until_absent(client, lease_key)
        successor = lock.try_acquire(logical_name, _options(lease=1.0))
        assert successor is not None
        successor.release()


def test_action_failure_is_reported_after_real_release(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as client:
        logical_name = unique_logical_name("action-failure")
        lease_key, _ = leader_keys(logical_name)
        failure = ValueError("caller failure")
        result = RedisLeaderElector(client).run_if_leader_result(
            logical_name,
            lambda _: (_ for _ in ()).throw(failure),
            _options(lease=1.0),
        )

        assert isinstance(result, ActionFailed)
        assert result.cause is failure
        assert client.exists(lease_key) == 0


def test_delayed_entry_fails_before_running_body(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as client:
        logical_name = unique_logical_name("delayed-entry")
        lease_key, _ = leader_keys(logical_name)
        handle = RedisDistributedLock(client).try_acquire(
            logical_name, _options(lease=_SHORT_LEASE)
        )
        assert handle is not None
        _wait_until_absent(client, lease_key)
        body_started = False

        with pytest.raises(LeaderLeaseLostError):
            with handle:
                body_started = True

        assert body_started is False


@pytest.mark.parametrize("state", ["malformed", "no-ttl", "wrong-type"])
def test_corrupt_lease_states_fail_closed(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
    state: str,
) -> None:
    del clean_redis_database
    with (
        borrowed_sync_client(redis_endpoint) as admin,
        borrowed_sync_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name(f"corrupt-{state}")
        lease_key, _ = leader_keys(logical_name)
        lock = RedisDistributedLock(client)
        if state == "malformed":
            admin.set(lease_key, b"not-a-lease", px=1000)
        elif state == "no-ttl":
            admin.set(lease_key, b"v1:" + b"A" * 32 + b":1")
        else:
            admin.rpush(lease_key, b"not-a-string")

        with pytest.raises(LeaderBackendError):
            lock.try_acquire(logical_name, _options())


def test_script_cache_flush_uses_eval_fallback_for_full_lifecycle(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with (
        borrowed_sync_client(redis_endpoint) as admin,
        borrowed_sync_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name("noscript")
        lock = RedisDistributedLock(client)
        admin.script_flush()
        handle = lock.try_acquire(logical_name, _options())
        assert handle is not None
        assert isinstance(handle.renew(), Renewed)
        handle.release()
        assert client.ping() is True


def test_fence_counter_is_exact_above_2_to_53_and_overflow_fails_closed(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with (
        borrowed_sync_client(redis_endpoint) as admin,
        borrowed_sync_client(redis_endpoint) as client,
    ):
        lock = RedisDistributedLock(client)
        exact_name = unique_logical_name("large-counter")
        _, exact_fence = leader_keys(exact_name)
        admin.set(exact_fence, b"9007199254740992")
        handle = lock.try_acquire(exact_name, _options())
        assert handle is not None
        assert handle.lease.fencing_token == 9_007_199_254_740_993
        handle.release()

        overflow_name = unique_logical_name("overflow")
        _, overflow_fence = leader_keys(overflow_name)
        admin.set(overflow_fence, b"9223372036854775807")
        with pytest.raises(LeaderBackendError):
            lock.try_acquire(overflow_name, _options())
        assert admin.get(overflow_fence) == b"9223372036854775807"


@pytest.mark.parametrize("auth,protocol,client_name,database", _ACL_SHAPES)
def test_acl_matrix_grants_only_shape_specific_adapter_commands(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
    auth: str,
    protocol: int,
    client_name: str | None,
    database: int,
) -> None:
    del clean_redis_database
    shape_id = f"{os.getpid()}-{auth}-{protocol}-{int(client_name is not None)}-{database}"
    admin_username = f"leader-admin-{shape_id}"
    admin_password = "leader-admin-fixed-password"
    target_username = "default" if auth != "username-password" else f"leader-acl-{shape_id}"
    password = "leader-acl-fixed-password"
    prefix = "leader-acl"
    conditional_permissions = []
    if protocol == 3:
        conditional_permissions.append("+hello")
    if client_name is not None:
        conditional_permissions.append("+client|setname")
    if database != 0:
        conditional_permissions.append("+select")

    with borrowed_sync_client(redis_endpoint) as bootstrap:
        bootstrap.execute_command(
            "ACL",
            "SETUSER",
            admin_username,
            "reset",
            "on",
            f">{admin_password}",
            "~*",
            "+@all",
        )
    admin = new_sync_client(
        redis_endpoint,
        username=admin_username,
        password=admin_password,
        protocol=2,
    )
    restricted: redis.Redis | None = None
    logical_name = unique_logical_name("acl-default")
    keys = leader_keys(logical_name, prefix)
    try:
        credential_rule = "nopass" if auth == "none" else f">{password}"
        admin.execute_command(
            "ACL",
            "SETUSER",
            target_username,
            "reset",
            "on",
            credential_rule,
            f"~{prefix}:*",
            "+evalsha",
            "+eval",
            "+get",
            "+type",
            "+pttl",
            "+incr",
            "+set",
            "+pexpire",
            "+del",
            *conditional_permissions,
        )
        authentication: dict[str, object] = {}
        if auth == "password":
            authentication["password"] = password
        elif auth == "username-password":
            authentication.update(username=target_username, password=password)
        restricted = new_sync_client(
            redis_endpoint,
            **authentication,
            protocol=protocol,
            client_name=client_name,
            db=database,
        )
        handle = RedisDistributedLock(restricted, prefix=prefix).try_acquire(
            logical_name, _options()
        )
        assert handle is not None
        assert isinstance(handle.renew(), Renewed)
        handle.release()

        with pytest.raises(redis.exceptions.NoPermissionError):
            restricted.script_load("return 1")
        with pytest.raises(redis.exceptions.NoPermissionError):
            restricted.ping()
        with pytest.raises(redis.exceptions.NoPermissionError):
            restricted.get(b"outside-prefix")
    finally:
        try:
            try:
                if restricted is not None:
                    restricted.close()
            finally:
                cleanup = new_sync_client(
                    redis_endpoint,
                    username=admin_username,
                    password=admin_password,
                    protocol=2,
                    db=database,
                )
                try:
                    clean_sync_keys(cleanup, keys)
                finally:
                    cleanup.close()
        finally:
            try:
                if auth == "username-password":
                    admin.execute_command("ACL", "DELUSER", target_username)
                else:
                    admin.execute_command(
                        "ACL", "SETUSER", "default", "reset", "on", "nopass", "~*", "+@all"
                    )
            finally:
                try:
                    admin.execute_command("ACL", "DELUSER", admin_username)
                finally:
                    admin.close()


def test_borrowed_client_remains_usable_after_adapter_lifecycle(
    redis_endpoint: RedisEndpoint,
    clean_redis_database: None,
) -> None:
    del clean_redis_database
    with borrowed_sync_client(redis_endpoint) as client:
        logical_name = unique_logical_name("borrowed-client")
        handle = RedisDistributedLock(client).try_acquire(logical_name, _options())
        assert handle is not None
        handle.release()
        assert client.ping() is True
