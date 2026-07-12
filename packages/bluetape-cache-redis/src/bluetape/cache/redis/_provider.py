"""Synchronous Redis byte provider with explicit ownership and lifecycle."""

import math
import threading
from collections.abc import Callable, Mapping
from time import perf_counter_ns
from types import TracebackType
from typing import Self

import redis

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

COMPARE_AND_DELETE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
""".strip()

COORDINATION_SNAPSHOT_SCRIPT = """
local marker_exists = redis.call('exists', KEYS[1])
local marker_length = redis.call('strlen', KEYS[1])
local marker_value = redis.call('getrange', KEYS[1], 0, ARGV[1] - 1)
local result_exists = redis.call('exists', KEYS[2])
local result_length = redis.call('strlen', KEYS[2])
local result_value = redis.call('getrange', KEYS[2], 0, ARGV[2] - 1)
return {marker_exists, marker_length, marker_value, result_exists, result_length, result_value}
""".strip()

PUBLISH_IF_VALUE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('set', KEYS[2], ARGV[2], 'PX', ARGV[3])
  redis.call('set', KEYS[1], ARGV[4], 'PX', ARGV[3])
  return 1
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


def _discover_command_policy(client: object) -> RedisCommandPolicy | None:
    pool = getattr(client, "connection_pool", None)
    options = getattr(pool, "connection_kwargs", None)
    if not isinstance(options, Mapping):
        return None
    if "retry_on_timeout" in options and options["retry_on_timeout"] is not False:
        return None
    retry_on_error = options.get("retry_on_error")
    if retry_on_error is not None and not (
        type(retry_on_error) in (list, tuple, set, frozenset) and len(retry_on_error) == 0
    ):
        return None
    if options.get("retry") is not None:
        return None
    try:
        return RedisCommandPolicy(
            connect_timeout=options.get("socket_connect_timeout"),  # type: ignore[arg-type]
            socket_timeout=options.get("socket_timeout"),  # type: ignore[arg-type]
        )
    except (TypeError, ValueError):
        return None


def _validate_size_limit(value: object, *, field: str, maximum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{field} must be an exact int")
    if not 1 <= value <= maximum:
        raise ValueError(f"{field} is outside its supported range")


def _snapshot_part(
    exists: object,
    length: object,
    value: object,
    *,
    maximum: int,
    operation: RedisOperation,
) -> tuple[bytes | None, bool]:
    if type(exists) is not int or exists not in (0, 1):
        raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
    if type(length) is not int or length < 0 or type(value) is not bytes:
        raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
    if exists == 0:
        if length != 0 or value != b"":
            raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
        return None, False
    oversized = length > maximum
    expected_size = maximum if oversized else length
    if len(value) != expected_size:
        raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
    return value, oversized


def _coordination_snapshot(
    response: object,
    *,
    max_marker_size: int,
    max_result_size: int,
) -> RedisCoordinationSnapshot:
    operation = RedisOperation.COORDINATION_SNAPSHOT
    if type(response) is not list or len(response) != 6:
        raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
    marker, marker_oversized = _snapshot_part(
        response[0], response[1], response[2], maximum=max_marker_size, operation=operation
    )
    result, result_oversized = _snapshot_part(
        response[3], response[4], response[5], maximum=max_result_size, operation=operation
    )
    return RedisCoordinationSnapshot(
        marker=marker,
        result=result,
        marker_oversized=marker_oversized,
        result_oversized=result_oversized,
    )


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
        self._command_policy = _discover_command_policy(client)
        self._owned = False
        self._condition = threading.Condition()
        self._state = "open"
        self._active = 0
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

    def coordination_snapshot(
        self,
        marker_key: str,
        result_key: str,
        *,
        max_marker_size: int = MAX_COORDINATION_MARKER_SIZE,
        max_result_size: int,
    ) -> RedisCoordinationSnapshot:
        """Atomically read bounded marker and result prefixes with exact lengths."""

        def action() -> RedisCoordinationSnapshot:
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
            response = self._client.eval(
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

        return self._execute(RedisOperation.COORDINATION_SNAPSHOT, action)

    def publish_if_value(
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

        def action() -> bool:
            _validate_key(condition_key)
            _validate_key(result_key)
            if condition_key == result_key:
                raise ValueError("condition_key and result_key must be distinct")
            _validate_value(expected_value, field="expected_value")
            _validate_value(result_value, field="result_value")
            _validate_value(completion_value, field="completion_value")
            milliseconds = _ttl_milliseconds(ttl)
            response = self._client.eval(
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

        return self._execute(RedisOperation.PUBLISH_IF_VALUE, action)

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
