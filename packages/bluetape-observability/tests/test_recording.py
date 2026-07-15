from __future__ import annotations

import ast
import importlib
import math
from importlib.metadata import version
from pathlib import Path

import pytest
from _support import EnumValue, RecordingCounter, RecordingHistogram, RecordingSpan


def recording_module():
    return importlib.import_module("bluetape.observability._recording")


def test_default_meter_uses_installed_distribution_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = recording_module()
    sentinel = object()
    calls: list[tuple[str, str]] = []

    def get_meter(name: str, package_version: str):
        calls.append((name, package_version))
        return sentinel

    monkeypatch.setattr(recording.metrics, "get_meter", get_meter)

    assert recording.default_meter() is sentinel
    assert calls == [("bluetape.observability", version("bluetape-observability"))]


def test_closed_values_are_exact_and_pinned() -> None:
    recording = recording_module()
    assert recording.POLICY_TYPES == frozenset({"retry", "timeout", "circuit-breaker", "bulkhead"})
    assert recording.REDIS_MODES == frozenset({"sync", "async"})
    assert recording.closed_value(EnumValue("retry"), recording.POLICY_TYPES) == "retry"
    assert recording.optional_closed_value(None, recording.POLICY_TYPES) is None

    with pytest.raises(ValueError, match="unsupported enum value"):
        recording.closed_value(EnumValue("unknown"), recording.POLICY_TYPES)

    class RaisingValue:
        @property
        def value(self) -> object:
            raise RuntimeError("value")

    with pytest.raises(RuntimeError, match="value"):
        recording.closed_value(RaisingValue(), recording.POLICY_TYPES)

    class ProcessControlValue:
        def __init__(self, failure: BaseException) -> None:
            self.failure = failure

        @property
        def value(self) -> object:
            raise self.failure

    for failure in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
        with pytest.raises(type(failure)):
            recording.closed_value(ProcessControlValue(failure), recording.POLICY_TYPES)


def test_numeric_normalization_enforces_exact_bounds() -> None:
    recording = recording_module()
    assert recording.bounded_int(0, minimum=0) == 0
    assert recording.bounded_int(1, minimum=1) == 1
    assert recording.bounded_int(2**63 - 1, minimum=0) == 2**63 - 1
    assert recording.optional_bounded_int(None, minimum=0) is None
    assert recording.optional_non_negative_float(None) is None
    assert recording.optional_non_negative_float(0) == 0.0
    assert recording.optional_non_negative_float(1.25) == 1.25
    assert recording.exact_bool(False) is False

    for value in (True, -1, 2**63):
        with pytest.raises(ValueError):
            recording.bounded_int(value, minimum=0)
    for value in (True, -1, math.nan, math.inf, -math.inf, "1"):
        with pytest.raises(ValueError):
            recording.optional_non_negative_float(value)
    for value in (0, 1, None):
        with pytest.raises(ValueError):
            recording.exact_bool(value)


def test_current_span_steps_isolate_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = recording_module()
    span = RecordingSpan()
    monkeypatch.setattr(recording.trace, "get_current_span", lambda: span)
    assert recording.recording_span() is span

    monkeypatch.setattr(
        recording.trace, "get_current_span", lambda: (_ for _ in ()).throw(RuntimeError("lookup"))
    )
    assert recording.recording_span() is None

    monkeypatch.setattr(
        recording.trace,
        "get_current_span",
        lambda: RecordingSpan(is_recording_failure=RuntimeError("recording")),
    )
    assert recording.recording_span() is None

    for failure in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
        monkeypatch.setattr(
            recording.trace,
            "get_current_span",
            lambda failure=failure: (_ for _ in ()).throw(failure),
        )
        with pytest.raises(type(failure)):
            recording.recording_span()


def test_recording_calls_isolate_exception_and_propagate_base_exception() -> None:
    recording = recording_module()
    attributes = {"key": "value"}

    recording.add_span_event(RecordingSpan(add_failure=RuntimeError("span")), "event", attributes)
    recording.add_counter(RecordingCounter(failure=RuntimeError("counter")), attributes)
    recording.record_histogram(
        RecordingHistogram(failure=RuntimeError("histogram")), 1.0, attributes
    )

    for failure in (KeyboardInterrupt, SystemExit, GeneratorExit):
        with pytest.raises(failure):
            recording.add_span_event(RecordingSpan(add_failure=failure()), "event", attributes)
        with pytest.raises(failure):
            recording.add_counter(RecordingCounter(failure=failure()), attributes)
        with pytest.raises(failure):
            recording.record_histogram(RecordingHistogram(failure=failure()), 1.0, attributes)


def test_recording_source_has_no_domain_sdk_or_owned_runtime_imports() -> None:
    source = (Path(__file__).parents[1] / "src/bluetape/observability/_recording.py").read_text()
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}

    assert imports <= {
        "__future__",
        "math",
        "importlib.metadata",
        "typing",
        "opentelemetry",
        "opentelemetry.metrics",
        "opentelemetry.trace",
    }
    assert (
        not {
            "threading",
            "asyncio",
            "queue",
            "logging",
            "opentelemetry.sdk",
            "bluetape.resilience",
            "bluetape.cache.redis",
        }
        & imports
    )
