"""Sync and async resilience policies for bluetape-py."""

from pkgutil import extend_path

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

__path__ = extend_path(__path__, __name__)

__all__ = [  # noqa: RUF022 - public order is part of the contract
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
