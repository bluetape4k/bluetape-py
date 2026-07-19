from __future__ import annotations

import asyncio
import os
from datetime import timedelta

import pytest
import redis
from _support import (
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

__all__ = ["clean_redis_database", "redis_endpoint"]

pytestmark = [TESTCONTAINERS_MARK, pytest.mark.usefixtures("clean_redis_database")]

_SHORT_LEASE = 0.20
_POLL_INTERVAL = 0.01
_ACL_SHAPES = [
    (protocol, client_name, database)
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


@pytest.mark.asyncio
async def test_real_async_lifecycle_reacquires_with_increasing_fence(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with asyncio.timeout(3.0), borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-lifecycle")
        lock = AsyncRedisDistributedLock(client)
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
    async with asyncio.timeout(3.0), borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-stale-owner")
        lease_key, _ = leader_keys(logical_name)
        lock = AsyncRedisDistributedLock(client)
        old = await lock.try_acquire(logical_name, _options(lease=_SHORT_LEASE))
        assert old is not None
        await _wait_until_absent(client, lease_key)

        successor = await lock.try_acquire(logical_name, _options())
        assert successor is not None
        record_before = await client.get(lease_key)
        ttl_before = await client.pttl(lease_key)
        assert record_before is not None and ttl_before > 0
        assert isinstance(await old.renew(), NotHeld)
        with pytest.raises(LeaderReleaseError):
            await old.release()
        record_after = await client.get(lease_key)
        ttl_after = await client.pttl(lease_key)

        assert record_after == record_before
        assert 0 < ttl_after <= ttl_before
        await successor.release()


@pytest.mark.asyncio
async def test_async_minimum_lease_delays_successor_then_expires(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with asyncio.timeout(3.0), borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-minimum")
        lease_key, _ = leader_keys(logical_name)
        lock = AsyncRedisDistributedLock(client)
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
    async with borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-long-action")
        lease_key, _ = leader_keys(logical_name)
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


@pytest.mark.asyncio
async def test_async_action_failure_is_reported_after_release(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with asyncio.timeout(3.0), borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-action-failure")
        lease_key, _ = leader_keys(logical_name)
        failure = ValueError("caller failure")

        async def action(_lease: object) -> None:
            raise failure

        result = await AsyncRedisLeaderElector(client).run_if_leader_result(
            logical_name, action, _options()
        )
        assert isinstance(result, ActionFailed)
        assert result.cause is failure
        assert await client.exists(lease_key) == 0


@pytest.mark.asyncio
async def test_async_cancellation_releases_and_restores_task_baseline(
    redis_endpoint: RedisEndpoint,
) -> None:
    baseline = task_baseline()
    task: asyncio.Task[None] | None = None
    async with borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-cancellation")
        lease_key, _ = leader_keys(logical_name)
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
            async with asyncio.timeout(3.0):
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
    async with asyncio.timeout(3.0), borrowed_async_client(redis_endpoint) as client:
        logical_name = unique_logical_name("async-delayed-entry")
        lease_key, _ = leader_keys(logical_name)
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
        asyncio.timeout(3.0),
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        logical_name = unique_logical_name(f"async-corrupt-{state}")
        lease_key, _ = leader_keys(logical_name)
        if state == "malformed":
            await admin.set(lease_key, b"not-a-lease", px=1000)
        elif state == "no-ttl":
            await admin.set(lease_key, b"v1:" + b"A" * 32 + b":1")
        else:
            await admin.rpush(lease_key, b"not-a-string")

        with pytest.raises(LeaderBackendError):
            await AsyncRedisDistributedLock(client).try_acquire(logical_name, _options())


@pytest.mark.asyncio
async def test_async_noscript_and_numeric_boundaries_fail_closed(
    redis_endpoint: RedisEndpoint,
) -> None:
    async with (
        asyncio.timeout(4.0),
        borrowed_async_client(redis_endpoint) as admin,
        borrowed_async_client(redis_endpoint) as client,
    ):
        lock = AsyncRedisDistributedLock(client)
        noscript_name = unique_logical_name("async-noscript")
        await admin.script_flush()
        handle = await lock.try_acquire(noscript_name, _options())
        assert handle is not None
        assert isinstance(await handle.renew(), Renewed)
        await handle.release()

        exact_name = unique_logical_name("async-large-counter")
        _, exact_fence = leader_keys(exact_name)
        await admin.set(exact_fence, b"9007199254740992")
        exact = await lock.try_acquire(exact_name, _options())
        assert exact is not None
        assert exact.lease.fencing_token == 9_007_199_254_740_993
        await exact.release()

        overflow_name = unique_logical_name("async-overflow")
        _, overflow_fence = leader_keys(overflow_name)
        await admin.set(overflow_fence, b"9223372036854775807")
        with pytest.raises(LeaderBackendError):
            await lock.try_acquire(overflow_name, _options())
        assert await admin.get(overflow_fence) == b"9223372036854775807"
        assert await client.ping() is True


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol,client_name,database", _ACL_SHAPES)
async def test_async_acl_matrix_grants_only_shape_specific_adapter_commands(
    redis_endpoint: RedisEndpoint,
    protocol: int,
    client_name: str | None,
    database: int,
) -> None:
    username = f"async-acl-{os.getpid()}-{protocol}-{int(client_name is not None)}-{database}"
    password = "async-acl-fixed-password"
    prefix = "async-leader-acl"
    conditional_permissions = []
    if protocol == 3:
        conditional_permissions.append("+hello")
    if client_name is not None:
        conditional_permissions.append("+client|setname")
    if database != 0:
        conditional_permissions.append("+select")

    async with borrowed_async_client(redis_endpoint) as admin:
        await admin.execute_command(
            "ACL",
            "SETUSER",
            username,
            "reset",
            "on",
            f">{password}",
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
            "+client|setinfo",
            *conditional_permissions,
        )
        restricted = new_async_client(
            redis_endpoint,
            username=username,
            password=password,
            protocol=protocol,
            client_name=client_name,
            db=database,
        )
        logical_name = unique_logical_name("async-acl-default")
        keys = leader_keys(logical_name, prefix)
        try:
            async with asyncio.timeout(3.0):
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
                await restricted.delete(*keys)
        finally:
            await restricted.aclose()
            await admin.execute_command("ACL", "DELUSER", username)
