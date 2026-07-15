from __future__ import annotations

from typing import TYPE_CHECKING

from bluetape.observability._recording import (
    CIRCUIT_STATES,
    FAILURE_CATEGORIES,
    POLICY_EVENT_KINDS,
    POLICY_OUTCOMES,
    POLICY_TYPES,
    Attributes,
    Scalar,
    add_counter,
    add_span_event,
    closed_value,
    default_meter,
    optional_bounded_int,
    optional_closed_value,
    optional_non_negative_float,
    recording_span,
)

if TYPE_CHECKING:
    from bluetape.resilience import PolicyEvent
    from opentelemetry.metrics import Meter

__all__ = ["OpenTelemetryPolicyObserver"]


def _normalize_policy(event: object) -> tuple[Attributes, tuple[tuple[str, Scalar | None], ...]]:
    policy_type = closed_value(event.policy_type, POLICY_TYPES)
    kind = closed_value(event.kind, POLICY_EVENT_KINDS)
    outcome = optional_closed_value(event.outcome, POLICY_OUTCOMES)
    failure = closed_value(event.failure_category, FAILURE_CATEGORIES)
    attempt = optional_bounded_int(event.attempt, minimum=1)
    delay = optional_non_negative_float(event.delay)
    timeout = optional_non_negative_float(event.timeout)
    state = optional_closed_value(event.state, CIRCUIT_STATES)
    previous_state = optional_closed_value(event.previous_state, CIRCUIT_STATES)
    in_flight = optional_bounded_int(event.in_flight, minimum=0)
    waiters = optional_bounded_int(event.waiters, minimum=0)

    metric: Attributes = {
        "bluetape.resilience.policy.type": policy_type,
        "bluetape.resilience.event.kind": kind,
        "bluetape.resilience.failure.category": failure,
    }
    if outcome is not None:
        metric["bluetape.resilience.outcome"] = outcome
    details = (
        ("bluetape.resilience.attempt", attempt),
        ("bluetape.resilience.delay", delay),
        ("bluetape.resilience.timeout", timeout),
        ("bluetape.resilience.state", state),
        ("bluetape.resilience.previous_state", previous_state),
        ("bluetape.resilience.in_flight", in_flight),
        ("bluetape.resilience.waiters", waiters),
    )
    return metric, details


class OpenTelemetryPolicyObserver:
    __slots__ = ("_counter",)

    def __init__(self, *, meter: Meter | None = None) -> None:
        selected = default_meter() if meter is None else meter
        self._counter = selected.create_counter(
            "bluetape.resilience.policy.events",
            unit="{event}",
            description="Number of observed Bluetape resilience policy events.",
        )

    def __call__(self, event: PolicyEvent) -> None:
        try:
            metric, details = _normalize_policy(event)
        except Exception:
            return
        span = recording_span()
        if span is not None:
            span_attributes = dict(metric)
            for key, value in details:
                if value is not None:
                    span_attributes[key] = value
            add_span_event(span, "bluetape.resilience.policy", span_attributes)
        add_counter(self._counter, metric)
