import inspect
import json
import threading

import pytest
from bluetape.cache import TTLCache
from bluetape.cache.redis import (
    EnvelopeSizeError,
    RedisCommandPolicy,
    RedisCoordinationError,
    RedisCoordinationErrorCode,
    RedisCoordinationOutcome,
    RedisCoordinationSnapshot,
    RedisCoordinationTimeoutError,
    RedisLoadOptions,
    ResultEnvelopeCodec,
    SyncRedisLoadCoordinator,
    SyncRedisProvider,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile


class JsonValueCodec:
    def encode(self, value: object) -> SerializedPayload:
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="json",
                version=1,
                content_type="application/json",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=json.dumps(value).encode(),
        )

    def decode(self, payload: SerializedPayload) -> object:
        return json.loads(payload.data)


class FakeProvider(SyncRedisProvider):
    def __init__(self) -> None:
        self.policy: RedisCommandPolicy | None = RedisCommandPolicy(
            connect_timeout=0.1, socket_timeout=0.1
        )
        self.acquires: list[tuple[str, bytes, float]] = []
        self.acquire_results: list[bool] = [True]
        self.snapshots: list[RedisCoordinationSnapshot] = []
        self.snapshot_calls = 0
        self.publishes: list[tuple[str, bytes, str, bytes, bytes, float]] = []
        self.publish_result = True
        self.cleanups: list[tuple[str, bytes]] = []
        self.cleanup_error: BaseException | None = None

    @property
    def command_policy(self) -> RedisCommandPolicy | None:
        return self.policy

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        self.acquires.append((key, value, ttl))
        return self.acquire_results.pop(0)

    def coordination_snapshot(
        self, marker_key: str, result_key: str, *, max_marker_size: int = 138, max_result_size: int
    ) -> RedisCoordinationSnapshot:
        self.snapshot_calls += 1
        return self.snapshots.pop(0)

    def publish_if_value(
        self,
        condition_key: str,
        expected_value: bytes,
        *,
        result_key: str,
        result_value: bytes,
        completion_value: bytes,
        ttl: float,
    ) -> bool:
        self.publishes.append(
            (condition_key, expected_value, result_key, result_value, completion_value, ttl)
        )
        return self.publish_result

    def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        self.cleanups.append((key, expected_value))
        if self.cleanup_error is not None:
            raise self.cleanup_error
        return True


class Observer:
    def __init__(self) -> None:
        self.events = []
        self.error: BaseException | None = None

    def on_event(self, event) -> None:
        self.events.append(event)
        if self.error is not None:
            raise self.error


def make_coordinator(
    *,
    provider: FakeProvider | None = None,
    observer: Observer | None = None,
    options: RedisLoadOptions | None = None,
) -> tuple[
    SyncRedisLoadCoordinator[object], TTLCache[str, object], FakeProvider, ResultEnvelopeCodec
]:
    cache = TTLCache[str, object](default_ttl=60, max_size=100)
    actual_provider = provider or FakeProvider()
    codec = ResultEnvelopeCodec(payload_codec=JsonValueCodec())
    coordinator = SyncRedisLoadCoordinator(
        cache,
        actual_provider,
        codec,
        options=options or RedisLoadOptions(namespace="orders:test:v1"),
        observer=observer,
    )
    return coordinator, cache, actual_provider, codec


def test_sync_coordinator_public_signatures_are_exact() -> None:
    assert (
        str(inspect.signature(SyncRedisLoadCoordinator))
        == "(cache: bluetape.cache._sync.TTLCache[str, V], provider: "
        "bluetape.cache.redis._provider.SyncRedisProvider, codec: "
        "bluetape.cache.redis._envelope.ResultEnvelopeCodec[V], *, options: "
        "bluetape.cache.redis._contracts.RedisLoadOptions, observer: "
        "bluetape.cache.redis._contracts.RedisCoordinationObserver | None = None) -> None"
    )
    assert (
        str(inspect.signature(SyncRedisLoadCoordinator.get_or_load))
        == "(self, key: str, loader: collections.abc.Callable[[str], V], *, "
        "ttl: float | None = None) -> V"
    )


def test_local_hit_never_touches_redis_or_emits_event() -> None:
    observer = Observer()
    coordinator, cache, provider, _ = make_coordinator(observer=observer)
    cache.set("key", "cached")

    assert coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) == "cached"
    assert provider.acquires == []
    assert observer.events == []


