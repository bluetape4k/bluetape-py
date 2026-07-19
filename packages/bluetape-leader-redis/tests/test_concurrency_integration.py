from __future__ import annotations

import asyncio
import multiprocessing
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import timedelta
from queue import Empty
from typing import Any, Literal

import pytest
from _support import (
    TESTCONTAINERS_MARK,
    RedisEndpoint,
    assert_task_baseline,
    borrowed_async_client,
    borrowed_sync_client,
    cancel_and_await_tasks,
    clean_redis_database,
    clean_sync_keys,
    leader_keys,
    new_async_client,
    new_sync_client,
    observed_timing,
    redis_endpoint,
    task_baseline,
    unique_logical_name,
)
from bluetape.leader import LeaderElectionOptions
from bluetape.leader.redis import AsyncRedisDistributedLock, RedisDistributedLock

__all__ = ["clean_redis_database", "redis_endpoint"]

pytestmark = [TESTCONTAINERS_MARK, pytest.mark.usefixtures("clean_redis_database")]

_CONTENDERS = 16
_GENERATIONS = 10
_SCHEDULING_MARGIN = 2.0
_ATOMIC_WRITE_SCRIPT = """
local stored = redis.call('HGET', KEYS[1], 'high_watermark')
local incoming = ARGV[1]
local counter = tonumber(redis.call('HGET', KEYS[1], 'counter') or '0')
local function is_canonical_positive_decimal(value)
  return string.match(value, '^[1-9][0-9]*$') ~= nil
end
local function is_strictly_greater(left, right)
  if right == false then
    return true
  end
  if string.len(left) ~= string.len(right) then
    return string.len(left) > string.len(right)
  end
  return left > right
end
if not is_canonical_positive_decimal(incoming) then
  return redis.error_reply('invalid fencing token')
end
if not is_strictly_greater(incoming, stored) then
  return {0, counter}
end
counter = redis.call('HINCRBY', KEYS[1], 'counter', 1)
redis.call('HSET', KEYS[1], 'high_watermark', ARGV[1], 'payload', ARGV[2])
return {1, counter}
"""


@dataclass(frozen=True, slots=True)
class ChildResult:
    scenario_id: Literal["sync-contention"]
    status: Literal["passed", "failed"]
    public_outcome: Literal["elected", "unexpected-public-outcome"]
    action_count: int
    fencing_relation: Literal["strictly-increasing", "not-applicable"]
    lease_cleanup: Literal["released", "not-applicable"]
    worker_delta: int
    task_delta: int
    borrowed_client_usable: bool
    failure_kind: Literal["none", "assertion", "unexpected-public-outcome"]


def _command_calls(commandstats: dict[str, Any], command: str) -> int:
    details = commandstats.get(f"cmdstat_{command}", {})
    return int(details.get("calls", 0))


def _assert_commandstats_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    expected_evalsha = _GENERATIONS * (_CONTENDERS + 2)
    expected_get = expected_evalsha + (_GENERATIONS - 1)
    assert _command_calls(after, "evalsha") - _command_calls(before, "evalsha") == expected_evalsha
    assert _command_calls(after, "eval") - _command_calls(before, "eval") == 0
    assert _command_calls(after, "get") - _command_calls(before, "get") == expected_get


def _assert_strict_generations(results: list[list[int]]) -> None:
    assert len(results) == _GENERATIONS
    assert all(len(generation) == 1 for generation in results)
    fences = [generation[0] for generation in results]
    assert fences == sorted(set(fences))


def _renew_worker_count() -> int:
    return sum(thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate())


