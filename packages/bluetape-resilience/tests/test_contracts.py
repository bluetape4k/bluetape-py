"""Shared public contract tests for bluetape-resilience."""

import importlib.util
import math
from dataclasses import FrozenInstanceError, fields

import bluetape.resilience as resilience
import pytest
from bluetape.resilience import _core

SHARED_EXPORTS = [
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


def test_shared_public_exports_are_ordered() -> None:
    assert resilience.__all__ == SHARED_EXPORTS
    assert not hasattr(resilience, "Timeout")
    assert importlib.util.find_spec("bluetape") is not None


def test_public_enums_have_fixed_string_values() -> None:
    assert [item.value for item in resilience.PolicyType] == [
        "retry",
        "timeout",
        "circuit-breaker",
        "bulkhead",
    ]
    assert [item.value for item in resilience.EventKind] == [
        "succeeded",
        "failed",
        "retry-scheduled",
        "timed-out",
        "circuit-transitioned",
        "admitted",
        "rejected",
    ]
    assert [item.value for item in resilience.PolicyOutcome] == [
        "success",
        "failure",
        "rejection",
    ]
    assert [item.value for item in resilience.FailureCategory] == [
        "none",
        "failure",
        "timeout",
        "retry-exhausted",
        "circuit-open",
        "bulkhead-rejected",
    ]
    assert [item.value for item in resilience.CircuitState] == [
        "closed",
        "open",
        "half-open",
    ]


def test_public_values_are_frozen_slotted_and_ordered() -> None:
    event = resilience.PolicyEvent(
        "retry",
        resilience.PolicyType.RETRY,
        resilience.EventKind.SUCCEEDED,
        resilience.PolicyOutcome.SUCCESS,
        resilience.FailureCategory.NONE,
        1,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    assert [field.name for field in fields(event)] == [
        "policy_name",
        "policy_type",
        "kind",
        "outcome",
        "failure_category",
        "attempt",
        "delay",
        "timeout",
        "state",
        "previous_state",
        "in_flight",
        "waiters",
    ]
    assert not hasattr(event, "__dict__")
    with pytest.raises(FrozenInstanceError):
        event.attempt = 2

    circuit = resilience.CircuitSnapshot("breaker", resilience.CircuitState.CLOSED, 0, 0, 0)
    bulkhead = resilience.BulkheadSnapshot("bulkhead", 2, 0, 0)
    assert [field.name for field in fields(circuit)] == [
        "name",
        "state",
        "consecutive_failures",
        "recovery_successes",
        "half_open_in_flight",
    ]
    assert [field.name for field in fields(bulkhead)] == [
        "name",
        "max_concurrency",
        "in_flight",
        "waiters",
    ]
    assert not hasattr(circuit, "__dict__")
    assert not hasattr(bulkhead, "__dict__")


def test_domain_error_hierarchy_and_safe_messages() -> None:
    exhausted = resilience.RetryExhaustedError("retry", 3)
    timeout = resilience.PolicyTimeoutError("timeout", 0.5)
    circuit = resilience.CircuitOpenError("breaker", resilience.CircuitState.OPEN)
    bulkhead = resilience.BulkheadRejectedError("bulkhead")

    assert isinstance(exhausted, RuntimeError)
    assert isinstance(timeout, TimeoutError)
    assert isinstance(circuit, RuntimeError)
    assert isinstance(bulkhead, RuntimeError)
    assert exhausted.name == "retry" and exhausted.attempts == 3
    assert timeout.name == "timeout" and timeout.timeout == 0.5
    assert circuit.name == "breaker" and circuit.state is resilience.CircuitState.OPEN
    assert bulkhead.name == "bulkhead"
    messages = " ".join(map(str, [exhausted, timeout, circuit, bulkhead]))
    assert "secret-operation-error" not in messages


@pytest.mark.parametrize("value", ["", " retry", "retry ", 1, None])
def test_name_validator_rejects_invalid_values(value: object) -> None:
    expected = TypeError if not isinstance(value, str) else ValueError
    with pytest.raises(expected):
        _core._validate_name(value)


@pytest.mark.parametrize("value", [True, 1.0, "1", None])
def test_positive_integer_validator_rejects_wrong_types(value: object) -> None:
    with pytest.raises(TypeError):
        _core._positive_int(value, "count")


@pytest.mark.parametrize("value", [0, -1])
def test_positive_integer_validator_rejects_non_positive_values(value: int) -> None:
    with pytest.raises(ValueError):
        _core._positive_int(value, "count")


@pytest.mark.parametrize("value", [True, "1", None])
def test_duration_validators_reject_wrong_types(value: object) -> None:
    with pytest.raises(TypeError):
        _core._finite_non_negative(value, "duration")
    with pytest.raises(TypeError):
        _core._finite_positive(value, "duration")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1.0])
def test_non_negative_duration_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        _core._finite_non_negative(value, "duration")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1.0, 0.0])
def test_positive_duration_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        _core._finite_positive(value, "duration")


def test_callable_validator_does_not_invoke_callback() -> None:
    invoked = False

    def callback() -> None:
        nonlocal invoked
        invoked = True

    assert _core._validate_callable(callback, "callback") is callback
    assert not invoked
    with pytest.raises(TypeError):
        _core._validate_callable(object(), "callback")


def test_failure_category_maps_only_public_domain_errors() -> None:
    assert _core._failure_category(ValueError()) is resilience.FailureCategory.FAILURE
    assert (
        _core._failure_category(resilience.PolicyTimeoutError("timeout", 1))
        is resilience.FailureCategory.TIMEOUT
    )
    assert (
        _core._failure_category(resilience.RetryExhaustedError("retry", 2))
        is resilience.FailureCategory.RETRY_EXHAUSTED
    )
    assert (
        _core._failure_category(
            resilience.CircuitOpenError("breaker", resilience.CircuitState.OPEN)
        )
        is resilience.FailureCategory.CIRCUIT_OPEN
    )
    assert (
        _core._failure_category(resilience.BulkheadRejectedError("bulkhead"))
        is resilience.FailureCategory.BULKHEAD_REJECTED
    )