def test_owner_loads_publishes_and_fills_local_cache() -> None:
    observer = Observer()
    coordinator, cache, provider, _ = make_coordinator(observer=observer)

    assert coordinator.get_or_load("order-42", lambda key: f"loaded:{key}") == "loaded:order-42"
    assert cache.get("order-42") == "loaded:order-42"
    assert len(provider.acquires) == 1
    assert len(provider.publishes) == 1
    assert observer.events[-1].outcome is RedisCoordinationOutcome.LOADED


def test_stale_owner_returns_local_without_publication_success() -> None:
    observer = Observer()
    provider = FakeProvider()
    provider.publish_result = False
    coordinator, _, provider, _ = make_coordinator(provider=provider, observer=observer)

    assert coordinator.get_or_load("key", lambda _: "local") == "local"
    assert provider.cleanups == []
    assert observer.events[-1].outcome is RedisCoordinationOutcome.LEASE_LOST


@pytest.mark.parametrize("remote", [None, "remote"])
def test_completed_result_is_reused_without_loader(remote: object) -> None:
    observer = Observer()
    provider = FakeProvider()
    provider.acquire_results = [False]
    codec = ResultEnvelopeCodec(payload_codec=JsonValueCodec())
    token = "remote-owner"
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=f"completed:{token}".encode(),
            result=codec.encode(token, remote),
            marker_oversized=False,
            result_oversized=False,
        )
    ]
    coordinator, cache, provider, _ = make_coordinator(provider=provider, observer=observer)
    coordinator._codec = codec

    assert coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) == remote
    assert cache.get("key") == remote
    assert observer.events[-1].outcome is RedisCoordinationOutcome.RESULT_REUSED


def test_missing_marker_reacquires_without_consuming_poll() -> None:
    observer = Observer()
    provider = FakeProvider()
    provider.acquire_results = [False, True]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=None, result=None, marker_oversized=False, result_oversized=False
        )
    ]
    coordinator, _, provider, _ = make_coordinator(provider=provider, observer=observer)

    assert coordinator.get_or_load("key", lambda _: "loaded") == "loaded"
    assert len(provider.acquires) == 2
    assert observer.events[-1].polls == 0


def test_active_marker_poll_then_matching_completed_result(monkeypatch) -> None:
    monkeypatch.setattr("bluetape.cache.redis._coordination._sleep", lambda _: None)
    monkeypatch.setattr("bluetape.cache.redis._coordination._jitter", lambda: 1.0)
    observer = Observer()
    provider = FakeProvider()
    provider.acquire_results = [False]
    codec = ResultEnvelopeCodec(payload_codec=JsonValueCodec())
    token = "remote-owner"
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=f"active:{token}".encode(),
            result=b"ignored",
            marker_oversized=False,
            result_oversized=False,
        ),
        RedisCoordinationSnapshot(
            marker=f"completed:{token}".encode(),
            result=codec.encode(token, "remote"),
            marker_oversized=False,
            result_oversized=False,
        ),
    ]
    coordinator, _, _, _ = make_coordinator(provider=provider, observer=observer)
    coordinator._codec = codec

    assert coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) == "remote"
    assert observer.events[-1].polls == 1


def test_oversized_or_malformed_artifact_fails_without_cleanup() -> None:
    provider = FakeProvider()
    provider.acquire_results = [False]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"secret-invalid-marker",
            result=None,
            marker_oversized=True,
            result_oversized=False,
        )
    ]
    coordinator, _, provider, _ = make_coordinator(provider=provider)

    with pytest.raises(RedisCoordinationError) as captured:
        coordinator.get_or_load("key", lambda _: "unused")

    assert captured.value.code is RedisCoordinationErrorCode.INVALID_ARTIFACT
    assert "secret" not in str(captured.value)
    assert provider.cleanups == []


def test_loader_failure_is_preserved_and_owner_marker_is_cleaned_once() -> None:
    provider = FakeProvider()
    coordinator, _, provider, _ = make_coordinator(provider=provider)
    cause = LookupError("caller-owned")

    with pytest.raises(LookupError) as captured:
        coordinator.get_or_load("key", lambda _: (_ for _ in ()).throw(cause))

    assert captured.value is cause
    assert len(provider.cleanups) == 1
    assert provider.publishes == []


def test_cleanup_failure_preserves_primary_and_adds_static_note() -> None:
    provider = FakeProvider()
    provider.cleanup_error = RuntimeError("provider-secret")
    coordinator, _, _, _ = make_coordinator(provider=provider)
    cause = LookupError("caller-owned")

    with pytest.raises(LookupError) as captured:
        coordinator.get_or_load("key", lambda _: (_ for _ in ()).throw(cause))

    assert captured.value is cause
    assert captured.value.__notes__ == ["Redis owner cleanup also failed (cleanup-failure)"]


