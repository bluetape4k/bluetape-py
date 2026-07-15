from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True, slots=True)
class EnumValue:
    value: object


class RecordingCounter:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.calls: list[tuple[int, dict[str, object]]] = []
        self.failure = failure
        self._lock = Lock()

    def add(self, amount: int, attributes: dict[str, object]) -> None:
        if self.failure is not None:
            raise self.failure
        with self._lock:
            self.calls.append((amount, dict(attributes)))


class RecordingHistogram:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.calls: list[tuple[float, dict[str, object]]] = []
        self.failure = failure
        self._lock = Lock()

    def record(self, amount: float, attributes: dict[str, object]) -> None:
        if self.failure is not None:
            raise self.failure
        with self._lock:
            self.calls.append((amount, dict(attributes)))


class RecordingMeter:
    def __init__(self, *, fail_at: int | None = None, failure: BaseException | None = None) -> None:
        self.calls: list[tuple[str, str, str, str]] = []
        self.instruments: list[RecordingCounter | RecordingHistogram] = []
        self.fail_at = fail_at
        self.failure = failure or RuntimeError("instrument setup")

    def _create(
        self, kind: str, name: str, unit: str, description: str
    ) -> RecordingCounter | RecordingHistogram:
        self.calls.append((kind, name, unit, description))
        if self.fail_at == len(self.calls):
            raise self.failure
        instrument = RecordingCounter() if kind == "counter" else RecordingHistogram()
        self.instruments.append(instrument)
        return instrument

    def create_counter(
        self, name: str, unit: str = "", description: str = ""
    ) -> RecordingCounter | RecordingHistogram:
        return self._create("counter", name, unit, description)

    def create_histogram(
        self, name: str, unit: str = "", description: str = ""
    ) -> RecordingCounter | RecordingHistogram:
        return self._create("histogram", name, unit, description)


class RecordingSpan:
    def __init__(
        self,
        *,
        recording: bool = True,
        is_recording_failure: BaseException | None = None,
        add_failure: BaseException | None = None,
    ) -> None:
        self.recording = recording
        self.is_recording_failure = is_recording_failure
        self.add_failure = add_failure
        self.events: list[tuple[str, dict[str, object]]] = []

    def is_recording(self) -> bool:
        if self.is_recording_failure is not None:
            raise self.is_recording_failure
        return self.recording

    def add_event(self, name: str, attributes: dict[str, object]) -> None:
        if self.add_failure is not None:
            raise self.add_failure
        self.events.append((name, dict(attributes)))


def policy_event(**overrides: Any) -> SimpleNamespace:
    values = {
        "policy_name": "must-never-be-read",
        "policy_type": EnumValue("retry"),
        "kind": EnumValue("succeeded"),
        "outcome": EnumValue("success"),
        "failure_category": EnumValue("none"),
        "attempt": 1,
        "delay": None,
        "timeout": None,
        "state": None,
        "previous_state": None,
        "in_flight": None,
        "waiters": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def redis_event(**overrides: Any) -> SimpleNamespace:
    values = {
        "mode": EnumValue("sync"),
        "operation": EnumValue("get"),
        "outcome": EnumValue("success"),
        "error_code": None,
        "elapsed_ns": 125_000_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def coordination_event(**overrides: Any) -> SimpleNamespace:
    values = {
        "mode": EnumValue("async"),
        "operation": EnumValue("get-or-load"),
        "outcome": EnumValue("loaded"),
        "error_code": None,
        "attempts": 1,
        "polls": 0,
        "cleanup_failed": False,
        "elapsed_ns": 250_000_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)
