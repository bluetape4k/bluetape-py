"""Asynchronous cache implementation."""

import asyncio
import time
from collections.abc import Callable, Hashable
from threading import Lock
from typing import Generic, TypeVar

from bluetape.cache._core import CacheStats, _CacheState, _positive_int, _require_callable, _ttl_ns

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


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
        self._active_flights: dict[K, object] = {}
        self._owned_flights: set[object] = set()
        self._state = _CacheState[K, V](self._max_size)

    def _owned_keys(self) -> set[K]:
        return set(self._active_flights)

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
                on_supersede=lambda _: self._owned_keys(),
            )

    async def clear(self) -> None:
        async with self._bound_lock():
            self._now()
            self._state.clear(owned_keys=self._owned_keys())

    async def stats(self) -> CacheStats:
        async with self._bound_lock():
            return self._state.stats(
                now=self._now(),
                owned_keys=self._owned_keys(),
                inflight_loads=len(self._owned_flights),
            )

    async def size(self) -> int:
        async with self._bound_lock():
            return self._state.size(now=self._now(), owned_keys=self._owned_keys())
