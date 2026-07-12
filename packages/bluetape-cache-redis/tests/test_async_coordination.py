import asyncio
import inspect

import pytest
from _support import sample_metadata
from bluetape.cache import AsyncTTLCache
from bluetape.cache.redis import (
    AsyncRedisLoadCoordinator,
    AsyncRedisProvider,
    EnvelopeSizeError,
    RedisCommandPolicy,
    RedisCoordinationError,
    RedisCoordinationErrorCode,
    RedisCoordinationOutcome,
    RedisCoordinationSnapshot,
    RedisCoordinationTimeoutError,
    RedisErrorCode,
    RedisLoadOptions,
    RedisOperation,
    RedisProviderError,
    ResultEnvelopeCodec,
)
from bluetape.serde import SerializedPayload


class BytesCodec:
    def encode(self, value: bytes | None) -> SerializedPayload:
        return SerializedPayload(
            metadata=sample_metadata(), data=b"null" if value is None else value
        )

    def decode(self, payload: SerializedPayload) -> bytes | None:
        return None if payload.data == b"null" else payload.data


class FakeAsyncProvider(AsyncRedisProvider):
    def __init__(self) -> None:
        self.policy = RedisCommandPolicy(connect_timeout=0.1, socket_timeout=0.1)
        self.acquire_results = [True]
        self.acquires = []
        self.snapshots: list[RedisCoordinationSnapshot] = []
        self.snapshot_calls = 0
        self.publishes = []
        self.publish_result = True
        self.cleanups = []
        self.owner_acquired = asyncio.Event()
        self.cleanup_started = asyncio.Event()
        self.cleanup_release: asyncio.Event | None = None
        self.cleanup_error: BaseException | None = None

    @property
    def command_policy(self):
        return self.policy

    async def set_if_absent(self, key, value, *, ttl):
        self.acquires.append((key, value, ttl))
        result = self.acquire_results.pop(0)
        if result:
            self.owner_acquired.set()
        return result

    async def coordination_snapshot(
        self, marker_key, result_key, *, max_marker_size=138, max_result_size
    ):
        self.snapshot_calls += 1
        return self.snapshots.pop(0)

    async def publish_if_value(
        self,
        condition_key,
        expected_value,
        *,
        result_key,
        result_value,
        completion_value,
        ttl,
    ):
        self.publishes.append(
            (condition_key, result_key, expected_value, result_value, completion_value, ttl)
        )
        return self.publish_result

    async def delete_if_value(self, key, expected_value):
        self.cleanups.append((key, expected_value))
        self.cleanup_started.set()
        if self.cleanup_release is not None:
            await self.cleanup_release.wait()
        if self.cleanup_error is not None:
            raise self.cleanup_error
        return True


class Observer:
    def __init__(self):
        self.events = []

    def on_event(self, event):
        self.events.append(event)


def make_coordinator(*, provider=None, observer=None, options=None):
    cache = AsyncTTLCache[str, bytes | None](default_ttl=60, max_size=100)
    actual = provider or FakeAsyncProvider()
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    coordinator = AsyncRedisLoadCoordinator(
        cache,
        actual,
        codec,
        options=options or RedisLoadOptions(namespace="orders:test:v1"),
        observer=observer,
    )
    return coordinator, cache, actual, codec


def test_async_coordinator_public_signatures_are_exact() -> None:
    assert "AsyncTTLCache[str, V]" in str(inspect.signature(AsyncRedisLoadCoordinator))
    assert (
        str(inspect.signature(AsyncRedisLoadCoordinator.get_or_load))
        == "(self, key: str, loader: collections.abc.Callable[[str], "
        "collections.abc.Awaitable[V]], *, ttl: float | None = None) -> V"
    )


@pytest.mark.asyncio
async def test_async_owner_loads_and_publishes() -> None:
    observer = Observer()
    coordinator, cache, provider, _ = make_coordinator(observer=observer)

    assert (
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"loaded"))
        == b"loaded"
    )
    assert await cache.get("key") == b"loaded"
    assert len(provider.acquires) == len(provider.publishes) == 1
    assert observer.events[-1].outcome is RedisCoordinationOutcome.LOADED


