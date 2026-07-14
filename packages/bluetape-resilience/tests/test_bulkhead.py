"""Bounded sync and async bulkhead tests."""

import asyncio
import threading

import pytest
from bluetape.resilience import (
    AsyncBulkhead,
    Bulkhead,
    BulkheadRejectedError,
    EventKind,
)


def test_bulkhead_constructor_validates_without_invoking_observer() -> None:
    invoked = False

    def observer(_: object) -> None:
        nonlocal invoked
        invoked = True

    bulkhead = Bulkhead(name="bulkhead", max_concurrency=2, observer=observer)
    assert bulkhead.snapshot().max_concurrency == 2
    assert not invoked
    with pytest.raises(TypeError):
        Bulkhead("bulkhead", 1)
    with pytest.raises(ValueError):
        Bulkhead(name="bulkhead", max_concurrency=0)
    with pytest.raises(ValueError):
        Bulkhead(name="bulkhead", max_concurrency=1, max_wait=-1)


def test_sync_bulkhead_never_exceeds_capacity_and_rejects_immediately() -> None:
    bulkhead = Bulkhead(name="bulkhead", max_concurrency=1)
    entered = threading.Event()
    release = threading.Event()

    def operation() -> None:
        entered.set()
        assert release.wait(1)

    thread = threading.Thread(target=lambda: bulkhead.call(operation))
    thread.start()
    assert entered.wait(1)
    assert bulkhead.snapshot().in_flight == 1
    with pytest.raises(BulkheadRejectedError):
        bulkhead.call(lambda: None)
    release.set()
    thread.join(1)
    assert not thread.is_alive()
    assert bulkhead.snapshot().in_flight == 0


def test_sync_waiter_enters_after_release_and_timeout_rejects() -> None:
    bulkhead = Bulkhead(name="bulkhead", max_concurrency=1, max_wait=0.05)
    entered = threading.Event()
    release = threading.Event()
    first = threading.Thread(
        target=lambda: bulkhead.call(lambda: (entered.set(), release.wait(1))[1])
    )
    first.start()
    assert entered.wait(1)
    with pytest.raises(BulkheadRejectedError):
        bulkhead.call(lambda: None)
    assert bulkhead.snapshot().waiters == 0
    release.set()
    first.join(1)

    assert bulkhead.call(lambda: "ok") == "ok"
    assert bulkhead.snapshot().in_flight == 0


def test_sync_failure_and_admitted_observer_error_release_permit() -> None:
    error = ValueError("operation")
    bulkhead = Bulkhead(name="bulkhead", max_concurrency=1)
    with pytest.raises(ValueError):
        bulkhead.call(lambda: (_ for _ in ()).throw(error))
    assert bulkhead.snapshot().in_flight == 0

    observer_error = LookupError("observer")

    def observer(event: object) -> None:
        if getattr(event, "kind", None) is EventKind.ADMITTED:
            raise observer_error

    observed = Bulkhead(name="observed", max_concurrency=1, observer=observer)
    with pytest.raises(LookupError):
        observed.call(lambda: None)
    assert observed.snapshot().in_flight == 0


@pytest.mark.asyncio
async def test_async_waiter_cancellation_does_not_release_unowned_permit() -> None:
    bulkhead = AsyncBulkhead(name="bulkhead", max_concurrency=1, max_wait=10)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def owner() -> None:
        entered.set()
        await release.wait()

    owner_task = asyncio.create_task(bulkhead.call(owner))
    await asyncio.wait_for(entered.wait(), 1)
    waiter = asyncio.create_task(bulkhead.call(asyncio.sleep, 0))
    for _ in range(10):
        if (await bulkhead.snapshot()).waiters == 1:
            break
        await asyncio.sleep(0)
    assert (await bulkhead.snapshot()).waiters == 1
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    snapshot = await bulkhead.snapshot()
    assert snapshot.in_flight == 1
    assert snapshot.waiters == 0
    release.set()
    await owner_task
    assert (await bulkhead.snapshot()).in_flight == 0


@pytest.mark.asyncio
async def test_async_admitted_cancellation_releases_permit_without_terminal_event() -> None:
    events = []
    bulkhead = AsyncBulkhead(name="bulkhead", max_concurrency=1, observer=events.append)
    entered = asyncio.Event()

    async def operation() -> None:
        entered.set()
        await asyncio.Future()

    task = asyncio.create_task(bulkhead.call(operation))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await bulkhead.snapshot()).in_flight == 0
    assert [event.kind for event in events] == [EventKind.ADMITTED]


def test_async_bulkhead_rejects_second_event_loop() -> None:
    bulkhead = AsyncBulkhead(name="bulkhead", max_concurrency=1)

    async def operation() -> str:
        return "ok"

    assert asyncio.run(bulkhead.call(operation)) == "ok"
    with pytest.raises(RuntimeError):
        asyncio.run(bulkhead.call(operation))
