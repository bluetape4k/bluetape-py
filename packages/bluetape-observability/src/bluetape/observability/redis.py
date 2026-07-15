from __future__ import annotations

from typing import TYPE_CHECKING

from bluetape.observability._recording import (
    COORDINATION_ERROR_CODES,
    COORDINATION_OPERATIONS,
    COORDINATION_OUTCOMES,
    REDIS_ERROR_CODES,
    REDIS_MODES,
    REDIS_OPERATIONS,
    REDIS_OUTCOMES,
    Attributes,
    add_counter,
    add_span_event,
    bounded_int,
    closed_value,
    default_meter,
    exact_bool,
    optional_closed_value,
    record_histogram,
    recording_span,
)

if TYPE_CHECKING:
    from bluetape.cache.redis import RedisCoordinationEvent, RedisEvent
    from opentelemetry.metrics import Meter

__all__ = [  # noqa: RUF022 - public order is an approved compatibility contract
    "OpenTelemetryRedisObserver",
    "OpenTelemetryRedisCoordinationObserver",
]


def _common(
    event: object,
    *,
    operations: frozenset[str],
    outcomes: frozenset[str],
    errors: frozenset[str],
) -> Attributes:
    attributes: Attributes = {
        "bluetape.redis.mode": closed_value(event.mode, REDIS_MODES),
        "bluetape.redis.operation": closed_value(event.operation, operations),
        "bluetape.redis.outcome": closed_value(event.outcome, outcomes),
    }
    error = optional_closed_value(event.error_code, errors)
    if error is not None:
        attributes["bluetape.redis.error.code"] = error
    return attributes


def _normalize_provider(event: object) -> tuple[Attributes, int]:
    metric = _common(
        event, operations=REDIS_OPERATIONS, outcomes=REDIS_OUTCOMES, errors=REDIS_ERROR_CODES
    )
    elapsed_ns = bounded_int(event.elapsed_ns, minimum=0)
    return metric, elapsed_ns


def _normalize_coordination(event: object) -> tuple[Attributes, int, int, int]:
    metric = _common(
        event,
        operations=COORDINATION_OPERATIONS,
        outcomes=COORDINATION_OUTCOMES,
        errors=COORDINATION_ERROR_CODES,
    )
    attempts = bounded_int(event.attempts, minimum=0)
    polls = bounded_int(event.polls, minimum=0)
    cleanup_failed = exact_bool(event.cleanup_failed)
    elapsed_ns = bounded_int(event.elapsed_ns, minimum=0)
    metric["bluetape.redis.coordination.cleanup_failed"] = cleanup_failed
    return metric, attempts, polls, elapsed_ns


class OpenTelemetryRedisObserver:
    __slots__ = ("_counter", "_histogram")

    def __init__(self, *, meter: Meter | None = None) -> None:
        selected = default_meter() if meter is None else meter
        self._counter = selected.create_counter(
            "bluetape.redis.operations",
            unit="{operation}",
            description="Number of observed Bluetape Redis operations.",
        )
        self._histogram = selected.create_histogram(
            "bluetape.redis.operation.duration",
            unit="s",
            description="Duration of observed Bluetape Redis operations.",
        )

    def on_event(self, event: RedisEvent) -> None:
        try:
            metric, elapsed_ns = _normalize_provider(event)
        except Exception:
            return
        span = recording_span()
        if span is not None:
            span_attributes = dict(metric)
            span_attributes["bluetape.redis.elapsed_ns"] = elapsed_ns
            add_span_event(span, "bluetape.redis.operation", span_attributes)
        add_counter(self._counter, metric)
        record_histogram(self._histogram, elapsed_ns / 1_000_000_000, metric)


class OpenTelemetryRedisCoordinationObserver:
    __slots__ = ("_counter", "_histogram")

    def __init__(self, *, meter: Meter | None = None) -> None:
        selected = default_meter() if meter is None else meter
        self._counter = selected.create_counter(
            "bluetape.redis.coordination.operations",
            unit="{operation}",
            description="Number of observed Bluetape Redis coordination operations.",
        )
        self._histogram = selected.create_histogram(
            "bluetape.redis.coordination.duration",
            unit="s",
            description="Duration of observed Bluetape Redis coordination operations.",
        )

    def on_event(self, event: RedisCoordinationEvent) -> None:
        try:
            metric, attempts, polls, elapsed_ns = _normalize_coordination(event)
        except Exception:
            return
        span = recording_span()
        if span is not None:
            span_attributes = dict(metric)
            span_attributes["bluetape.redis.coordination.attempts"] = attempts
            span_attributes["bluetape.redis.coordination.polls"] = polls
            span_attributes["bluetape.redis.elapsed_ns"] = elapsed_ns
            add_span_event(span, "bluetape.redis.coordination", span_attributes)
        add_counter(self._counter, metric)
        record_histogram(self._histogram, elapsed_ns / 1_000_000_000, metric)
