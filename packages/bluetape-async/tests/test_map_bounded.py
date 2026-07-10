import asyncio

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
