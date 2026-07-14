"""Bounded synchronous and asynchronous bulkhead policies."""

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from bluetape.resilience._core import (
    BulkheadRejectedError,
    BulkheadSnapshot,
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyType,
    _emit,
    _failure_category,
    _finite_non_negative,
    _positive_int,
    _validate_callable,
    _validate_name,
)
from bluetape.resilience._retry import (
    _ensure_async_operation,
    _ensure_sync_operation,
    _ensure_sync_result,
    _SyncResultContractError,
)

P = ParamSpec("P")
R = TypeVar("R")


def _event(
    name: str,
    kind: EventKind,
    outcome: PolicyOutcome | None,
    category: FailureCategory,
    snapshot: BulkheadSnapshot,
) -> PolicyEvent:
    return PolicyEvent(
        name,
        PolicyType.BULKHEAD,
        kind,
        outcome,
        category,
        None,
        None,
        None,
        None,
        None,
        snapshot.in_flight,
        snapshot.waiters,
    )


class Bulkhead:
    def __init__(
        self,
        *,
        name: str,
        max_concurrency: int,
        max_wait: float = 0,
        observer: Callable[[PolicyEvent], None] | None = None,
    ) -> None:
        self.name = _validate_name(name)
        self._max_concurrency = _positive_int(max_concurrency, "max_concurrency")
        self._max_wait = _finite_non_negative(max_wait, "max_wait")
        self._observer = None if observer is None else _validate_callable(observer, "observer")
        self._condition = threading.Condition()
        self._in_flight = 0
        self._waiters = 0

    def _snapshot_locked(self) -> BulkheadSnapshot:
        return BulkheadSnapshot(self.name, self._max_concurrency, self._in_flight, self._waiters)

    def snapshot(self) -> BulkheadSnapshot:
        with self._condition:
            return self._snapshot_locked()

    def _acquire(self) -> BulkheadSnapshot | None:
        with self._condition:
            if self._in_flight >= self._max_concurrency:
                if self._max_wait == 0:
                    return None
                deadline = time.monotonic() + self._max_wait
                self._waiters += 1
                try:
                    while self._in_flight >= self._max_concurrency:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return None
                        self._condition.wait(remaining)
                finally:
                    self._waiters -= 1
            self._in_flight += 1
            return self._snapshot_locked()

    def _release(self) -> BulkheadSnapshot:
        with self._condition:
            self._in_flight -= 1
            self._condition.notify()
            return self._snapshot_locked()

    def call(self, operation: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        _validate_callable(operation, "operation")
        _ensure_sync_operation(operation)
        snapshot = self._acquire()
        if snapshot is None:
            rejected = self.snapshot()
            _emit(
                self._observer,
                _event(
                    self.name,
                    EventKind.REJECTED,
                    PolicyOutcome.REJECTION,
                    FailureCategory.BULKHEAD_REJECTED,
                    rejected,
                ),
            )
            raise BulkheadRejectedError(self.name)
        try:
            _emit(
                self._observer,
                _event(self.name, EventKind.ADMITTED, None, FailureCategory.NONE, snapshot),
            )
        except BaseException:
            self._release()
            raise
        try:
            result = _ensure_sync_result(operation(*args, **kwargs))
        except _SyncResultContractError:
            self._release()
            raise
        except Exception as error:
            released = self._release()
            _emit(
                self._observer,
                _event(
                    self.name,
                    EventKind.FAILED,
                    PolicyOutcome.FAILURE,
                    _failure_category(error),
                    released,
                ),
            )
            raise
        except BaseException:
            self._release()
            raise
        released = self._release()
        _emit(
            self._observer,
            _event(
                self.name,
                EventKind.SUCCEEDED,
                PolicyOutcome.SUCCESS,
                FailureCategory.NONE,
                released,
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


class AsyncBulkhead:
    def __init__(
        self,
        *,
        name: str,
        max_concurrency: int,
        max_wait: float = 0,
        observer: Callable[[PolicyEvent], None] | None = None,
    ) -> None:
        self.name = _validate_name(name)
        self._max_concurrency = _positive_int(max_concurrency, "max_concurrency")
        self._max_wait = _finite_non_negative(max_wait, "max_wait")
        self._observer = None if observer is None else _validate_callable(observer, "observer")
        self._condition = asyncio.Condition()
        self._in_flight = 0
        self._waiters = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_guard = threading.Lock()

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        with self._loop_guard:
            if self._loop is None:
                self._loop = loop
            elif self._loop is not loop:
                raise RuntimeError("async bulkhead is bound to another event loop")

    def _snapshot_locked(self) -> BulkheadSnapshot:
        return BulkheadSnapshot(self.name, self._max_concurrency, self._in_flight, self._waiters)

    async def snapshot(self) -> BulkheadSnapshot:
        self._bind_loop()
        async with self._condition:
            return self._snapshot_locked()

    async def _acquire(self) -> BulkheadSnapshot | None:
        async with self._condition:
            if self._in_flight >= self._max_concurrency:
                if self._max_wait == 0:
                    return None
                self._waiters += 1
                try:
                    try:
                        async with asyncio.timeout(self._max_wait):
                            while self._in_flight >= self._max_concurrency:
                                await self._condition.wait()
                    except TimeoutError:
                        return None
                finally:
                    self._waiters -= 1
            self._in_flight += 1
            return self._snapshot_locked()

    async def _release(self) -> BulkheadSnapshot:
        async with self._condition:
            self._in_flight -= 1
            self._condition.notify()
            return self._snapshot_locked()

    async def _release_preserving_cancellation(self) -> tuple[BulkheadSnapshot, bool]:
        cancelled = False
        while True:
            try:
                return await self._release(), cancelled
            except asyncio.CancelledError:
                cancelled = True

    async def call(
        self, operation: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        _validate_callable(operation, "operation")
        _ensure_async_operation(operation)
        self._bind_loop()
        snapshot = await self._acquire()
        if snapshot is None:
            rejected = await self.snapshot()
            _emit(
                self._observer,
                _event(
                    self.name,
                    EventKind.REJECTED,
                    PolicyOutcome.REJECTION,
                    FailureCategory.BULKHEAD_REJECTED,
                    rejected,
                ),
            )
            raise BulkheadRejectedError(self.name)
        try:
            _emit(
                self._observer,
                _event(self.name, EventKind.ADMITTED, None, FailureCategory.NONE, snapshot),
            )
        except asyncio.CancelledError:
            await self._release_preserving_cancellation()
            raise
        except BaseException:
            _, cancelled = await self._release_preserving_cancellation()
            if cancelled:
                raise asyncio.CancelledError from None
            raise
        try:
            result = await operation(*args, **kwargs)
        except asyncio.CancelledError:
            await self._release_preserving_cancellation()
            raise
        except Exception as error:
            released, cancelled = await self._release_preserving_cancellation()
            if cancelled:
                raise asyncio.CancelledError from None
            _emit(
                self._observer,
                _event(
                    self.name,
                    EventKind.FAILED,
                    PolicyOutcome.FAILURE,
                    _failure_category(error),
                    released,
                ),
            )
            raise
        except BaseException:
            _, cancelled = await self._release_preserving_cancellation()
            if cancelled:
                raise asyncio.CancelledError from None
            raise
        released, cancelled = await self._release_preserving_cancellation()
        if cancelled:
            raise asyncio.CancelledError from None
        _emit(
            self._observer,
            _event(
                self.name,
                EventKind.SUCCEEDED,
                PolicyOutcome.SUCCESS,
                FailureCategory.NONE,
                released,
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
