"""Deterministic entry-state tests for the asyncio cache."""

import asyncio
import inspect
import threading
from collections.abc import Awaitable, Callable
from typing import get_type_hints

import pytest
from bluetape.cache import AsyncTTLCache, CacheLoadLimitError, RecursiveLoadError

from ._support import FakeClock


class CountingClock(FakeClock):
    """Record how often a public operation samples the clock."""

    def __init__(self, now_ns: int = 0) -> None:
        super().__init__(now_ns)
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return super().__call__()


async def _cancel_and_gather[V](tasks: list[asyncio.Task[V]]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 1)


def _named_cache_tasks() -> list[asyncio.Task[object]]:
    return [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and task.get_name().startswith("bluetape-cache-load-")
    ]


async def _assert_no_named_cache_task() -> None:
    async with asyncio.timeout(1):
        while _named_cache_tasks():
            await asyncio.sleep(0)


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


def test_async_get_or_load_signature_matches_public_contract() -> None:
    parameters = inspect.signature(AsyncTTLCache.get_or_load).parameters

    assert list(parameters) == ["self", "key", "loader", "ttl"]
    assert parameters["ttl"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["ttl"].default is None
    hints = get_type_hints(AsyncTTLCache.get_or_load)
    assert (
        hints["loader"]
        == Callable[[AsyncTTLCache.__parameters__[0]], Awaitable[AsyncTTLCache.__parameters__[1]]]
    )
    assert hints["ttl"] == float | None
    assert hints["return"].__name__ == "V"


@pytest.mark.asyncio
async def test_async_same_key_uses_one_owner_loader_and_ttl() -> None:
    clock = FakeClock()
    cache = AsyncTTLCache[str, object](default_ttl=1, max_size=2, clock=clock)
    started = asyncio.Event()
    release = asyncio.Event()
    owner_value = object()
    calls: list[str] = []
    tasks: list[asyncio.Task[object]] = []

    async def owner_loader(key: str) -> object:
        calls.append(key)
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return owner_value

    async def unused_loader(_: str) -> object:
        pytest.fail("coalesced loader must not run")

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", owner_loader, ttl=10e-9)))
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(asyncio.create_task(cache.get_or_load("key", unused_loader, ttl=100)))
        async with asyncio.timeout(1):
            while (await cache.stats()).coalesced_waiters != 1:
                await asyncio.sleep(0)
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), 1)
    finally:
        release.set()
        await _cancel_and_gather(tasks)

    assert results == [owner_value, owner_value]
    assert calls == ["key"]
    clock.now_ns = 9
    assert await cache.get("key") is owner_value
    clock.now_ns = 10
    with pytest.raises(KeyError):
        await cache.get("key")


@pytest.mark.asyncio
async def test_async_different_key_loader_bodies_progress_together() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=2)
    both_started = asyncio.Event()
    started = 0
    tasks: list[asyncio.Task[str]] = []

    async def loader(key: str) -> str:
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), 1)
        return key

    try:
        tasks = [asyncio.create_task(cache.get_or_load(key, loader)) for key in ("a", "b")]
        await asyncio.wait_for(both_started.wait(), 1)
        results = await asyncio.wait_for(asyncio.gather(*tasks), 1)
    finally:
        both_started.set()
        await _cancel_and_gather(tasks)

    assert sorted(results) == ["a", "b"]


@pytest.mark.asyncio
async def test_async_loader_failure_is_shared_not_cached() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=2)
    started = asyncio.Event()
    release = asyncio.Event()
    failure = LookupError("original")
    tasks: list[asyncio.Task[str]] = []

    async def failing_loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        raise failure

    async def unused_loader(_: str) -> str:
        pytest.fail("coalesced loader must not run")

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", failing_loader)))
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(asyncio.create_task(cache.get_or_load("key", unused_loader)))
        async with asyncio.timeout(1):
            while (await cache.stats()).coalesced_waiters != 1:
                await asyncio.sleep(0)
        release.set()
        outcomes = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            1,
        )
    finally:
        release.set()
        await _cancel_and_gather(tasks)

    assert outcomes == [failure, failure]
    assert outcomes[0] is failure
    assert outcomes[1] is failure
    assert (await cache.stats()).load_failures == 1
    assert await cache.get_or_load("key", lambda _: asyncio.sleep(0, result="recovered")) == (
        "recovered"
    )


