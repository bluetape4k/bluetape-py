"""Deterministic entry-state tests for the asyncio cache."""

import asyncio
import inspect
import threading
from typing import get_type_hints

import pytest
from bluetape.cache import AsyncTTLCache

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
    assert list(inspect.signature(AsyncTTLCache.get).parameters) == ["self", "key"]
    assert list(inspect.signature(AsyncTTLCache.set).parameters) == ["self", "key", "value", "ttl"]
    assert (
        inspect.signature(AsyncTTLCache.set).parameters["ttl"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert inspect.signature(AsyncTTLCache.set).parameters["ttl"].default is None
    assert list(inspect.signature(AsyncTTLCache.invalidate).parameters) == ["self", "key"]
    assert list(inspect.signature(AsyncTTLCache.clear).parameters) == ["self"]
    assert list(inspect.signature(AsyncTTLCache.stats).parameters) == ["self"]
    assert list(inspect.signature(AsyncTTLCache.size).parameters) == ["self"]
    assert get_type_hints(AsyncTTLCache.get)["return"].__name__ == "V"
    assert get_type_hints(AsyncTTLCache.set)["ttl"] == float | None
    assert get_type_hints(AsyncTTLCache.invalidate)["return"] is bool
    assert get_type_hints(AsyncTTLCache.size)["return"] is int


@pytest.mark.asyncio
async def test_set_get_preserves_none_and_mutable_identity() -> None:
    cache = AsyncTTLCache[str, object](default_ttl=1, max_size=2, clock=FakeClock())
    mutable: list[str] = []

    await cache.set("none", None)
    await cache.set("mutable", mutable)

    assert await cache.get("none") is None
    assert await cache.get("mutable") is mutable


@pytest.mark.asyncio
async def test_get_missing_and_unhashable_keys_preserve_native_errors() -> None:
    cache = AsyncTTLCache[str, object](default_ttl=1, max_size=2, clock=FakeClock())

    with pytest.raises(KeyError) as missing:
        await cache.get("missing")
    assert missing.value.args == ("missing",)

    with pytest.raises(TypeError, match="unhashable type: 'list'"):
        await cache.get([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unhashable type: 'list'"):
        await cache.set([], object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_default_and_per_entry_ttl_expire_at_exact_tick() -> None:
    clock = FakeClock(10)
    cache = AsyncTTLCache[str, str](default_ttl=10e-9, max_size=2, clock=clock)
    await cache.set("default", "a")
    await cache.set("explicit", "b", ttl=20e-9)

    clock.now_ns = 19
    assert await cache.get("default") == "a"
    clock.now_ns = 20
    with pytest.raises(KeyError):
        await cache.get("default")
    assert await cache.get("explicit") == "b"
    clock.now_ns = 30
    with pytest.raises(KeyError):
        await cache.get("explicit")


@pytest.mark.asyncio
async def test_clock_rollback_is_clamped() -> None:
    clock = FakeClock(100)
    cache = AsyncTTLCache[str, str](default_ttl=10e-9, max_size=1, clock=clock)
    await cache.set("key", "value")

    clock.now_ns = 105
    assert await cache.get("key") == "value"
    clock.now_ns = 1
    await cache.set("key", "new", ttl=5e-9)
    clock.now_ns = 104
    assert await cache.get("key") == "new"
    clock.now_ns = 110
    with pytest.raises(KeyError):
        await cache.get("key")


@pytest.mark.asyncio
async def test_each_public_state_operation_samples_clock_once() -> None:
    clock = CountingClock()
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=1, clock=clock)

    before = clock.calls
    await cache.set("key", 1)
    assert clock.calls == before + 1
    before = clock.calls
    await cache.get("key")
    assert clock.calls == before + 1
    before = clock.calls
    await cache.invalidate("missing")
    assert clock.calls == before + 1
    before = clock.calls
    await cache.clear()
    assert clock.calls == before + 1
    before = clock.calls
    await cache.stats()
    assert clock.calls == before + 1
    before = clock.calls
    await cache.size()
    assert clock.calls == before + 1


@pytest.mark.asyncio
async def test_successful_access_and_overwrite_move_entry_to_mru() -> None:
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=2, clock=FakeClock())
    await cache.set("a", 1)
    await cache.set("b", 2)
    assert await cache.get("a") == 1
    await cache.set("c", 3)
    with pytest.raises(KeyError):
        await cache.get("b")

    await cache.set("a", 10)
    await cache.set("d", 4)
    with pytest.raises(KeyError):
        await cache.get("c")
    assert await cache.get("a") == 10


@pytest.mark.asyncio
async def test_insert_purges_expired_before_evicting_live_lru() -> None:
    clock = FakeClock()
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=2, clock=clock)
    await cache.set("expired", 1, ttl=1e-9)
    await cache.set("live", 2)

    clock.now_ns = 1
    await cache.set("new", 3)

    assert await cache.get("live") == 2
    assert await cache.get("new") == 3
    assert (await cache.stats()).expirations == 1
    assert (await cache.stats()).evictions == 0


@pytest.mark.asyncio
async def test_growing_write_compacts_expiry_heap_after_push() -> None:
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=2, clock=FakeClock())
    for value in range(5):
        await cache.set("key", value)
        assert len(cache._state.expiry_heap) <= 4

    assert len(cache._state.expiry_heap) == 1
    assert await cache.get("key") == 4


@pytest.mark.asyncio
async def test_invalidate_result_clear_and_stats_lifetime() -> None:
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=1, clock=FakeClock())
    await cache.set("a", 1)
    assert await cache.get("a") == 1
    assert await cache.invalidate("a") is True
    assert await cache.invalidate("a") is False
    await cache.set("b", 2)
    await cache.set("c", 3)
    with pytest.raises(KeyError):
        await cache.get("missing")

    before = await cache.stats()
    await cache.clear()
    after = await cache.stats()

    assert (before.hits, before.misses, before.evictions, before.invalidations) == (1, 1, 1, 1)
    assert after == before
    assert await cache.size() == 0


