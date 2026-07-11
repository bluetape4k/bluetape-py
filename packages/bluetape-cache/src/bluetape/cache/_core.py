"""Shared cache contracts and validation."""

import heapq
import math
from collections import OrderedDict
from collections.abc import Callable, Hashable, Set
from dataclasses import dataclass


def _require_callable[F: Callable[..., object]](value: F | object, parameter: str) -> F:
    if not callable(value):
        raise TypeError(f"{parameter} must be callable")
    return value


def _ttl_ns(value: float, parameter: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{parameter} must be a finite positive number")
    if value <= 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError(f"{parameter} must be a finite positive number")
    if isinstance(value, int):
        nanoseconds = value * 1_000_000_000
    else:
        numerator, denominator = value.as_integer_ratio()
        nanoseconds = (numerator * 1_000_000_000) // denominator
    if nanoseconds < 1:
        raise ValueError(f"{parameter} must be at least one nanosecond")
    return nanoseconds


def _positive_int(value: int, parameter: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{parameter} must be an integer")
    if value < 1:
        raise ValueError(f"{parameter} must be greater than 0")
    return value


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Immutable snapshot of cache activity counters."""

    hits: int
    misses: int
    loads: int
    load_failures: int
    load_rejections: int
    coalesced_waiters: int
    evictions: int
    expirations: int
    invalidations: int
    inflight_loads: int
    abandoned_loads: int
    superseded_loads: int


class RecursiveLoadError(RuntimeError):
    """Raised when a loader recursively requests the same cache key."""


class CacheLoadLimitError(RuntimeError):
    """Raised when the cache cannot admit another owned load."""


@dataclass(slots=True)
class _Entry[V]:
    value: V
    expires_at: int
    version: int


class _CacheState[K: Hashable, V]:
    """Pure entry, expiry, recency, generation, and counter state."""

    def __init__(self, max_size: int) -> None:
        self.max_size = max_size
        self.entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self.expiry_heap: list[tuple[int, int, K, int]] = []
        self.key_versions: dict[K, int] = {}
        self.clear_epoch = 0
        self.last_tick = 0
        self.sequence = 0
        self.hits = 0
        self.misses = 0
        self.loads = 0
        self.load_failures = 0
        self.load_rejections = 0
        self.coalesced_waiters = 0
        self.evictions = 0
        self.expirations = 0
        self.invalidations = 0
        self.abandoned_loads = 0
        self.superseded_loads = 0

    def clamp_tick(self, tick: int) -> int:
        self.last_tick = max(self.last_tick, tick)
        return self.last_tick

    def bump_version(self, key: K) -> int:
        version = self.key_versions.get(key, 0) + 1
        self.key_versions[key] = version
        return version

    def drop_unused_version(self, key: K, *, owned_keys: Set[K]) -> None:
        if key not in self.entries and key not in owned_keys:
            self.key_versions.pop(key, None)

    def purge_expired(self, now: int, *, owned_keys: Set[K]) -> None:
        while self.expiry_heap and self.expiry_heap[0][0] <= now:
            _, _, key, version = heapq.heappop(self.expiry_heap)
            entry = self.entries.get(key)
            if entry is None or entry.version != version:
                continue
            del self.entries[key]
            self.expirations += 1
            self.drop_unused_version(key, owned_keys=owned_keys)

    def get(self, key: K, *, now: int, owned_keys: Set[K]) -> V:
        self.purge_expired(now, owned_keys=owned_keys)
        try:
            entry = self.entries[key]
        except KeyError:
            self.misses += 1
            raise KeyError(key) from None
        self.entries.move_to_end(key)
        self.hits += 1
        return entry.value

    def store(
        self,
        key: K,
        value: V,
        *,
        ttl_ns: int,
        now: int,
        owned_keys: Set[K],
    ) -> None:
        self.purge_expired(now, owned_keys=owned_keys)
        version = self.bump_version(key)
        expires_at = now + ttl_ns
        self.entries[key] = _Entry(value=value, expires_at=expires_at, version=version)
        self.entries.move_to_end(key)
        self.sequence += 1
        heapq.heappush(self.expiry_heap, (expires_at, self.sequence, key, version))
        while len(self.entries) > self.max_size:
            evicted_key, _ = self.entries.popitem(last=False)
            self.evictions += 1
            self.drop_unused_version(evicted_key, owned_keys=owned_keys)
        if len(self.expiry_heap) > 2 * self.max_size:
            self.rebuild_expiry_heap()

    def rebuild_expiry_heap(self) -> None:
        rebuilt: list[tuple[int, int, K, int]] = []
        for key, entry in self.entries.items():
            self.sequence += 1
            rebuilt.append((entry.expires_at, self.sequence, key, entry.version))
        heapq.heapify(rebuilt)
        self.expiry_heap = rebuilt

    def invalidate(
        self,
        key: K,
        *,
        now: int,
        on_supersede: Callable[[K], Set[K]],
    ) -> bool:
        owned_keys = on_supersede(key)
        self.purge_expired(now, owned_keys=owned_keys)
        entry = self.entries.pop(key, None)
        self.bump_version(key)
        if entry is not None:
            self.invalidations += 1
        self.drop_unused_version(key, owned_keys=owned_keys)
        return entry is not None

    def clear(self, *, owned_keys: Set[K]) -> None:
        self.clear_epoch += 1
        self.entries.clear()
        self.expiry_heap.clear()
        self.key_versions = {
            key: version for key, version in self.key_versions.items() if key in owned_keys
        }

    def size(self, *, now: int, owned_keys: Set[K]) -> int:
        self.purge_expired(now, owned_keys=owned_keys)
        return len(self.entries)

    def stats(self, *, now: int, owned_keys: Set[K], inflight_loads: int) -> CacheStats:
        self.purge_expired(now, owned_keys=owned_keys)
        return CacheStats(
            hits=self.hits,
            misses=self.misses,
            loads=self.loads,
            load_failures=self.load_failures,
            load_rejections=self.load_rejections,
            coalesced_waiters=self.coalesced_waiters,
            evictions=self.evictions,
            expirations=self.expirations,
            invalidations=self.invalidations,
            inflight_loads=inflight_loads,
            abandoned_loads=self.abandoned_loads,
            superseded_loads=self.superseded_loads,
        )