@pytest.mark.asyncio
async def test_async_owner_only_terminal_paths_cleanup() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1)
    failure = RuntimeError("failed")

    async def failing_loader(_: str) -> str:
        raise failure

    assert await cache.get_or_load("success", lambda _: asyncio.sleep(0, result="value")) == (
        "value"
    )
    with pytest.raises(RuntimeError) as caught:
        await cache.get_or_load("failure", failing_loader)
    assert caught.value is failure

    assert cache._active_flights == {}
    assert cache._owned_flights == set()
    assert "failure" not in cache._state.key_versions
    assert (await cache.stats()).inflight_loads == 0


@pytest.mark.asyncio
async def test_async_task_creation_failure_rolls_back_flight_and_recovers() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1, max_inflight=1)
    loop = asyncio.get_running_loop()
    original_factory = loop.get_task_factory()
    failure = RuntimeError("task factory rejected")
    loader_calls = 0

    async def loader(_: str) -> str:
        nonlocal loader_calls
        loader_calls += 1
        return "value"

    def rejecting_factory(
        _loop: asyncio.AbstractEventLoop,
        _coroutine: object,
        **_kwargs: object,
    ) -> asyncio.Task[object]:
        raise failure

    try:
        loop.set_task_factory(rejecting_factory)  # type: ignore[arg-type]
        with pytest.raises(RuntimeError) as caught:
            await cache.get_or_load("key", loader)
    finally:
        loop.set_task_factory(original_factory)

    assert caught.value is failure
    assert loader_calls == 0
    assert cache._active_flights == {}
    assert cache._owned_flights == set()
    assert "key" not in cache._state.key_versions
    stats = await cache.stats()
    assert stats.loads == 0
    assert stats.inflight_loads == 0
    assert await cache.get_or_load("key", loader) == "value"
    assert loader_calls == 1


@pytest.mark.asyncio
async def test_async_publication_failure_is_shared_and_always_cleans_flight() -> None:
    publication_failure = RuntimeError("publication clock failed")

    class PublicationFailingClock:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self) -> int:
            self.calls += 1
            if self.calls == 3:
                raise publication_failure
            return 0

    cache = AsyncTTLCache[str, str](
        default_ttl=1,
        max_size=1,
        max_inflight=1,
        clock=PublicationFailingClock(),
    )
    started = asyncio.Event()
    release = asyncio.Event()
    tasks: list[asyncio.Task[str]] = []

    async def loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return "value"

    async def unused_loader(_: str) -> str:
        pytest.fail("coalesced loader must not run")

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", loader)))
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(asyncio.create_task(cache.get_or_load("key", unused_loader)))
        async with asyncio.timeout(1):
            while cache._active_flights["key"].waiters != 2:
                await asyncio.sleep(0)
        release.set()
        outcomes = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            1,
        )
    finally:
        release.set()
        await _cancel_and_gather(tasks)

    assert outcomes == [publication_failure, publication_failure]
    assert outcomes[0] is publication_failure
    assert outcomes[1] is publication_failure
    assert cache._active_flights == {}
    assert cache._owned_flights == set()
    assert "key" not in cache._state.key_versions
    stats = await cache.stats()
    assert stats.load_failures == 0
    assert stats.inflight_loads == 0
    assert await cache.get_or_load("key", lambda _: asyncio.sleep(0, result="recovered")) == (
        "recovered"
    )


@pytest.mark.asyncio
async def test_inherited_child_task_same_key_recursion_is_rejected() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1)

    async def recursive_loader(key: str) -> str:
        child = asyncio.create_task(
            cache.get_or_load(key, lambda _: asyncio.sleep(0, result="unreachable"))
        )
        try:
            return await asyncio.wait_for(child, 1)
        finally:
            await _cancel_and_gather([child])

    with pytest.raises(RecursiveLoadError, match="recursive load for the same cache key"):
        await asyncio.wait_for(cache.get_or_load("key", recursive_loader), 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["set", "invalidate", "clear"])
