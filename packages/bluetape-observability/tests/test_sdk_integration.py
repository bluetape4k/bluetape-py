from __future__ import annotations

import asyncio
import threading
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib.metadata import version
from types import SimpleNamespace

import pytest
from _support import RecordingMeter
from bluetape.cache.redis import (
    RedisCoordinationEvent,
    RedisCoordinationOperation,
    RedisCoordinationOutcome,
    RedisEvent,
    RedisMode,
    RedisOperation,
    RedisOutcome,
)
from bluetape.resilience import (
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyType,
)

pytestmark = pytest.mark.observability_sdk


def policy_event(*, kind: EventKind = EventKind.SUCCEEDED) -> PolicyEvent:
    return PolicyEvent(
        policy_name="not-exported",
        policy_type=PolicyType.RETRY,
        kind=kind,
        outcome=PolicyOutcome.SUCCESS if kind is EventKind.SUCCEEDED else None,
        failure_category=FailureCategory.NONE,
        attempt=1,
        delay=None,
        timeout=None,
        state=None,
        previous_state=None,
        in_flight=None,
        waiters=None,
    )


def redis_event(*, mode: RedisMode = RedisMode.SYNC) -> RedisEvent:
    return RedisEvent(
        mode=mode,
        operation=RedisOperation.GET,
        outcome=RedisOutcome.SUCCESS,
        error_code=None,
        elapsed_ns=125_000_000,
    )


def coordination_event() -> RedisCoordinationEvent:
    return RedisCoordinationEvent(
        mode=RedisMode.ASYNC,
        operation=RedisCoordinationOperation.GET_OR_LOAD,
        outcome=RedisCoordinationOutcome.LOADED,
        error_code=None,
        attempts=2,
        polls=3,
        cleanup_failed=False,
        elapsed_ns=250_000_000,
    )


@contextmanager
def caller_owned_sdk() -> Iterator[SimpleNamespace]:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader], shutdown_on_exit=False)
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    state = SimpleNamespace(
        reader=reader,
        meter=meter_provider.get_meter("application"),
        exporter=exporter,
        tracer=tracer_provider.get_tracer("application"),
        shutdown_order=[],
    )
    try:
        yield state
    finally:
        tracer_provider.shutdown()
        state.shutdown_order.append("tracer")
        meter_provider.shutdown()
        state.shutdown_order.append("meter")


@pytest.fixture
def sdk_state() -> Iterator[SimpleNamespace]:
    with caller_owned_sdk() as state:
        yield state


def metrics_by_name(reader: object) -> dict[str, object]:
    data = reader.get_metrics_data()
    return {
        metric.name: metric
        for resource_metrics in data.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
    }


def only_point(metric: object) -> object:
    points = tuple(metric.data.data_points)
    assert len(points) == 1
    return points[0]


def test_sdk_records_exact_metrics_for_all_adapters(sdk_state: SimpleNamespace) -> None:
    from bluetape.observability.redis import (
        OpenTelemetryRedisCoordinationObserver,
        OpenTelemetryRedisObserver,
    )
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver
    from opentelemetry.sdk.metrics.export import Histogram, Sum

    OpenTelemetryPolicyObserver(meter=sdk_state.meter)(policy_event())
    OpenTelemetryRedisObserver(meter=sdk_state.meter).on_event(redis_event())
    OpenTelemetryRedisCoordinationObserver(meter=sdk_state.meter).on_event(coordination_event())

    metrics = metrics_by_name(sdk_state.reader)
    expected_descriptors = {
        "bluetape.resilience.policy.events": (
            "{event}",
            "Number of observed Bluetape resilience policy events.",
            Sum,
        ),
        "bluetape.redis.operations": (
            "{operation}",
            "Number of observed Bluetape Redis operations.",
            Sum,
        ),
        "bluetape.redis.operation.duration": (
            "s",
            "Duration of observed Bluetape Redis operations.",
            Histogram,
        ),
        "bluetape.redis.coordination.operations": (
            "{operation}",
            "Number of observed Bluetape Redis coordination operations.",
            Sum,
        ),
        "bluetape.redis.coordination.duration": (
            "s",
            "Duration of observed Bluetape Redis coordination operations.",
            Histogram,
        ),
    }
    assert set(metrics) == set(expected_descriptors)
    for name, (unit, description, data_type) in expected_descriptors.items():
        metric = metrics[name]
        assert (metric.unit, metric.description) == (unit, description)
        assert isinstance(metric.data, data_type)

    policy = metrics["bluetape.resilience.policy.events"]
    policy_point = only_point(policy)
    assert policy_point.value == 1
    assert dict(policy_point.attributes) == {
        "bluetape.resilience.policy.type": "retry",
        "bluetape.resilience.event.kind": "succeeded",
        "bluetape.resilience.failure.category": "none",
        "bluetape.resilience.outcome": "success",
    }

    provider_counter = only_point(metrics["bluetape.redis.operations"])
    provider_histogram = only_point(metrics["bluetape.redis.operation.duration"])
    assert provider_counter.value == 1
    assert (provider_histogram.count, provider_histogram.sum) == (1, 0.125)
    assert (
        dict(provider_counter.attributes)
        == dict(provider_histogram.attributes)
        == {
            "bluetape.redis.mode": "sync",
            "bluetape.redis.operation": "get",
            "bluetape.redis.outcome": "success",
        }
    )

    coordination_counter = only_point(metrics["bluetape.redis.coordination.operations"])
    coordination_histogram = only_point(metrics["bluetape.redis.coordination.duration"])
    assert coordination_counter.value == 1
    assert (coordination_histogram.count, coordination_histogram.sum) == (1, 0.25)
    assert (
        dict(coordination_counter.attributes)
        == dict(coordination_histogram.attributes)
        == {
            "bluetape.redis.mode": "async",
            "bluetape.redis.operation": "get-or-load",
            "bluetape.redis.outcome": "loaded",
            "bluetape.redis.coordination.cleanup_failed": False,
        }
    )
    assert all(
        forbidden not in attributes
        for metric in metrics.values()
        for point in metric.data.data_points
        for attributes in (point.attributes,)
        for forbidden in ("policy_name", "key", "value", "namespace", "elapsed_ns")
    )


