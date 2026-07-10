"""Bounded structured-concurrency helpers for bluetape-py."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import cast


async def map_bounded[T, R](
    items: Iterable[T],
    mapper: Callable[[T], Awaitable[R]],
    *,
    limit: int,
) -> list[R]:
    """Map items with at most ``limit`` concurrent mapper calls."""
    iterator = iter(items)
    results: list[R | None] = []

    async def worker() -> None:
        while True:
            try:
                item = next(iterator)
            except StopIteration:
                return
            index = len(results)
            results.append(None)
            results[index] = await mapper(item)

    async with asyncio.TaskGroup() as task_group:
        for _ in range(limit):
            task_group.create_task(worker())

    return cast(list[R], results)


__all__ = ["map_bounded"]
