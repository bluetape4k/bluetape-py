"""Synchronous and asynchronous retry policies."""

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from bluetape.resilience._backoff import Backoff, constant_backoff
from bluetape.resilience._core import (
    BulkheadRejectedError,
    CircuitOpenError,
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyTimeoutError,
    PolicyType,
    RetryExhaustedError,
    _emit,
    _failure_category,
    _finite_non_negative,
    _positive_int,
    _validate_callable,
    _validate_name,
)

P = ParamSpec("P")
R = TypeVar("R")


class _SyncResultContractError(TypeError):
    """A sync callable returned an awaitable instead of its declared result."""


def _ensure_sync_operation(operation: Callable[..., object]) -> None:
    if not callable(operation):
        raise TypeError("operation must be callable")
    targets = (operation, operation.__call__)
    if any(
        inspect.iscoroutinefunction(target)
        or inspect.isgeneratorfunction(target)
        or inspect.isasyncgenfunction(target)
        for target in targets
    ):
        raise TypeError("sync resilience policy requires a non-generator sync callable")


def _ensure_async_operation(operation: Callable[..., object]) -> None:
    if not callable(operation):
        raise TypeError("operation must be callable")
    targets = (operation, operation.__call__)
    if not any(inspect.iscoroutinefunction(target) for target in targets) or any(
        inspect.isgeneratorfunction(target) or inspect.isasyncgenfunction(target)
        for target in targets
    ):
        raise TypeError("async resilience policy requires an async callable")


def _ensure_sync_result[T](result: T) -> T:
    if inspect.isawaitable(result):
        close = getattr(result, "close", None)
        if callable(close):
            close()
        raise _SyncResultContractError("sync operation returned an awaitable")
    return result


def _event(
    name: str,
    kind: EventKind,
    outcome: PolicyOutcome | None,
    category: FailureCategory,
    attempt: int,
    *,
    delay: float | None = None,
) -> PolicyEvent:
    return PolicyEvent(
        name,
        PolicyType.RETRY,
        kind,
        outcome,
        category,
        attempt,
        delay,
        None,
        None,
        None,
        None,
        None,
    )


class Retry:
    def __init__(
        self,
        *,
        name: str,
        max_attempts: int,
        backoff: Backoff = constant_backoff(0),  # noqa: B008 - approved public signature
        retry_if: Callable[[Exception], bool] | None = None,
        observer: Callable[[PolicyEvent], None] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.name = _validate_name(name)
        self._max_attempts = _positive_int(max_attempts, "max_attempts")
        self._backoff = _validate_callable(backoff, "backoff")
        self._retry_if = None if retry_if is None else _validate_callable(retry_if, "retry_if")
        self._observer = None if observer is None else _validate_callable(observer, "observer")
        self._sleeper = _validate_callable(sleeper, "sleeper")

    def _is_retryable(self, error: Exception) -> bool:
        if self._retry_if is None:
            return not isinstance(
                error, (CircuitOpenError, BulkheadRejectedError, PolicyTimeoutError)
            )
        result = self._retry_if(error)
        if not isinstance(result, bool):
            raise TypeError("retry_if must return bool")
        return result

    def call(self, operation: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        _validate_callable(operation, "operation")
        _ensure_sync_operation(operation)
        attempt = 1
        while True:
            try:
                result = operation(*args, **kwargs)
            except _SyncResultContractError:
                raise
            except Exception as error:
                retryable = self._is_retryable(error)
                if not retryable:
                    _emit(
                        self._observer,
                        _event(
                            self.name,
                            EventKind.FAILED,
                            PolicyOutcome.FAILURE,
                            _failure_category(error),
                            attempt,
                        ),
                    )
                    raise
                if attempt >= self._max_attempts:
                    _emit(
                        self._observer,
                        _event(
                            self.name,
                            EventKind.FAILED,
                            PolicyOutcome.FAILURE,
                            FailureCategory.RETRY_EXHAUSTED,
                            attempt,
                        ),
                    )
                    raise RetryExhaustedError(self.name, attempt) from error
                delay = _finite_non_negative(self._backoff(attempt), "backoff result")
                _emit(
                    self._observer,
                    _event(
                        self.name,
                        EventKind.RETRY_SCHEDULED,
                        None,
                        _failure_category(error),
                        attempt,
                        delay=delay,
                    ),
                )
                self._sleeper(delay)
                attempt += 1
                continue
            result = _ensure_sync_result(result)
            _emit(
                self._observer,
                _event(
                    self.name,
                    EventKind.SUCCEEDED,
                    PolicyOutcome.SUCCESS,
                    FailureCategory.NONE,
                    attempt,
                ),
            )
            return result

    def __call__(self, operation: Callable[P, R]) -> Callable[P, R]:
        _validate_callable(operation, "operation")
        _ensure_sync_operation(operation)

        @wraps(operation)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return self.call(operation, *args, **kwargs)

        return wrapped


class AsyncRetry:
    def __init__(
        self,
        *,
        name: str,
        max_attempts: int,
        backoff: Backoff = constant_backoff(0),  # noqa: B008 - approved public signature
        retry_if: Callable[[Exception], bool] | None = None,
        observer: Callable[[PolicyEvent], None] | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.name = _validate_name(name)
        self._max_attempts = _positive_int(max_attempts, "max_attempts")
        self._backoff = _validate_callable(backoff, "backoff")
        self._retry_if = None if retry_if is None else _validate_callable(retry_if, "retry_if")
        self._observer = None if observer is None else _validate_callable(observer, "observer")
        self._sleeper = _validate_callable(sleeper, "sleeper")

    def _is_retryable(self, error: Exception) -> bool:
        if self._retry_if is None:
            return not isinstance(
                error, (CircuitOpenError, BulkheadRejectedError, PolicyTimeoutError)
            )
        result = self._retry_if(error)
        if not isinstance(result, bool):
            raise TypeError("retry_if must return bool")
        return result

    async def call(
        self, operation: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        _validate_callable(operation, "operation")
        _ensure_async_operation(operation)
        attempt = 1
        while True:
            try:
                result = await operation(*args, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                retryable = self._is_retryable(error)
                if not retryable:
                    _emit(
                        self._observer,
                        _event(
                            self.name,
                            EventKind.FAILED,
                            PolicyOutcome.FAILURE,
                            _failure_category(error),
                            attempt,
                        ),
                    )
                    raise
                if attempt >= self._max_attempts:
                    _emit(
                        self._observer,
                        _event(
                            self.name,
                            EventKind.FAILED,
                            PolicyOutcome.FAILURE,
                            FailureCategory.RETRY_EXHAUSTED,
                            attempt,
                        ),
                    )
                    raise RetryExhaustedError(self.name, attempt) from error
                delay = _finite_non_negative(self._backoff(attempt), "backoff result")
                _emit(
                    self._observer,
                    _event(
                        self.name,
                        EventKind.RETRY_SCHEDULED,
                        None,
                        _failure_category(error),
                        attempt,
                        delay=delay,
                    ),
                )
                await self._sleeper(delay)
                attempt += 1
                continue
            _emit(
                self._observer,
                _event(
                    self.name,
                    EventKind.SUCCEEDED,
                    PolicyOutcome.SUCCESS,
                    FailureCategory.NONE,
                    attempt,
                ),
            )
            return result

    def __call__(self, operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        _validate_callable(operation, "operation")
        _ensure_async_operation(operation)

        @wraps(operation)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            return await self.call(operation, *args, **kwargs)

        return wrapped
