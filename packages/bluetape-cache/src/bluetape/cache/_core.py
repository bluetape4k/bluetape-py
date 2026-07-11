"""Shared cache contracts and validation."""

import math
from dataclasses import dataclass


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