@pytest.mark.asyncio
async def test_size_reports_only_live_entries() -> None:
    clock = FakeClock()
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=2, clock=clock)
    await cache.set("short", 1, ttl=1e-9)
    await cache.set("long", 2)
    clock.now_ns = 1

    assert await cache.size() == 1
    assert (await cache.stats()).expirations == 1


@pytest.mark.asyncio
async def test_expiry_and_eviction_metadata_remain_bounded() -> None:
    clock = FakeClock()
    cache = AsyncTTLCache[str, int](default_ttl=1e-9, max_size=2, clock=clock)
    for value in range(20):
        await cache.set("same", value)
        assert len(cache._state.expiry_heap) <= 2 * cache._max_size

    clock.now_ns = 1
    assert await cache.size() == 0
    assert cache._state.key_versions == {}

    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)
    assert "a" not in cache._state.key_versions
    assert await cache.invalidate("b") is True
    assert "b" not in cache._state.key_versions


@pytest.mark.asyncio
async def test_first_public_use_binds_event_loop() -> None:
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=1)
    loop = asyncio.get_running_loop()

    await cache.stats()

    assert cache._loop is loop
    assert cache._lock is not None


def test_second_event_loop_is_rejected() -> None:
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=1)
    asyncio.run(cache.stats())

    with pytest.raises(RuntimeError, match=r"^AsyncTTLCache is bound to a different event loop$"):
        asyncio.run(cache.stats())


def test_simultaneous_first_use_has_one_winning_loop() -> None:
    cache = AsyncTTLCache[str, int](default_ttl=1, max_size=1)
    barrier = threading.Barrier(2)
    results: list[str] = []
    result_lock = threading.Lock()

    async def use_cache() -> None:
        await asyncio.to_thread(barrier.wait, 2)
        await cache.stats()

    def runner() -> None:
        try:
            asyncio.run(use_cache())
        except RuntimeError as error:
            outcome = str(error)
        else:
            outcome = "winner"
        with result_lock:
            results.append(outcome)

    threads = [threading.Thread(target=runner) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert all(not thread.is_alive() for thread in threads)
    finally:
        barrier.abort()
        for thread in threads:
            thread.join(timeout=1)

    assert sorted(results) == [
        "AsyncTTLCache is bound to a different event loop",
        "winner",
    ]
