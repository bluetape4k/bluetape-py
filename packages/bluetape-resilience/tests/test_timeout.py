"""Cooperative async timeout policy tests."""

import asyncio
import inspect

import pytest
from bluetape.resilience import (
    AsyncTimeout,
    EventKind,
    FailureCategory,
    PolicyOutcome,
    PolicyTimeoutError,
)


def test_timeout_constructor_is_keyword_only_and_does_not_invoke_observer() -> None:
    invoked = False

    def observer(_: object) -> None:
        nonlocal invoked
        invoked = True

    policy = AsyncTimeout(name="timeout", timeout=0.1, observer=observer)
    assert policy.name == "timeout"
    assert not invoked
    with pytest.raises(TypeError):
        AsyncTimeout("timeout", 1)
    with pytest.raises(ValueError):
        AsyncTimeout(name="timeout", timeout=0)


@pytest.mark.asyncio
async def test_timeout_preserves_success_and_emits_terminal_event() -> None:
    events = []
    policy = AsyncTimeout(name="timeout", timeout=1, observer=events.append)
    assert await policy.call(asyncio.sleep, 0, result="ok") == "ok"
    assert len(events) == 1
    assert events[0].kind is EventKind.SUCCEEDED
    assert events[0].outcome is PolicyOutcome.SUCCESS
    assert events[0].timeout == 1


@pytest.mark.asyncio
async def test_policy_expiry_raises_policy_timeout_with_cause() -> None:
    events = []
    policy = AsyncTimeout(name="timeout", timeout=0.001, observer=events.append)
    with pytest.raises(PolicyTimeoutError) as captured:
        await policy.call(asyncio.sleep, 10)
    assert isinstance(captured.value.__cause__, TimeoutError)
    assert events[0].kind is EventKind.TIMED_OUT
    assert events[0].failure_category is FailureCategory.TIMEOUT


@pytest.mark.asyncio
async def test_operation_timeout_error_is_not_translated() -> None:
    original = TimeoutError("operation")

    async def operation() -> None:
        raise original

    with pytest.raises(TimeoutError) as captured:
        await AsyncTimeout(name="timeout", timeout=1).call(operation)
    assert captured.value is original


@pytest.mark.asyncio
async def test_external_cancellation_is_not_translated_or_observed() -> None:
    entered = asyncio.Event()
    events = []

    async def operation() -> None:
        entered.set()
        await asyncio.Future()

    task = asyncio.create_task(
        AsyncTimeout(name="timeout", timeout=10, observer=events.append).call(operation)
    )
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == []


@pytest.mark.asyncio
async def test_operation_failure_emits_failed_and_preserves_error() -> None:
    error = ValueError("operation")
    events = []

    async def operation() -> None:
        raise error

    with pytest.raises(ValueError) as captured:
        await AsyncTimeout(name="timeout", timeout=1, observer=events.append).call(operation)
    assert captured.value is error
    assert events[0].kind is EventKind.FAILED
    assert events[0].failure_category is FailureCategory.FAILURE


@pytest.mark.asyncio
async def test_timeout_observer_error_propagates_after_context_cleanup() -> None:
    observer_error = LookupError("observer")

    def observer(_: object) -> None:
        raise observer_error

    with pytest.raises(LookupError) as captured:
        await AsyncTimeout(name="timeout", timeout=1, observer=observer).call(asyncio.sleep, 0)
    assert captured.value is observer_error


@pytest.mark.asyncio
async def test_timeout_creates_no_package_task() -> None:
    before = set(asyncio.all_tasks())
    await AsyncTimeout(name="timeout", timeout=1).call(asyncio.sleep, 0)
    assert set(asyncio.all_tasks()) == before


@pytest.mark.asyncio
async def test_timeout_decorator_preserves_metadata_and_rejects_sync() -> None:
    policy = AsyncTimeout(name="timeout", timeout=1)

    @policy
    async def operation(value: int) -> int:
        """Return the input."""
        return value

    assert await operation(4) == 4
    assert operation.__name__ == "operation"
    assert inspect.signature(operation).return_annotation is int
    with pytest.raises(TypeError):
        policy(lambda: 1)