@pytest.mark.asyncio
async def test_async_local_hit_never_touches_redis() -> None:
    coordinator, cache, provider, _ = make_coordinator()
    await cache.set("key", b"cached")

    assert await coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) == b"cached"
    assert provider.acquires == []


@pytest.mark.asyncio
async def test_async_completed_none_is_reused() -> None:
    provider = FakeAsyncProvider()
    provider.acquire_results = [False]
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"completed:remote",
            result=codec.encode("remote", None),
            marker_oversized=False,
            result_oversized=False,
        )
    ]
    coordinator, cache, _, _ = make_coordinator(provider=provider)
    coordinator._codec = codec

    assert await coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) is None
    assert await cache.get("key") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "snapshot",
    [
        RedisCoordinationSnapshot(
            marker=b"active:oversized",
            result=None,
            marker_oversized=True,
            result_oversized=False,
        ),
        RedisCoordinationSnapshot(
            marker=b"secret-invalid-marker",
            result=None,
            marker_oversized=False,
            result_oversized=False,
        ),
    ],
)
async def test_async_oversized_or_malformed_artifact_fails_without_cleanup(
    snapshot: RedisCoordinationSnapshot,
) -> None:
    provider = FakeAsyncProvider()
    provider.acquire_results = [False]
    provider.snapshots = [snapshot]
    coordinator, _, _, _ = make_coordinator(provider=provider)

    with pytest.raises(RedisCoordinationError) as captured:
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"unused"))

    assert captured.value.code is RedisCoordinationErrorCode.INVALID_ARTIFACT
    assert "secret" not in str(captured.value)
    assert provider.cleanups == []


@pytest.mark.asyncio
async def test_async_mismatched_completed_result_is_ignored_until_matching_result(
    monkeypatch,
) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("bluetape.cache.redis._async_coordination._sleep", no_sleep)
    provider = FakeAsyncProvider()
    provider.acquire_results = [False]
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"completed:new-owner",
            result=codec.encode("old-owner", b"stale"),
            marker_oversized=False,
            result_oversized=False,
        ),
        RedisCoordinationSnapshot(
            marker=b"completed:new-owner",
            result=codec.encode("new-owner", b"fresh"),
            marker_oversized=False,
            result_oversized=False,
        ),
    ]
    coordinator, cache, _, _ = make_coordinator(provider=provider)

    assert await coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) == b"fresh"
    assert await cache.get("key") == b"fresh"


@pytest.mark.asyncio
async def test_async_loader_failure_is_preserved_and_owner_marker_is_cleaned_once() -> None:
    coordinator, _, provider, _ = make_coordinator()
    cause = LookupError("caller-owned")

    async def fail(_: str) -> bytes:
        raise cause

    with pytest.raises(LookupError) as captured:
        await coordinator.get_or_load("key", fail)

    assert captured.value is cause
    assert len(provider.cleanups) == 1
    assert provider.publishes == []


@pytest.mark.asyncio
async def test_async_cleanup_failure_preserves_primary_and_adds_static_note() -> None:
    provider = FakeAsyncProvider()
    provider.cleanup_error = RuntimeError("provider-secret")
    coordinator, _, _, _ = make_coordinator(provider=provider)
    cause = LookupError("caller-owned")

    async def fail(_: str) -> bytes:
        raise cause

    with pytest.raises(LookupError) as captured:
        await coordinator.get_or_load("key", fail)

    assert captured.value is cause
    assert captured.value.__notes__ == ["Redis owner cleanup also failed (cleanup-failure)"]


@pytest.mark.asyncio
async def test_async_encode_overflow_cleans_owner_and_does_not_fill_cache() -> None:
    coordinator, cache, provider, _ = make_coordinator()
    coordinator._codec = ResultEnvelopeCodec(payload_codec=BytesCodec(), max_encoded_size=1)

    with pytest.raises(EnvelopeSizeError):
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"too-large"))

    assert len(provider.cleanups) == 1
    assert provider.publishes == []
    with pytest.raises(KeyError):
        await cache.get("key")


