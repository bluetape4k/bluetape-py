"""Sync and async retry policy tests."""

import asyncio
import inspect
import math

import pytest
from bluetape.resilience import (
    AsyncRetry,
    BulkheadRejectedError,
    EventKind,
    FailureCategory,
    PolicyOutcome,
    PolicyTimeoutError,
    Retry,
    RetryExhaustedError,
    constant_backoff,
)


def test_retry_constructor_validates_without_invoking_callbacks() -> None:
    invoked = False

    def callback(*args: object) -> bool:
        nonlocal invoked
        invoked = True
        return True

    policy = Retry(
        name="retry",
        max_attempts=2,
        backoff=callback,
        retry_if=callback,
        observer=callback,
        sleeper=callback,
    )
    assert policy.name == "retry"
    assert not invoked
    with pytest.raises(TypeError):
        Retry("retry", 2)
    with pytest.raises(ValueError):
        Retry(name=" retry", max_attempts=2)
    with pytest.raises(TypeError):
        Retry(name="retry", max_attempts=True)


def test_retry_succeeds_after_deterministic_backoff() -> None:
    attempts = 0
    sleeps: list[float] = []
    events = []

    def operation(value: str) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("transient")
        return value

    policy = Retry(
        name="retry",
        max_attempts=3,
        backoff=constant_backoff(0.25),
        observer=events.append,
        sleeper=sleeps.append,
    )
    assert policy.call(operation, "ok") == "ok"
    assert attempts == 3
    assert sleeps == [0.25, 0.25]
    assert [event.kind for event in events] == [
        EventKind.RETRY_SCHEDULED,
        EventKind.RETRY_SCHEDULED,
        EventKind.SUCCEEDED,
    ]
    assert [event.attempt for event in events] == [1, 2, 3]
    assert events[-1].outcome is PolicyOutcome.SUCCESS


def test_retry_exhaustion_chains_last_exception() -> None:
    last = ValueError("secret-operation-error")
    events = []
    policy = Retry(name="retry", max_attempts=2, observer=events.append, sleeper=lambda _: None)
    with pytest.raises(RetryExhaustedError) as captured:
        policy.call(lambda: (_ for _ in ()).throw(last))
    assert captured.value.__cause__ is last
    assert captured.value.attempts == 2
    assert [event.kind for event in events] == [EventKind.RETRY_SCHEDULED, EventKind.FAILED]
    assert events[-1].failure_category is FailureCategory.RETRY_EXHAUSTED


@pytest.mark.parametrize(
    "error",
    [BulkheadRejectedError("bulkhead"), PolicyTimeoutError("timeout", 1)],
)
def test_default_retry_propagates_policy_terminal_errors_unchanged(error: Exception) -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise error

    with pytest.raises(type(error)) as captured:
        Retry(name="retry", max_attempts=3).call(operation)
    assert captured.value is error
    assert attempts == 1


def test_retry_predicate_controls_classification_and_errors_propagate() -> None:
    error = ValueError("terminal")
    policy = Retry(name="retry", max_attempts=3, retry_if=lambda _: False)
    with pytest.raises(ValueError) as captured:
        policy.call(lambda: (_ for _ in ()).throw(error))
    assert captured.value is error

    predicate_error = LookupError("predicate")
    broken = Retry(
        name="retry", max_attempts=3, retry_if=lambda _: (_ for _ in ()).throw(predicate_error)
    )
    with pytest.raises(LookupError) as predicate_capture:
        broken.call(lambda: (_ for _ in ()).throw(error))
    assert predicate_capture.value is predicate_error


@pytest.mark.parametrize("delay", [math.nan, math.inf, -1.0, True])
def test_retry_validates_backoff_output_before_sleep(delay: object) -> None:
    slept = False

    def sleeper(_: float) -> None:
        nonlocal slept
        slept = True

    policy = Retry(name="retry", max_attempts=2, backoff=lambda _: delay, sleeper=sleeper)
    with pytest.raises((TypeError, ValueError)):
        policy.call(lambda: (_ for _ in ()).throw(ValueError()))
    assert not slept


def test_retry_decorator_preserves_metadata_and_rejects_generators() -> None:
    policy = Retry(name="retry", max_attempts=1)

    @policy
    def operation(value: int, *, scale: int = 2) -> int:
        """Multiply a value."""
        return value * scale

    assert operation(3, scale=4) == 12
    assert operation.__name__ == "operation"
    assert operation.__doc__ == "Multiply a value."
    assert list(inspect.signature(operation).parameters) == ["value", "scale"]

    def generator():
        yield 1

    with pytest.raises(TypeError):
        policy(generator)


@pytest.mark.asyncio
async def test_async_retry_succeeds_and_awaits_sleeper() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("transient")
        return "ok"

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    policy = AsyncRetry(
        name="retry", max_attempts=2, backoff=constant_backoff(0.5), sleeper=sleeper
    )
    assert await policy.call(operation) == "ok"
    assert sleeps == [0.5]


@pytest.mark.asyncio
async def test_async_retry_propagates_operation_cancellation_without_event_or_sleep() -> None:
    events = []
    slept = False

    async def operation() -> None:
        raise asyncio.CancelledError

    async def sleeper(_: float) -> None:
        nonlocal slept
        slept = True

    policy = AsyncRetry(name="retry", max_attempts=3, observer=events.append, sleeper=sleeper)
    with pytest.raises(asyncio.CancelledError):
        await policy.call(operation)
    assert events == []
    assert not slept


@pytest.mark.asyncio
async def test_async_retry_cancellation_during_backoff_starts_no_new_attempt() -> None:
    attempts = 0
    entered_sleep = asyncio.Event()

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("transient")

    async def sleeper(_: float) -> None:
        entered_sleep.set()
        await asyncio.Future()

    task = asyncio.create_task(
        AsyncRetry(name="retry", max_attempts=3, sleeper=sleeper).call(operation)
    )
    await asyncio.wait_for(entered_sleep.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert attempts == 1


@pytest.mark.asyncio
async def test_async_retry_decorator_preserves_metadata_and_rejects_sync() -> None:
    policy = AsyncRetry(name="retry", max_attempts=1)

    @policy
    async def operation(value: int) -> int:
        """Return a value."""
        return value

    assert await operation(3) == 3
    assert operation.__name__ == "operation"
    with pytest.raises(TypeError):
        policy(lambda: 1)
