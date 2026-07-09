"""Internal-first testing helpers with a small documented public subset."""

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic, sleep
from typing import cast


def _require_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _is_satisfied(value: object) -> bool:
    return value is not None and value is not False


def eventually[T](
    probe: Callable[[], T | None | bool],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> T:
    """Poll `probe` until it returns a truthy value or a non-`None` object."""
    _require_positive(timeout, "timeout")
    _require_positive(interval, "interval")
    deadline = monotonic() + timeout

    while monotonic() <= deadline:
        value = probe()
        if _is_satisfied(value):
            return cast(T, value)
        sleep(interval)

    raise AssertionError(f"condition was not satisfied within {timeout:g}s")


async def eventually_async[T](
    probe: Callable[[], Awaitable[T | None | bool]],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> T:
    """Async variant of `eventually`."""
    _require_positive(timeout, "timeout")
    _require_positive(interval, "interval")
    deadline = monotonic() + timeout

    while monotonic() <= deadline:
        value = await probe()
        if _is_satisfied(value):
            return cast(T, value)
        await asyncio.sleep(interval)

    raise AssertionError(f"condition was not satisfied within {timeout:g}s")


__all__ = [
    "eventually",
    "eventually_async",
]
