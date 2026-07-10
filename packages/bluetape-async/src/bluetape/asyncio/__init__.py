"""Bounded structured-concurrency helpers for bluetape-py."""

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

_MAX_LIMIT = 1024


class _InvocationCancelledError(Exception):
    """Private TaskGroup signal for non-external cancellation."""


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


def _raise_if_worker_cancelled(
    owner: asyncio.Task[object],
    owner_cancellation_baseline: int,
    terminal: asyncio.Event,
) -> None:
    worker = asyncio.current_task()
    if worker is None or not worker.cancelling():
        return
    if owner.cancelling() > owner_cancellation_baseline:
        raise asyncio.CancelledError
    terminal.set()
    raise _InvocationCancelledError


async def _invoke_mapper[T, R](
    mapper: Callable[[T], Awaitable[R]],
    item: T,
    owner: asyncio.Task[object],
    owner_cancellation_baseline: int,
    terminal: asyncio.Event,
) -> R:
    try:
        result = await mapper(item)
    except asyncio.CancelledError:
        if owner.cancelling() > owner_cancellation_baseline:
            raise
        terminal.set()
        raise _InvocationCancelledError from None
    except BaseException:
        terminal.set()
        raise
    _raise_if_worker_cancelled(owner, owner_cancellation_baseline, terminal)
    return result


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
    owner = asyncio.current_task()
    if owner is None:
        raise RuntimeError("map_bounded requires an active asyncio task")
    owner_cancellation_baseline = owner.cancelling()
    iterator = iter(items)
    if owner.cancelling() > owner_cancellation_baseline:
        raise asyncio.CancelledError
    results: list[R | None] = []
    terminal = asyncio.Event()

    async def worker() -> None:
        while True:
            if terminal.is_set():
                return
            try:
                item = next(iterator)
            except StopIteration:
                _raise_if_worker_cancelled(owner, owner_cancellation_baseline, terminal)
                return
            except asyncio.CancelledError:
                if owner.cancelling() > owner_cancellation_baseline:
                    raise
                terminal.set()
                raise _InvocationCancelledError from None
            except BaseException:
                terminal.set()
                raise
            _raise_if_worker_cancelled(owner, owner_cancellation_baseline, terminal)
            index = len(results)
            results.append(None)
            results[index] = await _invoke_mapper(
                mapper,
                item,
                owner,
                owner_cancellation_baseline,
                terminal,
            )

    async def run_workers() -> None:
        async with asyncio.TaskGroup() as task_group:
            for worker_index in range(limit):
                task_group.create_task(
                    worker(),
                    name=f"bluetape.map_bounded.{worker_index}",
                )

    try:
        if timeout is None:
            await run_workers()
        else:
            async with asyncio.timeout(timeout):
                await run_workers()
    except* _InvocationCancelledError:
        raise asyncio.CancelledError from None
    return cast(list[R], results)


__all__ = ["map_bounded"]
