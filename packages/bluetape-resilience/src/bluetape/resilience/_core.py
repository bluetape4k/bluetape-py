"""Shared immutable contracts and validation for resilience policies."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class PolicyType(StrEnum):
    RETRY = "retry"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER = "circuit-breaker"
    BULKHEAD = "bulkhead"


class EventKind(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry-scheduled"
    TIMED_OUT = "timed-out"
    CIRCUIT_TRANSITIONED = "circuit-transitioned"
    ADMITTED = "admitted"
    REJECTED = "rejected"


class PolicyOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    REJECTION = "rejection"


class FailureCategory(StrEnum):
    NONE = "none"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RETRY_EXHAUSTED = "retry-exhausted"
    CIRCUIT_OPEN = "circuit-open"
    BULKHEAD_REJECTED = "bulkhead-rejected"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


@dataclass(frozen=True, slots=True)
class PolicyEvent:
    policy_name: str
    policy_type: PolicyType
    kind: EventKind
    outcome: PolicyOutcome | None
    failure_category: FailureCategory
    attempt: int | None
    delay: float | None
    timeout: float | None
    state: CircuitState | None
    previous_state: CircuitState | None
    in_flight: int | None
    waiters: int | None


@dataclass(frozen=True, slots=True)
class CircuitSnapshot:
    name: str
    state: CircuitState
    consecutive_failures: int
    recovery_successes: int
    half_open_in_flight: int


@dataclass(frozen=True, slots=True)
class BulkheadSnapshot:
    name: str
    max_concurrency: int
    in_flight: int
    waiters: int


class RetryExhaustedError(RuntimeError):
    def __init__(self, name: str, attempts: int) -> None:
        self.name = name
        self.attempts = attempts
        super().__init__(f"retry policy {name!r} exhausted after {attempts} attempts")


class PolicyTimeoutError(TimeoutError):
    def __init__(self, name: str, timeout: float) -> None:
        self.name = name
        self.timeout = timeout
        super().__init__(f"timeout policy {name!r} expired after {timeout} seconds")


class CircuitOpenError(RuntimeError):
    def __init__(self, name: str, state: CircuitState) -> None:
        self.name = name
        self.state = state
        super().__init__(f"circuit breaker {name!r} rejected call in {state.value} state")


class BulkheadRejectedError(RuntimeError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"bulkhead {name!r} rejected call")


def _validate_name(value: object, parameter: str = "name") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{parameter} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{parameter} must be non-blank without surrounding whitespace")
    return value


def _positive_int(value: object, parameter: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{parameter} must be an integer")
    if value < 1:
        raise ValueError(f"{parameter} must be greater than 0")
    return value


def _finite_non_negative(value: object, parameter: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{parameter} must be a finite non-negative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{parameter} must be a finite non-negative number")
    return result


def _finite_positive(value: object, parameter: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{parameter} must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{parameter} must be a finite positive number")
    return result


def _validate_callable[T: Callable[..., object]](value: T, parameter: str) -> T:
    if not callable(value):
        raise TypeError(f"{parameter} must be callable")
    return value


def _failure_category(error: BaseException) -> FailureCategory:
    if isinstance(error, PolicyTimeoutError):
        return FailureCategory.TIMEOUT
    if isinstance(error, RetryExhaustedError):
        return FailureCategory.RETRY_EXHAUSTED
    if isinstance(error, CircuitOpenError):
        return FailureCategory.CIRCUIT_OPEN
    if isinstance(error, BulkheadRejectedError):
        return FailureCategory.BULKHEAD_REJECTED
    return FailureCategory.FAILURE


def _emit(observer: Callable[[PolicyEvent], None] | None, event: PolicyEvent) -> None:
    if observer is not None:
        observer(event)
