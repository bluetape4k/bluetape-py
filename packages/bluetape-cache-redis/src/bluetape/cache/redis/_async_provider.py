"""Asynchronous Redis byte provider with loop affinity and cancellation-safe close."""

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter_ns
from types import TracebackType
from typing import Self

import redis.asyncio as redis_async

from ._contracts import (
    DEFAULT_MAX_ENCODED_SIZE,
    MAX_COORDINATION_MARKER_SIZE,
    ProviderClosedError,
    RedisCommandPolicy,
    RedisCoordinationSnapshot,
    RedisErrorCode,
    RedisEvent,
    RedisMode,
    RedisObserver,
    RedisOperation,
    RedisOutcome,
    RedisProviderError,
)
from ._provider import (
    COMPARE_AND_DELETE_SCRIPT,
    COORDINATION_SNAPSHOT_SCRIPT,
    PUBLISH_IF_VALUE_SCRIPT,
    _coordination_snapshot,
    _deleted,
    _discover_command_policy,
    _error_code,
    _ttl_milliseconds,
    _validate_binary_client,
    _validate_key,
    _validate_size_limit,
    _validate_value,
    _wrapped_error,
)


class AsyncRedisProvider:
    """Asynchronous Redis byte operations with borrowed or factory-owned lifecycle."""

    def __init__(
        self,
        client: redis_async.Redis,
        *,
        observer: RedisObserver | None = None,
    ) -> None:
        _validate_binary_client(client)
        self._client = client
        self._observer = observer
        self._command_policy = _discover_command_policy(client)
        self._owned = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._condition: asyncio.Condition | None = None
        self._state = "open"
        self._active = 0
        self._close_task: asyncio.Task[None] | None = None
        self._terminal_close_error: RedisProviderError | None = None

    @property
    def command_policy(self) -> RedisCommandPolicy | None:
        """Return finite no-retry command bounds when the pool proves them."""
        return self._command_policy

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        observer: RedisObserver | None = None,
        **redis_options: object,
    ) -> Self:
        """Construct and own a binary async redis-py client from a caller URL."""
        started = perf_counter_ns()
        if type(url) is not str:
            raise TypeError("url must be an exact str")
        if not url or url != url.strip():
            raise ValueError("url must be non-blank without surrounding whitespace")
        if "connection_pool" in redis_options:
            raise TypeError("connection_pool cannot be supplied to from_url")
        if redis_options.get("decode_responses") is True:
            raise ValueError("decode_responses=True is incompatible with the binary provider")
        options = dict(redis_options)
        options["decode_responses"] = False
        try:
            client = redis_async.Redis.from_url(url, **options)
        except Exception as cause:
            code = _error_code(cause)
            error = _wrapped_error(operation=RedisOperation.CREATE, code=code, cause=cause)
            cls._emit_to(
                observer,
                RedisEvent(
                    mode=RedisMode.ASYNC,
                    operation=RedisOperation.CREATE,
                    outcome=RedisOutcome.FAILURE,
                    error_code=code,
                    elapsed_ns=perf_counter_ns() - started,
                ),
            )
            raise error from cause
        provider = cls(client, observer=observer)
        provider._owned = True
        cls._emit_to(
            observer,
            RedisEvent(
                mode=RedisMode.ASYNC,
                operation=RedisOperation.CREATE,
                outcome=RedisOutcome.SUCCESS,
                error_code=None,
                elapsed_ns=perf_counter_ns() - started,
            ),
        )
        return provider

    @staticmethod
    def _emit_to(observer: RedisObserver | None, event: RedisEvent) -> None:
        if observer is None:
            return
        try:
            observer.on_event(event)
        except Exception:
            return

    def _emit(
        self,
        *,
        operation: RedisOperation,
        outcome: RedisOutcome,
        error_code: RedisErrorCode | None,
        started: int,
    ) -> None:
        self._emit_to(
            self._observer,
            RedisEvent(
                mode=RedisMode.ASYNC,
                operation=operation,
                outcome=outcome,
                error_code=error_code,
                elapsed_ns=perf_counter_ns() - started,
            ),
        )

    def _bind_loop(self) -> asyncio.Condition:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
            self._condition = asyncio.Condition()
        elif self._loop is not loop:
            raise RuntimeError("async Redis provider is bound to a different event loop")
        assert self._condition is not None
        return self._condition

    async def _admit(self, operation: RedisOperation) -> None:
        condition = self._bind_loop()
        async with condition:
            if self._state != "open":
                raise ProviderClosedError(operation=operation)
            self._active += 1

    async def _release(self) -> None:
        condition = self._bind_loop()
        async with condition:
            self._active -= 1
            if self._active == 0:
                condition.notify_all()

    async def _execute[R](
        self,
        operation: RedisOperation,
        action: Callable[[], Awaitable[R]],
    ) -> R:
        started = perf_counter_ns()
        try:
            await self._admit(operation)
        except ProviderClosedError:
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=RedisErrorCode.CLOSED,
                started=started,
            )
            raise
        except RuntimeError:
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=RedisErrorCode.INVALID_INPUT,
                started=started,
            )
            raise
        try:
            result = await action()
        except asyncio.CancelledError:
            await self._release()
            self._emit(
                operation=operation,
                outcome=RedisOutcome.CANCELLED,
                error_code=None,
                started=started,
            )
            raise
        except RedisProviderError as error:
            await self._release()
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=error.code,
                started=started,
            )
            raise
        except (TypeError, ValueError):
            await self._release()
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=RedisErrorCode.INVALID_INPUT,
                started=started,
            )
            raise
        except Exception as cause:
            await self._release()
            code = _error_code(cause)
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=code,
                started=started,
            )
            raise _wrapped_error(operation=operation, code=code, cause=cause) from cause
        except BaseException:
            await self._release()
            raise
        await self._release()
        self._emit(
            operation=operation,
            outcome=RedisOutcome.SUCCESS,
            error_code=None,
            started=started,
        )
        return result

    async def get(self, key: str) -> bytes | None:
        """Return exact stored bytes or ``None`` when the key is absent."""

        async def action() -> bytes | None:
            _validate_key(key)
            response = await self._client.get(key)
            if response is None or type(response) is bytes:
                return response
            raise RedisProviderError(
                operation=RedisOperation.GET, code=RedisErrorCode.INVALID_RESPONSE
            )

        return await self._execute(RedisOperation.GET, action)

    async def set(self, key: str, value: bytes, *, ttl: float) -> None:
        """Store exact bytes with a required positive TTL."""

        async def action() -> None:
            _validate_key(key)
            _validate_value(value)
            milliseconds = _ttl_milliseconds(ttl)
            response = await self._client.set(key, value, px=milliseconds)
            if response is not True:
                raise RedisProviderError(
                    operation=RedisOperation.SET,
                    code=RedisErrorCode.INVALID_RESPONSE,
                )

        await self._execute(RedisOperation.SET, action)

    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        """Atomically store exact bytes only when the key is absent."""

        async def action() -> bool:
            _validate_key(key)
            _validate_value(value)
            milliseconds = _ttl_milliseconds(ttl)
            response = await self._client.set(key, value, nx=True, px=milliseconds)
            if response is True:
                return True
            if response is None:
                return False
            raise RedisProviderError(
                operation=RedisOperation.SET_IF_ABSENT,
                code=RedisErrorCode.INVALID_RESPONSE,
            )

        return await self._execute(RedisOperation.SET_IF_ABSENT, action)

    async def delete(self, key: str) -> bool:
        """Delete one key and report whether it existed."""

        async def action() -> bool:
            _validate_key(key)
            return _deleted(await self._client.delete(key), operation=RedisOperation.DELETE)

        return await self._execute(RedisOperation.DELETE, action)

    async def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        """Atomically compare and delete through the fixed internal Lua script."""

        async def action() -> bool:
            _validate_key(key)
            _validate_value(expected_value, field="expected_value")
            response = await self._client.eval(
                COMPARE_AND_DELETE_SCRIPT,
                1,
                key,
                expected_value,
            )
            return _deleted(response, operation=RedisOperation.DELETE_IF_VALUE)

        return await self._execute(RedisOperation.DELETE_IF_VALUE, action)

    async def coordination_snapshot(
        self,
        marker_key: str,
        result_key: str,
        *,
        max_marker_size: int = MAX_COORDINATION_MARKER_SIZE,
        max_result_size: int,
    ) -> RedisCoordinationSnapshot:
        """Atomically read bounded marker and result prefixes with exact lengths."""

        async def action() -> RedisCoordinationSnapshot:
            _validate_key(marker_key)
            _validate_key(result_key)
            if marker_key == result_key:
                raise ValueError("marker_key and result_key must be distinct")
            _validate_size_limit(
                max_marker_size,
                field="max_marker_size",
                maximum=MAX_COORDINATION_MARKER_SIZE,
            )
            _validate_size_limit(
                max_result_size,
                field="max_result_size",
                maximum=DEFAULT_MAX_ENCODED_SIZE,
            )
            response = await self._client.eval(
                COORDINATION_SNAPSHOT_SCRIPT,
                2,
                marker_key,
                result_key,
                max_marker_size,
                max_result_size,
            )
            return _coordination_snapshot(
                response,
                max_marker_size=max_marker_size,
                max_result_size=max_result_size,
            )

        return await self._execute(RedisOperation.COORDINATION_SNAPSHOT, action)

    async def publish_if_value(
        self,
        condition_key: str,
        expected_value: bytes,
        *,
        result_key: str,
        result_value: bytes,
        completion_value: bytes,
        ttl: float,
    ) -> bool:
        """Publish a result and completion marker only while ownership matches."""

        async def action() -> bool:
            _validate_key(condition_key)
            _validate_key(result_key)
            if condition_key == result_key:
                raise ValueError("condition_key and result_key must be distinct")
            _validate_value(expected_value, field="expected_value")
            _validate_value(result_value, field="result_value")
            _validate_value(completion_value, field="completion_value")
            milliseconds = _ttl_milliseconds(ttl)
            response = await self._client.eval(
                PUBLISH_IF_VALUE_SCRIPT,
                2,
                condition_key,
                result_key,
                expected_value,
                result_value,
                milliseconds,
                completion_value,
            )
            return _deleted(response, operation=RedisOperation.PUBLISH_IF_VALUE)

        return await self._execute(RedisOperation.PUBLISH_IF_VALUE, action)

    async def _cleanup(self) -> None:
        condition = self._bind_loop()
        terminal: RedisProviderError | None = None
        try:
            async with condition:
                while self._active:
                    await condition.wait()
            if self._owned:
                await self._client.aclose()
        except Exception as cause:
            terminal = _wrapped_error(
                operation=RedisOperation.CLOSE,
                code=_error_code(cause),
                cause=cause,
            )
        finally:
            async with condition:
                self._terminal_close_error = terminal
                self._state = "closed"
                self._close_task = None
                condition.notify_all()
        if terminal is not None:
            raise terminal

    async def _get_or_create_close_task(self) -> asyncio.Task[None] | None:
        condition = self._bind_loop()
        async with condition:
            if self._state == "closed":
                return None
            if self._state == "open":
                self._state = "closing"
                self._close_task = asyncio.create_task(self._cleanup())
            assert self._close_task is not None
            return self._close_task

    async def aclose(self) -> None:
        """Drain operations and finish one shielded owned-client cleanup before returning."""
        started = perf_counter_ns()
        cleanup = await self._get_or_create_close_task()
        if cleanup is None:
            self._emit(
                operation=RedisOperation.CLOSE,
                outcome=RedisOutcome.SUCCESS,
                error_code=None,
                started=started,
            )
            return
        cancelled: asyncio.CancelledError | None = None
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as error:
                if cancelled is None:
                    cancelled = error
            except Exception:
                break
        close_error = cleanup.exception()
        if cancelled is not None:
            self._emit(
                operation=RedisOperation.CLOSE,
                outcome=RedisOutcome.CANCELLED,
                error_code=(
                    close_error.code if isinstance(close_error, RedisProviderError) else None
                ),
                started=started,
            )
            raise cancelled
        if isinstance(close_error, RedisProviderError):
            self._emit(
                operation=RedisOperation.CLOSE,
                outcome=RedisOutcome.FAILURE,
                error_code=close_error.code,
                started=started,
            )
            raise close_error
        if close_error is not None:
            raise close_error
        self._emit(
            operation=RedisOperation.CLOSE,
            outcome=RedisOutcome.SUCCESS,
            error_code=None,
            started=started,
        )

    async def __aenter__(self) -> Self:
        """Bind to the current loop and return this open provider."""
        condition = self._bind_loop()
        async with condition:
            if self._state != "open":
                raise ProviderClosedError(operation=RedisOperation.GET)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close this provider without suppressing the active exception."""
        await self.aclose()
