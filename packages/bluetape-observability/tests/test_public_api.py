from __future__ import annotations

import importlib
import inspect

import pytest
from _support import RecordingMeter


def assert_keyword_only_meter(public_class: type[object]) -> None:
    signature = inspect.signature(public_class)
    assert list(signature.parameters) == ["meter"]
    meter = signature.parameters["meter"]
    assert meter.kind is inspect.Parameter.KEYWORD_ONLY
    assert meter.default is None


def test_policy_public_contract_and_setup() -> None:
    module = importlib.import_module("bluetape.observability.resilience")
    observer_class = module.OpenTelemetryPolicyObserver
    assert module.__all__ == ["OpenTelemetryPolicyObserver"]
    assert_keyword_only_meter(observer_class)

    meter = RecordingMeter()
    observer = observer_class(meter=meter)
    assert meter.calls == [
        (
            "counter",
            "bluetape.resilience.policy.events",
            "{event}",
            "Number of observed Bluetape resilience policy events.",
        )
    ]
    assert observer.__slots__ == ("_counter",)

    for failure in (RuntimeError("setup"), KeyboardInterrupt(), SystemExit(), GeneratorExit()):
        failing = RecordingMeter(fail_at=1, failure=failure)
        with pytest.raises(type(failure)):
            observer_class(meter=failing)
        retry = RecordingMeter()
        observer_class(meter=retry)
        assert len(retry.calls) == 1


def test_redis_public_contract_and_setup() -> None:
    module = importlib.import_module("bluetape.observability.redis")
    assert module.__all__ == [
        "OpenTelemetryRedisObserver",
        "OpenTelemetryRedisCoordinationObserver",
    ]

    expected = {
        module.OpenTelemetryRedisObserver: [
            (
                "counter",
                "bluetape.redis.operations",
                "{operation}",
                "Number of observed Bluetape Redis operations.",
            ),
            (
                "histogram",
                "bluetape.redis.operation.duration",
                "s",
                "Duration of observed Bluetape Redis operations.",
            ),
        ],
        module.OpenTelemetryRedisCoordinationObserver: [
            (
                "counter",
                "bluetape.redis.coordination.operations",
                "{operation}",
                "Number of observed Bluetape Redis coordination operations.",
            ),
            (
                "histogram",
                "bluetape.redis.coordination.duration",
                "s",
                "Duration of observed Bluetape Redis coordination operations.",
            ),
        ],
    }
    for observer_class, calls in expected.items():
        assert_keyword_only_meter(observer_class)
        meter = RecordingMeter()
        observer = observer_class(meter=meter)
        assert meter.calls == calls
        assert observer.__slots__ == ("_counter", "_histogram")
        for fail_at in (1, 2):
            failing = RecordingMeter(fail_at=fail_at)
            with pytest.raises(RuntimeError, match="instrument setup"):
                observer_class(meter=failing)
            retry = RecordingMeter()
            observer_class(meter=retry)
            assert retry.calls == calls
