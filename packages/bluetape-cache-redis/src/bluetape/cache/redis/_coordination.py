"""Synchronous cache-first Redis load coordination."""

import math
import random
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

from bluetape.cache import TTLCache

from ._contracts import (
    EnvelopeError,
    RedisCoordinationError,
    RedisCoordinationErrorCode,
    RedisCoordinationEvent,
    RedisCoordinationObserver,
    RedisCoordinationOperation,
    RedisCoordinationOutcome,
    RedisCoordinationTimeoutError,
    RedisLoadOptions,
    RedisMode,
    RedisProviderError,
    _validate_owner_token,
)
from ._envelope import ResultEnvelopeCodec
from ._provider import SyncRedisProvider

_clock = time.monotonic
_sleep = time.sleep
_jitter = random.random


def _new_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(slots=True)
class _FlightState:
    started_ns: int
    attempts: int = 0
    polls: int = 0
    cleanup_failed: bool = False


def _validate_logical_key(key: object) -> None:
    if type(key) is not str:
        raise TypeError("key must be an exact str")
    if len(key.encode("utf-8")) > 4096:
        raise ValueError("key must not exceed 4096 UTF-8 bytes")


def _coordination_keys(namespace_id: str, logical_key: str) -> tuple[str, str]:
    key_id = sha256(logical_key.encode("utf-8")).hexdigest()
    slot = f"{{{namespace_id}:{key_id}}}"
    prefix = f"bluetape:cache:coord:{namespace_id}:{slot}"
    return f"{prefix}:lease", f"{prefix}:result"


def _parse_marker(marker: bytes) -> tuple[str, str]:
    try:
        text = marker.decode("ascii")
        state, token = text.split(":", 1)
        if state not in {"active", "completed"}:
            raise ValueError
        _validate_owner_token(token)
    except (UnicodeDecodeError, TypeError, ValueError):
        raise RedisCoordinationError(code=RedisCoordinationErrorCode.INVALID_ARTIFACT) from None
    return state, token


def _poll_delay(options: RedisLoadOptions, polls: int, remaining: float) -> float:
    max_exponent = math.ceil(math.log2(options.max_poll_interval / options.poll_interval))
    exponent = min(polls - 1, max_exponent)
    return min(
        options.poll_interval * (2**exponent),
        options.max_poll_interval,
        remaining,
    )