def _assert_sync_auto_renew_worker_bound(endpoint: RedisEndpoint) -> None:
    baseline = _renew_worker_count()
    clients = [new_sync_client(endpoint) for _ in range(_CONTENDERS)]
    owned_keys: list[tuple[bytes, bytes]] = []
    maximum_seen = baseline
    try:
        timing = observed_timing(clients[0])
        renew_interval = timing.renew + 0.05
        options = LeaderElectionOptions(
            wait_time=timedelta(0),
            lease_time=timedelta(seconds=2),
            auto_renew=True,
            renew_interval=timedelta(seconds=renew_interval),
        )
        with ExitStack() as stack:
            for index, client in enumerate(clients):
                logical_name = unique_logical_name(f"sync-renew-workers-{index}")
                owned_keys.append(leader_keys(logical_name))
                handle = RedisDistributedLock(client).try_acquire(logical_name, options)
                assert handle is not None
                stack.enter_context(handle)

            deadline = time.monotonic() + timing.acquire + _SCHEDULING_MARGIN
            while True:
                current = _renew_worker_count()
                maximum_seen = max(maximum_seen, current)
                assert current <= baseline + _CONTENDERS
                if current == baseline + _CONTENDERS:
                    break
                if time.monotonic() >= deadline:
                    pytest.fail("sync renew worker startup deadline exceeded", pytrace=False)
                time.sleep(0.01)

        deadline = time.monotonic() + timing.release + _SCHEDULING_MARGIN
        while _renew_worker_count() != baseline:
            if time.monotonic() >= deadline:
                pytest.fail("sync renew worker cleanup deadline exceeded", pytrace=False)
            time.sleep(0.01)
        assert maximum_seen == baseline + _CONTENDERS
    finally:
        for client, keys in zip(clients, owned_keys, strict=False):
            clean_sync_keys(client, keys)
        for client in clients:
            client.close()


def _prepared_sync_locks(
    endpoint: RedisEndpoint,
) -> tuple[list[Any], list[RedisDistributedLock]]:
    clients = [new_sync_client(endpoint) for _ in range(_CONTENDERS)]
    try:
        locks = [RedisDistributedLock(client) for client in clients]
        for client in clients:
            assert client.ping() is True
    except BaseException:
        for client in clients:
            client.close()
        raise
    return clients, locks


async def _prepared_async_locks(
    endpoint: RedisEndpoint,
) -> tuple[list[Any], list[AsyncRedisDistributedLock]]:
    clients = [new_async_client(endpoint) for _ in range(_CONTENDERS)]
    try:
        locks = [AsyncRedisDistributedLock(client) for client in clients]
        for client in clients:
            assert await client.ping() is True
    except BaseException:
        for client in clients:
            await client.aclose()
        raise
    return clients, locks


def _sync_contention_child(endpoint: RedisEndpoint, result_queue: Any) -> None:
    try:
        result = _run_sync_contention(endpoint)
    except AssertionError:
        result_queue.put(
            ChildResult(
                scenario_id="sync-contention",
                status="failed",
                public_outcome="unexpected-public-outcome",
                action_count=0,
                fencing_relation="not-applicable",
                lease_cleanup="not-applicable",
                worker_delta=0,
                task_delta=0,
                borrowed_client_usable=False,
                failure_kind="assertion",
            )
        )
        result_queue.close()
        result_queue.join_thread()
        raise SystemExit(1) from None
    except BaseException:
        os._exit(2)
    result_queue.put(result)
    result_queue.close()
    result_queue.join_thread()


