"""Deterministic performance and lifecycle evidence for bluetape-cache."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import threading
import time
import tracemalloc
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bluetape.cache import AsyncTTLCache, TTLCache


class FakeClock:
    """Caller-controlled nanosecond clock used by deterministic scenarios."""

    def __init__(self) -> None:
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return ordered[index]


def _summary(samples: list[int], operations: int) -> dict[str, Any]:
    p50 = _percentile(samples, 0.50)
    return {
        "raw_samples_ns": samples,
        "p50_ns": p50,
        "p95_ns": _percentile(samples, 0.95),
        "p99_ns": _percentile(samples, 0.99),
        "max_ns": max(samples),
        "median_ns_per_op": p50 / operations,
        "throughput_ops_per_sec": operations * 1_000_000_000 / p50,
    }


def _measure(
    function: Callable[[], None],
    *,
    operations: int,
    warmups: int,
    repetitions: int,
) -> dict[str, Any]:
    for _ in range(warmups):
        function()
    samples: list[int] = []
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        function()
        samples.append(time.perf_counter_ns() - started)
    return _summary(samples, operations)


def _microbenchmarks(
    *, capacity: int, operations: int, warmups: int, repetitions: int
) -> dict[str, Any]:
    keys = [index % capacity for index in range(operations)]
    missing_keys = [capacity + index for index in range(operations)]

    reference = OrderedDict((key, key) for key in range(capacity))

    def ordered_hit_touch() -> None:
        for key in keys:
            reference[key]
            reference.move_to_end(key)

    hit_cache = TTLCache[int, int](default_ttl=60, max_size=capacity)
    for key in range(capacity):
        hit_cache.set(key, key)

    def cache_hit() -> None:
        for key in keys:
            hit_cache.get(key)

    miss_cache = TTLCache[int, int](default_ttl=60, max_size=capacity)

    def cache_miss() -> None:
        for key in missing_keys:
            try:
                miss_cache.get(key)
            except KeyError:
                pass

    set_cache = TTLCache[int, int](default_ttl=60, max_size=capacity)

    def cache_set() -> None:
        for index, key in enumerate(keys):
            set_cache.set(key, index)

    load_hit_cache = TTLCache[int, int](default_ttl=60, max_size=capacity)
    for key in range(capacity):
        load_hit_cache.set(key, key)

    def cache_get_or_load_hit() -> None:
        for key in keys:
            load_hit_cache.get_or_load(key, lambda current: current)

    return {
        "ordered_dict_hit_touch": _measure(
            ordered_hit_touch,
            operations=operations,
            warmups=warmups,
            repetitions=repetitions,
        ),
        "ttl_cache_get_hit": _measure(
            cache_hit, operations=operations, warmups=warmups, repetitions=repetitions
        ),
        "ttl_cache_get_miss": _measure(
            cache_miss, operations=operations, warmups=warmups, repetitions=repetitions
        ),
        "ttl_cache_set": _measure(
            cache_set, operations=operations, warmups=warmups, repetitions=repetitions
        ),
        "ttl_cache_get_or_load_hit": _measure(
            cache_get_or_load_hit,
            operations=operations,
            warmups=warmups,
            repetitions=repetitions,
        ),
    }


def _coordination_observations() -> dict[str, Any]:
    callers = 8
    cache = TTLCache[str, int](default_ttl=60, max_size=16)
    start = threading.Barrier(callers)
    loader_entered = threading.Event()
    release = threading.Event()
    invocation_count = 0
    count_lock = threading.Lock()
    results: list[int] = []
    errors: list[str] = []

    def loader(_: str) -> int:
        nonlocal invocation_count
        with count_lock:
            invocation_count += 1
        loader_entered.set()
        if not release.wait(5):
            raise TimeoutError("same-key loader release timed out")
        return 41

    def caller() -> None:
        try:
            start.wait(5)
            results.append(cache.get_or_load("shared", loader))
        except BaseException as error:  # benchmark records every terminal path
            errors.append(type(error).__name__)

    threads = [threading.Thread(target=caller) for _ in range(callers)]
    for thread in threads:
        thread.start()
    if not loader_entered.wait(5):
        raise RuntimeError("same-key loader did not start")
    release.set()
    for thread in threads:
        thread.join(5)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("same-key contention left a live thread")

    overlap_cache = TTLCache[int, int](default_ttl=60, max_size=16)
    overlap = threading.Barrier(2)
    overlap_count = 0
    overlap_lock = threading.Lock()

    def overlapping_loader(key: int) -> int:
        nonlocal overlap_count
        with overlap_lock:
            overlap_count += 1
        overlap.wait(5)
        return key

    overlap_threads = [
        threading.Thread(target=lambda key=key: overlap_cache.get_or_load(key, overlapping_loader))
        for key in (1, 2)
    ]
    for thread in overlap_threads:
        thread.start()
    for thread in overlap_threads:
        thread.join(5)
    if any(thread.is_alive() for thread in overlap_threads):
        raise RuntimeError("different-key overlap left a live thread")

    return {
        "same_key": {
            "callers": callers,
            "actual_loader_count": invocation_count,
            "results": len(results),
            "errors": errors,
        },
        "different_key": {
            "loaders_entered_overlap_barrier": overlap_count == 2,
            "actual_loader_count": overlap_count,
        },
    }


def _fixed_worker_contention(*, distinct_keys: bool) -> dict[str, Any]:
    workers = 8
    operations_per_worker = 20_000
    cache = TTLCache[int, int](default_ttl=60, max_size=64)
    for key in range(workers):
        cache.set(key, 0)
    start = threading.Barrier(workers + 1)
    elapsed: list[int] = []
    errors: list[str] = []

    def worker(worker_id: int) -> None:
        key = worker_id if distinct_keys else 0
        try:
            start.wait(5)
            for index in range(operations_per_worker):
                began = time.perf_counter_ns()
                if index % 10 == 0:
                    cache.set(key, index)
                else:
                    cache.get(key)
                elapsed.append(time.perf_counter_ns() - began)
        except BaseException as error:
            errors.append(type(error).__name__)

    threads = [threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(workers)]
    for thread in threads:
        thread.start()
    started = time.perf_counter_ns()
    start.wait(5)
    for thread in threads:
        thread.join(20)
    total_ns = time.perf_counter_ns() - started
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("fixed-worker contention left a live thread")
    if errors:
        raise RuntimeError(f"fixed-worker contention failed: {errors}")
    total_operations = workers * operations_per_worker
    return {
        "workers": workers,
        "operations_per_worker": operations_per_worker,
        "total_operations": total_operations,
        "p50_latency_ns": _percentile(elapsed, 0.50),
        "p95_latency_ns": _percentile(elapsed, 0.95),
        "throughput_ops_per_sec": total_operations * 1_000_000_000 / total_ns,
    }


def _expiry_heavy(capacity: int, repetitions: int) -> dict[str, Any]:
    operations = capacity * 10
    normalized: list[int] = []
    batch_samples: list[int] = []
    for _ in range(repetitions):
        clock = FakeClock()
        cache = TTLCache[int, int](default_ttl=0.000001, max_size=capacity, clock=clock)
        started = time.perf_counter_ns()
        batch_started = started
        for index in range(operations):
            key = (index // 10) % capacity
            cache.set(key, index)
            if index % 10 == 9:
                clock.now_ns += 1_000
            if index % 100 == 99:
                now = time.perf_counter_ns()
                batch_samples.append(now - batch_started)
                batch_started = now
        normalized.append((time.perf_counter_ns() - started) // operations)
    return {
        "capacity": capacity,
        "operations": operations,
        "raw_ns_per_op": normalized,
        "median_ns_per_op": statistics.median(normalized),
        "batch_size": 100,
        "batch_p95_ns": _percentile(batch_samples, 0.95),
        "batch_p99_ns": _percentile(batch_samples, 0.99),
        "batch_max_ns": max(batch_samples),
    }


def _rebuild_proxy(capacity: int) -> dict[str, Any]:
    clock = FakeClock()
    cache = TTLCache[int, int](default_ttl=60, max_size=capacity, clock=clock)
    durations: list[int] = []
    observations: list[dict[str, int]] = []
    for index in range(3 * capacity):
        before = len(cache._state.expiry_heap)
        started = time.perf_counter_ns()
        cache.set(index % capacity, index)
        duration = time.perf_counter_ns() - started
        after = len(cache._state.expiry_heap)
        if after < before:
            durations.append(duration)
            observations.append({"before": before, "after": after, "duration_ns": duration})
    return {
        "capacity": capacity,
        "rebuild_count": len(durations),
        "rebuild_trigger_upper_bound_ns": durations,
        "max_rebuild_trigger_upper_bound_ns": max(durations, default=0),
        "observations": observations,
        "final_heap_length": len(cache._state.expiry_heap),
        "heap_bound": 2 * capacity,
    }


def _allocation_phase(capacity: int) -> dict[str, int]:
    cache = TTLCache[int, int](default_ttl=60, max_size=capacity)
    for key in range(capacity):
        cache.set(key, key)
    tracemalloc.start()
    for index in range(10_000):
        cache.get(index % capacity)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"operations": 10_000, "traced_current_bytes": current, "traced_peak_bytes": peak}


def _normalized_rss_bytes() -> int:
    high_water = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(high_water if sys.platform == "darwin" else high_water * 1024)


def _rss_child(scenario: str, capacity: int, operations: int) -> None:
    cache = TTLCache[int, int](default_ttl=60, max_size=capacity)
    if scenario == "hit":
        for key in range(capacity):
            cache.set(key, key)
        for index in range(operations):
            cache.get(index % capacity)
    elif scenario == "overwrite":
        for index in range(operations):
            cache.set(index % capacity, index)
    else:  # pragma: no cover - argparse constrains parent invocations
        raise ValueError(scenario)
    print(json.dumps({"scenario": scenario, "process_high_water_bytes": _normalized_rss_bytes()}))


def _rss_scenarios(capacity: int, operations: int) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for scenario in ("hit", "overwrite"):
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--rss-child",
                scenario,
                "--capacity",
                str(capacity),
                "--operations",
                str(operations),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        results[scenario] = json.loads(completed.stdout)
    return {
        "label": "fresh-process high-water, not retained memory",
        "platform_unit_normalization": "macOS bytes; Linux KiB multiplied by 1024",
        "scenarios": results,
    }


async def _async_scenarios(operations: int) -> dict[str, Any]:
    hit_operations = min(operations, 20_000)
    cache = AsyncTTLCache[int, int](default_ttl=60, max_size=1_000)
    for key in range(1_000):
        await cache.set(key, key)
    started = time.perf_counter_ns()
    for index in range(hit_operations):
        await cache.get(index % 1_000)
    hit_elapsed = time.perf_counter_ns() - started

    load_cache = AsyncTTLCache[str, int](default_ttl=60, max_size=16)
    entered = asyncio.Event()
    release = asyncio.Event()
    invocations = 0

    async def loader(_: str) -> int:
        nonlocal invocations
        invocations += 1
        entered.set()
        async with asyncio.timeout(5):
            await release.wait()
        return 7

    tasks = [asyncio.create_task(load_cache.get_or_load("shared", loader)) for _ in range(8)]
    async with asyncio.timeout(5):
        await entered.wait()
    release.set()
    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
    return {
        "hit": {
            "operations": hit_operations,
            "elapsed_ns": hit_elapsed,
            "ns_per_op": hit_elapsed / hit_operations,
            "throughput_ops_per_sec": hit_operations * 1_000_000_000 / hit_elapsed,
        },
        "coalesced_load": {
            "callers": len(tasks),
            "actual_loader_count": invocations,
            "results": results,
        },
    }


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _run(args: argparse.Namespace) -> dict[str, Any]:
    micro = _microbenchmarks(
        capacity=args.capacity,
        operations=args.operations,
        warmups=args.warmups,
        repetitions=args.repetitions,
    )
    hot = _fixed_worker_contention(distinct_keys=False)
    distinct = _fixed_worker_contention(distinct_keys=True)
    expiry_1k = _expiry_heavy(1_000, args.repetitions)
    expiry_10k = _expiry_heavy(10_000, args.repetitions)
    rebuild_1k = _rebuild_proxy(1_000)
    rebuild_10k = _rebuild_proxy(10_000)
    return {
        "schema_version": 1,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "git_sha": _git_sha(),
        },
        "parameters": {
            "capacity": args.capacity,
            "operations": args.operations,
            "warmups": args.warmups,
            "repetitions": args.repetitions,
        },
        "timing": micro,
        "coordination": _coordination_observations(),
        "fixed_worker_contention": {"hot_key": hot, "distinct_keys": distinct},
        "expiry_heavy": {"capacity_1000": expiry_1k, "capacity_10000": expiry_10k},
        "heap_rebuild_proxy": {"capacity_1000": rebuild_1k, "capacity_10000": rebuild_10k},
        "allocation": _allocation_phase(min(args.capacity, 10_000)),
        "rss": _rss_scenarios(args.capacity, args.operations),
        "async": asyncio.run(_async_scenarios(args.operations)),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity", type=int, default=10_000)
    parser.add_argument("--operations", type=int, default=100_000)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rss-child", choices=("hit", "overwrite"))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.capacity < 1 or args.operations < 1 or args.warmups < 0 or args.repetitions < 1:
        raise SystemExit(
            "capacity/operations/repetitions must be positive; warmups must be non-negative"
        )
    if args.rss_child is not None:
        _rss_child(args.rss_child, args.capacity, args.operations)
        return
    if args.output is None:
        raise SystemExit("--output is required")
    payload = _run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": _sha256(args.output)}))


if __name__ == "__main__":
    main()
