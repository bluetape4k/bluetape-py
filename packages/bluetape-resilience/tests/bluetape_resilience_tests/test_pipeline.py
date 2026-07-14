"""Immutable decorator pipeline tests."""

import asyncio
import inspect
from functools import partial

import bluetape.resilience as resilience
import pytest
from bluetape.resilience import (
    AsyncBulkhead,
    AsyncResiliencePipeline,
    AsyncRetry,
    AsyncTimeout,
    Bulkhead,
    CircuitBreaker,
    CircuitState,
    EventKind,
    ResiliencePipeline,
    Retry,
)

EXPECTED_EXPORTS = [
    "Retry",
    "AsyncRetry",
    "CircuitBreaker",
    "AsyncCircuitBreaker",
    "Bulkhead",
    "AsyncBulkhead",
    "AsyncTimeout",
    "ResiliencePipeline",
    "AsyncResiliencePipeline",
    "Backoff",
    "constant_backoff",
    "exponential_backoff",
    "PolicyEvent",
    "PolicyType",
    "EventKind",
    "PolicyOutcome",
    "FailureCategory",
    "CircuitState",
    "CircuitSnapshot",
    "BulkheadSnapshot",
    "RetryExhaustedError",
    "PolicyTimeoutError",
    "CircuitOpenError",
    "BulkheadRejectedError",
]


def test_exact_public_exports() -> None:
    assert resilience.__all__ == EXPECTED_EXPORTS
    assert not hasattr(resilience, "Timeout")


def test_sync_pipeline_is_immutable_and_shares_policy_instances() -> None:
    empty = ResiliencePipeline()
    retry = Retry(name="retry", max_attempts=1)
    with_retry = empty.with_retry(retry)
    with_bulkhead = with_retry.with_bulkhead(Bulkhead(name="bulkhead", max_concurrency=1))
    assert empty.call(lambda: "empty") == "empty"
    assert with_retry is not empty
    assert with_bulkhead is not with_retry
    assert with_retry._policies == (retry,)
    assert empty._policies == ()
    with pytest.raises(TypeError):
        empty.with_retry(AsyncRetry(name="async", max_attempts=1))


def test_last_added_policy_is_outermost_and_changes_breaker_visibility() -> None:
    attempts = 0
    breaker_events = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("transient")
        return "ok"

    breaker = CircuitBreaker(
        name="breaker",
        failure_threshold=3,
        open_duration=1,
        observer=breaker_events.append,
    )
    retry = Retry(name="retry", max_attempts=2, sleeper=lambda _: None)
    outside_retry = ResiliencePipeline().with_circuit_breaker(breaker).with_retry(retry)
    assert outside_retry.call(operation) == "ok"
    assert [event.kind for event in breaker_events].count(EventKind.ADMITTED) == 2

    attempts = 0
    breaker_events.clear()
    outside_breaker = ResiliencePipeline().with_retry(retry).with_circuit_breaker(breaker)
    assert outside_breaker.call(operation) == "ok"
    assert [event.kind for event in breaker_events].count(EventKind.ADMITTED) == 1


def test_sync_pipeline_decorator_preserves_signature_and_bound_method() -> None:
    pipeline = ResiliencePipeline().with_retry(Retry(name="retry", max_attempts=1))

    class Service:
        @pipeline
        def load(self, value: int, *, scale: int = 2) -> int:
            """Load a scaled value."""
            return value * scale

    method = Service().load
    assert method(3, scale=4) == 12
    assert method.__name__ == "load"
    assert method.__doc__ == "Load a scaled value."
    assert list(inspect.signature(method).parameters) == ["value", "scale"]


def test_sync_pipeline_rejects_async_generators_and_awaitable_results() -> None:
    pipeline = ResiliencePipeline()

    async def async_operation() -> None:
        return None

    def generator():
        yield 1

    with pytest.raises(TypeError):
        pipeline(async_operation)
    with pytest.raises(TypeError):
        pipeline(generator)
    with pytest.raises(TypeError):
        pipeline.call(lambda: async_operation())


def test_sync_pipeline_propagates_awaitable_contract_error_through_policies() -> None:
    attempts = 0
    breaker = CircuitBreaker(name="breaker", failure_threshold=1, open_duration=1)
    bulkhead = Bulkhead(name="bulkhead", max_concurrency=1)
    pipeline = (
        ResiliencePipeline()
        .with_bulkhead(bulkhead)
        .with_circuit_breaker(breaker)
        .with_retry(Retry(name="retry", max_attempts=3))
    )

    async def async_result() -> None:
        return None

    def operation() -> object:
        nonlocal attempts
        attempts += 1
        return async_result()

    with pytest.raises(TypeError, match="sync operation returned an awaitable"):
        pipeline.call(operation)
    assert attempts == 1
    assert breaker.snapshot().state is CircuitState.CLOSED
    assert bulkhead.snapshot().in_flight == 0


@pytest.mark.asyncio
async def test_async_pipeline_is_immutable_outermost_and_preserves_metadata() -> None:
    pipeline = (
        AsyncResiliencePipeline()
        .with_retry(AsyncRetry(name="retry", max_attempts=1))
        .with_timeout(AsyncTimeout(name="timeout", timeout=1))
        .with_bulkhead(AsyncBulkhead(name="bulkhead", max_concurrency=1))
    )

    @pipeline
    async def operation(value: int) -> int:
        """Return a value."""
        return value

    assert await operation(4) == 4
    assert operation.__name__ == "operation"
    assert await AsyncResiliencePipeline().call(asyncio.sleep, 0, result="empty") == "empty"
    with pytest.raises(TypeError):
        AsyncResiliencePipeline().with_retry(Retry(name="sync", max_attempts=1))
    with pytest.raises(TypeError):
        AsyncResiliencePipeline()(lambda: 1)


@pytest.mark.asyncio
async def test_pipelines_classify_partial_async_callable_before_invocation() -> None:
    invoked = False

    async def operation(value: int) -> int:
        nonlocal invoked
        invoked = True
        return value

    bound = partial(operation, 9)
    with pytest.raises(TypeError):
        ResiliencePipeline().call(bound)
    assert not invoked
    assert await AsyncResiliencePipeline().call(bound) == 9