def _run_sync_contention(endpoint: RedisEndpoint) -> ChildResult:
    baseline_threads = frozenset(threading.enumerate())
    logical_name = unique_logical_name("sync-contention")
    prewarm_name = unique_logical_name("sync-contention-prewarm")
    lease_key, fence_key = leader_keys(logical_name)
    prewarm_keys = leader_keys(prewarm_name)
    options = LeaderElectionOptions(
        wait_time=timedelta(0),
        lease_time=timedelta(seconds=5),
    )
    generations: list[list[int]] = []
    total_actions = 0

    with borrowed_sync_client(endpoint) as prewarm_client:
        timing = observed_timing(prewarm_client)
        prewarm_handle = RedisDistributedLock(prewarm_client).try_acquire(prewarm_name, options)
        assert prewarm_handle is not None
        with prewarm_handle:
            pass
        clean_sync_keys(prewarm_client, prewarm_keys)

    generation_envelope = timing.acquire + timing.release + _SCHEDULING_MARGIN
    with borrowed_sync_client(endpoint) as stats_client:
        before = stats_client.info("commandstats")
        try:
            for _ in range(_GENERATIONS):
                barrier = threading.Barrier(_CONTENDERS)
                all_losers_returned = threading.Event()
                release_gate = threading.Event()
                counts_lock = threading.Lock()
                loser_count = 0
                action_count = 0
                clients, locks = _prepared_sync_locks(endpoint)

                def contend(
                    lock: RedisDistributedLock,
                    barrier: threading.Barrier = barrier,
                    counts_lock: threading.Lock = counts_lock,
                    all_losers_returned: threading.Event = all_losers_returned,
                    release_gate: threading.Event = release_gate,
                ) -> int | None:
                    nonlocal action_count, loser_count
                    barrier.wait(timeout=generation_envelope)
                    handle = lock.try_acquire(logical_name, options)
                    if handle is None:
                        with counts_lock:
                            loser_count += 1
                            if loser_count == _CONTENDERS - 1:
                                all_losers_returned.set()
                        return None
                    with handle as held:
                        with counts_lock:
                            action_count += 1
                        assert all_losers_returned.wait(timeout=generation_envelope)
                        assert release_gate.wait(timeout=generation_envelope)
                        return held.lease.fencing_token

                executor: ThreadPoolExecutor | None = None
                futures: list[Future[int | None]] = []
                try:
                    executor = ThreadPoolExecutor(max_workers=_CONTENDERS)
                    futures = [executor.submit(contend, lock) for lock in locks]
                    assert all_losers_returned.wait(timeout=generation_envelope)
                    release_gate.set()
                    deadline = time.monotonic() + generation_envelope
                    outcomes = [
                        future.result(timeout=max(0.0, deadline - time.monotonic()))
                        for future in futures
                    ]
                finally:
                    release_gate.set()
                    try:
                        barrier.abort()
                    except threading.BrokenBarrierError:
                        pass
                    for future in futures:
                        future.cancel()
                    if executor is not None:
                        executor.shutdown(wait=False, cancel_futures=True)
                        join_deadline = time.monotonic() + generation_envelope
                        for thread in tuple(executor._threads):
                            thread.join(max(0.0, join_deadline - time.monotonic()))
                        assert not any(thread.is_alive() for thread in executor._threads)
                    for client in clients:
                        client.close()

                winners = [outcome for outcome in outcomes if outcome is not None]
                assert len(outcomes) == _CONTENDERS
                assert loser_count == _CONTENDERS - 1
                assert action_count == 1
                assert stats_client.exists(lease_key) == 0
                assert frozenset(threading.enumerate()) == baseline_threads
                total_actions += action_count
                generations.append(winners)

            after = stats_client.info("commandstats")
            _assert_commandstats_delta(before, after)
            _assert_strict_generations(generations)
            assert total_actions == _GENERATIONS
            assert stats_client.ping() is True
            assert stats_client.exists(lease_key) == 0
            assert stats_client.exists(fence_key) == 1
        finally:
            clean_sync_keys(stats_client, (lease_key, fence_key))

    _assert_sync_auto_renew_worker_bound(endpoint)
    assert frozenset(threading.enumerate()) == baseline_threads
    return ChildResult(
        scenario_id="sync-contention",
        status="passed",
        public_outcome="elected",
        action_count=total_actions,
        fencing_relation="strictly-increasing",
        lease_cleanup="released",
        worker_delta=0,
        task_delta=0,
        borrowed_client_usable=True,
        failure_kind="none",
    )


def test_sync_contention_is_bounded_by_a_spawned_child_process(
    request: pytest.FixtureRequest,
) -> None:
    redis_endpoint: RedisEndpoint = request.getfixturevalue("redis_endpoint")
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_sync_contention_child,
        args=(redis_endpoint, result_queue),
    )
    process.start()
    with borrowed_sync_client(redis_endpoint) as timing_client:
        timing = observed_timing(timing_client)
    parent_deadline = _GENERATIONS * (timing.acquire + timing.release + _SCHEDULING_MARGIN) + 5.0
    process.join(parent_deadline)
    if process.is_alive():
        process.terminate()
        process.join(2.0)
        if process.is_alive():
            process.kill()
            process.join(2.0)
        result_queue.close()
        result_queue.join_thread()
        pytest.fail("sync contention child deadline exceeded", pytrace=False)
    if process.exitcode != 0:
        result_queue.close()
        result_queue.join_thread()
        pytest.fail("sync contention child failed", pytrace=False)
    try:
        result = result_queue.get(timeout=1.0)
    except Empty:
        pytest.fail("sync contention child returned no terminal record", pytrace=False)
    try:
        result_queue.get_nowait()
    except Empty:
        pass
    else:
        pytest.fail("sync contention child returned duplicate terminal records", pytrace=False)
    finally:
        result_queue.close()
        result_queue.join_thread()

    assert isinstance(result, ChildResult)
    assert result == ChildResult(
        scenario_id="sync-contention",
        status="passed",
        public_outcome="elected",
        action_count=_GENERATIONS,
        fencing_relation="strictly-increasing",
        lease_cleanup="released",
        worker_delta=0,
        task_delta=0,
        borrowed_client_usable=True,
        failure_kind="none",
    )


