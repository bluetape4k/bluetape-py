"""Scenario measurement primitives and correctness contracts."""

import asyncio
import resource
import sys
import threading
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter_ns, sleep

from _coordination_matrix import BenchmarkProfile, ScenarioCase
from _coordination_security import (
    build_envelope_codec,
    load_options,
    make_async_client,
    make_sync_client,
)
from bluetape.benchmark import BenchmarkScenarioResult, summarize_timings
from bluetape.cache import AsyncTTLCache, TTLCache
from bluetape.cache.redis import (
    AsyncRedisLoadCoordinator,
    AsyncRedisProvider,
    RedisCoordinationSnapshot,
    SyncRedisLoadCoordinator,
    SyncRedisProvider,
)
from bluetape.cache.redis._coordination import _coordination_keys

_ACTIVE_MARKER_PREFIX = b"active:"
_COMPLETED_MARKER_PREFIX = b"completed:"
_ACTIVE_SNAPSHOT_GATE_TIMEOUT = 5.0
_LOADER_OVERLAP_GATE_TIMEOUT = 5.0


class BenchmarkScenarioError(RuntimeError):
    """Low-cardinality benchmark scenario failure."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CorrectnessMetrics:
    loader_count: int
    redis_commands: int
    active_snapshot_count: int
    active_result_bytes: int
    completed_result_bytes: int
    overlap_observed: bool


def sync_measure_calls[T](
    calls: Sequence[Callable[[], T]],
    *,
    timeout: float,
    verify: Callable[[tuple[T, ...]], None],
) -> int:
    """Start ready workers together, stop after joins, then verify results."""
    if not calls:
        raise ValueError("calls must not be empty")
    barrier = threading.Barrier(len(calls) + 1, timeout=timeout)
    values: list[T | None] = [None] * len(calls)
    failures: list[BaseException | None] = [None] * len(calls)

    def worker(index: int, call: Callable[[], T]) -> None:
        try:
            barrier.wait()
            values[index] = call()
        except BaseException as error:
            failures[index] = error

    threads = [
        threading.Thread(target=worker, args=(index, call), daemon=True)
        for index, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    started = perf_counter_ns()
    try:
        barrier.wait()
    except threading.BrokenBarrierError:
        barrier.abort()
        raise BenchmarkScenarioError("ready-barrier") from None
    for thread in threads:
        thread.join(timeout)
    stopped = perf_counter_ns()
    if any(thread.is_alive() for thread in threads):
        barrier.abort()
        raise BenchmarkScenarioError("live-worker")
    if any(error is not None for error in failures):
        raise BenchmarkScenarioError("worker-failed")
    completed = tuple(values)  # type: ignore[arg-type]
    verify(completed)
    return stopped - started


async def async_measure_calls[T](
    calls: Sequence[Callable[[], Awaitable[T]]],
    *,
    timeout: float,
    verify: Callable[[tuple[T, ...]], None],
) -> int:
    """Async two-phase ready/release measurement with post-clock verification."""
    if not calls:
        raise ValueError("calls must not be empty")
    condition = asyncio.Condition()
    release = asyncio.Event()
    ready = 0

    async def worker(call: Callable[[], Awaitable[T]]) -> T:
        nonlocal ready
        async with condition:
            ready += 1
            condition.notify_all()
        await release.wait()
        return await call()

    tasks = tuple(asyncio.create_task(worker(call)) for call in calls)
    try:
        async with asyncio.timeout(timeout):
            async with condition:
                await condition.wait_for(lambda: ready == len(calls))
        started = perf_counter_ns()
        release.set()
        async with asyncio.timeout(timeout):
            values = tuple(await asyncio.gather(*tasks))
        stopped = perf_counter_ns()
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    verify(values)
    return stopped - started


def invariants_for(
    scenario_id: str,
    metrics: CorrectnessMetrics,
    *,
    coordinators: int,
    keys: int,
    stale_result_bytes: int = 0,
) -> dict[str, bool]:
    """Return exact low-cardinality invariants for one stable scenario ID."""
    if scenario_id == "local-only":
        return {
            "independent_cold_caches": metrics.loader_count == coordinators,
            "redis_commands_zero": metrics.redis_commands == 0,
        }
    if scenario_id == "local-hit":
        return {
            "loader_count_zero": metrics.loader_count == 0,
            "redis_commands_zero": metrics.redis_commands == 0,
        }
    if scenario_id == "single-coordinator":
        return {"one_loader": metrics.loader_count == 1}
    if scenario_id == "multi-coordinator":
        result = {"one_loader": metrics.loader_count == 1}
        if stale_result_bytes:
            result["multiple_active_snapshots"] = metrics.active_snapshot_count >= 2
        return result
    if scenario_id == "completed-reuse":
        return {
            "waiter_loader_zero": metrics.loader_count == 0,
            "completed_result_observed": metrics.completed_result_bytes > 0,
        }
    if scenario_id == "unrelated-keys":
        return {
            "one_loader_per_key": metrics.loader_count == keys,
            "loader_overlap": metrics.overlap_observed,
        }
    raise ValueError("scenario_id is unsupported")


def process_high_water_bytes() -> int | None:
    """Return a non-timed process high-water mark when the platform supports it."""
    try:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (AttributeError, OSError, ValueError):
        return None
    if value <= 0:
        return None
    return value if sys.platform == "darwin" else value * 1024


class _Recorder:
    def __init__(self, *, active_snapshot_target: int = 0) -> None:
        if type(active_snapshot_target) is not int:
            raise TypeError("active_snapshot_target must be an exact int")
        if active_snapshot_target < 0:
            raise ValueError("active_snapshot_target must be non-negative")
        self._lock = threading.Lock()
        self._active_snapshot_target = active_snapshot_target
        self._sync_active_snapshots = threading.Event()
        self._async_active_snapshots: asyncio.Event | None = None
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self.commands = 0
        self.active_snapshot_count = 0
        self.active_result_bytes = 0
        self.completed_result_bytes = 0

    def command(self) -> None:
        with self._lock:
            self.commands += 1

    def snapshot(self, value: RedisCoordinationSnapshot) -> None:
        with self._lock:
            self.commands += 1
            if value.marker is not None and value.marker.startswith(_ACTIVE_MARKER_PREFIX):
                self.active_snapshot_count += 1
                if value.result is not None:
                    self.active_result_bytes += len(value.result)
                if self.active_snapshot_count >= self._active_snapshot_target:
                    self._sync_active_snapshots.set()
                    if self._async_active_snapshots is not None:
                        self._async_active_snapshots.set()
            elif (
                value.marker is not None
                and value.marker.startswith(_COMPLETED_MARKER_PREFIX)
                and value.result is not None
            ):
                self.completed_result_bytes += len(value.result)

    def wait_for_active_snapshots(self, *, timeout: float) -> None:
        if self._active_snapshot_target == 0:
            return
        if not self._sync_active_snapshots.wait(timeout):
            raise BenchmarkScenarioError("active-snapshot-gate")

    async def wait_for_active_snapshots_async(self, *, timeout: float) -> None:
        if self._active_snapshot_target == 0:
            return
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._async_loop is not None and self._async_loop is not loop:
                raise BenchmarkScenarioError("active-snapshot-gate")
            self._async_loop = loop
            event = self._async_active_snapshots
            if event is None:
                event = asyncio.Event()
                self._async_active_snapshots = event
            if self.active_snapshot_count >= self._active_snapshot_target:
                event.set()
        try:
            async with asyncio.timeout(timeout):
                await event.wait()
        except TimeoutError:
            raise BenchmarkScenarioError("active-snapshot-gate") from None


class _RecordingSyncProvider(SyncRedisProvider):
    def __init__(self, client, recorder: _Recorder) -> None:
        super().__init__(client)
        self._recorder = recorder

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        self._recorder.command()
        return super().set_if_absent(key, value, ttl=ttl)

    def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        self._recorder.command()
        return super().delete_if_value(key, expected_value)

    def coordination_snapshot(
        self,
        marker_key: str,
        result_key: str,
        *,
        max_marker_size: int = 138,
        max_result_size: int,
    ) -> RedisCoordinationSnapshot:
        result = super().coordination_snapshot(
            marker_key,
            result_key,
            max_marker_size=max_marker_size,
            max_result_size=max_result_size,
        )
        self._recorder.snapshot(result)
        return result

    def publish_if_value(
        self,
        condition_key: str,
        expected_value: bytes,
        *,
        result_key: str,
        result_value: bytes,
        completion_value: bytes,
        ttl: float,
    ) -> bool:
        self._recorder.command()
        return super().publish_if_value(
            condition_key,
            expected_value,
            result_key=result_key,
            result_value=result_value,
            completion_value=completion_value,
            ttl=ttl,
        )


class _RecordingAsyncProvider(AsyncRedisProvider):
    def __init__(self, client, recorder: _Recorder) -> None:
        super().__init__(client)
        self._recorder = recorder

    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        self._recorder.command()
        return await super().set_if_absent(key, value, ttl=ttl)

    async def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        self._recorder.command()
        return await super().delete_if_value(key, expected_value)

    async def coordination_snapshot(
        self,
        marker_key: str,
        result_key: str,
        *,
        max_marker_size: int = 138,
        max_result_size: int,
    ) -> RedisCoordinationSnapshot:
        result = await super().coordination_snapshot(
            marker_key,
            result_key,
            max_marker_size=max_marker_size,
            max_result_size=max_result_size,
        )
        self._recorder.snapshot(result)
        return result

    async def publish_if_value(
        self,
        condition_key: str,
        expected_value: bytes,
        *,
        result_key: str,
        result_value: bytes,
        completion_value: bytes,
        ttl: float,
    ) -> bool:
        self._recorder.command()
        return await super().publish_if_value(
            condition_key,
            expected_value,
            result_key=result_key,
            result_value=result_value,
            completion_value=completion_value,
            ttl=ttl,
        )


class _SyncLoader:
    def __init__(
        self,
        payload: bytes,
        delay: float,
        *,
        pre_return_gate: Callable[[], None] | None = None,
        overlap_target: int = 0,
    ) -> None:
        if type(overlap_target) is not int:
            raise TypeError("overlap_target must be an exact int")
        if overlap_target < 0:
            raise ValueError("overlap_target must be non-negative")
        self.payload = payload
        self.delay = delay
        self.pre_return_gate = pre_return_gate
        self.overlap_target = overlap_target
        self.overlap_ready = threading.Event()
        self.count = 0
        self.active = 0
        self.overlap = False
        self.lock = threading.Lock()

    def __call__(self, _key: str) -> bytes:
        with self.lock:
            self.count += 1
            self.active += 1
            self.overlap = self.overlap or self.active > 1
            if self.overlap_target and self.active >= self.overlap_target:
                self.overlap_ready.set()
        try:
            if self.overlap_target and not self.overlap_ready.wait(_LOADER_OVERLAP_GATE_TIMEOUT):
                raise BenchmarkScenarioError("loader-overlap-gate")
            if self.pre_return_gate is not None:
                self.pre_return_gate()
            if self.delay:
                sleep(self.delay)
            return self.payload
        finally:
            with self.lock:
                self.active -= 1


class _AsyncLoader:
    def __init__(
        self,
        payload: bytes,
        delay: float,
        *,
        pre_return_gate: Callable[[], Awaitable[None]] | None = None,
        overlap_target: int = 0,
    ) -> None:
        if type(overlap_target) is not int:
            raise TypeError("overlap_target must be an exact int")
        if overlap_target < 0:
            raise ValueError("overlap_target must be non-negative")
        self.payload = payload
        self.delay = delay
        self.pre_return_gate = pre_return_gate
        self.overlap_target = overlap_target
        self.overlap_ready = asyncio.Event()
        self.count = 0
        self.active = 0
        self.overlap = False

    async def __call__(self, _key: str) -> bytes:
        self.count += 1
        self.active += 1
        self.overlap = self.overlap or self.active > 1
        if self.overlap_target and self.active >= self.overlap_target:
            self.overlap_ready.set()
        try:
            if self.overlap_target:
                try:
                    async with asyncio.timeout(_LOADER_OVERLAP_GATE_TIMEOUT):
                        await self.overlap_ready.wait()
                except TimeoutError:
                    raise BenchmarkScenarioError("loader-overlap-gate") from None
            if self.pre_return_gate is not None:
                await self.pre_return_gate()
            if self.delay:
                await asyncio.sleep(self.delay)
            return self.payload
        finally:
            self.active -= 1


def _namespace(
    profile: str,
    mode: str,
    case: ScenarioCase,
    phase: str,
    repetition: int,
    seed: int,
) -> str:
    raw = f"{profile}|{mode}|{case.scenario_id}|{case.case_id}|{phase}|{repetition}|{seed}"
    return f"benchmark:{sha256(raw.encode()).hexdigest()}"


def _parameters(case: ScenarioCase) -> dict[str, object]:
    return {
        "callers": case.callers,
        "case_id": case.case_id,
        "coordinators": case.coordinators,
        "keys": case.keys,
        "loader_delay_seconds": case.loader_delay_seconds,
        "payload_bytes": case.payload_bytes,
        "stale_result_bytes": case.stale_result_bytes,
        "repetitions": case.repetitions,
        "warmups": case.warmups,
    }


def _verify_payload(payload: bytes, values: tuple[bytes, ...]) -> None:
    if not values or any(value != payload for value in values):
        raise BenchmarkScenarioError("result-mismatch")


def _stale_result_key(namespace: str) -> str:
    namespace_id = sha256(namespace.encode("utf-8")).hexdigest()
    return _coordination_keys(namespace_id, "key-0")[1]


def _seed_sync_stale_result(
    case: ScenarioCase,
    providers: Sequence[SyncRedisProvider],
    namespace: str,
) -> None:
    if not case.stale_result_bytes:
        return
    options = load_options(namespace)
    providers[0].set(
        _stale_result_key(namespace),
        b"s" * case.stale_result_bytes,
        ttl=options.result_ttl,
    )


async def _seed_async_stale_result(
    case: ScenarioCase,
    providers: Sequence[AsyncRedisProvider],
    namespace: str,
) -> None:
    if not case.stale_result_bytes:
        return
    options = load_options(namespace)
    await providers[0].set(
        _stale_result_key(namespace),
        b"s" * case.stale_result_bytes,
        ttl=options.result_ttl,
    )


def _sync_repetition(
    case: ScenarioCase,
    providers: Sequence[SyncRedisProvider],
    namespace: str,
    payload: bytes,
    loader: Callable[[str], bytes],
    *,
    timeout: float,
) -> int:
    if case.scenario_id == "local-only":
        caches = [
            TTLCache[str, bytes](default_ttl=60, max_size=128) for _ in range(case.coordinators)
        ]
        calls = tuple(
            lambda index=index: caches[index % len(caches)].get_or_load("key-0", loader)
            for index in range(case.callers)
        )
        return sync_measure_calls(
            calls, timeout=timeout, verify=lambda values: _verify_payload(payload, values)
        )

    codec = build_envelope_codec()
    caches = [TTLCache[str, bytes](default_ttl=60, max_size=128) for _ in providers]
    coordinators = [
        SyncRedisLoadCoordinator(cache, provider, codec, options=load_options(namespace))
        for cache, provider in zip(caches, providers, strict=True)
    ]
    _seed_sync_stale_result(case, providers, namespace)
    if case.scenario_id == "local-hit":
        caches[0].set("key-0", payload)
        started = perf_counter_ns()
        values = tuple(
            coordinators[0].get_or_load("key-0", loader) for _ in range(case.operations_per_sample)
        )
        stopped = perf_counter_ns()
        _verify_payload(payload, values)
        return stopped - started
    if case.scenario_id == "completed-reuse":
        coordinators[0].get_or_load("key-0", lambda _key: payload)
        for cache in caches:
            cache.clear()
    calls = tuple(
        lambda index=index: coordinators[index % len(coordinators)].get_or_load(
            f"key-{index % case.keys}" if case.scenario_id == "unrelated-keys" else "key-0",
            loader,
        )
        for index in range(case.callers)
    )
    return sync_measure_calls(
        calls, timeout=timeout, verify=lambda values: _verify_payload(payload, values)
    )


def _sync_resources(
    redis_url: str, count: int, *, recorder: _Recorder | None
) -> tuple[list[object], list[SyncRedisProvider]]:
    clients: list[object] = []
    providers: list[SyncRedisProvider] = []
    try:
        for _ in range(count):
            clients.append(make_sync_client(redis_url))
        for client in clients:
            client.ping()
        if recorder is None:
            providers = [SyncRedisProvider(client) for client in clients]
        else:
            providers = [_RecordingSyncProvider(client, recorder) for client in clients]
        return clients, providers
    except BaseException as primary:
        try:
            _close_sync(clients, providers)
        except KeyboardInterrupt:
            raise
        except BaseException:
            primary.add_note("benchmark resource cleanup also failed")
        raise


def _close_sync(clients: Sequence[object], providers: Sequence[SyncRedisProvider]) -> None:
    failure: BaseException | None = None
    interrupted: KeyboardInterrupt | None = None
    for provider in providers:
        try:
            provider.close()
        except KeyboardInterrupt as error:
            interrupted = interrupted or error
        except BaseException as error:
            failure = failure or error
    for client in clients:
        try:
            client.close()  # type: ignore[attr-defined]
        except KeyboardInterrupt as error:
            interrupted = interrupted or error
        except BaseException as error:
            failure = failure or error
    if interrupted is not None:
        raise interrupted
    if failure is not None:
        raise failure


def _close_sync_preserving(
    clients: Sequence[object],
    providers: Sequence[SyncRedisProvider],
    primary: BaseException | None,
) -> None:
    try:
        _close_sync(clients, providers)
    except KeyboardInterrupt:
        raise
    except BaseException:
        if primary is None:
            raise
        primary.add_note("benchmark resource cleanup also failed")


def run_sync_case(
    redis_url: str,
    profile: BenchmarkProfile,
    case: ScenarioCase,
    seed: int,
) -> BenchmarkScenarioResult:
    """Run correctness, warmup, and uninstrumented sync measurement phases."""
    payload = b"x" * case.payload_bytes
    active_snapshot_target = 2 if case.stale_result_bytes else 0
    recorder = _Recorder(active_snapshot_target=active_snapshot_target)
    correctness_loader = _SyncLoader(
        payload,
        case.loader_delay_seconds,
        pre_return_gate=(
            lambda: recorder.wait_for_active_snapshots(timeout=_ACTIVE_SNAPSHOT_GATE_TIMEOUT)
        )
        if active_snapshot_target
        else None,
        overlap_target=2 if case.scenario_id == "unrelated-keys" else 0,
    )
    clients: list[object] = []
    providers: list[SyncRedisProvider] = []
    if case.scenario_id != "local-only":
        clients, providers = _sync_resources(redis_url, case.coordinators, recorder=recorder)
    primary: BaseException | None = None
    try:
        _sync_repetition(
            case,
            providers,
            _namespace(profile.profile_id, "sync", case, "correctness", 0, seed),
            payload,
            correctness_loader,
            timeout=120.0 if case.near_boundary else 30.0,
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        _close_sync_preserving(clients, providers, primary)
    metrics = CorrectnessMetrics(
        loader_count=correctness_loader.count,
        redis_commands=recorder.commands,
        active_snapshot_count=recorder.active_snapshot_count,
        active_result_bytes=recorder.active_result_bytes,
        completed_result_bytes=recorder.completed_result_bytes,
        overlap_observed=correctness_loader.overlap,
    )
    invariants = invariants_for(
        case.scenario_id,
        metrics,
        coordinators=case.coordinators,
        keys=case.keys,
        stale_result_bytes=case.stale_result_bytes,
    )
    if not all(invariants.values()):
        raise BenchmarkScenarioError("correctness-failed")

    samples: list[int] = []
    clients = []
    providers = []
    if case.scenario_id != "local-only":
        clients, providers = _sync_resources(redis_url, case.coordinators, recorder=None)
    primary = None
    try:
        for repetition in range(case.warmups):
            _sync_repetition(
                case,
                providers,
                _namespace(profile.profile_id, "sync", case, "warmup", repetition, seed),
                payload,
                lambda _key: sleep(case.loader_delay_seconds) or payload,
                timeout=120.0 if case.near_boundary else 30.0,
            )
        for repetition in range(case.repetitions):
            samples.append(
                _sync_repetition(
                    case,
                    providers,
                    _namespace(profile.profile_id, "sync", case, "measurement", repetition, seed),
                    payload,
                    lambda _key: sleep(case.loader_delay_seconds) or payload,
                    timeout=120.0 if case.near_boundary else 30.0,
                )
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        _close_sync_preserving(clients, providers, primary)
    metric_fields = {
        "correctness_active_result_bytes": metrics.active_result_bytes,
        "correctness_active_snapshot_count": metrics.active_snapshot_count,
        "correctness_completed_result_bytes": metrics.completed_result_bytes,
        "correctness_loader_count": metrics.loader_count,
        "correctness_overlap_observed": metrics.overlap_observed,
        "correctness_redis_commands": metrics.redis_commands,
        "process_high_water_bytes": process_high_water_bytes(),
    }
    return BenchmarkScenarioResult(
        scenario_id=case.scenario_id,
        mode="sync",
        parameters=_parameters(case),
        timing=summarize_timings(samples, operations_per_sample=case.operations_per_sample),
        metrics=metric_fields,
        invariants=invariants,
    )


async def _async_repetition(
    case: ScenarioCase,
    providers: Sequence[AsyncRedisProvider],
    namespace: str,
    payload: bytes,
    loader: Callable[[str], Awaitable[bytes]],
    *,
    timeout: float,
) -> int:
    if case.scenario_id == "local-only":
        caches = [
            AsyncTTLCache[str, bytes](default_ttl=60, max_size=128)
            for _ in range(case.coordinators)
        ]
        calls = tuple(
            lambda index=index: caches[index % len(caches)].get_or_load("key-0", loader)
            for index in range(case.callers)
        )
        return await async_measure_calls(
            calls, timeout=timeout, verify=lambda values: _verify_payload(payload, values)
        )

    codec = build_envelope_codec()
    caches = [AsyncTTLCache[str, bytes](default_ttl=60, max_size=128) for _ in providers]
    coordinators = [
        AsyncRedisLoadCoordinator(cache, provider, codec, options=load_options(namespace))
        for cache, provider in zip(caches, providers, strict=True)
    ]
    await _seed_async_stale_result(case, providers, namespace)
    if case.scenario_id == "local-hit":
        await caches[0].set("key-0", payload)
        started = perf_counter_ns()
        values = tuple(
            [
                await coordinators[0].get_or_load("key-0", loader)
                for _ in range(case.operations_per_sample)
            ]
        )
        stopped = perf_counter_ns()
        _verify_payload(payload, values)
        return stopped - started
    if case.scenario_id == "completed-reuse":

        async def seed_loader(_key: str) -> bytes:
            return payload

        await coordinators[0].get_or_load("key-0", seed_loader)
        for cache in caches:
            await cache.clear()
    calls = tuple(
        lambda index=index: coordinators[index % len(coordinators)].get_or_load(
            f"key-{index % case.keys}" if case.scenario_id == "unrelated-keys" else "key-0",
            loader,
        )
        for index in range(case.callers)
    )
    return await async_measure_calls(
        calls, timeout=timeout, verify=lambda values: _verify_payload(payload, values)
    )


async def _async_resources(
    redis_url: str, count: int, *, recorder: _Recorder | None
) -> tuple[list[object], list[AsyncRedisProvider]]:
    clients: list[object] = []
    providers: list[AsyncRedisProvider] = []
    try:
        for _ in range(count):
            clients.append(make_async_client(redis_url))
        for client in clients:
            await client.ping()
        if recorder is None:
            providers = [AsyncRedisProvider(client) for client in clients]
        else:
            providers = [_RecordingAsyncProvider(client, recorder) for client in clients]
        return clients, providers
    except BaseException as primary:
        try:
            await _close_async(clients, providers)
        except KeyboardInterrupt:
            raise
        except BaseException:
            primary.add_note("benchmark resource cleanup also failed")
        raise


async def _close_async(clients: Sequence[object], providers: Sequence[AsyncRedisProvider]) -> None:
    failure: BaseException | None = None
    interrupted: KeyboardInterrupt | None = None
    for provider in providers:
        try:
            await provider.aclose()
        except KeyboardInterrupt as error:
            interrupted = interrupted or error
        except BaseException as error:
            failure = failure or error
    for client in clients:
        try:
            await client.aclose()  # type: ignore[attr-defined]
        except KeyboardInterrupt as error:
            interrupted = interrupted or error
        except BaseException as error:
            failure = failure or error
    if interrupted is not None:
        raise interrupted
    if failure is not None:
        raise failure


async def _close_async_preserving(
    clients: Sequence[object],
    providers: Sequence[AsyncRedisProvider],
    primary: BaseException | None,
) -> None:
    try:
        await _close_async(clients, providers)
    except KeyboardInterrupt:
        raise
    except BaseException:
        if primary is None:
            raise
        primary.add_note("benchmark resource cleanup also failed")


async def run_async_case(
    redis_url: str,
    profile: BenchmarkProfile,
    case: ScenarioCase,
    seed: int,
) -> BenchmarkScenarioResult:
    """Run correctness, warmup, and uninstrumented async measurement phases."""
    payload = b"x" * case.payload_bytes
    active_snapshot_target = 2 if case.stale_result_bytes else 0
    recorder = _Recorder(active_snapshot_target=active_snapshot_target)

    async def wait_for_active_snapshots() -> None:
        await recorder.wait_for_active_snapshots_async(timeout=_ACTIVE_SNAPSHOT_GATE_TIMEOUT)

    correctness_loader = _AsyncLoader(
        payload,
        case.loader_delay_seconds,
        pre_return_gate=wait_for_active_snapshots if active_snapshot_target else None,
        overlap_target=2 if case.scenario_id == "unrelated-keys" else 0,
    )
    clients: list[object] = []
    providers: list[AsyncRedisProvider] = []
    if case.scenario_id != "local-only":
        clients, providers = await _async_resources(redis_url, case.coordinators, recorder=recorder)
    primary: BaseException | None = None
    try:
        await _async_repetition(
            case,
            providers,
            _namespace(profile.profile_id, "async", case, "correctness", 0, seed),
            payload,
            correctness_loader,
            timeout=120.0 if case.near_boundary else 30.0,
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        await _close_async_preserving(clients, providers, primary)
    metrics = CorrectnessMetrics(
        loader_count=correctness_loader.count,
        redis_commands=recorder.commands,
        active_snapshot_count=recorder.active_snapshot_count,
        active_result_bytes=recorder.active_result_bytes,
        completed_result_bytes=recorder.completed_result_bytes,
        overlap_observed=correctness_loader.overlap,
    )
    invariants = invariants_for(
        case.scenario_id,
        metrics,
        coordinators=case.coordinators,
        keys=case.keys,
        stale_result_bytes=case.stale_result_bytes,
    )
    if not all(invariants.values()):
        raise BenchmarkScenarioError("correctness-failed")

    async def measured_loader(_key: str) -> bytes:
        if case.loader_delay_seconds:
            await asyncio.sleep(case.loader_delay_seconds)
        return payload

    samples: list[int] = []
    clients = []
    providers = []
    if case.scenario_id != "local-only":
        clients, providers = await _async_resources(redis_url, case.coordinators, recorder=None)
    primary = None
    try:
        for repetition in range(case.warmups):
            await _async_repetition(
                case,
                providers,
                _namespace(profile.profile_id, "async", case, "warmup", repetition, seed),
                payload,
                measured_loader,
                timeout=120.0 if case.near_boundary else 30.0,
            )
        for repetition in range(case.repetitions):
            samples.append(
                await _async_repetition(
                    case,
                    providers,
                    _namespace(profile.profile_id, "async", case, "measurement", repetition, seed),
                    payload,
                    measured_loader,
                    timeout=120.0 if case.near_boundary else 30.0,
                )
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        await _close_async_preserving(clients, providers, primary)
    metric_fields = {
        "correctness_active_result_bytes": metrics.active_result_bytes,
        "correctness_active_snapshot_count": metrics.active_snapshot_count,
        "correctness_completed_result_bytes": metrics.completed_result_bytes,
        "correctness_loader_count": metrics.loader_count,
        "correctness_overlap_observed": metrics.overlap_observed,
        "correctness_redis_commands": metrics.redis_commands,
        "process_high_water_bytes": process_high_water_bytes(),
    }
    return BenchmarkScenarioResult(
        scenario_id=case.scenario_id,
        mode="async",
        parameters=_parameters(case),
        timing=summarize_timings(samples, operations_per_sample=case.operations_per_sample),
        metrics=metric_fields,
        invariants=invariants,
    )


__all__ = [
    "BenchmarkScenarioError",
    "CorrectnessMetrics",
    "async_measure_calls",
    "invariants_for",
    "process_high_water_bytes",
    "run_async_case",
    "run_sync_case",
    "sync_measure_calls",
]