@pytest.mark.asyncio
async def test_async_publish_provider_failure_cleans_owner_and_is_preserved(monkeypatch) -> None:
    provider = FakeAsyncProvider()
    error = RedisProviderError(
        operation=RedisOperation.PUBLISH_IF_VALUE,
        code=RedisErrorCode.PROVIDER_FAILURE,
    )

    async def fail_publish(*args, **kwargs) -> bool:
        raise error

    monkeypatch.setattr(provider, "publish_if_value", fail_publish)
    coordinator, _, _, _ = make_coordinator(provider=provider)

    with pytest.raises(RedisProviderError) as captured:
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"loaded"))

    assert captured.value is error
    assert len(provider.cleanups) == 1


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_flight() -> None:
    coordinator, cache, provider, _ = make_coordinator()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def loader(_: str) -> bytes:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return b"value"

    first = asyncio.create_task(coordinator.get_or_load("key", loader))
    second = asyncio.create_task(coordinator.get_or_load("key", loader))
    await started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()

    assert await second == b"value"
    assert calls == 1
    assert len(provider.acquires) == 1
    assert await cache.get("key") == b"value"


@pytest.mark.asyncio
async def test_last_waiter_cancellation_finishes_one_cleanup() -> None:
    coordinator, cache, provider, _ = make_coordinator()
    blocker = asyncio.Event()

    async def loader(_: str) -> bytes:
        await blocker.wait()
        return b"never"

    caller = asyncio.create_task(coordinator.get_or_load("key", loader))
    await provider.owner_acquired.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    for _ in range(20):
        stats = await cache.stats()
        if stats.inflight_loads == 0:
            break
        await asyncio.sleep(0)

    assert len(provider.cleanups) == 1
    assert (await cache.stats()).inflight_loads == 0
    assert provider.publishes == []


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_one_cleanup_then_raises_original() -> None:
    provider = FakeAsyncProvider()
    provider.cleanup_release = asyncio.Event()
    coordinator, cache, _, _ = make_coordinator(provider=provider)
    blocker = asyncio.Event()

    async def loader(_: str) -> bytes:
        await blocker.wait()
        return b"never"

    caller = asyncio.create_task(coordinator.get_or_load("key", loader))
    await provider.owner_acquired.wait()
    caller.cancel()
    await provider.cleanup_started.wait()
    caller.cancel()
    provider.cleanup_release.set()

    with pytest.raises(asyncio.CancelledError):
        await caller
    for _ in range(20):
        if (await cache.stats()).inflight_loads == 0:
            break
        await asyncio.sleep(0)
    assert len(provider.cleanups) == 1


@pytest.mark.asyncio
async def test_cancellation_wins_over_cleanup_failure_with_static_note() -> None:
    provider = FakeAsyncProvider()
    provider.cleanup_error = RuntimeError("secret")
    observer = Observer()
    coordinator, cache, _, _ = make_coordinator(provider=provider, observer=observer)
    blocker = asyncio.Event()

    async def loader(_: str) -> bytes:
        await blocker.wait()
        return b"never"

    caller = asyncio.create_task(coordinator.get_or_load("key", loader))
    await provider.owner_acquired.wait()
    caller.cancel()

    with pytest.raises(asyncio.CancelledError):
        await caller
    for _ in range(20):
        if (await cache.stats()).inflight_loads == 0:
            break
        await asyncio.sleep(0)
    assert observer.events[-1].outcome is RedisCoordinationOutcome.CANCELLED
    assert observer.events[-1].cleanup_failed is True


@pytest.mark.asyncio
async def test_async_stale_owner_returns_local() -> None:
    observer = Observer()
    provider = FakeAsyncProvider()
    provider.publish_result = False
    coordinator, _, _, _ = make_coordinator(provider=provider, observer=observer)

    assert (
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"local"))
        == b"local"
    )
    assert observer.events[-1].outcome is RedisCoordinationOutcome.LEASE_LOST
    assert provider.cleanups == []


@pytest.mark.asyncio
async def test_async_token_work_cannot_start_acquire_after_deadline(monkeypatch) -> None:
    now = 0.0

    def delayed_token() -> str:
        nonlocal now
        now = 11.0
        return "owner"

    monkeypatch.setattr("bluetape.cache.redis._async_coordination._clock", lambda: now)
    monkeypatch.setattr("bluetape.cache.redis._async_coordination._new_token", delayed_token)
    coordinator, _, provider, _ = make_coordinator()

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"unused"))

    assert captured.value.code is RedisCoordinationErrorCode.DEADLINE_EXCEEDED
    assert provider.acquires == []