@pytest.mark.asyncio
async def test_async_contention_has_one_winner_per_generation_and_no_task_leaks(
    request: pytest.FixtureRequest,
) -> None:
    redis_endpoint: RedisEndpoint = request.getfixturevalue("redis_endpoint")
    logical_name = unique_logical_name("async-contention")
    prewarm_name = unique_logical_name("async-contention-prewarm")
    lease_key, fence_key = leader_keys(logical_name)
    prewarm_keys = leader_keys(prewarm_name)
    options = LeaderElectionOptions(
        wait_time=timedelta(0),
        lease_time=timedelta(seconds=5),
    )
    generations: list[list[int]] = []
    total_actions = 0

    async with borrowed_async_client(redis_endpoint) as prewarm_client:
        timing = observed_timing(prewarm_client)
        prewarm_handle = await AsyncRedisDistributedLock(prewarm_client).try_acquire(
            prewarm_name, options
        )
        assert prewarm_handle is not None
        async with prewarm_handle:
            pass
        await prewarm_client.delete(*prewarm_keys)

    generation_envelope = timing.acquire + timing.release + _SCHEDULING_MARGIN
    async with borrowed_async_client(redis_endpoint) as stats_client:
        before = await stats_client.info("commandstats")
        try:
            for _ in range(_GENERATIONS):
                baseline = task_baseline()
                start = asyncio.Event()
                all_losers_returned = asyncio.Event()
                release_gate = asyncio.Event()
                loser_count = 0
                action_count = 0
                clients, locks = await _prepared_async_locks(redis_endpoint)

                async def contend(
                    lock: AsyncRedisDistributedLock,
                    start: asyncio.Event = start,
                    all_losers_returned: asyncio.Event = all_losers_returned,
                    release_gate: asyncio.Event = release_gate,
                ) -> int | None:
                    nonlocal action_count, loser_count
                    await start.wait()
                    handle = await lock.try_acquire(logical_name, options)
                    if handle is None:
                        loser_count += 1
                        if loser_count == _CONTENDERS - 1:
                            all_losers_returned.set()
                        return None
                    async with handle as held:
                        action_count += 1
                        await all_losers_returned.wait()
                        await release_gate.wait()
                        return held.lease.fencing_token

                tasks: list[asyncio.Task[int | None]] = []
                try:
                    for lock in locks:
                        coroutine = contend(lock)
                        try:
                            task = asyncio.create_task(coroutine)
                        except BaseException:
                            coroutine.close()
                            raise
                        tasks.append(task)
                    async with asyncio.timeout(generation_envelope):
                        start.set()
                        await all_losers_returned.wait()
                        release_gate.set()
                        outcomes = await asyncio.gather(*tasks)
                finally:
                    start.set()
                    release_gate.set()
                    await cancel_and_await_tasks(tasks)
                    for client in clients:
                        await client.aclose()

                winners = [outcome for outcome in outcomes if outcome is not None]
                assert len(outcomes) == _CONTENDERS
                assert loser_count == _CONTENDERS - 1
                assert action_count == 1
                assert await stats_client.exists(lease_key) == 0
                assert_task_baseline(baseline)
                total_actions += action_count
                generations.append(winners)

            after = await stats_client.info("commandstats")
            _assert_commandstats_delta(before, after)
            _assert_strict_generations(generations)
            assert total_actions == _GENERATIONS
            assert await stats_client.ping() is True
            assert await stats_client.exists(lease_key) == 0
            assert await stats_client.exists(fence_key) == 1
        finally:
            await stats_client.delete(lease_key, fence_key)


