"""Synchronous Redis byte provider with explicit ownership and lifecycle."""

import math
import threading
from collections.abc import Callable, Mapping
from time import perf_counter_ns
from types import TracebackType
from typing import Self

import redis

from ._contracts import (
    ProviderClosedError,
    RedisErrorCode,
    RedisEvent,
    RedisMode,
    RedisObserver,
    RedisOperation,
    RedisOutcome,
    RedisProviderError,
)

COMPARE_AND_DELETE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
""".strip()


def _validate_key(key: object) -> None:
    if type(key) is not str:
        raise TypeError("key must be an exact str")
    if (
        not key
        or key != key.strip()
        or any(
            character.isspace() or ord(character) < 32 or ord(character) == 127 for character in key
        )
    ):
        raise ValueError("key must be non-blank without whitespace or control characters")


def _validate_value(value: object, *, field: str = "value") -> None:
    if type(value) is not bytes:
        raise TypeError(f"{field} must be exact bytes")


def _ttl_milliseconds(ttl: float) -> int:
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
        raise TypeError("ttl must be a real number")
    if not math.isfinite(ttl) or ttl <= 0:
        raise ValueError("ttl must be finite and positive")
    milliseconds = math.ceil(ttl * 1000)
    if milliseconds > 0x7FFF_FFFF_FFFF_FFFF:
        raise ValueError("ttl is outside the supported Redis range")
    return milliseconds


def _error_code(error: Exception) -> RedisErrorCode:
    if isinstance(error, redis.TimeoutError):
        return RedisErrorCode.TIMEOUT
    if isinstance(error, redis.ConnectionError):
        return RedisErrorCode.CONNECTION
    return RedisErrorCode.PROVIDER_FAILURE


def _wrapped_error(
    *, operation: RedisOperation, code: RedisErrorCode, cause: Exception | None = None
) -> RedisProviderError:
    error = RedisProviderError(operation=operation, code=code)
    if cause is not None:
        error.__cause__ = cause
    return error


def _validate_binary_client(client: object) -> None:
    pool = getattr(client, "connection_pool", None)
    options = getattr(pool, "connection_kwargs", None)
    if isinstance(options, Mapping) and options.get("decode_responses") is True:
        raise ValueError("decode_responses=True is incompatible with the binary provider")


def _deleted(response: object, *, operation: RedisOperation) -> bool:
    if type(response) is not int or response not in (0, 1):
        raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
    return response == 1


class SyncRedisProvider:
    """Synchronous Redis byte operations with borrowed or factory-owned lifecycle."""

    def __init__(
        self,
        client: redis.Redis,
        *,
        observer: RedisObserver | None = None,
    ) -> None:
        _validate_binary_client(client)
        self._client = client
        self._observer = observer
        self._owned = False
        self._condition = threading.Condition()
        self._state = "open"
        self._active = 0
        self._terminal_close_error: RedisProviderError | None = None

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        observer: RedisObserver | None = None,
        **redis_options: object,
    ) -> Self:
        """Construct and own a binary redis-py client from a caller URL."""
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
            client = redis.Redis.from_url(url, **options)
        except Exception as cause:
            code = _error_code(cause)
            error = _wrapped_error(operation=RedisOperation.CREATE, code=code, cause=cause)
            cls._emit_to(
                observer,
                RedisEvent(
                    mode=RedisMode.SYNC,
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
                mode=RedisMode.SYNC,
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
                mode=RedisMode.SYNC,
                operation=operation,
                outcome=outcome,
                error_code=error_code,
                elapsed_ns=perf_counter_ns() - started,
            ),
        )

    def _admit(self, operation: RedisOperation) -> None:
        with self._condition:
            if self._state != "open":
                raise ProviderClosedError(operation=operation)
            self._active += 1

    def _release(self) -> None:
        with self._condition:
            self._active -= 1
            if self._active == 0:
                self._condition.notify_all()

    def _execute[R](self, operation: RedisOperation, action: Callable[[], R]) -> R:
        started = perf_counter_ns()
        try:
            self._admit(operation)
        except ProviderClosedError:
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=RedisErrorCode.CLOSED,
                started=started,
            )
            raise
        try:
            result = action()
        except RedisProviderError as error:
            self._release()
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=error.code,
                started=started,
            )
            raise
        except (TypeError, ValueError):
            self._release()
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=RedisErrorCode.INVALID_INPUT,
                started=started,
            )
            raise
        except Exception as cause:
            self._release()
            code = _error_code(cause)
            self._emit(
                operation=operation,
                outcome=RedisOutcome.FAILURE,
                error_code=code,
                started=started,
            )
            raise _wrapped_error(operation=operation, code=code, cause=cause) from cause
        except BaseException:
            self._release()
            raise
        self._release()
        self._emit(
            operation=operation,
            outcome=RedisOutcome.SUCCESS,
            error_code=None,
            started=started,
        )
        return result

    def get(self, key: str) -> bytes | None:
        """Return exact stored bytes or ``None`` when the key is absent."""

        def action() -> bytes | None:
            _validate_key(key)
            response = self._client.get(key)
            if response is None or type(response) is bytes:
                return response
            raise RedisProviderError(
                operation=RedisOperation.GET, code=RedisErrorCode.INVALID_RESPONSE
            )

        return self._execute(RedisOperation.GET, action)

    def set(self, key: str, value: bytes, *, ttl: float) -> None:
        """Store exact bytes with a required positive TTL."""

        def action() -> None:
            _validate_key(key)
            _validate_value(value)
            milliseconds = _ttl_milliseconds(ttl)
            response = self._client.set(key, value, px=milliseconds)
            if response is not True:
                raise RedisProviderError(
                    operation=RedisOperation.SET,
                    code=RedisErrorCode.INVALID_RESPONSE,
                )

        self._execute(RedisOperation.SET, action)

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        """Atomically store exact bytes only when the key is absent."""

        def action() -> bool:
            _validate_key(key)
            _validate_value(value)
            milliseconds = _ttl_milliseconds(ttl)
            response = self._client.set(key, value, nx=True, px=milliseconds)
            if response is True:
                return True
            if response is None:
                return False
            raise RedisProviderError(
                operation=RedisOperation.SET_IF_ABSENT,
                code=RedisErrorCode.INVALID_RESPONSE,
            )

        return self._execute(RedisOperation.SET_IF_ABSENT, action)

    def delete(self, key: str) -> bool:
        """Delete one key and report whether it existed."""

        def action() -> bool:
            _validate_key(key)
            return _deleted(self._client.delete(key), operation=RedisOperation.DELETE)

        return self._execute(RedisOperation.DELETE, action)

    def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        """Atomically compare and delete through the fixed internal Lua script."""

        def action() -> bool:
            _validate_key(key)
            _validate_value(expected_value, field="expected_value")
            response = self._client.eval(
                COMPARE_AND_DELETE_SCRIPT,
                1,
                key,
                expected_value,
            )
            return _deleted(response, operation=RedisOperation.DELETE_IF_VALUE)

        return self._execute(RedisOperation.DELETE_IF_VALUE, action)

    def close(self) -> None:
        """Drain admitted operations and close a factory-owned client exactly once."""
        started = perf_counter_ns()
        leader = False
        with self._condition:
            if self._state == "closed":
                terminal = None
            elif self._state == "closing":
                while self._state != "closed":
                    self._condition.wait()
                terminal = self._terminal_close_error
            else:
                self._state = "closing"
                leader = True
                while self._active:
                    self._condition.wait()
                terminal = None

        if leader:
            try:
                if self._owned:
                    self._client.close()
            except Exception as cause:
                terminal = _wrapped_error(
                    operation=RedisOperation.CLOSE,
                    code=_error_code(cause),
                    cause=cause,
                )
            finally:
                with self._condition:
                    self._terminal_close_error = terminal
                    self._state = "closed"
                    self._condition.notify_all()

        self._emit(
            operation=RedisOperation.CLOSE,
            outcome=RedisOutcome.FAILURE if terminal is not None else RedisOutcome.SUCCESS,
            error_code=None if terminal is None else terminal.code,
            started=started,
        )
        if terminal is not None:
            raise terminal

    def __enter__(self) -> Self:
        """Return this open provider."""
        with self._condition:
            if self._state != "open":
                raise ProviderClosedError(operation=RedisOperation.GET)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close this provider without suppressing the active exception."""
        self.close()