async def test_async_mutations_prevent_stale_publication(mutation: str) -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=2)
    started = asyncio.Event()
    release = asyncio.Event()
    task: asyncio.Task[str] | None = None

    async def loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return "loaded"

    try:
        task = asyncio.create_task(cache.get_or_load("key", loader))
        await asyncio.wait_for(started.wait(), 1)
        if mutation == "set":
            await cache.set("key", "explicit")
        elif mutation == "invalidate":
            await cache.invalidate("key")
        else:
            await cache.clear()
        release.set()
        assert await asyncio.wait_for(task, 1) == "loaded"
    finally:
        release.set()
        if task is not None:
            await _cancel_and_gather([task])

    if mutation == "set":
        assert await cache.get("key") == "explicit"
    else:
        with pytest.raises(KeyError):
            await cache.get("key")
    assert cache._active_flights == {}
    assert cache._owned_flights == set()


@pytest.mark.asyncio
async def test_async_post_mutation_caller_uses_new_generation() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=2)
    old_started = asyncio.Event()
    old_release = asyncio.Event()
    new_started = asyncio.Event()
    tasks: list[asyncio.Task[str]] = []

    async def old_loader(_: str) -> str:
        old_started.set()
        await asyncio.wait_for(old_release.wait(), 1)
        return "old"

    async def new_loader(_: str) -> str:
        new_started.set()
        return "new"

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", old_loader)))
        await asyncio.wait_for(old_started.wait(), 1)
        assert await cache.invalidate("key") is False
        tasks.append(asyncio.create_task(cache.get_or_load("key", new_loader)))
        await asyncio.wait_for(new_started.wait(), 1)
        assert await asyncio.wait_for(tasks[1], 1) == "new"
        old_release.set()
        assert await asyncio.wait_for(tasks[0], 1) == "old"
    finally:
        old_release.set()
        await _cancel_and_gather(tasks)

    assert await cache.get("key") == "new"
    assert cache._active_flights == {}
    assert cache._owned_flights == set()


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_surviving_waiter_load() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1)
    started = asyncio.Event()
    release = asyncio.Event()
    tasks: list[asyncio.Task[str]] = []

    async def loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return "value"

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", loader)))
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(asyncio.create_task(cache.get_or_load("key", loader)))
        async with asyncio.timeout(1):
            while cache._active_flights["key"].waiters != 2:
                await asyncio.sleep(0)
        tasks[0].cancel()
        cancelled = await asyncio.wait_for(asyncio.gather(tasks[0], return_exceptions=True), 1)
        assert isinstance(cancelled[0], asyncio.CancelledError)
        release.set()
        assert await asyncio.wait_for(tasks[1], 1) == "value"
    finally:
        release.set()
        await _cancel_and_gather(tasks)
        await _assert_no_named_cache_task()


@pytest.mark.asyncio
async def test_last_waiter_cancellation_returns_before_slow_loader_cleanup() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1)
    started = asyncio.Event()
    cancellation_seen = asyncio.Event()
    cleanup_release = asyncio.Event()
    caller: asyncio.Task[str] | None = None

    async def loader(_: str) -> str:
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancellation_seen.set()
            await asyncio.wait_for(cleanup_release.wait(), 1)
            return "late"

    try:
        caller = asyncio.create_task(cache.get_or_load("key", loader))
        await asyncio.wait_for(started.wait(), 1)
        caller.cancel()
        outcome = await asyncio.wait_for(asyncio.gather(caller, return_exceptions=True), 0.2)
        assert isinstance(outcome[0], asyncio.CancelledError)
        await asyncio.wait_for(cancellation_seen.wait(), 1)
        stats = await cache.stats()
        assert stats.inflight_loads == 1
        assert stats.abandoned_loads == 1
    finally:
        cleanup_release.set()
        if caller is not None:
            await _cancel_and_gather([caller])
        await _assert_no_named_cache_task()