def test_same_cache_burst_uses_one_distributed_flight() -> None:
    coordinator, _, provider, _ = make_coordinator()
    entered = threading.Event()
    release = threading.Event()
    results: list[object] = []

    def loader(_: str) -> str:
        entered.set()
        assert release.wait(2)
        return "loaded"

    threads = [
        threading.Thread(target=lambda: results.append(coordinator.get_or_load("key", loader)))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    assert entered.wait(2)
    release.set()
    for thread in threads:
        thread.join(2)

    assert results == ["loaded"] * 8
    assert len(provider.acquires) == 1


def test_redis_keys_are_digest_only() -> None:
    coordinator, _, provider, _ = make_coordinator()
    coordinator.get_or_load("customer-secret", lambda _: "loaded")

    lease_key = provider.acquires[0][0]
    assert "customer-secret" not in lease_key
    assert "orders:test:v1" not in lease_key
    assert lease_key.startswith("bluetape:cache:coord:")
    assert provider.publishes[0][2].endswith(":result")


def test_invalid_key_fails_before_cache_or_redis_access() -> None:
    coordinator, _, provider, _ = make_coordinator()

    with pytest.raises((TypeError, ValueError)):
        coordinator.get_or_load(b"key", lambda _: "unused")  # type: ignore[arg-type]

    assert provider.acquires == []


def test_unbounded_provider_policy_is_rejected_at_construction() -> None:
    provider = FakeProvider()
    provider.policy = None

    with pytest.raises(ValueError, match="bounded no-retry policy"):
        make_coordinator(provider=provider)


def test_provider_policy_must_fit_redis_io_timeout() -> None:
    provider = FakeProvider()

    with pytest.raises(ValueError, match="redis_io_timeout"):
        make_coordinator(
            provider=provider,
            options=RedisLoadOptions(namespace="orders:test:v1", redis_io_timeout=0.1),
        )


def test_observer_failure_is_isolated() -> None:
    observer = Observer()
    observer.error = RuntimeError("observer")
    coordinator, _, _, _ = make_coordinator(observer=observer)

    assert coordinator.get_or_load("key", lambda _: "loaded") == "loaded"
    assert len(observer.events) == 1


def test_poll_budget_exhaustion_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr("bluetape.cache.redis._coordination._sleep", lambda _: None)
    provider = FakeProvider()
    provider.acquire_results = [False]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"active:remote", result=None, marker_oversized=False, result_oversized=False
        )
    ]
    coordinator, _, _, _ = make_coordinator(
        provider=provider,
        options=RedisLoadOptions(namespace="orders:test:v1", max_polls=1),
    )

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        coordinator.get_or_load("key", lambda _: "unused")

    assert captured.value.code is RedisCoordinationErrorCode.POLLS_EXHAUSTED


def test_large_poll_budget_stays_bounded_and_ends_with_stable_timeout(monkeypatch) -> None:
    snapshot = RedisCoordinationSnapshot(
        marker=b"active:remote",
        result=None,
        marker_oversized=False,
        result_oversized=False,
    )
    provider = FakeProvider()
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
    monkeypatch.setattr("bluetape.cache.redis._coordination._sleep", lambda _: None)
    monkeypatch.setattr("bluetape.cache.redis._coordination._jitter", lambda: 1.0)

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        coordinator.get_or_load("key", lambda _: b"never")

    assert captured.value.code is RedisCoordinationErrorCode.POLLS_EXHAUSTED
    assert provider.snapshot_calls == 1_100


def test_attempt_budget_exhaustion_is_explicit() -> None:
    provider = FakeProvider()
    provider.acquire_results = [False]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=None, result=None, marker_oversized=False, result_oversized=False
        )
    ]
    coordinator, _, _, _ = make_coordinator(
        provider=provider,
        options=RedisLoadOptions(namespace="orders:test:v1", max_attempts=1),
    )

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        coordinator.get_or_load("key", lambda _: "unused")

    assert captured.value.code is RedisCoordinationErrorCode.ATTEMPTS_EXHAUSTED


def test_mismatched_completed_result_is_ignored_until_matching_result(monkeypatch) -> None:
    monkeypatch.setattr("bluetape.cache.redis._coordination._sleep", lambda _: None)
    provider = FakeProvider()
    provider.acquire_results = [False]
    codec = ResultEnvelopeCodec(payload_codec=JsonValueCodec())
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"completed:new-owner",
            result=codec.encode("old-owner", "stale"),
            marker_oversized=False,
            result_oversized=False,
        ),
        RedisCoordinationSnapshot(
            marker=b"completed:new-owner",
            result=codec.encode("new-owner", "fresh"),
            marker_oversized=False,
            result_oversized=False,
        ),
    ]
    coordinator, cache, _, _ = make_coordinator(provider=provider)
    coordinator._codec = codec

    assert coordinator.get_or_load("key", lambda _: pytest.fail("loader called")) == "fresh"
    assert cache.get("key") == "fresh"


