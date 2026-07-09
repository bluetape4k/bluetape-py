import asyncio

import pytest
from bluetape.testing import eventually, eventually_async


def test_eventually_returns_value_after_retries() -> None:
    attempts = 0

    def probe() -> str | None:
        nonlocal attempts
        attempts += 1
        return "ready" if attempts == 3 else None

    assert eventually(probe, timeout=0.5, interval=0.001) == "ready"
    assert attempts == 3


def test_eventually_raises_assertion_error_on_timeout() -> None:
    with pytest.raises(AssertionError, match=r"condition was not satisfied within 0\.01s"):
        eventually(lambda: False, timeout=0.01, interval=0.001)


async def test_eventually_async_returns_value_after_retries() -> None:
    attempts = 0

    async def probe() -> str | None:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(0)
        return "ready" if attempts == 2 else None

    assert await eventually_async(probe, timeout=0.5, interval=0.001) == "ready"
    assert attempts == 2