@pytest.mark.asyncio
async def test_cancellation_suppressing_loader_cannot_publish_and_keeps_slot() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1, max_inflight=1)
    started = asyncio.Event()
    cancellation_seen = asyncio.Event()
    terminal_release = asyncio.Event()
    caller: asyncio.Task[str] | None = None

    async def stubborn_loader(_: str) -> str:
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancellation_seen.set()
            await asyncio.wait_for(terminal_release.wait(), 1)
            return "stale"

    try:
        caller = asyncio.create_task(cache.get_or_load("secret", stubborn_loader))
        await asyncio.wait_for(started.wait(), 1)
        caller.cancel()
        outcome = await asyncio.wait_for(asyncio.gather(caller, return_exceptions=True), 0.2)
        assert isinstance(outcome[0], asyncio.CancelledError)
        await asyncio.wait_for(cancellation_seen.wait(), 1)
        with pytest.raises(CacheLoadLimitError, match="maximum in-flight cache loads reached"):
            await cache.get_or_load("other", lambda _: asyncio.sleep(0, result="other"))
        terminal_release.set()
        await _assert_no_named_cache_task()
        with pytest.raises(KeyError):
            await cache.get("secret")
        assert await cache.get_or_load("other", lambda _: asyncio.sleep(0, result="fresh")) == (
            "fresh"
        )
    finally:
        terminal_release.set()
        if caller is not None:
            await _cancel_and_gather([caller])
        await _assert_no_named_cache_task()


@pytest.mark.asyncio
async def test_new_generation_never_joins_abandoned_or_superseded_flight() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=2, max_inflight=3)
    abandoned_started = asyncio.Event()
    abandoned_cancelled = asyncio.Event()
    abandoned_release = asyncio.Event()
    superseded_started = asyncio.Event()
    superseded_release = asyncio.Event()
    tasks: list[asyncio.Task[str]] = []

    async def abandoned_loader(_: str) -> str:
        abandoned_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            abandoned_cancelled.set()
            await asyncio.wait_for(abandoned_release.wait(), 1)
            return "abandoned"

    async def superseded_loader(_: str) -> str:
        superseded_started.set()
        await asyncio.wait_for(superseded_release.wait(), 1)
        return "superseded"

    try:
        abandoned_caller = asyncio.create_task(cache.get_or_load("a", abandoned_loader))
        tasks.append(abandoned_caller)
        await asyncio.wait_for(abandoned_started.wait(), 1)
        abandoned_caller.cancel()
        await asyncio.wait_for(asyncio.gather(abandoned_caller, return_exceptions=True), 0.2)
        await asyncio.wait_for(abandoned_cancelled.wait(), 1)
        assert await cache.get_or_load("a", lambda _: asyncio.sleep(0, result="new-a")) == "new-a"

        tasks.append(asyncio.create_task(cache.get_or_load("b", superseded_loader)))
        await asyncio.wait_for(superseded_started.wait(), 1)
        assert await cache.invalidate("b") is False
        assert await cache.get_or_load("b", lambda _: asyncio.sleep(0, result="new-b")) == "new-b"
        superseded_release.set()
        assert await asyncio.wait_for(tasks[-1], 1) == "superseded"
        abandoned_release.set()
        await _assert_no_named_cache_task()
    finally:
        abandoned_release.set()
        superseded_release.set()
        await _cancel_and_gather(tasks)
        await _assert_no_named_cache_task()

    assert await cache.get("a") == "new-a"
    assert await cache.get("b") == "new-b"


@pytest.mark.asyncio
async def test_loader_self_cancellation_cleans_owned_state_and_counts_failure() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1)

    async def self_cancelling_loader(_: str) -> str:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(cache.get_or_load("key", self_cancelling_loader), 1)

    await _assert_no_named_cache_task()
    stats = await cache.stats()
    assert stats.loads == 1
    assert stats.load_failures == 1
    assert stats.inflight_loads == 0
    assert cache._active_flights == {}
    assert cache._owned_flights == set()


