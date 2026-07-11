"""Synchronous cache implementation."""

import time
from collections.abc import Callable, Hashable
from threading import RLock
from typing import Generic, TypeVar

from bluetape.cache._core import CacheStats, _CacheState, _positive_int, _require_callable, _ttl_ns

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class TTLCache(Generic[K, V]):  # noqa: UP046 - public generics intentionally use TypeVar
    """Bounded synchronous local cache."""

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
        self._lock = RLock()
        self._active_flights: dict[K, object] = {}
        self._owned_flights: set[object] = set()
        self._state = _CacheState[K, V](self._max_size)

    def _owned_keys(self) -> set[K]:
        return set(self._active_flights)

    def _now(self) -> int:
        return self._state.clamp_tick(self._clock())

    def get(self, key: K) -> V:
        with self._lock:
            return self._state.get(key, now=self._now(), owned_keys=self._owned_keys())

    def set(self, key: K, value: V, *, ttl: float | None = None) -> None:
        ttl_ns = self._default_ttl_ns if ttl is None else _ttl_ns(ttl, "ttl")
        with self._lock:
            self._state.store(
                key,
                value,
                ttl_ns=ttl_ns,
                now=self._now(),
                owned_keys=self._owned_keys(),
            )

    def invalidate(self, key: K) -> bool:
        with self._lock:
            return self._state.invalidate(
                key,
                now=self._now(),
                on_supersede=lambda _: self._owned_keys(),
            )

    def clear(self) -> None:
        with self._lock:
            self._now()
            self._state.clear(owned_keys=self._owned_keys())

    def stats(self) -> CacheStats:
        with self._lock:
            return self._state.stats(
                now=self._now(),
                owned_keys=self._owned_keys(),
                inflight_loads=len(self._owned_flights),
            )

    def __len__(self) -> int:
        with self._lock:
            return self._state.size(now=self._now(), owned_keys=self._owned_keys())
