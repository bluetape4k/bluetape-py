import asyncio
from collections.abc import Iterator

import pytest
from bluetape.asyncio import map_bounded


async def test_map_bounded_preserves_input_order_with_bounded_work() -> None:
    active = 0
    maximum = 0

    async def mapper(value: int) -> int:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return value * 10

    assert await map_bounded([1, 2, 3], mapper, limit=2) == [10, 20, 30]
    assert maximum == 2


def _raising_items() -> Iterator[int]:
    raise AssertionError("items must not be consumed")
    yield 0


async def _identity(value: int) -> int:
    return value


@pytest.mark.parametrize(
    ("limit", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        (0, ValueError),
        (-1, ValueError),
        (1025, ValueError),
    ],
)
async def test_map_bounded_validates_limit_before_consuming_items(
    limit: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        await map_bounded(_raising_items(), _identity, limit=limit)  # type: ignore[arg-type]


async def test_map_bounded_rejects_non_callable_mapper_before_consuming_items() -> None:
    with pytest.raises(TypeError, match="mapper must be callable"):
        await map_bounded(_raising_items(), None, limit=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("timeout", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        ("1", TypeError),
        (-0.1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
    ],
)
async def test_map_bounded_validates_timeout_before_consuming_items(
    timeout: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        await map_bounded(
            _raising_items(),
            _identity,
            limit=1,
            timeout=timeout,  # type: ignore[arg-type]
        )


async def test_map_bounded_times_out_after_mapper_cleanup() -> None:
    cleaned = asyncio.Event()

    async def mapper(_: int) -> int:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises(TimeoutError):
        await map_bounded([1], mapper, limit=1, timeout=0.01)
    assert cleaned.is_set()


async def test_map_bounded_direct_mapper_cancellation_cleans_up_siblings() -> None:
    cleaned = asyncio.Event()
    sibling_started = asyncio.Event()

    async def mapper(value: int) -> int:
        if value == 0:
            sibling_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        await sibling_started.wait()
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await map_bounded([0, 1], mapper, limit=2)
    assert cleaned.is_set()


async def test_map_bounded_preserves_external_cancellation_and_cleanup() -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def mapper(_: int) -> int:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    task = asyncio.create_task(map_bounded([1], mapper, limit=1))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()


async def test_map_bounded_fails_closed_when_mapper_self_cancels_then_returns() -> None:
    admitted: list[int] = []

    async def mapper(value: int) -> int:
        admitted.append(value)
        asyncio.current_task().cancel()  # type: ignore[union-attr]
        return value

    with pytest.raises(asyncio.CancelledError):
        await map_bounded([1, 2, 3], mapper, limit=1)
    assert admitted == [1]


async def test_map_bounded_fails_closed_when_iterator_self_cancels() -> None:
    admitted: list[int] = []

    class SelfCancellingItems:
        def __iter__(self) -> Iterator[int]:
            asyncio.current_task().cancel()  # type: ignore[union-attr]
            return iter([1, 2])

    async def mapper(value: int) -> int:
        admitted.append(value)
        return value

    task = asyncio.create_task(map_bounded(SelfCancellingItems(), mapper, limit=1))
    with pytest.raises(asyncio.CancelledError):
        await task
    assert admitted == []


async def test_map_bounded_propagates_iterator_cancellation() -> None:
    class CancelledItems:
        def __iter__(self) -> Iterator[int]:
            return self

        def __next__(self) -> int:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await map_bounded(CancelledItems(), _identity, limit=1)


async def test_map_bounded_cleans_up_after_iterator_failure() -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    class FailingItems:
        def __iter__(self) -> Iterator[int]:
            yield 0
            started.set()
            raise RuntimeError("iterator failed")

    async def mapper(_: int) -> int:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises(ExceptionGroup) as error:
        await map_bounded(FailingItems(), mapper, limit=2)
    assert any(isinstance(item, RuntimeError) for item in error.value.exceptions)
    assert cleaned.is_set()


async def test_map_bounded_uses_a_total_cooperative_timeout_budget() -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def mapper(value: int) -> int:
        if value == 0:
            return value
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises(TimeoutError):
        await map_bounded([0, 1], mapper, limit=1, timeout=0.01)
    assert started.is_set()
    assert cleaned.is_set()


async def test_map_bounded_leaves_no_named_worker_tasks_after_cancellation() -> None:
    started = asyncio.Event()

    async def mapper(_: int) -> int:
        started.set()
        await asyncio.Event().wait()
        return 0

    task = asyncio.create_task(map_bounded([1], mapper, limit=1))
    await started.wait()
    task.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not any(
        task.get_name().startswith("bluetape.map_bounded.")
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
    )
