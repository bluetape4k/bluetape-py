"""Deterministic entry-state tests for the synchronous cache."""

import inspect
from typing import get_type_hints

import pytest
from bluetape.cache import TTLCache

from ._support import FakeClock


class CountingClock(FakeClock):
    """Record how often a public operation samples the clock."""

    def __init__(self, now_ns: int = 0) -> None:
        super().__init__(now_ns)
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return super().__call__()


def test_non_loading_state_method_signatures_match_public_contract() -> None:
    assert list(inspect.signature(TTLCache.get).parameters) == ["self", "key"]
    assert list(inspect.signature(TTLCache.set).parameters) == ["self", "key", "value", "ttl"]
    assert inspect.signature(TTLCache.set).parameters["ttl"].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(TTLCache.set).parameters["ttl"].default is None
    assert list(inspect.signature(TTLCache.invalidate).parameters) == ["self", "key"]
    assert list(inspect.signature(TTLCache.clear).parameters) == ["self"]
    assert list(inspect.signature(TTLCache.stats).parameters) == ["self"]
    assert list(inspect.signature(TTLCache.__len__).parameters) == ["self"]
    assert get_type_hints(TTLCache.get)["return"].__name__ == "V"
    assert get_type_hints(TTLCache.set)["ttl"] == float | None
    assert get_type_hints(TTLCache.invalidate)["return"] is bool
    assert get_type_hints(TTLCache.__len__)["return"] is int


def test_set_get_preserves_none_and_mutable_identity() -> None:
    cache = TTLCache[str, object](default_ttl=1, max_size=2, clock=FakeClock())
    mutable: list[str] = []

    cache.set("none", None)
    cache.set("mutable", mutable)

    assert cache.get("none") is None
    assert cache.get("mutable") is mutable


def test_get_missing_and_unhashable_keys_preserve_native_errors() -> None:
    cache = TTLCache[str, object](default_ttl=1, max_size=2, clock=FakeClock())

    with pytest.raises(KeyError) as missing:
        cache.get("missing")
    assert missing.value.args == ("missing",)

    with pytest.raises(TypeError, match="unhashable type: 'list'"):
        cache.get([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unhashable type: 'list'"):
        cache.set([], object())  # type: ignore[arg-type]


def test_default_and_per_entry_ttl_expire_at_exact_tick() -> None:
    clock = FakeClock(10)
    cache = TTLCache[str, str](default_ttl=10e-9, max_size=2, clock=clock)
    cache.set("default", "a")
    cache.set("explicit", "b", ttl=20e-9)

    clock.now_ns = 19
    assert cache.get("default") == "a"
    clock.now_ns = 20
    with pytest.raises(KeyError):
        cache.get("default")
    assert cache.get("explicit") == "b"
    clock.now_ns = 30
    with pytest.raises(KeyError):
        cache.get("explicit")


def test_clock_rollback_is_clamped() -> None:
    clock = FakeClock(100)
    cache = TTLCache[str, str](default_ttl=10e-9, max_size=1, clock=clock)
    cache.set("key", "value")

    clock.now_ns = 105
    assert cache.get("key") == "value"
    clock.now_ns = 1
    cache.set("key", "new", ttl=5e-9)
    clock.now_ns = 104
    assert cache.get("key") == "new"
    clock.now_ns = 110
    with pytest.raises(KeyError):
        cache.get("key")


def test_each_public_state_operation_samples_clock_once() -> None:
    clock = CountingClock()
    cache = TTLCache[str, int](default_ttl=1, max_size=1, clock=clock)

    operations = [
        lambda: cache.set("key", 1),
        lambda: cache.get("key"),
        lambda: cache.invalidate("missing"),
        cache.clear,
        cache.stats,
        lambda: len(cache),
    ]
    for operation in operations:
        before = clock.calls
        operation()
        assert clock.calls == before + 1


def test_successful_access_and_overwrite_move_entry_to_mru() -> None:
    cache = TTLCache[str, int](default_ttl=1, max_size=2, clock=FakeClock())
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)
    with pytest.raises(KeyError):
        cache.get("b")

    cache.set("a", 10)
    cache.set("d", 4)
    with pytest.raises(KeyError):
        cache.get("c")
    assert cache.get("a") == 10


def test_insert_purges_expired_before_evicting_live_lru() -> None:
    clock = FakeClock()
    cache = TTLCache[str, int](default_ttl=1, max_size=2, clock=clock)
    cache.set("expired", 1, ttl=1e-9)
    cache.set("live", 2)

    clock.now_ns = 1
    cache.set("new", 3)

    assert cache.get("live") == 2
    assert cache.get("new") == 3
    assert cache.stats().expirations == 1
    assert cache.stats().evictions == 0


def test_growing_write_compacts_expiry_heap_after_push() -> None:
    cache = TTLCache[str, int](default_ttl=1, max_size=2, clock=FakeClock())
    for value in range(5):
        cache.set("key", value)
        assert len(cache._state.expiry_heap) <= 4

    assert len(cache._state.expiry_heap) == 1
    assert cache.get("key") == 4


def test_invalidate_result_clear_and_stats_lifetime() -> None:
    cache = TTLCache[str, int](default_ttl=1, max_size=1, clock=FakeClock())
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert cache.invalidate("a") is True
    assert cache.invalidate("a") is False
    cache.set("b", 2)
    cache.set("c", 3)
    with pytest.raises(KeyError):
        cache.get("missing")

    before = cache.stats()
    cache.clear()
    after = cache.stats()

    assert (before.hits, before.misses, before.evictions, before.invalidations) == (1, 1, 1, 1)
    assert after == before
    assert len(cache) == 0


def test_size_reports_only_live_entries() -> None:
    clock = FakeClock()
    cache = TTLCache[str, int](default_ttl=1, max_size=2, clock=clock)
    cache.set("short", 1, ttl=1e-9)
    cache.set("long", 2)
    clock.now_ns = 1

    assert len(cache) == 1
    assert cache.stats().expirations == 1


def test_expiry_and_eviction_metadata_remain_bounded() -> None:
    clock = FakeClock()
    cache = TTLCache[str, int](default_ttl=1e-9, max_size=2, clock=clock)
    for value in range(20):
        cache.set("same", value)
        assert len(cache._state.expiry_heap) <= 2 * cache._max_size

    clock.now_ns = 1
    assert len(cache) == 0
    assert cache._state.key_versions == {}

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert "a" not in cache._state.key_versions
    assert cache.invalidate("b") is True
    assert "b" not in cache._state.key_versions
