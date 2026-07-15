from __future__ import annotations

import argparse
import gc
import json
import math
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import perf_counter_ns
from types import SimpleNamespace

from bluetape.cache.redis import (
    RedisCoordinationEvent,
    RedisCoordinationOperation,
    RedisCoordinationOutcome,
    RedisEvent,
    RedisMode,
    RedisOperation,
    RedisOutcome,
)
from bluetape.observability.redis import (
    OpenTelemetryRedisCoordinationObserver,
    OpenTelemetryRedisObserver,
)
from bluetape.observability.resilience import OpenTelemetryPolicyObserver
from bluetape.resilience import (
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyType,
)

type Callback = Callable[[object], None]


def events() -> dict[str, object]:
    return {
        "policy": PolicyEvent(
            policy_name="benchmark",
            policy_type=PolicyType.RETRY,
            kind=EventKind.SUCCEEDED,
            outcome=PolicyOutcome.SUCCESS,
            failure_category=FailureCategory.NONE,
            attempt=1,
            delay=None,
            timeout=None,
            state=None,
            previous_state=None,
            in_flight=None,
            waiters=None,
        ),
        "redis": RedisEvent(
            mode=RedisMode.SYNC,
            operation=RedisOperation.GET,
            outcome=RedisOutcome.SUCCESS,
            error_code=None,
            elapsed_ns=125_000,
        ),
        "redis-coordination": RedisCoordinationEvent(
            mode=RedisMode.ASYNC,
            operation=RedisCoordinationOperation.GET_OR_LOAD,
            outcome=RedisCoordinationOutcome.LOADED,
            error_code=None,
            attempts=1,
            polls=0,
            cleanup_failed=False,
            elapsed_ns=250_000,
        ),
    }


def adapter(name: str, meter: object | None = None) -> Callback:
    if name == "policy":
        observer = OpenTelemetryPolicyObserver(meter=meter)
        return observer
    if name == "redis":
        observer = OpenTelemetryRedisObserver(meter=meter)
        return observer.on_event
    observer = OpenTelemetryRedisCoordinationObserver(meter=meter)
    return observer.on_event


def quantile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def measure(callback: Callback, event: object, calls: int) -> dict[str, int]:
    for _ in range(min(1_000, calls)):
        callback(event)
    gc.collect()
    samples: list[int] = []
    for _ in range(calls):
        started = perf_counter_ns()
        callback(event)
        samples.append(perf_counter_ns() - started)
    return {"median_ns": quantile(samples, 0.5), "p95_ns": quantile(samples, 0.95)}


def incremental(adapter_sample: dict[str, int], baseline: dict[str, int]) -> dict[str, int]:
    return {key: max(0, adapter_sample[key] - baseline[key]) for key in ("median_ns", "p95_ns")}


@contextmanager
def sdk_fixture(name: str) -> Iterator[SimpleNamespace]:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.trace import SpanLimits, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader], shutdown_on_exit=False)
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(
        shutdown_on_exit=False,
        span_limits=SpanLimits(max_events=128),
    )
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = tracer_provider.get_tracer("benchmark")
    shutdown_order: list[str] = []
    try:
        with tracer.start_as_current_span(f"benchmark-{name}"):
            yield SimpleNamespace(
                callback=adapter(name, meter_provider.get_meter("benchmark")),
                event=events()[name],
                exporter=exporter,
                shutdown_order=shutdown_order,
            )
    finally:
        tracer_provider.shutdown()
        shutdown_order.append("tracer")
        meter_provider.shutdown()
        shutdown_order.append("meter")


def api_sample(name: str, calls: int) -> dict[str, object]:
    event = events()[name]
    baseline = measure(lambda _: None, event, calls)
    observed = measure(adapter(name), event, calls)
    return {
        "baseline": baseline,
        "adapter": observed,
        "incremental": incremental(observed, baseline),
        "exported_events": 0,
        "shutdown_order": [],
    }


def sdk_sample(name: str, calls: int) -> dict[str, object]:
    with sdk_fixture(name) as state:
        baseline = measure(lambda _: None, state.event, calls)
        observed = measure(state.callback, state.event, calls)
    exported = state.exporter.get_finished_spans()
    event_count = sum(len(span.events) for span in exported)
    return {
        "baseline": baseline,
        "adapter": observed,
        "incremental": incremental(observed, baseline),
        "exported_events": event_count,
        "span_event_limit": 128,
        "shutdown_order": state.shutdown_order,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("api", "sdk"), required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--calls", type=int, default=100_000)
    args = parser.parse_args()
    if args.runs < 1 or args.calls < 1:
        parser.error("runs and calls must be positive")

    def thread_ids() -> list[int]:
        return sorted(thread.ident for thread in threading.enumerate() if thread.ident is not None)

    before = thread_ids()
    sample = api_sample if args.mode == "api" else sdk_sample
    results = {
        name: [sample(name, args.calls) for _ in range(args.runs)]
        for name in ("policy", "redis", "redis-coordination")
    }
    gc.collect()
    output = {
        "schema_version": 1,
        "mode": args.mode,
        "runs": args.runs,
        "calls": args.calls,
        "adapters": results,
        "resources": {
            "threads_before": before,
            "threads_after": thread_ids(),
            "owned_tasks_before": 0,
            "owned_tasks_after": 0,
        },
    }
    print(json.dumps(output, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
