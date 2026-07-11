"""Public contract tests for bluetape-cache."""

import inspect
import time
from collections.abc import Callable, Hashable
from dataclasses import FrozenInstanceError, fields
from typing import get_type_hints

import bluetape.cache as cache
import pytest

from ._support import FakeClock

EXPECTED_EXPORTS = [
    "TTLCache",
    "AsyncTTLCache",
    "CacheStats",
    "RecursiveLoadError",
    "CacheLoadLimitError",
]

EXPECTED_STAT_FIELDS = [
    "hits",
    "misses",
    "loads",
    "load_failures",
    "load_rejections",
    "coalesced_waiters",
    "evictions",
    "expirations",
    "invalidations",
    "inflight_loads",
    "abandoned_loads",
    "superseded_loads",
]

INVALID_TTLS = [
    (True, TypeError, "default_ttl must be a finite positive number"),
    ("1", TypeError, "default_ttl must be a finite positive number"),
    (float("nan"), ValueError, "default_ttl must be a finite positive number"),
    (float("inf"), ValueError, "default_ttl must be a finite positive number"),
    (float("-inf"), ValueError, "default_ttl must be a finite positive number"),
    (0.0, ValueError, "default_ttl must be a finite positive number"),
    (-1.0, ValueError, "default_ttl must be a finite positive number"),
    (0.5e-9, ValueError, "default_ttl must be at least one nanosecond"),
]

INVALID_MAX_SIZES = [
    (True, TypeError, "max_size must be an integer"),
    (1.0, TypeError, "max_size must be an integer"),
    ("1", TypeError, "max_size must be an integer"),
    (0, ValueError, "max_size must be greater than 0"),
    (-1, ValueError, "max_size must be greater than 0"),
]

INVALID_MAX_INFLIGHT = [
    (True, TypeError, "max_inflight must be an integer"),
    (1.0, TypeError, "max_inflight must be an integer"),
    ("1", TypeError, "max_inflight must be an integer"),
    (0, ValueError, "max_inflight must be greater than 0"),
    (-1, ValueError, "max_inflight must be greater than 0"),
]


def test_exact_exports_and_stats_shape() -> None:
    assert getattr(cache, "__all__", None) == EXPECTED_EXPORTS

    stats = cache.CacheStats(*range(len(EXPECTED_STAT_FIELDS)))
    assert [field.name for field in fields(stats)] == EXPECTED_STAT_FIELDS
    assert get_type_hints(cache.CacheStats) == dict.fromkeys(EXPECTED_STAT_FIELDS, int)
    assert not hasattr(stats, "__dict__")
    with pytest.raises(FrozenInstanceError):
        stats.hits = 99

    assert issubclass(cache.RecursiveLoadError, RuntimeError)
    assert issubclass(cache.CacheLoadLimitError, RuntimeError)


@pytest.mark.parametrize("cache_type", [cache.TTLCache, cache.AsyncTTLCache])
def test_cache_constructors_are_keyword_only(cache_type: type[object]) -> None:
    parameters = list(inspect.signature(cache_type).parameters.values())
    assert [parameter.name for parameter in parameters] == [
        "default_ttl",
        "max_size",
        "max_inflight",
        "clock",
    ]
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters)
    assert parameters[2].default is None
    assert parameters[3].default is time.monotonic_ns
    assert get_type_hints(cache_type.__init__) == {
        "default_ttl": float,
        "max_size": int,
        "max_inflight": int | None,
        "clock": Callable[[], int],
        "return": type(None),
    }

    type_parameters = cache_type.__parameters__
    assert [parameter.__name__ for parameter in type_parameters] == ["K", "V"]
    assert type_parameters[0].__bound__ is Hashable
    assert type_parameters[1].__bound__ is None

    with pytest.raises(TypeError):
        cache_type(1.0, 2)
    cache_type(default_ttl=1.0, max_size=2)


@pytest.mark.parametrize("cache_type", [cache.TTLCache, cache.AsyncTTLCache])
@pytest.mark.parametrize("clock", [None, 0, "clock", object()])
def test_constructor_rejects_non_callable_clock(
    cache_type: type[object],
    clock: object,
) -> None:
    with pytest.raises(TypeError, match=r"^clock must be callable$"):
        cache_type(default_ttl=1.0, max_size=1, clock=clock)


@pytest.mark.parametrize("cache_type", [cache.TTLCache, cache.AsyncTTLCache])
@pytest.mark.parametrize(("value", "error", "message"), INVALID_TTLS)
def test_constructor_rejects_invalid_default_ttl(
    cache_type: type[object],
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=f"^{message}$"):
        cache_type(default_ttl=value, max_size=1)


@pytest.mark.parametrize("cache_type", [cache.TTLCache, cache.AsyncTTLCache])
@pytest.mark.parametrize("value", [1e300, 10**400])
def test_constructor_accepts_large_finite_default_ttl(
    cache_type: type[object],
    value: int | float,
) -> None:
    instance = cache_type(default_ttl=value, max_size=1)
    if isinstance(value, int):
        expected_ns = value * 1_000_000_000
    else:
        numerator, denominator = value.as_integer_ratio()
        expected_ns = (numerator * 1_000_000_000) // denominator

    assert instance._default_ttl_ns == expected_ns


@pytest.mark.parametrize("cache_type", [cache.TTLCache, cache.AsyncTTLCache])
@pytest.mark.parametrize(("value", "error", "message"), INVALID_MAX_SIZES)
def test_constructor_rejects_invalid_max_size(
    cache_type: type[object],
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=f"^{message}$"):
        cache_type(default_ttl=1.0, max_size=value)


@pytest.mark.parametrize("cache_type", [cache.TTLCache, cache.AsyncTTLCache])
@pytest.mark.parametrize(("value", "error", "message"), INVALID_MAX_INFLIGHT)
def test_constructor_rejects_invalid_max_inflight(
    cache_type: type[object],
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=f"^{message}$"):
        cache_type(default_ttl=1.0, max_size=2, max_inflight=value)


def test_valid_constructor_stores_state_and_resolves_default_max_inflight() -> None:
    clock = FakeClock(42)
    sync_cache = cache.TTLCache[str, object](default_ttl=1.25, max_size=7, clock=clock)
    async_cache = cache.AsyncTTLCache[str, object](
        default_ttl=2,
        max_size=11,
        max_inflight=3,
        clock=clock,
    )

    assert sync_cache._clock is clock
    assert sync_cache._default_ttl_ns == 1_250_000_000
    assert sync_cache._max_size == 7
    assert sync_cache._max_inflight == 7
    assert sync_cache._active_flights == {}
    assert sync_cache._owned_flights == set()
    assert sync_cache._lock.acquire(blocking=False)
    sync_cache._lock.release()

    assert async_cache._clock is clock
    assert async_cache._default_ttl_ns == 2_000_000_000
    assert async_cache._max_size == 11
    assert async_cache._max_inflight == 3
    assert async_cache._active_flights == {}
    assert async_cache._owned_flights == set()
    assert async_cache._loop is None
    assert async_cache._lock is None
    assert not async_cache._loop_guard.locked()
