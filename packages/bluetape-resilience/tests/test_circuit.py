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


def test_stale_success_cannot_close_reopened_epoch() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(name="breaker", failure_threshold=1, open_duration=1, clock=clock)
    entered = threading.Event()
    release = threading.Event()

    def late_success() -> None:
        breaker.call(lambda: (entered.set(), release.wait(1))[1])

    thread = threading.Thread(target=late_success)
    thread.start()
    assert entered.wait(1)
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("open")))
    clock.advance(1)
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("reopen")))
    assert breaker.snapshot().state is CircuitState.OPEN
    release.set()
    thread.join(1)
    assert not thread.is_alive()
    assert breaker.snapshot().state is CircuitState.OPEN


@pytest.mark.asyncio
@pytest.mark.parametrize("late_failure", [False, True])
async def test_async_stale_completion_cannot_mutate_newer_epoch(late_failure: bool) -> None:
    clock = FakeClock()
    breaker = AsyncCircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        clock=clock,
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def late_operation() -> str:
        entered.set()
        await release.wait()
        if late_failure:
            raise ValueError("late")
        return "ok"

    late_task = asyncio.create_task(breaker.call(late_operation))
    await asyncio.wait_for(entered.wait(), 1)

    async def fail(message: str) -> None:
        raise ValueError(message)

    with pytest.raises(ValueError):
        await breaker.call(fail, "open")
    clock.advance(1)
    if late_failure:
        assert await breaker.call(asyncio.sleep, 0, result="recovered") == "recovered"
        expected = CircuitState.CLOSED
    else:
        with pytest.raises(ValueError):
            await breaker.call(fail, "reopen")
        expected = CircuitState.OPEN
    assert (await breaker.snapshot()).state is expected
    release.set()
    if late_failure:
        with pytest.raises(ValueError):
            await asyncio.wait_for(late_task, 1)
    else:
        assert await asyncio.wait_for(late_task, 1) == "ok"
    assert (await breaker.snapshot()).state is expected


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


def test_sync_circuit_rejects_awaitable_result_without_counting_failure() -> None:
    async def async_result() -> None:
        return None

    breaker = CircuitBreaker(name="breaker", failure_threshold=1, open_duration=1)
    with pytest.raises(TypeError, match="sync operation returned an awaitable"):
        breaker.call(lambda: async_result())
    snapshot = breaker.snapshot()
    assert snapshot.state is CircuitState.CLOSED
    assert snapshot.consecutive_failures == 0
    assert snapshot.half_open_in_flight == 0


@pytest.mark.parametrize("operation_fails", [False, True])
def test_sync_completion_clock_error_releases_half_open_probe(operation_fails: bool) -> None:
    clock_values = iter([0.0, 0.0, 1.0])
    clock_error = LookupError("clock")

    def clock() -> float:
        try:
            return next(clock_values)
        except StopIteration:
            raise clock_error from None

    breaker = CircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        clock=clock,
    )
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("open")))

    def probe() -> str:
        if operation_fails:
            raise ValueError("probe")
        return "ok"

    with pytest.raises(LookupError) as captured:
        breaker.call(probe)
    assert captured.value is clock_error
    snapshot = breaker.snapshot()
    assert snapshot.state is CircuitState.HALF_OPEN
    assert snapshot.half_open_in_flight == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation_fails", [False, True])
async def test_async_completion_clock_error_releases_half_open_probe(
    operation_fails: bool,
) -> None:
    clock_values = iter([0.0, 0.0, 1.0])
    clock_error = LookupError("clock")

    def clock() -> float:
        try:
            return next(clock_values)
        except StopIteration:
            raise clock_error from None

    breaker = AsyncCircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        clock=clock,
    )

    async def fail() -> None:
        raise ValueError("open")

    with pytest.raises(ValueError):
        await breaker.call(fail)

    async def probe() -> str:
        if operation_fails:
            raise ValueError("probe")
        return "ok"

    with pytest.raises(LookupError) as captured:
        await breaker.call(probe)
    assert captured.value is clock_error
    snapshot = await breaker.snapshot()
    assert snapshot.state is CircuitState.HALF_OPEN
    assert snapshot.half_open_in_flight == 0


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