def _acquire_and_release_token(
    lock: RedisDistributedLock,
    logical_name: str,
    options: LeaderElectionOptions,
) -> int:
    handle = lock.try_acquire(logical_name, options)
    assert handle is not None
    with handle as held:
        return held.lease.fencing_token


def _atomic_write(client: Any, resource_key: bytes, token: int, payload: bytes) -> list[int]:
    result = client.eval(_ATOMIC_WRITE_SCRIPT, 1, resource_key, token, payload)
    return [int(value) for value in result]


def test_atomic_downstream_fence_rejects_replay_stale_and_rolled_back_tokens(
    request: pytest.FixtureRequest,
) -> None:
    redis_endpoint: RedisEndpoint = request.getfixturevalue("redis_endpoint")
    logical_name = unique_logical_name("atomic-fence")
    lease_key, fence_key = leader_keys(logical_name)
    resource_key = f"{logical_name}-resource".encode()
    options = LeaderElectionOptions(
        wait_time=timedelta(0),
        lease_time=timedelta(seconds=2),
    )

    with borrowed_sync_client(redis_endpoint) as client:
        try:
            lock = RedisDistributedLock(client)
            stale_token = _acquire_and_release_token(lock, logical_name, options)
            high_token = _acquire_and_release_token(lock, logical_name, options)
            assert stale_token < high_token

            assert _atomic_write(client, resource_key, high_token, b"accepted") == [1, 1]
            accepted_state = client.hmget(resource_key, b"high_watermark", b"counter", b"payload")
            assert _atomic_write(client, resource_key, high_token, b"replay") == [0, 1]
            assert _atomic_write(client, resource_key, stale_token, b"stale") == [0, 1]
            assert (
                client.hmget(resource_key, b"high_watermark", b"counter", b"payload")
                == accepted_state
            )

            client.delete(fence_key)
            rolled_back_token = _acquire_and_release_token(lock, logical_name, options)
            assert rolled_back_token < high_token
            assert _atomic_write(client, resource_key, rolled_back_token, b"rollback") == [0, 1]
            assert (
                client.hmget(resource_key, b"high_watermark", b"counter", b"payload")
                == accepted_state
            )

            client.hset(
                resource_key,
                mapping={
                    b"high_watermark": b"9007199254740993",
                    b"counter": b"1",
                    b"payload": b"large-accepted",
                },
            )
            assert _atomic_write(client, resource_key, 9_007_199_254_740_992, b"rounded") == [
                0,
                1,
            ]
            assert _atomic_write(client, resource_key, 9_007_199_254_740_994, b"larger") == [
                1,
                2,
            ]
        finally:
            clean_sync_keys(client, (lease_key, fence_key, resource_key))


def test_non_atomic_check_then_write_is_deliberately_unsupported_evidence(
    request: pytest.FixtureRequest,
) -> None:
    redis_endpoint: RedisEndpoint = request.getfixturevalue("redis_endpoint")
    logical_name = unique_logical_name("non-atomic-fence")
    lease_key, fence_key = leader_keys(logical_name)
    resource_key = f"{logical_name}-resource".encode()
    options = LeaderElectionOptions(
        wait_time=timedelta(0),
        lease_time=timedelta(seconds=2),
    )

    with borrowed_sync_client(redis_endpoint) as client:
        try:
            lock = RedisDistributedLock(client)
            stale_token = _acquire_and_release_token(lock, logical_name, options)
            fresh_token = _acquire_and_release_token(lock, logical_name, options)
            observed_by_stale = int(client.hget(resource_key, b"high_watermark") or -1)
            observed_by_fresh = int(client.hget(resource_key, b"high_watermark") or -1)
            assert stale_token > observed_by_stale
            assert fresh_token > observed_by_fresh

            client.hset(
                resource_key,
                mapping={b"high_watermark": fresh_token, b"payload": b"fresh"},
            )
            client.hincrby(resource_key, b"counter", 1)
            client.hset(
                resource_key,
                mapping={b"high_watermark": stale_token, b"payload": b"stale"},
            )
            client.hincrby(resource_key, b"counter", 1)

            assert client.hmget(resource_key, b"high_watermark", b"counter", b"payload") == [
                str(stale_token).encode(),
                b"2",
                b"stale",
            ]
        finally:
            clean_sync_keys(client, (lease_key, fence_key, resource_key))
