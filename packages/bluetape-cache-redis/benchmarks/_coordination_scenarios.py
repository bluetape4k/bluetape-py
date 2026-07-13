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


class BenchmarkScenarioError(RuntimeError):
    """Low-cardinality benchmark scenario failure."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CorrectnessMetrics:
    loader_count: int
    redis_commands: int
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
        return {"one_loader": metrics.loader_count == 1}
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
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.commands = 0
        self.active_result_bytes = 0
        self.completed_result_bytes = 0

    def command(self) -> None:
        with self._lock:
            self.commands += 1

    def snapshot(self, value: RedisCoordinationSnapshot) -> None:
        with self._lock:
            self.commands += 1
            if value.result is not None:
                self.completed_result_bytes += len(value.result)


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
    def __init__(self, payload: bytes, delay: float) -> None:
        self.payload = payload
        self.delay = delay
        self.count = 0
        self.active = 0
        self.overlap = False
        self.lock = threading.Lock()

    def __call__(self, _key: str) -> bytes:
        with self.lock:
            self.count += 1
            self.active += 1
            self.overlap = self.overlap or self.active > 1
        try:
            if self.delay:
                sleep(self.delay)
            return self.payload
        finally:
            with self.lock:
                self.active -= 1


class _AsyncLoader:
    def __init__(self, payload: bytes, delay: float) -> None:
        self.payload = payload
        self.delay = delay
        self.count = 0
        self.active = 0
        self.overlap = False

    async def __call__(self, _key: str) -> bytes:
        self.count += 1
        self.active += 1
        self.overlap = self.overlap or self.active > 1
        try:
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
        "repetitions": case.repetitions,
        "warmups": case.warmups,
    }


def _verify_payload(payload: bytes, values: tuple[bytes, ...]) -> None:
    if not values or any(value != payload for value in values):
        raise BenchmarkScenarioError("result-mismatch")


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
    clients = [make_sync_client(redis_url) for _ in range(count)]
    for client in clients:
        client.ping()
    providers: list[SyncRedisProvider]
    if recorder is None:
        providers = [SyncRedisProvider(client) for client in clients]
    else:
        providers = [_RecordingSyncProvider(client, recorder) for client in clients]
    return clients, providers


def _close_sync(clients: Sequence[object], providers: Sequence[SyncRedisProvider]) -> None:
    for provider in providers:
        provider.close()
    for client in clients:
        client.close()  # type: ignore[attr-defined]


def run_sync_case(
    redis_url: str,
    profile: BenchmarkProfile,
    case: ScenarioCase,
    seed: int,
) -> BenchmarkScenarioResult:
    """Run correctness, warmup, and uninstrumented sync measurement phases."""
    payload = b"x" * case.payload_bytes
    recorder = _Recorder()
    correctness_loader = _SyncLoader(payload, case.loader_delay_seconds)
    clients: list[object] = []
    providers: list[SyncRedisProvider] = []
    if case.scenario_id != "local-only":
        clients, providers = _sync_resources(redis_url, case.coordinators, recorder=recorder)
    try:
        _sync_repetition(
            case,
            providers,
            _namespace(profile.profile_id, "sync", case, "correctness", 0, seed),
            payload,
            correctness_loader,
            timeout=120.0 if case.near_boundary else 30.0,
        )
    finally:
        _close_sync(clients, providers)
    metrics = CorrectnessMetrics(
        loader_count=correctness_loader.count,
        redis_commands=recorder.commands,
        active_result_bytes=recorder.active_result_bytes,
        completed_result_bytes=recorder.completed_result_bytes,
        overlap_observed=correctness_loader.overlap,
    )
    invariants = invariants_for(
        case.scenario_id, metrics, coordinators=case.coordinators, keys=case.keys
    )
    if not all(invariants.values()):
        raise BenchmarkScenarioError("correctness-failed")

    samples: list[int] = []
    clients = []
    providers = []
    if case.scenario_id != "local-only":
        clients, providers = _sync_resources(redis_url, case.coordinators, recorder=None)
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
    finally:
        _close_sync(clients, providers)
    metric_fields = {
        "correctness_active_result_bytes": metrics.active_result_bytes,
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
    clients = [make_async_client(redis_url) for _ in range(count)]
    for client in clients:
        await client.ping()
    providers: list[AsyncRedisProvider]
    if recorder is None:
        providers = [AsyncRedisProvider(client) for client in clients]
    else:
        providers = [_RecordingAsyncProvider(client, recorder) for client in clients]
    return clients, providers


async def _close_async(clients: Sequence[object], providers: Sequence[AsyncRedisProvider]) -> None:
    for provider in providers:
        await provider.aclose()
    for client in clients:
        await client.aclose()  # type: ignore[attr-defined]


async def run_async_case(
    redis_url: str,
    profile: BenchmarkProfile,
    case: ScenarioCase,
    seed: int,
) -> BenchmarkScenarioResult:
    """Run correctness, warmup, and uninstrumented async measurement phases."""
    payload = b"x" * case.payload_bytes
    recorder = _Recorder()
    correctness_loader = _AsyncLoader(payload, case.loader_delay_seconds)
    clients: list[object] = []
    providers: list[AsyncRedisProvider] = []
    if case.scenario_id != "local-only":
        clients, providers = await _async_resources(redis_url, case.coordinators, recorder=recorder)
    try:
        await _async_repetition(
            case,
            providers,
            _namespace(profile.profile_id, "async", case, "correctness", 0, seed),
            payload,
            correctness_loader,
            timeout=120.0 if case.near_boundary else 30.0,
        )
    finally:
        await _close_async(clients, providers)
    metrics = CorrectnessMetrics(
        loader_count=correctness_loader.count,
        redis_commands=recorder.commands,
        active_result_bytes=recorder.active_result_bytes,
        completed_result_bytes=recorder.completed_result_bytes,
        overlap_observed=correctness_loader.overlap,
    )
    invariants = invariants_for(
        case.scenario_id, metrics, coordinators=case.coordinators, keys=case.keys
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
    finally:
        await _close_async(clients, providers)
    metric_fields = {
        "correctness_active_result_bytes": metrics.active_result_bytes,
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