def test_sdk_adds_events_only_to_current_span(sdk_state: SimpleNamespace) -> None:
    from bluetape.observability.redis import OpenTelemetryRedisObserver
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    policy = OpenTelemetryPolicyObserver(meter=sdk_state.meter)
    redis = OpenTelemetryRedisObserver(meter=sdk_state.meter)
    with sdk_state.tracer.start_as_current_span("outer"):
        policy(policy_event())
        with sdk_state.tracer.start_as_current_span("inner"):
            redis.on_event(redis_event())
        policy(policy_event(kind=EventKind.RETRY_SCHEDULED))
    with sdk_state.tracer.start_as_current_span("sequential"):
        redis.on_event(redis_event(mode=RedisMode.ASYNC))

    spans = {span.name: span for span in sdk_state.exporter.get_finished_spans()}
    assert set(spans) == {"outer", "inner", "sequential"}
    assert [event.name for event in spans["outer"].events] == [
        "bluetape.resilience.policy",
        "bluetape.resilience.policy",
    ]
    assert [event.name for event in spans["inner"].events] == ["bluetape.redis.operation"]
    assert [event.name for event in spans["sequential"].events] == ["bluetape.redis.operation"]


async def test_same_adapter_isolates_concurrent_coroutine_contexts(
    sdk_state: SimpleNamespace,
) -> None:
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    observer = OpenTelemetryPolicyObserver(meter=sdk_state.meter)
    ready = asyncio.Event()
    count = 0
    lock = asyncio.Lock()

    async def invoke(name: str, kind: EventKind) -> None:
        nonlocal count
        with sdk_state.tracer.start_as_current_span(name):
            async with lock:
                count += 1
                if count == 2:
                    ready.set()
            await ready.wait()
            observer(policy_event(kind=kind))

    await asyncio.gather(
        invoke("success-task", EventKind.SUCCEEDED),
        invoke("retry-task", EventKind.RETRY_SCHEDULED),
    )
    spans = {span.name: span for span in sdk_state.exporter.get_finished_spans()}
    assert {name: len(span.events) for name, span in spans.items()} == {
        "success-task": 1,
        "retry-task": 1,
    }
    assert (
        spans["success-task"].events[0].attributes["bluetape.resilience.event.kind"] == "succeeded"
    )
    assert (
        spans["retry-task"].events[0].attributes["bluetape.resilience.event.kind"]
        == "retry-scheduled"
    )


def test_thread_pool_metrics_do_not_claim_context_propagation() -> None:
    from bluetape.observability.redis import OpenTelemetryRedisObserver

    meter = RecordingMeter()
    observer = OpenTelemetryRedisObserver(meter=meter)
    prefix = "issue24-observability"
    before = {thread.ident for thread in threading.enumerate()}
    events = [
        redis_event(mode=RedisMode.SYNC if index % 2 == 0 else RedisMode.ASYNC)
        for index in range(64)
    ]
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix=prefix) as executor:
        list(executor.map(observer.on_event, events))
    assert not any(thread.name.startswith(prefix) for thread in threading.enumerate())
    assert before <= {thread.ident for thread in threading.enumerate()}

    counter_calls = meter.instruments[0].calls
    assert len(counter_calls) == 64
    assert Counter(attributes["bluetape.redis.mode"] for _, attributes in counter_calls) == {
        "sync": 32,
        "async": 32,
    }


def test_default_scope_never_mutates_global_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.observability import _recording
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver
    from opentelemetry import metrics, trace

    meter = RecordingMeter()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        _recording.metrics,
        "get_meter",
        lambda name, package_version: calls.append((name, package_version)) or meter,
    )
    monkeypatch.setattr(
        metrics,
        "set_meter_provider",
        lambda *_: (_ for _ in ()).throw(AssertionError("global meter mutation")),
    )
    monkeypatch.setattr(
        trace,
        "set_tracer_provider",
        lambda *_: (_ for _ in ()).throw(AssertionError("global tracer mutation")),
    )
    OpenTelemetryPolicyObserver()(policy_event())
    assert calls == [("bluetape.observability", version("bluetape-observability"))]


def test_application_teardown_runs_in_order_when_body_raises() -> None:
    captured = None
    with pytest.raises(RuntimeError, match="body"):
        with caller_owned_sdk() as state:
            captured = state
            raise RuntimeError("body")
    assert captured is not None
    assert captured.shutdown_order == ["tracer", "meter"]
