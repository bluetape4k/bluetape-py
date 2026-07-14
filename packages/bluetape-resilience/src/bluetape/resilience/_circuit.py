"""Generation-safe synchronous and asynchronous circuit breakers."""

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import ParamSpec, TypeVar

from bluetape.resilience._core import (
    CircuitOpenError,
    CircuitSnapshot,
    CircuitState,
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyType,
    _emit,
    _failure_category,
    _finite_non_negative,
    _finite_positive,
    _positive_int,
    _validate_callable,
    _validate_name,
)
from bluetape.resilience._retry import _ensure_async_operation, _ensure_sync_operation

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class _Admission:
    generation: int
    state: CircuitState
    owns_half_open_slot: bool


@dataclass(frozen=True, slots=True)
class _Transition:
    previous: CircuitState
    current: CircuitState


class _CircuitData:
    def __init__(
        self,
        *,
        failure_threshold: int,
        open_duration: float,
        half_open_max_calls: int,
        recovery_success_threshold: int,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.open_duration = open_duration
        self.half_open_max_calls = half_open_max_calls
        self.recovery_success_threshold = recovery_success_threshold
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.recovery_successes = 0
        self.half_open_in_flight = 0
        self.open_until = 0.0
        self.generation = 0

    def snapshot(self, name: str) -> CircuitSnapshot:
        return CircuitSnapshot(
            name,
            self.state,
            self.consecutive_failures,
            self.recovery_successes,
            self.half_open_in_flight,
        )

    def _transition(self, state: CircuitState, now: float) -> _Transition:
        previous = self.state
        self.state = state
        self.generation += 1
        self.consecutive_failures = 0
        self.recovery_successes = 0
        self.half_open_in_flight = 0
        if state is CircuitState.OPEN:
            self.open_until = now + self.open_duration
        return _Transition(previous, state)

    def admit(self, now: float) -> tuple[_Admission | None, _Transition | None]:
        transition = None
        if self.state is CircuitState.OPEN:
            if now < self.open_until:
                return None, None
            transition = self._transition(CircuitState.HALF_OPEN, now)
        owns_slot = self.state is CircuitState.HALF_OPEN
        if owns_slot:
            if self.half_open_in_flight >= self.half_open_max_calls:
                return None, transition
            self.half_open_in_flight += 1
        return _Admission(self.generation, self.state, owns_slot), transition

    def ignore(self, admission: _Admission) -> None:
        if (
            admission.generation == self.generation
            and admission.owns_half_open_slot
            and self.state is CircuitState.HALF_OPEN
        ):
            self.half_open_in_flight -= 1

    def succeed(self, admission: _Admission, now: float) -> _Transition | None:
        if admission.generation != self.generation:
            return None
        if admission.owns_half_open_slot and self.state is CircuitState.HALF_OPEN:
            self.half_open_in_flight -= 1
            self.recovery_successes += 1
            if self.recovery_successes >= self.recovery_success_threshold:
                return self._transition(CircuitState.CLOSED, now)
        elif self.state is CircuitState.CLOSED:
            self.consecutive_failures = 0
        return None

    def fail(self, admission: _Admission, now: float) -> _Transition | None:
        if admission.generation != self.generation:
            return None
        if admission.owns_half_open_slot and self.state is CircuitState.HALF_OPEN:
            self.half_open_in_flight -= 1
            return self._transition(CircuitState.OPEN, now)
        if self.state is CircuitState.CLOSED:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.failure_threshold:
                return self._transition(CircuitState.OPEN, now)
        return None


class _CircuitEvents:
    def __init__(self, name: str) -> None:
        self.name = name

    def make(
        self,
        kind: EventKind,
        outcome: PolicyOutcome | None,
        category: FailureCategory,
        snapshot: CircuitSnapshot,
        transition: _Transition | None = None,
    ) -> PolicyEvent:
        return PolicyEvent(
            self.name,
            PolicyType.CIRCUIT_BREAKER,
            kind,
            outcome,
            category,
            None,
            None,
            None,
            snapshot.state,
            None if transition is None else transition.previous,
            snapshot.half_open_in_flight,
            None,
        )


class CircuitBreaker:
    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int,
        open_duration: float,
        half_open_max_calls: int = 1,
        recovery_success_threshold: int = 1,
        failure_if: Callable[[Exception], bool] | None = None,
        observer: Callable[[PolicyEvent], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = _validate_name(name)
        self._data = _CircuitData(
            failure_threshold=_positive_int(failure_threshold, "failure_threshold"),
            open_duration=_finite_positive(open_duration, "open_duration"),
            half_open_max_calls=_positive_int(half_open_max_calls, "half_open_max_calls"),
            recovery_success_threshold=_positive_int(
                recovery_success_threshold, "recovery_success_threshold"
            ),
        )
        self._failure_if = (
            None if failure_if is None else _validate_callable(failure_if, "failure_if")
        )
        self._observer = None if observer is None else _validate_callable(observer, "observer")
        self._clock = _validate_callable(clock, "clock")
        self._lock = threading.Lock()
        self._events = _CircuitEvents(self.name)

    def snapshot(self) -> CircuitSnapshot:
        with self._lock:
            return self._data.snapshot(self.name)

    def _release(self, admission: _Admission) -> CircuitSnapshot:
        with self._lock:
            self._data.ignore(admission)
            return self._data.snapshot(self.name)

    def _classify(self, error: Exception) -> bool:
        if self._failure_if is None:
            return True
        result = self._failure_if(error)
        if not isinstance(result, bool):
            raise TypeError("failure_if must return bool")
        return result

    def call(self, operation: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        _validate_callable(operation, "operation")
        _ensure_sync_operation(operation)
        now = _finite_non_negative(self._clock(), "clock result")
        with self._lock:
            admission, transition = self._data.admit(now)
            snapshot = self._data.snapshot(self.name)
        try:
            if transition is not None:
                _emit(
                    self._observer,
                    self._events.make(
                        EventKind.CIRCUIT_TRANSITIONED,
                        None,
                        FailureCategory.NONE,
                        snapshot,
                        transition,
                    ),
                )
            if admission is None:
                _emit(
                    self._observer,
                    self._events.make(
                        EventKind.REJECTED,
                        PolicyOutcome.REJECTION,
                        FailureCategory.CIRCUIT_OPEN,
                        snapshot,
                    ),
                )
                raise CircuitOpenError(self.name, snapshot.state)
            _emit(
                self._observer,
                self._events.make(EventKind.ADMITTED, None, FailureCategory.NONE, snapshot),
            )
        except Exception:
            if admission is not None:
                self._release(admission)
            raise
        try:
            result = operation(*args, **kwargs)
        except Exception as error:
            try:
                classified = self._classify(error)
            except Exception:
                self._release(admission)
                raise
            now = _finite_non_negative(self._clock(), "clock result")
            with self._lock:
                changed = self._data.fail(admission, now) if classified else None
                if not classified:
                    self._data.ignore(admission)
                snapshot = self._data.snapshot(self.name)
            if changed is not None:
                _emit(
                    self._observer,
                    self._events.make(
                        EventKind.CIRCUIT_TRANSITIONED,
                        None,
                        FailureCategory.NONE,
                        snapshot,
                        changed,
                    ),
                )
            _emit(
                self._observer,
                self._events.make(
                    EventKind.FAILED,
                    PolicyOutcome.FAILURE,
                    _failure_category(error),
                    snapshot,
                ),
            )
            raise
        now = _finite_non_negative(self._clock(), "clock result")
        with self._lock:
            changed = self._data.succeed(admission, now)
            snapshot = self._data.snapshot(self.name)
        if changed is not None:
            _emit(
                self._observer,
                self._events.make(
                    EventKind.CIRCUIT_TRANSITIONED,
                    None,
                    FailureCategory.NONE,
                    snapshot,
                    changed,
                ),
            )
        _emit(
            self._observer,
            self._events.make(
                EventKind.SUCCEEDED,
                PolicyOutcome.SUCCESS,
                FailureCategory.NONE,
                snapshot,
            ),
        )
        return result

    def __call__(self, operation: Callable[P, R]) -> Callable[P, R]:
        _validate_callable(operation, "operation")
        _ensure_sync_operation(operation)

        @wraps(operation)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return self.call(operation, *args, **kwargs)

        return wrapped


class AsyncCircuitBreaker:
    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int,
        open_duration: float,
        half_open_max_calls: int = 1,
        recovery_success_threshold: int = 1,
        failure_if: Callable[[Exception], bool] | None = None,
        observer: Callable[[PolicyEvent], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = _validate_name(name)
        self._data = _CircuitData(
            failure_threshold=_positive_int(failure_threshold, "failure_threshold"),
            open_duration=_finite_positive(open_duration, "open_duration"),
            half_open_max_calls=_positive_int(half_open_max_calls, "half_open_max_calls"),
            recovery_success_threshold=_positive_int(
                recovery_success_threshold, "recovery_success_threshold"
            ),
        )
        self._failure_if = (
            None if failure_if is None else _validate_callable(failure_if, "failure_if")
        )
        self._observer = None if observer is None else _validate_callable(observer, "observer")
        self._clock = _validate_callable(clock, "clock")
        self._lock = asyncio.Lock()
        self._events = _CircuitEvents(self.name)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_guard = threading.Lock()

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        with self._loop_guard:
            if self._loop is None:
                self._loop = loop
            elif self._loop is not loop:
                raise RuntimeError("async circuit breaker is bound to another event loop")

    async def snapshot(self) -> CircuitSnapshot:
        self._bind_loop()
        async with self._lock:
            return self._data.snapshot(self.name)

    async def _release(self, admission: _Admission) -> CircuitSnapshot:
        async with self._lock:
            self._data.ignore(admission)
            return self._data.snapshot(self.name)

    def _classify(self, error: Exception) -> bool:
        if self._failure_if is None:
            return True
        result = self._failure_if(error)
        if not isinstance(result, bool):
            raise TypeError("failure_if must return bool")
        return result

    async def call(
        self, operation: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        _validate_callable(operation, "operation")
        _ensure_async_operation(operation)
        self._bind_loop()
        now = _finite_non_negative(self._clock(), "clock result")
        async with self._lock:
            admission, transition = self._data.admit(now)
            snapshot = self._data.snapshot(self.name)
        try:
            if transition is not None:
                _emit(
                    self._observer,
                    self._events.make(
                        EventKind.CIRCUIT_TRANSITIONED,
                        None,
                        FailureCategory.NONE,
                        snapshot,
                        transition,
                    ),
                )
            if admission is None:
                _emit(
                    self._observer,
                    self._events.make(
                        EventKind.REJECTED,
                        PolicyOutcome.REJECTION,
                        FailureCategory.CIRCUIT_OPEN,
                        snapshot,
                    ),
                )
                raise CircuitOpenError(self.name, snapshot.state)
            _emit(
                self._observer,
                self._events.make(EventKind.ADMITTED, None, FailureCategory.NONE, snapshot),
            )
        except Exception:
            if admission is not None:
                await self._release(admission)
            raise
        try:
            result = await operation(*args, **kwargs)
        except asyncio.CancelledError:
            await self._release(admission)
            raise
        except Exception as error:
            try:
                classified = self._classify(error)
            except Exception:
                await self._release(admission)
                raise
            now = _finite_non_negative(self._clock(), "clock result")
            async with self._lock:
                changed = self._data.fail(admission, now) if classified else None
                if not classified:
                    self._data.ignore(admission)
                snapshot = self._data.snapshot(self.name)
            if changed is not None:
                _emit(
                    self._observer,
                    self._events.make(
                        EventKind.CIRCUIT_TRANSITIONED,
                        None,
                        FailureCategory.NONE,
                        snapshot,
                        changed,
                    ),
                )
            _emit(
                self._observer,
                self._events.make(
                    EventKind.FAILED,
                    PolicyOutcome.FAILURE,
                    _failure_category(error),
                    snapshot,
                ),
            )
            raise
        now = _finite_non_negative(self._clock(), "clock result")
        async with self._lock:
            changed = self._data.succeed(admission, now)
            snapshot = self._data.snapshot(self.name)
        if changed is not None:
            _emit(
                self._observer,
                self._events.make(
                    EventKind.CIRCUIT_TRANSITIONED,
                    None,
                    FailureCategory.NONE,
                    snapshot,
                    changed,
                ),
            )
        _emit(
            self._observer,
            self._events.make(
                EventKind.SUCCEEDED,
                PolicyOutcome.SUCCESS,
                FailureCategory.NONE,
                snapshot,
            ),
        )
        return result

    def __call__(self, operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        _validate_callable(operation, "operation")
        _ensure_async_operation(operation)

        @wraps(operation)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return await self.call(operation, *args, **kwargs)

        return wrapped
