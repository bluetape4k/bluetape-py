"""Asynchronous cache-first Redis load coordination."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from hashlib import sha256

from bluetape.cache import AsyncTTLCache

from ._async_provider import AsyncRedisProvider
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
from ._coordination import (
    _coordination_keys,
    _FlightState,
    _new_token,
    _parse_marker,
    _poll_delay,
    _validate_logical_key,
)
from ._envelope import ResultEnvelopeCodec

_sleep = asyncio.sleep
_jitter = random.random


def _clock() -> float:
    return asyncio.get_running_loop().time()


class AsyncRedisLoadCoordinator[V]:
    """Coordinate cache-owned asynchronous loads through bounded Redis leases."""

    def __init__(
        self,
        cache: AsyncTTLCache[str, V],
        provider: AsyncRedisProvider,
        codec: ResultEnvelopeCodec[V],
        *,
        options: RedisLoadOptions,
        observer: RedisCoordinationObserver | None = None,
    ) -> None:
        if not isinstance(cache, AsyncTTLCache):
            raise TypeError("cache must be an AsyncTTLCache")
        if not isinstance(provider, AsyncRedisProvider):
            raise TypeError("provider must be an AsyncRedisProvider")
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

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[str], Awaitable[V]],
        *,
        ttl: float | None = None,
    ) -> V:
        """Return a local hit or coordinate one bounded distributed async load."""
        _validate_logical_key(key)
        if not callable(loader):
            raise TypeError("loader must be callable")
        return await self._cache.get_or_load(
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
            mode=RedisMode.ASYNC,
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

    async def _cleanup_primary(
        self,
        lease_key: str,
        active_marker: bytes,
        primary: BaseException,
        state: _FlightState,
    ) -> None:
        cleanup = asyncio.create_task(
            self._provider.delete_if_value(lease_key, active_marker),
            name="bluetape-redis-owner-cleanup",
        )
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        try:
            cleanup.result()
        except BaseException:
            state.cleanup_failed = True
            primary.add_note("Redis owner cleanup also failed (cleanup-failure)")

    @staticmethod
    def _timeout(code: RedisCoordinationErrorCode) -> RedisCoordinationTimeoutError:
        return RedisCoordinationTimeoutError(code=code)

    async def _distributed_load(self, key: str, loader: Callable[[str], Awaitable[V]]) -> V:
        state = _FlightState(started_ns=time.perf_counter_ns())
        deadline = _clock() + self._options.wait_timeout
        lease_key, result_key = _coordination_keys(self._namespace_id, key)
        try:
            value, outcome = await self._run_flight(
                key,
                loader,
                state=state,
                deadline=deadline,
                lease_key=lease_key,
                result_key=result_key,
            )
        except asyncio.CancelledError:
            self._emit(
                state,
                outcome=RedisCoordinationOutcome.CANCELLED,
                error_code=None,
            )
            raise
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

    async def _run_flight(
        self,
        key: str,
        loader: Callable[[str], Awaitable[V]],
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
            acquired = await self._provider.set_if_absent(
                lease_key, active_marker, ttl=self._options.lease_ttl
            )
            if acquired:
                if _clock() >= deadline:
                    error = self._timeout(RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
                    await self._cleanup_primary(lease_key, active_marker, error, state)
                    raise error
                return await self._run_owner(
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
                snapshot = await self._provider.coordination_snapshot(
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
                await _sleep(cap * _jitter())

    async def _run_owner(
        self,
        key: str,
        loader: Callable[[str], Awaitable[V]],
        *,
        state: _FlightState,
        lease_key: str,
        result_key: str,
        active_marker: bytes,
        completion_marker: bytes,
        lease_deadline: float,
    ) -> tuple[V, RedisCoordinationOutcome]:
        try:
            value = await loader(key)
            if _clock() >= lease_deadline:
                return value, RedisCoordinationOutcome.LEASE_LOST
            encoded = self._codec.encode(active_marker[7:].decode("ascii"), value)
            if _clock() >= lease_deadline:
                return value, RedisCoordinationOutcome.LEASE_LOST
            published = await self._provider.publish_if_value(
                lease_key,
                active_marker,
                result_key=result_key,
                result_value=encoded,
                completion_value=completion_marker,
                ttl=self._options.result_ttl,
            )
        except BaseException as primary:
            await self._cleanup_primary(lease_key, active_marker, primary, state)
            raise
        if not published:
            return value, RedisCoordinationOutcome.LEASE_LOST
        return value, RedisCoordinationOutcome.LOADED
