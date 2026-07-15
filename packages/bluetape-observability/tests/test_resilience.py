from __future__ import annotations

import pytest
from _observability_support import (
    EnumValue,
    RecordingCounter,
    RecordingMeter,
    RecordingSpan,
    policy_event,
)
from bluetape.resilience import (
    CircuitState,
    EventKind,
    FailureCategory,
    PolicyOutcome,
    PolicyType,
    Retry,
    RetryExhaustedError,
)


def observer_with_span(monkeypatch: pytest.MonkeyPatch, span: RecordingSpan | None = None):
    from bluetape.observability import _recording
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    selected_span = span or RecordingSpan()
    monkeypatch.setattr(_recording.trace, "get_current_span", lambda: selected_span)
    meter = RecordingMeter()
    return OpenTelemetryPolicyObserver(meter=meter), meter, selected_span


def test_policy_maps_exact_metric_and_span_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.observability import _recording

    assert _recording.POLICY_TYPES == frozenset(item.value for item in PolicyType)
    assert _recording.POLICY_EVENT_KINDS == frozenset(item.value for item in EventKind)
    assert _recording.POLICY_OUTCOMES == frozenset(item.value for item in PolicyOutcome)
    assert _recording.FAILURE_CATEGORIES == frozenset(item.value for item in FailureCategory)
    assert _recording.CIRCUIT_STATES == frozenset(item.value for item in CircuitState)

    observer, meter, span = observer_with_span(monkeypatch)
    observer(
        policy_event(
            policy_type=EnumValue("circuit-breaker"),
            kind=EnumValue("circuit-transitioned"),
            outcome=EnumValue("failure"),
            failure_category=EnumValue("failure"),
            attempt=2,
            delay=0.25,
            timeout=1,
            state=EnumValue("open"),
            previous_state=EnumValue("closed"),
            in_flight=3,
            waiters=4,
        )
    )
    metric = {
        "bluetape.resilience.policy.type": "circuit-breaker",
        "bluetape.resilience.event.kind": "circuit-transitioned",
        "bluetape.resilience.failure.category": "failure",
        "bluetape.resilience.outcome": "failure",
    }
    assert meter.instruments[0].calls == [(1, metric)]
    assert span.events == [
        (
            "bluetape.resilience.policy",
            metric
            | {
                "bluetape.resilience.attempt": 2,
                "bluetape.resilience.delay": 0.25,
                "bluetape.resilience.timeout": 1.0,
                "bluetape.resilience.state": "open",
                "bluetape.resilience.previous_state": "closed",
                "bluetape.resilience.in_flight": 3,
                "bluetape.resilience.waiters": 4,
            },
        )
    ]

    observer(policy_event(outcome=None, attempt=None))
    assert "bluetape.resilience.outcome" not in meter.instruments[0].calls[-1][1]
    assert "bluetape.resilience.attempt" not in span.events[-1][1]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_type", EnumValue("unknown")),
        ("kind", EnumValue("unknown")),
        ("outcome", EnumValue("unknown")),
        ("failure_category", EnumValue("unknown")),
        ("attempt", 0),
        ("delay", -1),
        ("timeout", float("inf")),
        ("state", EnumValue("unknown")),
        ("previous_state", EnumValue("unknown")),
        ("in_flight", -1),
        ("waiters", True),
    ],
)
def test_policy_rejects_invalid_consumed_fields_before_emission(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    observer, meter, span = observer_with_span(monkeypatch)
    assert observer(policy_event(**{field: value})) is None
    assert meter.instruments[0].calls == []
    assert span.events == []


def test_policy_propagates_process_control_from_consumed_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ProcessControlEvent:
        kind = EventKind.SUCCEEDED
        outcome = PolicyOutcome.SUCCESS
        failure_category = FailureCategory.NONE
        attempt = 1
        delay = timeout = state = previous_state = in_flight = waiters = None

        def __init__(self, failure: BaseException) -> None:
            self.failure = failure

        @property
        def policy_type(self) -> PolicyType:
            raise self.failure

    for failure in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
        observer, meter, span = observer_with_span(monkeypatch)
        with pytest.raises(type(failure)):
            observer(ProcessControlEvent(failure))
        assert meter.instruments[0].calls == []
        assert span.events == []


def test_policy_never_reads_forbidden_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    observer, meter, span = observer_with_span(monkeypatch)

    class PrivateEvent:
        policy_type = EnumValue("retry")
        kind = EnumValue("succeeded")
        outcome = EnumValue("success")
        failure_category = EnumValue("none")
        attempt = 1
        delay = timeout = state = previous_state = in_flight = waiters = None

        @property
        def policy_name(self) -> str:
            raise AssertionError("policy_name was read")

        def __repr__(self) -> str:
            raise AssertionError("repr was read")

    observer(PrivateEvent())
    assert len(meter.instruments[0].calls) == 1
    assert len(span.events) == 1
    assert "must-never-be-read" not in repr((meter.instruments[0].calls, span.events))


def test_policy_runtime_channels_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.observability import _recording
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    meter = RecordingMeter()
    observer = OpenTelemetryPolicyObserver(meter=meter)
    counter = meter.instruments[0]
    assert isinstance(counter, RecordingCounter)

    monkeypatch.setattr(
        _recording.trace,
        "get_current_span",
        lambda: (_ for _ in ()).throw(RuntimeError("trace")),
    )
    observer(policy_event())
    assert len(counter.calls) == 1

    monkeypatch.setattr(
        _recording.trace,
        "get_current_span",
        lambda: RecordingSpan(add_failure=RuntimeError("span")),
    )
    observer(policy_event())
    assert len(counter.calls) == 2

    counter.failure = RuntimeError("counter")
    observer(policy_event())
    counter.failure = None
    observer(policy_event())
    assert len(counter.calls) == 3

    for failure in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
        counter.failure = failure
        with pytest.raises(type(failure)):
            observer(policy_event())
    counter.failure = None


def test_policy_actual_retry_behavior_is_preserved() -> None:
    from bluetape.observability.resilience import OpenTelemetryPolicyObserver

    meter = RecordingMeter()
    observer = OpenTelemetryPolicyObserver(meter=meter)
    retry = Retry(name="observed", max_attempts=2, observer=observer, sleeper=lambda _: None)
    attempts = 0

    def eventually() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("retry")
        return "ok"

    assert retry.call(eventually) == "ok"
    sentinel = ValueError("sentinel")

    def always_fails() -> None:
        raise sentinel

    with pytest.raises(RetryExhaustedError) as raised:
        retry.call(always_fails)
    assert raised.value.__cause__ is sentinel
    assert len(meter.instruments[0].calls) == 4
