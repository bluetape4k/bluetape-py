from __future__ import annotations

import math
from importlib.metadata import version
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Span

type Scalar = str | bool | int | float
type Attributes = dict[str, Scalar]

PACKAGE_VERSION = version("bluetape-observability")
MAX_INT64 = 2**63 - 1

POLICY_TYPES = frozenset({"retry", "timeout", "circuit-breaker", "bulkhead"})
POLICY_EVENT_KINDS = frozenset(
    {
        "succeeded",
        "failed",
        "retry-scheduled",
        "timed-out",
        "circuit-transitioned",
        "admitted",
        "rejected",
    }
)
POLICY_OUTCOMES = frozenset({"success", "failure", "rejection"})
FAILURE_CATEGORIES = frozenset(
    {"none", "failure", "timeout", "retry-exhausted", "circuit-open", "bulkhead-rejected"}
)
CIRCUIT_STATES = frozenset({"closed", "open", "half-open"})
REDIS_MODES = frozenset({"sync", "async"})
REDIS_OPERATIONS = frozenset(
    {
        "create",
        "get",
        "set",
        "set-if-absent",
        "delete",
        "delete-if-value",
        "coordination-snapshot",
        "publish-if-value",
        "close",
    }
)
REDIS_OUTCOMES = frozenset({"success", "failure", "cancelled"})
REDIS_ERROR_CODES = frozenset(
    {"closed", "invalid-input", "connection", "timeout", "provider-failure", "invalid-response"}
)
COORDINATION_OPERATIONS = frozenset({"get-or-load"})
COORDINATION_OUTCOMES = frozenset(
    {"loaded", "result-reused", "lease-lost", "timeout", "failure", "cancelled"}
)
COORDINATION_ERROR_CODES = frozenset(
    {
        "attempts-exhausted",
        "polls-exhausted",
        "deadline-exceeded",
        "invalid-artifact",
        "provider-failure",
        "envelope-failure",
        "loader-failure",
    }
)


def default_meter() -> Meter:
    return metrics.get_meter("bluetape.observability", PACKAGE_VERSION)


def closed_value(value: object, allowed: frozenset[str]) -> str:
    raw = value.value
    if type(raw) is not str or raw not in allowed:
        raise ValueError("unsupported enum value")
    return raw


def optional_closed_value(value: object | None, allowed: frozenset[str]) -> str | None:
    return None if value is None else closed_value(value, allowed)


def bounded_int(value: object, *, minimum: int) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INT64:
        raise ValueError("integer outside supported range")
    return value


def optional_bounded_int(value: object | None, *, minimum: int) -> int | None:
    return None if value is None else bounded_int(value, minimum=minimum)


def optional_non_negative_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("unsupported number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError("unsupported number")
    return normalized


def exact_bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("unsupported boolean")
    return value


def recording_span() -> Span | None:
    try:
        span = trace.get_current_span()
    except Exception:
        return None
    try:
        return span if span.is_recording() else None
    except Exception:
        return None


def add_span_event(span: Span | None, name: str, attributes: Attributes) -> None:
    if span is None:
        return
    try:
        span.add_event(name, attributes)
    except Exception:
        return


def add_counter(counter: Counter, attributes: Attributes) -> None:
    try:
        counter.add(1, attributes)
    except Exception:
        return


def record_histogram(histogram: Histogram, value: float, attributes: Attributes) -> None:
    try:
        histogram.record(value, attributes)
    except Exception:
        return
