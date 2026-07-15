from __future__ import annotations

import ast
import asyncio
import gc
import json
import subprocess
import sys
import threading
import tracemalloc
import weakref
from collections.abc import Callable
from pathlib import Path

import pytest
from _support import coordination_event, policy_event, redis_event

PACKAGE_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src/bluetape/observability"
BENCHMARK = PACKAGE_ROOT / "benchmarks/observer_overhead.py"


class NoopInstrument:
    def add(self, amount: int, attributes: dict[str, object]) -> None:
        return

    def record(self, amount: float, attributes: dict[str, object]) -> None:
        return


class NoopMeter:
    def create_counter(self, name: str, unit: str = "", description: str = "") -> NoopInstrument:
        return NoopInstrument()

    def create_histogram(self, name: str, unit: str = "", description: str = "") -> NoopInstrument:
        return NoopInstrument()


def adapter_cases() -> list[tuple[object, Callable[[object], None], Callable[[], object]]]:
    from bluetape.observability.redis import (
        OpenTelemetryRedisCoordinationObserver,
        OpenTelemetryRedisObserver,
    )
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    meter = NoopMeter()
    policy = OpenTelemetryPolicyObserver(meter=meter)
    redis = OpenTelemetryRedisObserver(meter=meter)
    coordination = OpenTelemetryRedisCoordinationObserver(meter=meter)
    return [
        (policy, policy, policy_event),
        (redis, redis.on_event, redis_event),
        (coordination, coordination.on_event, coordination_event),
    ]


@pytest.mark.parametrize("case_index", range(3))
def test_each_adapter_releases_event_reference(case_index: int) -> None:
    adapter, callback, factory = adapter_cases()[case_index]
    values = vars(factory())

    class WeakEvent:
        pass

    event = WeakEvent()
    event.__dict__.update(values)
    reference = weakref.ref(event)
    callback(event)
    del event
    gc.collect()

    assert reference() is None
    assert set(adapter.__slots__) <= {"_counter", "_histogram"}


def retained_size(callback: Callable[[object], None], event: object, calls: int) -> int:
    for _ in range(100):
        callback(event)
    gc.collect()
    before = tracemalloc.take_snapshot()
    for _ in range(calls):
        callback(event)
    gc.collect()
    after = tracemalloc.take_snapshot()
    return sum(stat.size_diff for stat in after.compare_to(before, "lineno") if stat.size_diff > 0)


@pytest.mark.parametrize("case_index", range(3))
def test_each_adapter_retains_at_most_64_kib(case_index: int) -> None:
    _, callback, factory = adapter_cases()[case_index]
    event = factory()
    tracemalloc.start()
    try:
        baseline = retained_size(lambda _: None, event, 100_000)
        adapter = retained_size(callback, event, 100_000)
    finally:
        tracemalloc.stop()
    assert max(0, adapter - baseline) <= 64 * 1024


def test_package_owns_no_runtime_resource() -> None:
    forbidden_imports = {"asyncio", "concurrent", "queue", "threading", "weakref"}
    forbidden_methods = {"close", "flush", "shutdown"}
    for path in SOURCE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        assert not imports & forbidden_imports
        assert not methods & forbidden_methods

    threads_before = {thread.ident for thread in threading.enumerate()}
    try:
        tasks_before = set(asyncio.all_tasks())
    except RuntimeError:
        tasks_before = set()
    for _, callback, factory in adapter_cases():
        for _ in range(1_000):
            callback(factory())
    assert threads_before == {thread.ident for thread in threading.enumerate()}
    try:
        assert tasks_before == set(asyncio.all_tasks())
    except RuntimeError:
        assert tasks_before == set()


@pytest.mark.parametrize("mode", ["api", "sdk"])
def test_benchmark_modes_repeat_without_resource_leak(mode: str) -> None:
    outputs = []
    for _ in range(2):
        completed = subprocess.run(
            [sys.executable, str(BENCHMARK), "--mode", mode, "--runs", "1", "--calls", "1000"],
            cwd=PACKAGE_ROOT.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(json.loads(completed.stdout))
    for output in outputs:
        assert output["mode"] == mode
        assert output["runs"] == 1
        assert output["calls"] == 1000
        assert set(output["adapters"]) == {"policy", "redis", "redis-coordination"}
        assert output["resources"]["threads_after"] == output["resources"]["threads_before"]
        assert all(len(samples) == 1 for samples in output["adapters"].values())