def test_loader_finishing_after_lease_returns_local_without_encode_or_publish(monkeypatch) -> None:
    ticks = iter([0.0, 0.0, 0.0, 0.0, 0.0, 6.0])
    monkeypatch.setattr("bluetape.cache.redis._coordination._clock", lambda: next(ticks))
    observer = Observer()
    coordinator, _, provider, _ = make_coordinator(observer=observer)

    assert coordinator.get_or_load("key", lambda _: "local") == "local"
    assert provider.publishes == []
    assert provider.cleanups == []
    assert observer.events[-1].outcome is RedisCoordinationOutcome.LEASE_LOST


def test_late_acquire_deadline_cleans_marker_without_calling_loader(monkeypatch) -> None:
    ticks = iter([0.0, 0.0, 0.0, 11.0])
    monkeypatch.setattr("bluetape.cache.redis._coordination._clock", lambda: next(ticks))
    coordinator, _, provider, _ = make_coordinator()

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        coordinator.get_or_load("key", lambda _: pytest.fail("loader called"))

    assert captured.value.code is RedisCoordinationErrorCode.DEADLINE_EXCEEDED
    assert len(provider.cleanups) == 1
    assert provider.publishes == []


def test_token_work_cannot_start_acquire_after_deadline(monkeypatch) -> None:
    now = 0.0

    def delayed_token() -> str:
        nonlocal now
        now = 11.0
        return "owner"

    monkeypatch.setattr("bluetape.cache.redis._coordination._clock", lambda: now)
    monkeypatch.setattr("bluetape.cache.redis._coordination._new_token", delayed_token)
    observer = Observer()
    coordinator, _, provider, _ = make_coordinator(observer=observer)

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        coordinator.get_or_load("key", lambda _: pytest.fail("loader called"))

    assert captured.value.code is RedisCoordinationErrorCode.DEADLINE_EXCEEDED
    assert provider.acquires == []
    assert observer.events[-1].attempts == 0


def test_poll_sleep_cannot_start_snapshot_after_deadline(monkeypatch) -> None:
    now = 0.0
    provider = FakeProvider()
    provider.acquire_results = [False]
    provider.snapshots = [
        RedisCoordinationSnapshot(
            marker=b"active:remote",
            result=None,
            marker_oversized=False,
            result_oversized=False,
        )
    ]

    def expire_deadline(_: float) -> None:
        nonlocal now
        now = 11.0

    monkeypatch.setattr("bluetape.cache.redis._coordination._clock", lambda: now)
    monkeypatch.setattr("bluetape.cache.redis._coordination._sleep", expire_deadline)
    coordinator, _, _, _ = make_coordinator(provider=provider)

    with pytest.raises(RedisCoordinationTimeoutError) as captured:
        coordinator.get_or_load("key", lambda _: pytest.fail("loader called"))

    assert captured.value.code is RedisCoordinationErrorCode.DEADLINE_EXCEEDED
    assert provider.snapshot_calls == 1


def test_encode_overflow_cleans_owner_and_does_not_fill_cache() -> None:
    coordinator, cache, provider, _ = make_coordinator()
    coordinator._codec = ResultEnvelopeCodec(payload_codec=JsonValueCodec(), max_encoded_size=1)

    with pytest.raises(EnvelopeSizeError):
        coordinator.get_or_load("key", lambda _: "too-large")

    assert len(provider.cleanups) == 1
    assert provider.publishes == []
    with pytest.raises(KeyError):
        cache.get("key")


def test_local_cache_supersession_preserves_caller_value() -> None:
    coordinator, cache, provider, _ = make_coordinator()

    def loader(_: str) -> str:
        cache.set("key", "caller-value")
        return "loaded-snapshot"

    assert coordinator.get_or_load("key", loader) == "loaded-snapshot"
    assert cache.get("key") == "caller-value"
    assert len(provider.publishes) == 1


@pytest.mark.parametrize("ttl", [True, 0, -1, float("inf"), "1"])
def test_invalid_local_ttl_fails_before_redis_access(ttl: object) -> None:
    coordinator, _, provider, _ = make_coordinator()

    with pytest.raises((TypeError, ValueError)):
        coordinator.get_or_load("key", lambda _: "unused", ttl=ttl)  # type: ignore[arg-type]

    assert provider.acquires == []
