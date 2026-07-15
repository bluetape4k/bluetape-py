from __future__ import annotations

import logging
from pathlib import Path

import pytest
from _observability_support import RecordingMeter, coordination_event, policy_event, redis_event
from opentelemetry import baggage, context, trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

pytestmark = pytest.mark.observability_workspace


def test_log_context_baggage_and_trace_ids_remain_separate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from bluetape.logging import ContextLogFilter, log_context
    from bluetape.observability.redis import (
        OpenTelemetryRedisCoordinationObserver,
        OpenTelemetryRedisObserver,
    )
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    meters = [RecordingMeter(), RecordingMeter(), RecordingMeter()]
    adapters = [
        (OpenTelemetryPolicyObserver(meter=meters[0]), policy_event()),
        (OpenTelemetryRedisObserver(meter=meters[1]).on_event, redis_event()),
        (
            OpenTelemetryRedisCoordinationObserver(meter=meters[2]).on_event,
            coordination_event(),
        ),
    ]
    baggage_context = baggage.set_baggage("baggage-secret", "must-not-export")
    token = context.attach(baggage_context)
    span = NonRecordingSpan(
        SpanContext(
            trace_id=1,
            span_id=2,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    )
    logger = logging.getLogger("observability-separation")
    logger.addFilter(ContextLogFilter())
    try:
        with trace.use_span(span), log_context(tenant="blue", log_marker="log-only"):
            for callback, event in adapters:
                callback(event)
            with caplog.at_level(logging.INFO, logger=logger.name):
                logger.info("separated")
    finally:
        context.detach(token)
        logger.filters.clear()

    attributes = [
        values
        for meter in meters
        for instrument in meter.instruments
        for call in instrument.calls
        for values in (call[-1],)
    ]
    assert all("must-not-export" not in repr(values) for values in attributes)
    assert all("log-only" not in repr(values) for values in attributes)
    record = caplog.records[-1]
    assert record.tenant == "blue"
    assert not hasattr(record, "trace_id")
    assert not hasattr(record, "span_id")

    sources = "\n".join(
        path.read_text()
        for path in (Path(__file__).parents[1] / "src/bluetape/observability").glob("*.py")
    )
    assert "opentelemetry.baggage" not in sources
    assert "bluetape.logging" not in sources
