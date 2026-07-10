"""Bounded structured-concurrency helpers for bluetape-py."""

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

_MAX_LIMIT = 1024


def _require_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    if limit > _MAX_LIMIT:
        raise ValueError(f"limit must be less than or equal to {_MAX_LIMIT}")


def _require_timeout(timeout: float | None) -> None:
    if timeout is None:
        return
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be a finite non-negative number")
    if timeout < 0 or not math.isfinite(timeout):
        raise ValueError("timeout must be a finite non-negative number")


async def map_bounded[T, R](
    items: Iterable[T],
    mapper: Callable[[T], Awaitable[R]],
    *,
    limit: int,
    timeout: float | None = None,
) -> list[R]:
    """Map items with at most ``limit`` concurrent mapper calls."""
    _require_limit(limit)
    if not callable(mapper):
        raise TypeError("mapper must be callable")
    _require_timeout(timeout)
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

    async def run_workers() -> None:
        async with asyncio.TaskGroup() as task_group:
            for _ in range(limit):
                task_group.create_task(worker())

    if timeout is None:
        await run_workers()
    else:
        async with asyncio.timeout(timeout):
            await run_workers()
    return cast(list[R], results)


__all__ = ["map_bounded"]