@pytest.mark.asyncio
async def test_async_saturation_allows_joiners_rejects_new_keys_and_recovers() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=2, max_inflight=1)
    started = asyncio.Event()
    release = asyncio.Event()
    tasks: list[asyncio.Task[str]] = []

    async def loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return "shared"

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", loader)))
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(
            asyncio.create_task(
                cache.get_or_load("key", lambda _: asyncio.sleep(0, result="unused"))
            )
        )
        async with asyncio.timeout(1):
            while cache._active_flights["key"].waiters != 2:
                await asyncio.sleep(0)
        with pytest.raises(CacheLoadLimitError, match="maximum in-flight cache loads reached"):
            await cache.get_or_load("other", lambda _: asyncio.sleep(0, result="other"))
        release.set()
        assert await asyncio.wait_for(asyncio.gather(*tasks), 1) == ["shared", "shared"]
        assert await cache.get_or_load("other", lambda _: asyncio.sleep(0, result="recovered")) == (
            "recovered"
        )
    finally:
        release.set()
        await _cancel_and_gather(tasks)
        await _assert_no_named_cache_task()


@pytest.mark.asyncio
async def test_async_loading_counters_and_current_gauges_are_exact() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1, max_inflight=1)
    started = asyncio.Event()
    release = asyncio.Event()
    tasks: list[asyncio.Task[str]] = []

    async def loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return "value"

    try:
        tasks.append(asyncio.create_task(cache.get_or_load("key", loader)))
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(
            asyncio.create_task(
                cache.get_or_load("key", lambda _: asyncio.sleep(0, result="unused"))
            )
        )
        async with asyncio.timeout(1):
            while cache._active_flights["key"].waiters != 2:
                await asyncio.sleep(0)
        assert await cache.invalidate("key") is False
        current = await cache.stats()
        assert current.loads == 1
        assert current.coalesced_waiters == 1
        assert current.inflight_loads == 1
        assert current.abandoned_loads == 0
        assert current.superseded_loads == 1
        with pytest.raises(CacheLoadLimitError):
            await cache.get_or_load("other", lambda _: asyncio.sleep(0, result="other"))
        assert (await cache.stats()).load_rejections == 1
        release.set()
        assert await asyncio.wait_for(asyncio.gather(*tasks), 1) == ["value", "value"]
    finally:
        release.set()
        await _cancel_and_gather(tasks)
        await _assert_no_named_cache_task()

    terminal = await cache.stats()
    assert terminal.loads == 1
    assert terminal.load_failures == 0
    assert terminal.load_rejections == 1
    assert terminal.coalesced_waiters == 1
    assert terminal.inflight_loads == 0
    assert terminal.abandoned_loads == 0
    assert terminal.superseded_loads == 0


@pytest.mark.asyncio
async def test_task_names_and_stats_never_expose_secret_sentinel() -> None:
    secret = "SECRET-SENTINEL-9b4520"
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=1)
    started = asyncio.Event()
    release = asyncio.Event()
    task: asyncio.Task[str] | None = None

    async def loader(_: str) -> str:
        started.set()
        await asyncio.wait_for(release.wait(), 1)
        return secret

    try:
        task = asyncio.create_task(cache.get_or_load(secret, loader))
        await asyncio.wait_for(started.wait(), 1)
        assert _named_cache_tasks()
        assert all(secret not in named.get_name() for named in _named_cache_tasks())
        assert secret not in repr(await cache.stats())
        release.set()
        assert await asyncio.wait_for(task, 1) == secret
    finally:
        release.set()
        if task is not None:
            await _cancel_and_gather([task])
        await _assert_no_named_cache_task()


@pytest.mark.asyncio
async def test_every_terminal_scenario_leaves_no_named_cache_task() -> None:
    cache = AsyncTTLCache[str, str](default_ttl=1, max_size=3)

    assert await cache.get_or_load("success", lambda _: asyncio.sleep(0, result="ok")) == "ok"

    failure = RuntimeError("failure")

    async def failing(_: str) -> str:
        raise failure

    with pytest.raises(RuntimeError) as caught:
        await cache.get_or_load("failure", failing)
    assert caught.value is failure

    async def self_cancel(_: str) -> str:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await cache.get_or_load("cancel", self_cancel)

    await _assert_no_named_cache_task()
    assert cache._active_flights == {}
    assert cache._owned_flights == set()