@pytest.mark.asyncio
async def test_async_completion_cancellation_waits_for_probe_reconciliation() -> None:
    clock = FakeClock()
    breaker = AsyncCircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        clock=clock,
    )

    async def fail() -> None:
        raise ValueError

    with pytest.raises(ValueError):
        await breaker.call(fail)
    clock.advance(1)
    operation_entered = asyncio.Event()
    finish_operation = asyncio.Event()
    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def probe() -> str:
        operation_entered.set()
        await finish_operation.wait()
        return "ok"

    async def hold_lock() -> None:
        async with breaker._lock:
            lock_held.set()
            await release_lock.wait()

    call_task = asyncio.create_task(breaker.call(probe))
    await asyncio.wait_for(operation_entered.wait(), 1)
    holder = asyncio.create_task(hold_lock())
    await asyncio.wait_for(lock_held.wait(), 1)
    finish_operation.set()
    await asyncio.sleep(0)
    call_task.cancel()
    release_lock.set()
    await asyncio.wait_for(holder, 1)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(call_task, 1)
    snapshot = await breaker.snapshot()
    assert snapshot.state is CircuitState.HALF_OPEN
    assert snapshot.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_async_repeated_cancellation_cannot_interrupt_probe_cleanup() -> None:
    clock = FakeClock()
    breaker = AsyncCircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        clock=clock,
    )

    async def fail() -> None:
        raise ValueError

    with pytest.raises(ValueError):
        await breaker.call(fail)
    clock.advance(1)
    operation_entered = asyncio.Event()
    lock_held = asyncio.Event()
    release_lock = asyncio.Event()

    async def probe() -> None:
        operation_entered.set()
        await asyncio.Future()

    async def hold_lock() -> None:
        async with breaker._lock:
            lock_held.set()
            await release_lock.wait()

    call_task = asyncio.create_task(breaker.call(probe))
    await asyncio.wait_for(operation_entered.wait(), 1)
    holder = asyncio.create_task(hold_lock())
    await asyncio.wait_for(lock_held.wait(), 1)
    call_task.cancel()
    await asyncio.sleep(0)
    call_task.cancel()
    release_lock.set()
    await asyncio.wait_for(holder, 1)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(call_task, 1)
    snapshot = await breaker.snapshot()
    assert snapshot.state is CircuitState.HALF_OPEN
    assert snapshot.half_open_in_flight == 0


def test_sync_half_open_base_exception_releases_probe() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        clock=clock,
    )
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("open")))
    clock.advance(1)
    with pytest.raises(KeyboardInterrupt):
        breaker.call(lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    snapshot = breaker.snapshot()
    assert snapshot.state is CircuitState.HALF_OPEN
    assert snapshot.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_async_admitted_observer_cancellation_releases_probe() -> None:
    clock = FakeClock()
    cancel_observer = False

    def observer(event: object) -> None:
        if cancel_observer and getattr(event, "kind", None) is EventKind.ADMITTED:
            raise asyncio.CancelledError

    breaker = AsyncCircuitBreaker(
        name="breaker",
        failure_threshold=1,
        open_duration=1,
        observer=observer,
        clock=clock,
    )

    async def fail() -> None:
        raise ValueError

    with pytest.raises(ValueError):
        await breaker.call(fail)
    clock.advance(1)
    cancel_observer = True
    with pytest.raises(asyncio.CancelledError):
        await breaker.call(asyncio.sleep, 0)
    snapshot = await breaker.snapshot()
    assert snapshot.state is CircuitState.HALF_OPEN
    assert snapshot.half_open_in_flight == 0


def test_async_circuit_rejects_second_event_loop_before_operation() -> None:
    breaker = AsyncCircuitBreaker(name="breaker", failure_threshold=1, open_duration=1)

    async def operation() -> str:
        return "ok"

    assert asyncio.run(breaker.call(operation)) == "ok"
    with pytest.raises(RuntimeError):
        asyncio.run(breaker.call(operation))