class SyncRedisLoadCoordinator[V]:
    """Coordinate cache-owned synchronous loads through bounded Redis leases."""

    def __init__(
        self,
        cache: TTLCache[str, V],
        provider: SyncRedisProvider,
        codec: ResultEnvelopeCodec[V],
        *,
        options: RedisLoadOptions,
        observer: RedisCoordinationObserver | None = None,
    ) -> None:
        if not isinstance(cache, TTLCache):
            raise TypeError("cache must be a TTLCache")
        if not isinstance(provider, SyncRedisProvider):
            raise TypeError("provider must be a SyncRedisProvider")
        if not isinstance(codec, ResultEnvelopeCodec):
            raise TypeError("codec must be a ResultEnvelopeCodec")
        if type(options) is not RedisLoadOptions:
            raise TypeError("options must be an exact RedisLoadOptions")
        if observer is not None and not callable(getattr(observer, "on_event", None)):
            raise TypeError("observer must provide on_event")
        policy = provider.command_policy
        if policy is None:
            raise ValueError("provider must expose a bounded no-retry policy")
        if policy.max_command_time > options.redis_io_timeout:
            raise ValueError("provider command policy exceeds redis_io_timeout")
        self._cache = cache
        self._provider = provider
        self._codec = codec
        self._options = options
        self._observer = observer
        self._namespace_id = sha256(options.namespace.encode("utf-8")).hexdigest()

    def get_or_load(
        self,
        key: str,
        loader: Callable[[str], V],
        *,
        ttl: float | None = None,
    ) -> V:
        """Return a local hit or coordinate one bounded distributed load."""
        _validate_logical_key(key)
        if not callable(loader):
            raise TypeError("loader must be callable")
        return self._cache.get_or_load(
            key,
            lambda logical_key: self._distributed_load(logical_key, loader),
            ttl=ttl,
        )

    def _emit(
        self,
        state: _FlightState,
        *,
        outcome: RedisCoordinationOutcome,
        error_code: RedisCoordinationErrorCode | None,
    ) -> None:
        observer = self._observer
        if observer is None:
            return
        event = RedisCoordinationEvent(
            mode=RedisMode.SYNC,
            operation=RedisCoordinationOperation.GET_OR_LOAD,
            outcome=outcome,
            error_code=error_code,
            attempts=state.attempts,
            polls=state.polls,
            cleanup_failed=state.cleanup_failed,
            elapsed_ns=max(0, time.perf_counter_ns() - state.started_ns),
        )
        try:
            observer.on_event(event)
        except Exception:
            return

    def _cleanup(self, lease_key: str, active_marker: bytes, primary: BaseException) -> None:
        try:
            self._provider.delete_if_value(lease_key, active_marker)
        except BaseException:
            primary.add_note("Redis owner cleanup also failed (cleanup-failure)")
            raise

    @staticmethod
    def _timeout(code: RedisCoordinationErrorCode) -> RedisCoordinationTimeoutError:
        return RedisCoordinationTimeoutError(code=code)

    def _distributed_load(self, key: str, loader: Callable[[str], V]) -> V:
        state = _FlightState(started_ns=time.perf_counter_ns())
        deadline = _clock() + self._options.wait_timeout
        lease_key, result_key = _coordination_keys(self._namespace_id, key)
        try:
            value, outcome = self._run_flight(
                key,
                loader,
                state=state,
                deadline=deadline,
                lease_key=lease_key,
                result_key=result_key,
            )
        except RedisCoordinationTimeoutError as error:
            self._emit(state, outcome=RedisCoordinationOutcome.TIMEOUT, error_code=error.code)
            raise
        except RedisCoordinationError as error:
            self._emit(state, outcome=RedisCoordinationOutcome.FAILURE, error_code=error.code)
            raise
        except RedisProviderError:
            self._emit(
                state,
                outcome=RedisCoordinationOutcome.FAILURE,
                error_code=RedisCoordinationErrorCode.PROVIDER_FAILURE,
            )
            raise
        except EnvelopeError:
            self._emit(
                state,
                outcome=RedisCoordinationOutcome.FAILURE,
                error_code=RedisCoordinationErrorCode.ENVELOPE_FAILURE,
            )
            raise
        except BaseException:
            self._emit(
                state,
                outcome=RedisCoordinationOutcome.FAILURE,
                error_code=RedisCoordinationErrorCode.LOADER_FAILURE,
            )
            raise
        self._emit(state, outcome=outcome, error_code=None)
        return value

    def _run_flight(
        self,
        key: str,
        loader: Callable[[str], V],
        *,
        state: _FlightState,
        deadline: float,
        lease_key: str,
        result_key: str,
    ) -> tuple[V, RedisCoordinationOutcome]:
        while True:
            if _clock() >= deadline:
                raise self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
            if state.attempts >= self._options.max_attempts:
                raise self._timeout(RedisCoordinationErrorCode.ATTEMPTS_EXHAUSTED)
            token = _new_token()
            _validate_owner_token(token)
            active_marker = f"active:{token}".encode("ascii")
            completion_marker = f"completed:{token}".encode("ascii")
            if _clock() >= deadline:
                raise self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
            state.attempts += 1
            acquired = self._provider.set_if_absent(
                lease_key, active_marker, ttl=self._options.lease_ttl
            )
            if acquired:
                if _clock() >= deadline:
                    error = self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
                    try:
                        self._cleanup(lease_key, active_marker, error)
                    except BaseException:
                        state.cleanup_failed = True
                    raise error
                return self._run_owner(
                    key,
                    loader,
                    state=state,
                    lease_key=lease_key,
                    result_key=result_key,
                    active_marker=active_marker,
                    completion_marker=completion_marker,
                    lease_deadline=_clock() + self._options.lease_ttl,
                )
            if _clock() >= deadline:
                raise self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
            while True:
                if _clock() >= deadline:
                    raise self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
                snapshot = self._provider.coordination_snapshot(
                    lease_key,
                    result_key,
                    max_result_size=self._codec.max_encoded_size,
                )
                if _clock() >= deadline:
                    raise self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
                if snapshot.marker_oversized or snapshot.result_oversized:
                    raise RedisCoordinationError(code=RedisCoordinationErrorCode.INVALID_ARTIFACT)
                if snapshot.marker is None:
                    break
                marker_state, marker_token = _parse_marker(snapshot.marker)
                if marker_state == "completed":
                    if snapshot.result is None:
                        raise RedisCoordinationError(
                            code=RedisCoordinationErrorCode.INVALID_ARTIFACT
                        )
                    match = self._codec.decode_matching(
                        snapshot.result,
                        expected_owner_token=marker_token,
                    )
                    if match is not None:
                        return match.value, RedisCoordinationOutcome.RESULT_REUSED
                state.polls += 1
                if state.polls >= self._options.max_polls:
                    raise self._timeout(RedisCoordinationErrorCode.POLLS_EXHAUSTED)
                remaining = deadline - _clock()
                if remaining <= 0:
                    raise self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
                cap = _poll_delay(self._options, state.polls, remaining)
                _sleep(cap * _jitter())

    def _run_owner(
        self,
        key: str,
        loader: Callable[[str], V],
        *,
        state: _FlightState,
        lease_key: str,
        result_key: str,
        active_marker: bytes,
        completion_marker: bytes,
        lease_deadline: float,
    ) -> tuple[V, RedisCoordinationOutcome]:
        try:
            value = loader(key)
            if _clock() >= lease_deadline:
                return value, RedisCoordinationOutcome.LEASE_LOST
            encoded = self._codec.encode(active_marker[7:].decode("ascii"), value)
            if _clock() >= lease_deadline:
                return value, RedisCoordinationOutcome.LEASE_LOST
            published = self._provider.publish_if_value(
                lease_key,
                active_marker,
                result_key=result_key,
                result_value=encoded,
                completion_value=completion_marker,
                ttl=self._options.result_ttl,
            )
        except BaseException as primary:
            try:
                self._cleanup(lease_key, active_marker, primary)
            except BaseException:
                state.cleanup_failed = True
            raise
        if not published:
            return value, RedisCoordinationOutcome.LEASE_LOST
        return value, RedisCoordinationOutcome.LOADED
