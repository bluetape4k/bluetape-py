"""Deterministic entry-state tests for the synchronous cache."""

import inspect
import threading
import time
from collections.abc import Callable
from typing import get_type_hints

import pytest
from bluetape.cache import CacheLoadLimitError, RecursiveLoadError, TTLCache

from ._support import FakeClock


class CountingClock(FakeClock):
    """Record how often a public operation samples the clock."""

    def __init__(self, now_ns: int = 0) -> None:
        super().__init__(now_ns)
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return super().__call__()


def _run_in_thread[V](
    operation: Callable[[], V],
    results: list[V],
    errors: list[BaseException],
) -> threading.Thread:
    def target() -> None:
        try:
            results.append(operation())
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=target)
    thread.start()
    return thread


def _join(thread: threading.Thread) -> None:
    thread.join(2)
    assert not thread.is_alive()


def _wait_until(predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 2
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("timed out waiting for concurrent cache transition")
        time.sleep(0.001)


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


def test_get_or_load_signature_matches_public_contract() -> None:
    parameters = inspect.signature(TTLCache.get_or_load).parameters

    assert list(parameters) == ["self", "key", "loader", "ttl"]
    assert parameters["ttl"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["ttl"].default is None
    hints = get_type_hints(TTLCache.get_or_load)
    assert hints["loader"] == Callable[[TTLCache.__parameters__[0]], TTLCache.__parameters__[1]]
    assert hints["ttl"] == float | None
    assert hints["return"].__name__ == "V"


def test_same_key_uses_one_owner_loader_and_ttl() -> None:
    clock = FakeClock()
    cache = TTLCache[str, object](default_ttl=1, max_size=2, clock=clock)
    started = threading.Event()
    release = threading.Event()
    owner_value = object()
    results: list[object] = []
    errors: list[BaseException] = []
    calls: list[str] = []
    threads: list[threading.Thread] = []

    def owner_loader(key: str) -> object:
        calls.append(key)
        started.set()
        assert release.wait(2)
        return owner_value

    try:
        threads.append(
            _run_in_thread(
                lambda: cache.get_or_load("key", owner_loader, ttl=10e-9), results, errors
            )
        )
        assert started.wait(2)
        threads.append(
            _run_in_thread(
                lambda: cache.get_or_load("key", lambda _: object(), ttl=100), results, errors
            )
        )
        _wait_until(lambda: cache.stats().coalesced_waiters == 1)
        release.set()
    finally:
        release.set()
        for thread in threads:
            _join(thread)

    assert errors == []
    assert results == [owner_value, owner_value]
    assert calls == ["key"]
    clock.now_ns = 9
    assert cache.get("key") is owner_value
    clock.now_ns = 10
    with pytest.raises(KeyError):
        cache.get("key")


def test_different_key_loader_bodies_enter_concurrently() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=2)
    barrier = threading.Barrier(2)
    results: list[str] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def loader(key: str) -> str:
        barrier.wait(2)
        return key

    try:
        for key in ("a", "b"):
            threads.append(
                _run_in_thread(lambda key=key: cache.get_or_load(key, loader), results, errors)
            )
        _wait_until(lambda: len(results) + len(errors) == 2)
    finally:
        barrier.abort()
        for thread in threads:
            _join(thread)

    assert errors == []
    assert sorted(results) == ["a", "b"]


def test_loader_failure_is_shared_not_cached_and_preserves_exception() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=2)
    started = threading.Event()
    release = threading.Event()
    failure = LookupError("original")
    results: list[str] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def failing_loader(_: str) -> str:
        started.set()
        assert release.wait(2)
        raise failure

    try:
        threads.append(
            _run_in_thread(lambda: cache.get_or_load("key", failing_loader), results, errors)
        )
        assert started.wait(2)
        threads.append(
            _run_in_thread(lambda: cache.get_or_load("key", lambda _: "unused"), results, errors)
        )
        _wait_until(lambda: cache.stats().coalesced_waiters == 1)
        release.set()
    finally:
        release.set()
        for thread in threads:
            _join(thread)

    assert results == []
    assert len(errors) == 2
    assert errors[0] is failure
    assert errors[1] is failure
    assert cache.get_or_load("key", lambda _: "recovered") == "recovered"


def test_owner_only_success_and_failure_cleanup_flights_and_versions() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=2)

    assert cache.get_or_load("success", lambda _: "value") == "value"
    failure = RuntimeError("failure")
    with pytest.raises(RuntimeError) as raised:
        cache.get_or_load("failure", lambda _: (_ for _ in ()).throw(failure))

    assert raised.value is failure
    assert cache._active_flights == {}
    assert cache._owned_flights == set()
    assert "failure" not in cache._state.key_versions
    assert cache.invalidate("success") is True
    assert cache._state.key_versions == {}


