"""Sync and async resilience policies for bluetape-py."""

from pkgutil import extend_path

from bluetape.resilience._backoff import Backoff, constant_backoff, exponential_backoff
from bluetape.resilience._circuit import AsyncCircuitBreaker, CircuitBreaker
from bluetape.resilience._core import (
    BulkheadRejectedError,
    BulkheadSnapshot,
    CircuitOpenError,
    CircuitSnapshot,
    CircuitState,
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyTimeoutError,
    PolicyType,
    RetryExhaustedError,
)
from bluetape.resilience._retry import AsyncRetry, Retry
from bluetape.resilience._timeout import AsyncTimeout

__path__ = extend_path(__path__, __name__)

__all__ = [  # noqa: RUF022 - public order is part of the contract
    "Retry",
    "AsyncRetry",
    "CircuitBreaker",
    "AsyncCircuitBreaker",
    "AsyncTimeout",
    "Backoff",
    "constant_backoff",
    "exponential_backoff",
    "PolicyEvent",
    "PolicyType",
    "EventKind",
    "PolicyOutcome",
    "FailureCategory",
    "CircuitState",
    "CircuitSnapshot",
    "BulkheadSnapshot",
    "RetryExhaustedError",
    "PolicyTimeoutError",
    "CircuitOpenError",
    "BulkheadRejectedError",
]
