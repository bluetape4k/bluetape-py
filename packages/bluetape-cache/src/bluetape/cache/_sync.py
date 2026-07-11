"""Synchronous cache implementation."""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from threading import Condition, RLock, get_ident, local
from typing import Generic, TypeVar, cast

from bluetape.cache._core import (
    CacheLoadLimitError,
    CacheStats,
    RecursiveLoadError,
    _CacheState,
    _positive_int,
    _require_callable,
    _ttl_ns,
)

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")
_UNSET = object()


@dataclass(slots=True, eq=False, repr=False)
class _SyncFlight[K: Hashable, V]:
    key: K
    epoch: int
    version: int
    ttl_ns: int
    owner_thread: int
    condition: Condition
    terminal: bool = False
    superseded: bool = False
    result: V | object = _UNSET
    error: BaseException | None = None


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
        self._active_flights: dict[K, _SyncFlight[K, V]] = {}
        self._owned_flights: set[_SyncFlight[K, V]] = set()
        self._loader_scope = local()
        self._state = _CacheState[K, V](self._max_size)

    def _owned_keys(self) -> set[K]:
        return {flight.key for flight in self._owned_flights}

    def _now(self) -> int:
        return self._state.clamp_tick(self._clock())

    def get(self, key: K) -> V:
        with self._lock:
            return self._state.get(key, now=self._now(), owned_keys=self._owned_keys())

    def set(self, key: K, value: V, *, ttl: float | None = None) -> None:
        ttl_ns = self._default_ttl_ns if ttl is None else _ttl_ns(ttl, "ttl")
        with self._lock:
            self._supersede(key)
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
                on_supersede=self._supersede,
            )

    def clear(self) -> None:
        with self._lock:
            self._now()
            for flight in self._active_flights.values():
                flight.superseded = True
            self._active_flights.clear()
            self._state.clear(owned_keys=self._owned_keys())

    def get_or_load(
        self,
        key: K,
        loader: Callable[[K], V],
        *,
        ttl: float | None = None,
    ) -> V:
        token = (id(self), key)
        tokens = self._loader_tokens()
        if token in tokens:
            raise RecursiveLoadError("recursive load for the same cache key")

        ttl_ns = self._default_ttl_ns if ttl is None else _ttl_ns(ttl, "ttl")
        with self._lock:
            try:
                return self._state.get(key, now=self._now(), owned_keys=self._owned_keys())
            except KeyError:
                pass

            flight = self._active_flights.get(key)
            if flight is not None:
                self._state.coalesced_waiters += 1
                flight.condition.wait_for(lambda: flight.terminal)
                return self._flight_outcome(flight)

            if len(self._owned_flights) >= self._max_inflight:
                self._state.load_rejections += 1
                raise CacheLoadLimitError("maximum in-flight cache loads reached")

            flight = _SyncFlight[K, V](
                key=key,
                epoch=self._state.clear_epoch,
                version=self._state.version(key),
                ttl_ns=ttl_ns,
                owner_thread=get_ident(),
                condition=Condition(self._lock),
            )
            self._active_flights[key] = flight
            self._owned_flights.add(flight)
            self._state.loads += 1

        result: V | object = _UNSET
        error: BaseException | None = None
        tokens.add(token)
        try:
            result = loader(key)
        except BaseException as caught:
            error = caught
        finally:
            tokens.remove(token)

        self._finish_flight(flight, result=result, error=error)
        return self._flight_outcome(flight)

    def stats(self) -> CacheStats:
        with self._lock:
            return self._state.stats(
                now=self._now(),
                owned_keys=self._owned_keys(),
                inflight_loads=len(self._owned_flights),
                superseded_loads=sum(flight.superseded for flight in self._owned_flights),
            )

    def __len__(self) -> int:
        with self._lock:
            return self._state.size(now=self._now(), owned_keys=self._owned_keys())

    def _loader_tokens(self) -> set[tuple[int, K]]:
        tokens = getattr(self._loader_scope, "tokens", None)
        if tokens is None:
            tokens = set()
            self._loader_scope.tokens = tokens
        return tokens

    def _supersede(self, key: K) -> set[K]:
        flight = self._active_flights.pop(key, None)
        if flight is not None:
            flight.superseded = True
        return self._owned_keys()

    def _finish_flight(
        self,
        flight: _SyncFlight[K, V],
        *,
        result: V | object,
        error: BaseException | None,
    ) -> None:
        with self._lock:
            can_publish = (
                error is None
                and result is not _UNSET
                and not flight.superseded
                and self._state.clear_epoch == flight.epoch
                and self._state.version(flight.key) == flight.version
                and self._active_flights.get(flight.key) is flight
            )
            if can_publish:
                self._state.store(
                    flight.key,
                    cast(V, result),
                    ttl_ns=flight.ttl_ns,
                    now=self._now(),
                    owned_keys=self._owned_keys(),
                )
            if error is not None:
                self._state.load_failures += 1
            flight.result = result
            flight.error = error
            flight.terminal = True
            if self._active_flights.get(flight.key) is flight:
                del self._active_flights[flight.key]
            self._owned_flights.discard(flight)
            self._state.drop_unused_version(flight.key, owned_keys=self._owned_keys())
            flight.condition.notify_all()

    @staticmethod
    def _flight_outcome(flight: _SyncFlight[K, V]) -> V:
        if flight.error is not None:
            raise flight.error
        if flight.result is _UNSET:  # pragma: no cover - internal terminal invariant
            raise RuntimeError("cache flight completed without an outcome")
        return cast(V, flight.result)
