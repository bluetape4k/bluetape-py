from __future__ import annotations

import asyncio
import os
from datetime import timedelta

import pytest
import redis
import redis.asyncio as async_redis
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
from bluetape.leader.redis import AsyncRedisDistributedLock, AsyncRedisLeaderElector
from leader_redis_test_support import (
    TESTCONTAINERS_MARK,
    RedisEndpoint,
    assert_task_baseline,
    borrowed_async_client,
    clean_redis_database,
    leader_keys,
    new_async_client,
    observed_timing,
    redis_endpoint,
    task_baseline,
    unique_logical_name,
)

__all__ = ["clean_redis_database", "redis_endpoint"]

pytestmark = [TESTCONTAINERS_MARK, pytest.mark.usefixtures("clean_redis_database")]

_SHORT_LEASE = 0.20
_POLL_INTERVAL = 0.01
_ACL_SHAPES = [
    (auth, protocol, client_name, database)
    for auth in ("none", "password", "username-password")
    for protocol in (2, 3)
    for client_name in (None, "leader-test")
    for database in (0, 1)
]


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


async def _wait_until_absent(client: object, key: bytes, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while await client.exists(key):  # type: ignore[attr-defined]
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail("Redis expiry deadline exceeded", pytrace=False)
        await asyncio.sleep(_POLL_INTERVAL)


def _command_calls(commandstats: dict[str, object], command: str) -> int:
    details = commandstats.get(f"cmdstat_{command}", {})
    assert isinstance(details, dict)
    return int(details.get("calls", 0))


@pytest.mark.asyncio
async def test_real_async_lifecycle_reacquires_with_increasing_fence(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with borrowed_async_client(redis_endpoint) as client:
        timing = observed_timing(client)
        logical_name = unique_logical_name("async-lifecycle")
        lock = AsyncRedisDistributedLock(client)
        async with asyncio.timeout(3 * timing.acquire + timing.renew + 2 * timing.release + 1.0):
            first = await lock.try_acquire(logical_name, _options())
            assert first is not None
            assert isinstance(await first.renew(), Renewed)
            assert await lock.try_acquire(logical_name, _options()) is None
            first_token = first.lease.fencing_token
            await first.release()

            successor = await lock.try_acquire(logical_name, _options())
            assert successor is not None
            assert successor.lease.fencing_token > first_token
            await successor.release()
        assert await client.ping() is True


@pytest.mark.asyncio
async def test_expired_async_owner_cannot_change_successor_record_or_ttl(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with borrowed_async_client(redis_endpoint) as client:
        timing = observed_timing(client)
        logical_name = unique_logical_name("async-stale-owner")
        lease_key, _, _ = leader_keys(logical_name)
        lock = AsyncRedisDistributedLock(client)
        async with asyncio.timeout(2 * timing.acquire + timing.renew + 2 * timing.release + 2.0):
            old = await lock.try_acquire(logical_name, _options(lease=_SHORT_LEASE))
            assert old is not None
            await _wait_until_absent(client, lease_key)

            successor = await lock.try_acquire(logical_name, _options())
            assert successor is not None
            record_before = await client.get(lease_key)
            ttl_before = await client.pttl(lease_key)
            assert record_before is not None and ttl_before > 0
            commands_before = await client.info("commandstats")
            assert isinstance(await old.renew(), NotHeld)
            with pytest.raises(LeaderReleaseError):
                await old.release()
            commands_after = await client.info("commandstats")
            record_after = await client.get(lease_key)
            ttl_after = await client.pttl(lease_key)

            assert record_after == record_before
            assert 0 < ttl_after <= ttl_before
            assert _command_calls(commands_after, "pexpire") == _command_calls(
                commands_before, "pexpire"
            )
            assert _command_calls(commands_after, "del") == _command_calls(commands_before, "del")
            await successor.release()


@pytest.mark.asyncio
async def test_async_minimum_lease_delays_successor_then_expires(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with borrowed_async_client(redis_endpoint) as client:
        timing = observed_timing(client)
        logical_name = unique_logical_name("async-minimum")
        lease_key, _, _ = leader_keys(logical_name)
        lock = AsyncRedisDistributedLock(client)
        async with asyncio.timeout(3 * timing.acquire + 2 * timing.release + 2.0):
            handle = await lock.try_acquire(logical_name, _options(minimum=0.30))
            assert handle is not None
            await handle.release()
            assert 0 < await client.pttl(lease_key) <= 300
            assert await lock.try_acquire(logical_name, _options()) is None
            await _wait_until_absent(client, lease_key)
            successor = await lock.try_acquire(logical_name, _options())
            assert successor is not None
            await successor.release()


@pytest.mark.asyncio
async def test_async_long_action_crosses_three_ttls_and_releases(
    redis_endpoint: RedisEndpoint,
) -> None:
    baseline = task_baseline()
    async with borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-long-action")
        lease_key, _, _ = leader_keys(logical_name)
        timing = observed_timing(client)
        renew_interval = timing.renew + 0.05
        assert timing.renew + renew_interval < 2.0
        action_count = 0

        async def action(_lease: object) -> str:
            nonlocal action_count
            action_count += 1
            await asyncio.sleep(6.1)
            return "completed"

        async with asyncio.timeout(8.0):
            result = await AsyncRedisLeaderElector(client).run_if_leader_result(
                logical_name,
                action,
                _options(lease=2.0, auto_renew=True, renew_interval=renew_interval),
            )
        assert isinstance(result, Elected)
        assert result.value == "completed"
        assert action_count == 1
        assert await client.exists(lease_key) == 0
    assert_task_baseline(baseline)


@pytest.mark.asyncio
async def test_async_action_failure_is_reported_after_release(
    redis_endpoint: RedisEndpoint,
) -> None:
    baseline = task_baseline()
    async with borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-action-failure")
        lease_key, _, _ = leader_keys(logical_name)
        failure = ValueError("caller failure")
        timing = observed_timing(client)
        renew_interval = timing.renew + 0.05

        async def action(_lease: object) -> None:
            raise failure

        async with asyncio.timeout(timing.acquire + timing.release + 1.0):
            result = await AsyncRedisLeaderElector(client).run_if_leader_result(
                logical_name,
                action,
                _options(lease=2.0, auto_renew=True, renew_interval=renew_interval),
            )
        assert isinstance(result, ActionFailed)
        assert result.cause is failure
        assert await client.exists(lease_key) == 0
    assert_task_baseline(baseline)


@pytest.mark.asyncio
async def test_real_async_renewal_loss_prevents_successful_scoped_completion(
    redis_endpoint: RedisEndpoint,
) -> None:
    baseline = task_baseline()
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name("async-renewal-loss")
        lease_key, _, _ = leader_keys(logical_name)
        timing = observed_timing(client)
        renew_interval = timing.renew + 0.05

        async def invalidate(_lease: object) -> str:
            await admin.delete(lease_key)
            await asyncio.sleep(renew_interval + 0.20)
            return "must-not-complete"

        with pytest.raises(LeaderLeaseLostError):
            async with asyncio.timeout(timing.acquire + timing.renew + timing.release + 2.0):
                await AsyncRedisLeaderElector(client).run_if_leader_result(
                    logical_name,
                    invalidate,
                    _options(lease=2.0, auto_renew=True, renew_interval=renew_interval),
                )
        assert await client.exists(lease_key) == 0
    assert_task_baseline(baseline)


@pytest.mark.asyncio
async def test_async_cancellation_releases_and_restores_task_baseline(
    redis_endpoint: RedisEndpoint,
) -> None:
    baseline = task_baseline()
    task: asyncio.Task[None] | None = None
    async with borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-cancellation")
        lease_key, _, _ = leader_keys(logical_name)
        timing = observed_timing(client)
        renew_interval = timing.renew + 0.05
        entered = asyncio.Event()

        async def hold() -> None:
            handle = await AsyncRedisDistributedLock(client).try_acquire(
                logical_name,
                _options(lease=2.0, auto_renew=True, renew_interval=renew_interval),
            )
            assert handle is not None
            async with handle:
                entered.set()
                await asyncio.Event().wait()

        try:
            task = asyncio.create_task(hold())
            async with asyncio.timeout(timing.acquire + timing.release + 1.0):
                await entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            assert await client.exists(lease_key) == 0
            assert await client.ping() is True
        finally:
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert_task_baseline(baseline)


@pytest.mark.asyncio
async def test_delayed_async_entry_fails_before_running_body(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with borrowed_async_client(redis_endpoint) as client:
        timing = observed_timing(client)
        logical_name = unique_logical_name("async-delayed-entry")
        lease_key, _, _ = leader_keys(logical_name)
        async with asyncio.timeout(timing.acquire + timing.probe + timing.release + 2.0):
            handle = await AsyncRedisDistributedLock(client).try_acquire(
                logical_name, _options(lease=_SHORT_LEASE)
            )
            assert handle is not None
            await _wait_until_absent(client, lease_key)
            body_started = False

            with pytest.raises(LeaderLeaseLostError):
                async with handle:
                    body_started = True
            assert body_started is False


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["malformed", "no-ttl", "wrong-type"])
async def test_async_corrupt_lease_states_fail_closed(
    redis_endpoint: RedisEndpoint,
    state: str,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        timing = observed_timing(client)
        logical_name = unique_logical_name(f"async-corrupt-{state}")
        lease_key, _, _ = leader_keys(logical_name)
        if state == "malformed":
            await admin.set(lease_key, b"not-a-lease", px=1000)
        elif state == "no-ttl":
            await admin.set(lease_key, b"v1:" + b"A" * 32 + b":1")
        else:
            await admin.rpush(lease_key, b"not-a-string")

        async with asyncio.timeout(timing.acquire + 1.0):
            with pytest.raises(LeaderBackendError):
                await AsyncRedisDistributedLock(client).try_acquire(logical_name, _options())


@pytest.mark.asyncio
async def test_async_noscript_and_numeric_boundaries_fail_closed(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        timing = observed_timing(client)
        lock = AsyncRedisDistributedLock(client)
        async with asyncio.timeout(3 * timing.acquire + timing.renew + 2 * timing.release + 1.0):
            noscript_name = unique_logical_name("async-noscript")
            await admin.script_flush()
            handle = await lock.try_acquire(noscript_name, _options())
            assert handle is not None
            assert isinstance(await handle.renew(), Renewed)
            await handle.release()

            exact_name = unique_logical_name("async-large-counter")
            _, exact_fence, exact_history = leader_keys(exact_name)
            await admin.set(exact_history, b"v1")
            await admin.set(exact_fence, b"9007199254740992")
            exact = await lock.try_acquire(exact_name, _options())
            assert exact is not None
            assert exact.lease.fencing_token == 9_007_199_254_740_993
            await exact.release()

            overflow_name = unique_logical_name("async-overflow")
            _, overflow_fence, overflow_history = leader_keys(overflow_name)
            await admin.set(overflow_history, b"v1")
            await admin.set(overflow_fence, b"9223372036854775806")
            maximum = await lock.try_acquire(overflow_name, _options())
            assert maximum is not None
            assert maximum.lease.fencing_token == 9_223_372_036_854_775_807
            assert await lock.try_acquire(overflow_name, _options()) is None
            await maximum.release()
            with pytest.raises(LeaderBackendError):
                await lock.try_acquire(overflow_name, _options())
            assert await admin.get(overflow_fence) == b"9223372036854775807"
            assert await client.ping() is True


@pytest.mark.asyncio
async def test_async_expiring_fence_counter_fails_closed_without_issuing_a_lease(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name("async-expiring-counter")
        lease_key, fence_key, history_key = leader_keys(logical_name)
        lock = AsyncRedisDistributedLock(client)
        first = await lock.try_acquire(logical_name, _options())
        assert first is not None
        await first.release()
        assert await admin.get(history_key) == b"v1"
        assert await admin.pttl(history_key) == -1
        assert await admin.pexpire(fence_key, 50) is True

        with pytest.raises(LeaderBackendError):
            await lock.try_acquire(logical_name, _options())

        assert await admin.pttl(fence_key) > 0
        await _wait_until_absent(admin, fence_key)
        with pytest.raises(LeaderBackendError):
            await lock.try_acquire(logical_name, _options())

        assert await admin.get(fence_key) is None
        assert await admin.get(history_key) == b"v1"
        assert await admin.pttl(history_key) == -1
        assert await admin.get(lease_key) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["missing", "wrong-type", "wrong-value", "ttl"])
async def test_async_corrupt_fence_history_states_fail_closed_without_mutation(
    redis_endpoint: RedisEndpoint,
    state: str,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name(f"async-corrupt-history-{state}")
        lease_key, fence_key, history_key = leader_keys(logical_name)
        await admin.set(fence_key, b"9")
        if state == "wrong-type":
            await admin.rpush(history_key, b"v1")
        elif state == "wrong-value":
            await admin.set(history_key, b"v2")
        elif state == "ttl":
            await admin.set(history_key, b"v1", px=5_000)

        before_dump = await admin.dump(history_key)
        before_ttl = await admin.pttl(history_key)
        before_fence = await admin.get(fence_key)
        with pytest.raises(LeaderBackendError):
            await AsyncRedisDistributedLock(client).try_acquire(logical_name, _options())

        after_ttl = await admin.pttl(history_key)
        assert await admin.dump(history_key) == before_dump
        assert await admin.get(fence_key) == before_fence
        if state == "ttl":
            assert 0 < after_ttl <= before_ttl
        else:
            assert after_ttl == before_ttl
        assert await admin.get(lease_key) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["wrong-type", "malformed"])
async def test_async_corrupt_fence_counter_states_fail_closed_without_mutation(
    redis_endpoint: RedisEndpoint,
    state: str,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name(f"async-corrupt-counter-{state}")
        lease_key, fence_key, history_key = leader_keys(logical_name)
        await admin.set(history_key, b"v1")
        if state == "wrong-type":
            await admin.rpush(fence_key, b"9")
        else:
            await admin.set(fence_key, b"09")

        before_fence = await admin.dump(fence_key)
        with pytest.raises(LeaderBackendError):
            await AsyncRedisDistributedLock(client).try_acquire(logical_name, _options())

        assert await admin.dump(fence_key) == before_fence
        assert await admin.get(history_key) == b"v1"
        assert await admin.pttl(history_key) == -1
        assert await admin.get(lease_key) is None


@pytest.mark.asyncio
async def test_async_active_lease_with_missing_fence_history_fails_closed(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name("async-active-missing-fence-history")
        lease_key, fence_key, history_key = leader_keys(logical_name)
        lock = AsyncRedisDistributedLock(client)
        held = await lock.try_acquire(logical_name, _options())
        assert held is not None
        lease_record = await admin.get(lease_key)
        await admin.delete(fence_key, history_key)

        with pytest.raises(LeaderBackendError):
            await lock.try_acquire(logical_name, _options())

        assert await admin.get(lease_key) == lease_record
        assert await admin.get(fence_key) is None
        assert await admin.get(history_key) is None
        await held.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", [b"9", b"11"])
async def test_async_active_lease_with_mismatched_fence_counter_fails_closed(
    redis_endpoint: RedisEndpoint,
    replacement: bytes,
) -> None:
    async with (
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name(f"async-active-mismatched-fence-{replacement.decode()}")
        lease_key, fence_key, history_key = leader_keys(logical_name)
        await admin.set(history_key, b"v1")
        await admin.set(fence_key, b"9")
        lock = AsyncRedisDistributedLock(client)
        held = await lock.try_acquire(logical_name, _options())
        assert held is not None
        assert held.lease.fencing_token == 10
        lease_record = await admin.get(lease_key)
        await admin.set(fence_key, replacement)

        with pytest.raises(LeaderBackendError):
            await lock.try_acquire(logical_name, _options())

        assert await admin.get(lease_key) == lease_record
        assert await admin.get(fence_key) == replacement
        assert await admin.get(history_key) == b"v1"
        await held.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("auth,protocol,client_name,database", _ACL_SHAPES)
async def test_async_acl_matrix_grants_only_shape_specific_adapter_commands(
    redis_endpoint: RedisEndpoint,
    auth: str,
    protocol: int,
    client_name: str | None,
    database: int,
) -> None:
    shape_id = f"{os.getpid()}-{auth}-{protocol}-{int(client_name is not None)}-{database}"
    admin_username = f"async-admin-{shape_id}"
    admin_password = "async-admin-fixed-password"
    target_username = "default" if auth != "username-password" else f"async-acl-{shape_id}"
    password = "async-acl-fixed-password"
    prefix = "async-leader-acl"
    conditional_permissions = []
    if protocol == 3:
        conditional_permissions.append("+hello")
    if client_name is not None:
        conditional_permissions.append("+client|setname")
    if database != 0:
        conditional_permissions.append("+select")

    async with borrowed_async_client(redis_endpoint) as bootstrap:
        await bootstrap.execute_command(
            "ACL",
            "SETUSER",
            admin_username,
            "reset",
            "on",
            f">{admin_password}",
            "~*",
            "+@all",
        )
    admin = new_async_client(
        redis_endpoint,
        username=admin_username,
        password=admin_password,
        protocol=2,
    )
    restricted: async_redis.Redis | None = None
    logical_name = unique_logical_name("async-acl-default")
    keys = leader_keys(logical_name, prefix)
    try:
        credential_rule = "nopass" if auth == "none" else f">{password}"
        await admin.execute_command(
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
        restricted = new_async_client(
            redis_endpoint,
            **authentication,
            protocol=protocol,
            client_name=client_name,
            db=database,
        )
        timing = observed_timing(restricted)
        async with asyncio.timeout(timing.acquire + timing.renew + timing.release + 1.0):
            handle = await AsyncRedisDistributedLock(restricted, prefix=prefix).try_acquire(
                logical_name, _options()
            )
            assert handle is not None
            assert isinstance(await handle.renew(), Renewed)
            await handle.release()

            with pytest.raises(redis.exceptions.NoPermissionError):
                await restricted.script_load("return 1")
            with pytest.raises(redis.exceptions.NoPermissionError):
                await restricted.ping()
            with pytest.raises(redis.exceptions.NoPermissionError):
                await restricted.get(b"outside-prefix")
    finally:
        try:
            try:
                if restricted is not None:
                    await restricted.aclose()
            finally:
                cleanup = new_async_client(
                    redis_endpoint,
                    username=admin_username,
                    password=admin_password,
                    protocol=2,
                    db=database,
                )
                try:
                    await cleanup.delete(*keys)
                finally:
                    await cleanup.aclose()
        finally:
            try:
                if auth == "username-password":
                    await admin.execute_command("ACL", "DELUSER", target_username)
                else:
                    await admin.execute_command(
                        "ACL", "SETUSER", "default", "reset", "on", "nopass", "~*", "+@all"
                    )
            finally:
                try:
                    await admin.execute_command("ACL", "DELUSER", admin_username)
                finally:
                    await admin.aclose()