@pytest.mark.asyncio
async def test_async_poll_sleep_cannot_start_snapshot_after_deadline(monkeypatch) -> None:
    now = 0.0
    provider = FakeAsyncProvider()
    provider.acquire_results = [False]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"active:remote",
            result=None,
            marker_oversized=False,
            result_oversized=False,
        )
    ]

    async def expire_deadline(_: float) -> None:
        nonlocal now
        now = 11.0

    monkeypatch.setattr("bluetape.cache.redis._async_coordination._clock", lambda: now)
    monkeypatch.setattr("bluetape.cache.redis._async_coordination._sleep", expire_deadline)
    coordinator, _, _, _ = make_coordinator(provider=provider)

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"unused"))

    assert captured.value.code is RedisCoordinationErrorCode.DEADLINE_EXCEEDED
    assert provider.snapshot_calls == 1


@pytest.mark.asyncio
async def test_async_large_poll_budget_ends_with_stable_timeout(monkeypatch) -> None:
    snapshot = RedisCoordinationSnapshot(
        marker=b"active:remote",
        result=None,
        marker_oversized=False,
        result_oversized=False,
    )
    provider = FakeAsyncProvider()
    provider.acquire_results = [False]
    provider.snapshots = [snapshot] * 1_100
    coordinator, _, _, _ = make_coordinator(
        provider=provider,
        options=RedisLoadOptions(
            namespace="orders:test:v1",
            max_polls=1_100,
            wait_timeout=3_600,
        ),
    )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("bluetape.cache.redis._async_coordination._sleep", no_sleep)
    monkeypatch.setattr("bluetape.cache.redis._async_coordination._jitter", lambda: 1.0)

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"unused"))

    assert captured.value.code is RedisCoordinationErrorCode.POLLS_EXHAUSTED
    assert provider.snapshot_calls == 1_100


@pytest.mark.asyncio
async def test_async_attempt_budget_exhaustion_is_explicit() -> None:
    provider = FakeAsyncProvider()
    provider.acquire_results = [False]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=None,
            result=None,
            marker_oversized=False,
            result_oversized=False,
        )
    ]
    coordinator, _, _, _ = make_coordinator(
        provider=provider,
        options=RedisLoadOptions(namespace="orders:test:v1", max_attempts=1),
    )

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        await coordinator.get_or_load("key", lambda _: asyncio.sleep(0, result=b"unused"))

    assert captured.value.code is RedisCoordinationErrorCode.ATTEMPTS_EXHAUSTED


def test_async_unbounded_provider_policy_is_rejected_at_construction() -> None:
    provider = FakeAsyncProvider()
    provider.policy = None

    with pytest.raises(ValueError, match="bounded no-retry policy"):
        make_coordinator(provider=provider)


@pytest.mark.asyncio
async def test_async_invalid_key_fails_before_cache_or_redis_access() -> None:
    coordinator, _, provider, _ = make_coordinator()

    with pytest.raises((TypeError, ValueError)):
        await coordinator.get_or_load(  # type: ignore[arg-type]
            b"key", lambda _: asyncio.sleep(0, result=b"unused")
        )

    assert provider.acquires == []


@pytest.mark.asyncio
@pytest.mark.parametrize("ttl", [True, 0, -1, float("inf"), "1"])
async def test_async_invalid_local_ttl_fails_before_redis_access(ttl: object) -> None:
    coordinator, _, provider, _ = make_coordinator()

    with pytest.raises((TypeError, ValueError)):
        await coordinator.get_or_load(  # type: ignore[arg-type]
            "key", lambda _: asyncio.sleep(0, result=b"unused"), ttl=ttl
        )

    assert provider.acquires == []


@pytest.mark.asyncio
async def test_async_same_key_burst_uses_one_flight() -> None:
    coordinator, _, provider, _ = make_coordinator()
    started = asyncio.Event()
    release = asyncio.Event()

    async def loader(_: str) -> bytes:
        started.set()
        await release.wait()
        return b"loaded"

    callers = [asyncio.create_task(coordinator.get_or_load("key", loader)) for _ in range(20)]
    await started.wait()
    release.set()

    assert await asyncio.gather(*callers) == [b"loaded"] * 20
    assert len(provider.acquires) == 1
