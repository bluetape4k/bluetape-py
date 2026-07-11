"""Asynchronous cache implementation."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Hashable
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar, cast

from bluetape.cache._core import (
    CacheStats,
    RecursiveLoadError,
    _CacheState,
    _positive_int,
    _require_callable,
    _ttl_ns,
)

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(slots=True, eq=False, repr=False)
class _AsyncFlight[K: Hashable, V]:
    key: K
    epoch: int
    version: int
    ttl_ns: int
    sequence: int
    task: asyncio.Task[V] | None = None
    waiters: int = 0
    abandoned: bool = False
    superseded: bool = False


_LOAD_SCOPE: ContextVar[frozenset[tuple[int, Hashable]]] = ContextVar(
    "bluetape_cache_load_scope",
    default=frozenset(),
)


class AsyncTTLCache(Generic[K, V]):  # noqa: UP046 - public generics intentionally use TypeVar
    """Bounded asyncio local cache."""

    def __init__(
        self,
        *,
        default_ttl: float,
        max_size: int,
        max_inflight: int | None = None,
        clock: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._default_ttl_ns = _ttl_ns(default_ttl, "default_ttl")
        self._max_size = _positive_int(max_size, "max_size")
        self._max_inflight = (
            self._max_size if max_inflight is None else _positive_int(max_inflight, "max_inflight")
        )
        self._clock = _require_callable(clock, "clock")
        self._loop_guard = Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock: asyncio.Lock | None = None
        self._active_flights: dict[K, _AsyncFlight[K, V]] = {}
        self._owned_flights: set[_AsyncFlight[K, V]] = set()
        self._flight_sequence = 0
        self._state = _CacheState[K, V](self._max_size)

    def _owned_keys(self) -> set[K]:
        return {flight.key for flight in self._owned_flights}

    def _require_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        with self._loop_guard:
            if self._loop is None:
                self._loop = loop
                self._lock = asyncio.Lock()
            elif self._loop is not loop:
                raise RuntimeError("AsyncTTLCache is bound to a different event loop")
        return loop

    def _bound_lock(self) -> asyncio.Lock:
        self._require_loop()
        lock = self._lock
        if lock is None:  # pragma: no cover - established atomically by _require_loop
            raise RuntimeError("AsyncTTLCache event loop lock was not initialized")
        return lock

    def _now(self) -> int:
        return self._state.clamp_tick(self._clock())

    async def get(self, key: K) -> V:
        async with self._bound_lock():
            return self._state.get(key, now=self._now(), owned_keys=self._owned_keys())

    async def set(self, key: K, value: V, *, ttl: float | None = None) -> None:
        ttl_ns = self._default_ttl_ns if ttl is None else _ttl_ns(ttl, "ttl")
        async with self._bound_lock():
            self._supersede(key)
            self._state.store(
                key,
                value,
                ttl_ns=ttl_ns,
                now=self._now(),
                owned_keys=self._owned_keys(),
            )

    async def invalidate(self, key: K) -> bool:
        async with self._bound_lock():
            return self._state.invalidate(
                key,
                now=self._now(),
                on_supersede=self._supersede,
            )

    async def clear(self) -> None:
        async with self._bound_lock():
            self._now()
            for flight in self._active_flights.values():
                flight.superseded = True
            self._active_flights.clear()
            self._state.clear(owned_keys=self._owned_keys())

    async def get_or_load(
        self,
        key: K,
        loader: Callable[[K], Awaitable[V]],
        *,
        ttl: float | None = None,
    ) -> V:
        scope_key = (id(self), key)
        if scope_key in _LOAD_SCOPE.get():
            raise RecursiveLoadError("recursive load for the same cache key")

        ttl_ns = self._default_ttl_ns if ttl is None else _ttl_ns(ttl, "ttl")
        lock = self._bound_lock()
        async with lock:
            try:
                return self._state.get(key, now=self._now(), owned_keys=self._owned_keys())
            except KeyError:
                pass

            flight = self._active_flights.get(key)
            if flight is not None:
                flight.waiters += 1
                self._state.coalesced_waiters += 1
            else:
                self._flight_sequence += 1
                flight = _AsyncFlight[K, V](
                    key=key,
                    epoch=self._state.clear_epoch,
                    version=self._state.version(key),
                    ttl_ns=ttl_ns,
                    sequence=self._flight_sequence,
                    waiters=1,
                )
                self._active_flights[key] = flight
                self._owned_flights.add(flight)
                self._state.loads += 1
                flight.task = asyncio.create_task(
                    self._run_loader(flight, loader),
                    name=f"bluetape-cache-load-{flight.sequence}",
                )

        task = flight.task
        if task is None:  # pragma: no cover - task is installed before lock release
            raise RuntimeError("cache flight task was not initialized")
        try:
            return await task
        finally:
            async with lock:
                flight.waiters -= 1

    async def stats(self) -> CacheStats:
        async with self._bound_lock():
            return self._state.stats(
                now=self._now(),
                owned_keys=self._owned_keys(),
                inflight_loads=len(self._owned_flights),
                superseded_loads=sum(flight.superseded for flight in self._owned_flights),
            )

    async def size(self) -> int:
        async with self._bound_lock():
            return self._state.size(now=self._now(), owned_keys=self._owned_keys())

    def _supersede(self, key: K) -> set[K]:
        flight = self._active_flights.pop(key, None)
        if flight is not None:
            flight.superseded = True
        return self._owned_keys()

    def _can_publish(self, flight: _AsyncFlight[K, V]) -> bool:
        return (
            not flight.abandoned
            and not flight.superseded
            and self._state.clear_epoch == flight.epoch
            and self._state.version(flight.key) == flight.version
            and self._active_flights.get(flight.key) is flight
        )

    def _complete_async_flight(
        self,
        flight: _AsyncFlight[K, V],
        *,
        result: V | None,
        publish: bool,
    ) -> None:
        try:
            if publish:
                self._state.store(
                    flight.key,
                    cast(V, result),
                    ttl_ns=flight.ttl_ns,
                    now=self._now(),
                    owned_keys=self._owned_keys(),
                )
        finally:
            if self._active_flights.get(flight.key) is flight:
                del self._active_flights[flight.key]
            self._owned_flights.discard(flight)
            self._state.drop_unused_version(flight.key, owned_keys=self._owned_keys())

    async def _run_loader(
        self,
        flight: _AsyncFlight[K, V],
        loader: Callable[[K], Awaitable[V]],
    ) -> V:
        token = _LOAD_SCOPE.set(_LOAD_SCOPE.get() | {(id(self), flight.key)})
        try:
            try:
                result = await loader(flight.key)
            except BaseException:
                async with self._bound_lock():
                    self._state.load_failures += 1
                    self._complete_async_flight(flight, result=None, publish=False)
                raise
            else:
                async with self._bound_lock():
                    self._complete_async_flight(
                        flight,
                        result=result,
                        publish=self._can_publish(flight),
                    )
                return result
        finally:
            _LOAD_SCOPE.reset(token)
