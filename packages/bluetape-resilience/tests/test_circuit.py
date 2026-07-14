"""Generation-safe circuit breaker tests."""

import asyncio
import threading

import pytest
from bluetape.resilience import (
    AsyncCircuitBreaker,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    EventKind,
)

from ._support import FakeClock


def test_circuit_constructor_validates_without_invoking_callbacks() -> None:
    invoked = False

    def callback(*_: object) -> bool:
        nonlocal invoked
        invoked = True
        return True

    breaker = CircuitBreaker(
        name="breaker",
        failure_threshold=2,
        open_duration=3,
        failure_if=callback,
        observer=callback,
        clock=callback,
    )
    assert breaker.snapshot().state is CircuitState.CLOSED
    assert not invoked
    with pytest.raises(TypeError):
        CircuitBreaker("breaker", 1, 1)
    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", failure_threshold=0, open_duration=1)
    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", failure_threshold=1, open_duration=0)


def test_circuit_opens_rejects_and_lazily_recovers() -> None:
    clock = FakeClock()
    events = []
    breaker = CircuitBreaker(
        name="breaker",
        failure_threshold=2,
        open_duration=5,
        observer=events.append,
        clock=clock,
    )
    for _ in range(2):
        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("failure")))
    assert breaker.snapshot().state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "not-called")
    clock.advance(5)
    assert breaker.call(lambda: "ok") == "ok"
    snapshot = breaker.snapshot()
    assert snapshot.state is CircuitState.CLOSED
    assert snapshot.consecutive_failures == 0
    assert [event.kind for event in events].count(EventKind.CIRCUIT_TRANSITIONED) == 3


def test_half_open_probe_limit_rejects_concurrent_probe() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(name="breaker", failure_threshold=1, open_duration=1, clock=clock)
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError()))
    clock.advance(1)
    entered = threading.Event()
    release = threading.Event()

    def probe() -> None:
        breaker.call(lambda: (entered.set(), release.wait(1))[1])

    thread = threading.Thread(target=probe)
    thread.start()
    assert entered.wait(1)
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: None)
    assert breaker.snapshot().half_open_in_flight == 1
    release.set()
    thread.join(1)
    assert not thread.is_alive()
    assert breaker.snapshot().state is CircuitState.CLOSED


def test_stale_failure_cannot_reopen_recovered_epoch() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(name="breaker", failure_threshold=1, open_duration=1, clock=clock)
    entered = threading.Event()
    release = threading.Event()

    def late_failure() -> None:
        def operation() -> None:
            entered.set()
            assert release.wait(1)
            raise ValueError("late")

        with pytest.raises(ValueError):
            breaker.call(operation)

    thread = threading.Thread(target=late_failure)
    thread.start()
    assert entered.wait(1)
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("open")))
    clock.advance(1)
    assert breaker.call(lambda: "recovered") == "recovered"
    assert breaker.snapshot().state is CircuitState.CLOSED
    release.set()
    thread.join(1)
    assert not thread.is_alive()
    assert breaker.snapshot().state is CircuitState.CLOSED


def test_predicate_error_and_admitted_observer_error_release_half_open_probe() -> None:
    clock = FakeClock()
    predicate_error = LookupError("predicate")
    classify_calls = 0

    def failure_if(_: Exception) -> bool:
        nonlocal classify_calls
        classify_calls += 1
        if classify_calls == 1:
            return True
        raise predicate_error

    breaker = CircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        failure_if=failure_if,
        clock=clock,
    )
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError()))
    clock.advance(1)
    with pytest.raises(LookupError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError()))
    assert breaker.snapshot().half_open_in_flight == 0

    observer_enabled = False
    observer_error = LookupError("observer")

    def observer(event: object) -> None:
        if observer_enabled and getattr(event, "kind", None) is EventKind.ADMITTED:
            raise observer_error

    seed = CircuitBreaker(
        name="seed",
        failure_threshold=1,
        open_duration=1,
        observer=observer,
        clock=clock,
    )
    with pytest.raises(ValueError):
        seed.call(lambda: (_ for _ in ()).throw(ValueError()))
    clock.advance(1)
    observer_enabled = True
    with pytest.raises(LookupError):
        seed.call(lambda: None)
    assert seed.snapshot().half_open_in_flight == 0


@pytest.mark.asyncio
async def test_async_circuit_cancellation_releases_probe_without_terminal_event() -> None:
    clock = FakeClock()
    events = []
    breaker = AsyncCircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        observer=events.append,
        clock=clock,
    )

    async def fail() -> None:
        raise ValueError

    with pytest.raises(ValueError):
        await breaker.call(fail)
    clock.advance(1)
    entered = asyncio.Event()

    async def probe() -> None:
        entered.set()
        await asyncio.Future()

    task = asyncio.create_task(breaker.call(probe))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    snapshot = await breaker.snapshot()
    assert snapshot.half_open_in_flight == 0
    assert events[-1].kind is EventKind.ADMITTED


def test_async_circuit_rejects_second_event_loop_before_operation() -> None:
    breaker = AsyncCircuitBreaker(name="breaker", failure_threshold=1, open_duration=1)

    async def operation() -> str:
        return "ok"

    assert asyncio.run(breaker.call(operation)) == "ok"
    with pytest.raises(RuntimeError):
        asyncio.run(breaker.call(operation))
