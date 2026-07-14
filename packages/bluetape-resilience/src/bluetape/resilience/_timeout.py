"""Cooperative asyncio timeout policy."""

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from bluetape.resilience._core import (
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyTimeoutError,
    PolicyType,
    _emit,
    _failure_category,
    _finite_positive,
    _validate_callable,
    _validate_name,
)
from bluetape.resilience._retry import _ensure_async_operation

P = ParamSpec("P")
R = TypeVar("R")


class AsyncTimeout:
    def __init__(
        self,
        *,
        name: str,
        timeout: float,
        observer: Callable[[PolicyEvent], None] | None = None,
    ) -> None:
        self.name = _validate_name(name)
        self.timeout = _finite_positive(timeout, "timeout")
        self._observer = None if observer is None else _validate_callable(observer, "observer")

    def _event(
        self,
        kind: EventKind,
        outcome: PolicyOutcome,
        category: FailureCategory,
    ) -> PolicyEvent:
        return PolicyEvent(
            self.name,
            PolicyType.TIMEOUT,
            kind,
            outcome,
            category,
            None,
            None,
            self.timeout,
            None,
            None,
            None,
            None,
        )

    async def call(
        self, operation: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        _validate_callable(operation, "operation")
        _ensure_async_operation(operation)
        context = asyncio.timeout(self.timeout)
        try:
            async with context:
                result = await operation(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except TimeoutError as error:
            if context.expired():
                _emit(
                    self._observer,
                    self._event(
                        EventKind.TIMED_OUT,
                        PolicyOutcome.FAILURE,
                        FailureCategory.TIMEOUT,
                    ),
                )
                raise PolicyTimeoutError(self.name, self.timeout) from error
            _emit(
                self._observer,
                self._event(
                    EventKind.FAILED,
                    PolicyOutcome.FAILURE,
                    _failure_category(error),
                ),
            )
            raise
        except Exception as error:
            _emit(
                self._observer,
                self._event(
                    EventKind.FAILED,
                    PolicyOutcome.FAILURE,
                    _failure_category(error),
                ),
            )
            raise
        _emit(
            self._observer,
            self._event(
                EventKind.SUCCEEDED,
                PolicyOutcome.SUCCESS,
                FailureCategory.NONE,
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
