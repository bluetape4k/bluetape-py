"""Immutable synchronous and asynchronous resilience pipelines."""

import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from bluetape.resilience._bulkhead import AsyncBulkhead, Bulkhead
from bluetape.resilience._circuit import AsyncCircuitBreaker, CircuitBreaker
from bluetape.resilience._retry import (
    AsyncRetry,
    Retry,
    _ensure_async_operation,
    _ensure_sync_operation,
)
from bluetape.resilience._timeout import AsyncTimeout

P = ParamSpec("P")
R = TypeVar("R")

SyncPolicy = Retry | CircuitBreaker | Bulkhead
AsyncPolicy = AsyncRetry | AsyncCircuitBreaker | AsyncBulkhead | AsyncTimeout


class ResiliencePipeline:
    def __init__(self) -> None:
        self._policies: tuple[SyncPolicy, ...] = ()

    @classmethod
    def _from(cls, policies: tuple[SyncPolicy, ...]) -> "ResiliencePipeline":
        pipeline = object.__new__(cls)
        pipeline._policies = policies
        return pipeline

    def with_retry(self, policy: Retry) -> "ResiliencePipeline":
        if not isinstance(policy, Retry):
            raise TypeError("policy must be Retry")
        return self._from((*self._policies, policy))

    def with_circuit_breaker(self, policy: CircuitBreaker) -> "ResiliencePipeline":
        if not isinstance(policy, CircuitBreaker):
            raise TypeError("policy must be CircuitBreaker")
        return self._from((*self._policies, policy))

    def with_bulkhead(self, policy: Bulkhead) -> "ResiliencePipeline":
        if not isinstance(policy, Bulkhead):
            raise TypeError("policy must be Bulkhead")
        return self._from((*self._policies, policy))

    def call(self, operation: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        _ensure_sync_operation(operation)
        wrapped: Callable[P, R] = operation
        for policy in self._policies:
            wrapped = policy(wrapped)
        result = wrapped(*args, **kwargs)
        if inspect.isawaitable(result):
            close = getattr(result, "close", None)
            if callable(close):
                close()
            raise TypeError("sync operation returned an awaitable")
        return result

    def __call__(self, operation: Callable[P, R]) -> Callable[P, R]:
        _ensure_sync_operation(operation)

        @wraps(operation)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return self.call(operation, *args, **kwargs)

        return wrapped


class AsyncResiliencePipeline:
    def __init__(self) -> None:
        self._policies: tuple[AsyncPolicy, ...] = ()

    @classmethod
    def _from(cls, policies: tuple[AsyncPolicy, ...]) -> "AsyncResiliencePipeline":
        pipeline = object.__new__(cls)
        pipeline._policies = policies
        return pipeline

    def with_retry(self, policy: AsyncRetry) -> "AsyncResiliencePipeline":
        if not isinstance(policy, AsyncRetry):
            raise TypeError("policy must be AsyncRetry")
        return self._from((*self._policies, policy))

    def with_circuit_breaker(self, policy: AsyncCircuitBreaker) -> "AsyncResiliencePipeline":
        if not isinstance(policy, AsyncCircuitBreaker):
            raise TypeError("policy must be AsyncCircuitBreaker")
        return self._from((*self._policies, policy))

    def with_bulkhead(self, policy: AsyncBulkhead) -> "AsyncResiliencePipeline":
        if not isinstance(policy, AsyncBulkhead):
            raise TypeError("policy must be AsyncBulkhead")
        return self._from((*self._policies, policy))

    def with_timeout(self, policy: AsyncTimeout) -> "AsyncResiliencePipeline":
        if not isinstance(policy, AsyncTimeout):
            raise TypeError("policy must be AsyncTimeout")
        return self._from((*self._policies, policy))

    async def call(
        self, operation: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        _ensure_async_operation(operation)
        wrapped: Callable[P, Awaitable[R]] = operation
        for policy in self._policies:
            wrapped = policy(wrapped)
        return await wrapped(*args, **kwargs)

    def __call__(self, operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        _ensure_async_operation(operation)

        @wraps(operation)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return await self.call(operation, *args, **kwargs)

        return wrapped
