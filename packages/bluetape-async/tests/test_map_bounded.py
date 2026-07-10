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
