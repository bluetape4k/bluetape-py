"""Integrated low-cardinality observability tests."""

from dataclasses import fields

import pytest
from bluetape.resilience import Bulkhead, EventKind, Retry, RetryExhaustedError


def test_events_exclude_caller_values_raw_errors_and_dynamic_fields() -> None:
    secret = "caller-secret-4f91"
    events = []
    policy = Retry(name="stable-policy", max_attempts=1, observer=events.append)

    def operation(value: str) -> None:
        raise ValueError(value)

    with pytest.raises(RetryExhaustedError):
        policy.call(operation, secret)
    assert events
    assert secret not in repr(events)
    assert [field.name for field in fields(events[0])] == [
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


def test_terminal_observer_sees_reconciled_bulkhead_and_stops_path() -> None:
    bulkhead: Bulkhead
    observed_in_flight = -1
    observer_error = LookupError("observer")

    def observer(event: object) -> None:
        nonlocal observed_in_flight
        if getattr(event, "kind", None) is EventKind.SUCCEEDED:
            observed_in_flight = bulkhead.snapshot().in_flight
            raise observer_error

    bulkhead = Bulkhead(name="bulkhead", max_concurrency=1, observer=observer)
    with pytest.raises(LookupError) as captured:
        bulkhead.call(lambda: "ok")
    assert captured.value is observer_error
    assert observed_in_flight == 0
    assert bulkhead.snapshot().in_flight == 0