def test_same_thread_same_key_recursion_is_rejected() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=1)

    def loader(key: str) -> str:
        return cache.get_or_load(key, lambda _: "unreachable")

    with pytest.raises(RecursiveLoadError, match="same cache key"):
        cache.get_or_load("key", loader)

    assert cache._active_flights == {}
    assert cache._owned_flights == set()


@pytest.mark.parametrize("mutation", ["set", "invalidate", "clear"])
def test_set_invalidate_and_clear_supersede_without_stale_publication(mutation: str) -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=2)
    started = threading.Event()
    release = threading.Event()
    results: list[str] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def loader(_: str) -> str:
        started.set()
        assert release.wait(2)
        return "stale"

    try:
        threads.append(_run_in_thread(lambda: cache.get_or_load("key", loader), results, errors))
        assert started.wait(2)
        if mutation == "set":
            cache.set("key", "explicit")
        elif mutation == "invalidate":
            assert cache.invalidate("key") is False
        else:
            cache.clear()
        release.set()
    finally:
        release.set()
        for thread in threads:
            _join(thread)

    assert errors == []
    assert results == ["stale"]
    if mutation == "set":
        assert cache.get("key") == "explicit"
    else:
        with pytest.raises(KeyError):
            cache.get("key")


def test_post_mutation_caller_never_joins_superseded_flight() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=2)
    old_started = threading.Event()
    old_release = threading.Event()
    old_results: list[str] = []
    new_results: list[str] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def old_loader(_: str) -> str:
        old_started.set()
        assert old_release.wait(2)
        return "old"

    try:
        threads.append(
            _run_in_thread(lambda: cache.get_or_load("key", old_loader), old_results, errors)
        )
        assert old_started.wait(2)
        assert cache.invalidate("key") is False
        threads.append(
            _run_in_thread(lambda: cache.get_or_load("key", lambda _: "new"), new_results, errors)
        )
        _wait_until(lambda: new_results == ["new"])
        old_release.set()
    finally:
        old_release.set()
        for thread in threads:
            _join(thread)

    assert errors == []
    assert old_results == ["old"]
    assert new_results == ["new"]
    assert cache.get("key") == "new"


def test_active_and_superseded_flights_consume_limit_until_terminal() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=2, max_inflight=2)
    old_started = threading.Event()
    old_release = threading.Event()
    new_started = threading.Event()
    new_release = threading.Event()
    results: list[str] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def old_loader(_: str) -> str:
        old_started.set()
        assert old_release.wait(2)
        return "old"

    def new_loader(_: str) -> str:
        new_started.set()
        assert new_release.wait(2)
        return "new"

    try:
        threads.append(_run_in_thread(lambda: cache.get_or_load("a", old_loader), results, errors))
        assert old_started.wait(2)
        assert cache.invalidate("a") is False
        threads.append(_run_in_thread(lambda: cache.get_or_load("a", new_loader), results, errors))
        assert new_started.wait(2)
        with pytest.raises(CacheLoadLimitError):
            cache.get_or_load("b", lambda _: "b")
        new_release.set()
        old_release.set()
    finally:
        new_release.set()
        old_release.set()
        for thread in threads:
            _join(thread)

    assert errors == []
    assert sorted(results) == ["new", "old"]
    assert cache.get_or_load("b", lambda _: "b") == "b"


def test_sync_loading_stats_change_at_exact_ownership_transitions() -> None:
    cache = TTLCache[str, str](default_ttl=1, max_size=1, max_inflight=1)
    started = threading.Event()
    release = threading.Event()
    results: list[str] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def loader(_: str) -> str:
        started.set()
        assert release.wait(2)
        return "value"

    try:
        threads.append(_run_in_thread(lambda: cache.get_or_load("key", loader), results, errors))
        assert started.wait(2)
        assert cache.stats().loads == 1
        assert cache.stats().inflight_loads == 1
        threads.append(
            _run_in_thread(lambda: cache.get_or_load("key", lambda _: "unused"), results, errors)
        )
        _wait_until(lambda: cache.stats().coalesced_waiters == 1)
        assert cache.invalidate("key") is False
        superseded = cache.stats()
        assert superseded.inflight_loads == 1
        assert superseded.superseded_loads == 1
        with pytest.raises(CacheLoadLimitError):
            cache.get_or_load("other", lambda _: "other")
        assert cache.stats().load_rejections == 1
        release.set()
    finally:
        release.set()
        for thread in threads:
            _join(thread)

    terminal = cache.stats()
    assert errors == []
    assert results == ["value", "value"]
    assert terminal.loads == 1
    assert terminal.load_failures == 0
    assert terminal.coalesced_waiters == 1
    assert terminal.inflight_loads == 0
    assert terminal.superseded_loads == 0
