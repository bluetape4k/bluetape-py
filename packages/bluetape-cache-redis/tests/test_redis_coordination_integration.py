import asyncio
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from urllib.parse import urlsplit

import pytest
import redis
import redis.asyncio as redis_async
from _support import sample_metadata
from bluetape.cache import AsyncTTLCache, TTLCache
from bluetape.cache.redis import (
    AsyncRedisLoadCoordinator,
    AsyncRedisProvider,
    RedisErrorCode,
    RedisLoadOptions,
    RedisProviderError,
    ResultEnvelopeCodec,
    SyncRedisLoadCoordinator,
    SyncRedisProvider,
)
from bluetape.serde import SerializedPayload
from bluetape.testcontainers import RedisServer

pytestmark = pytest.mark.testcontainers


class BytesCodec:
    def encode(self, value: bytes) -> SerializedPayload:
        return SerializedPayload(metadata=sample_metadata(), data=value)

    def decode(self, payload: SerializedPayload) -> bytes:
        return payload.data


def options(namespace: str = "orders:test:v1") -> RedisLoadOptions:
    return RedisLoadOptions(
        namespace=namespace,
        lease_ttl=2.0,
        result_ttl=2.0,
        poll_interval=0.001,
        max_poll_interval=0.01,
        wait_timeout=2.0,
        redis_io_timeout=0.4,
    )


def sync_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
        retry_on_timeout=False,
    )


def async_client(url: str) -> redis_async.Redis:
    return redis_async.Redis.from_url(
        url,
        decode_responses=False,
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
        retry_on_timeout=False,
    )


def coordination_keys(namespace: str, logical_key: str) -> tuple[str, str]:
    namespace_id = sha256(namespace.encode()).hexdigest()
    key_id = sha256(logical_key.encode()).hexdigest()
    slot = f"{{{namespace_id}:{key_id}}}"
    prefix = f"bluetape:cache:coord:{namespace_id}:{slot}"
    return f"{prefix}:lease", f"{prefix}:result"


def restricted_url(url: str, username: str, password: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or "localhost"
    authority = f"[{host}]" if ":" in host else host
    return f"redis://{username}:{password}@{authority}:{parsed.port}/0"


def create_acl_user(
    admin: redis.Redis,
    *,
    username: str,
    password: str,
    key_pattern: str,
    commands: tuple[str, ...],
) -> None:
    admin.execute_command(
        "ACL",
        "SETUSER",
        username,
        "reset",
        "on",
        f">{password}",
        f"~{key_pattern}",
        *(f"+{command}" for command in commands),
    )


@contextmanager
def acl_provider(
    redis_server: RedisServer,
    *,
    namespace: str,
    logical_key: str,
    username: str,
    password: str,
    allow_eval: bool,
) -> Iterator[tuple[redis.Redis, SyncRedisProvider, str]]:
    lease_key, _ = coordination_keys(namespace, logical_key)
    prefix = lease_key.rsplit(":", 1)[0] + ":*"
    commands = ["ping", "client", "get", "set", "del", "exists", "strlen", "getrange"]
    if allow_eval:
        commands.append("eval")
    admin = sync_client(redis_server.url)
    provider: SyncRedisProvider | None = None
    create_acl_user(
        admin,
        username=username,
        password=password,
        key_pattern=prefix,
        commands=tuple(commands),
    )
    try:
        provider = SyncRedisProvider.from_url(
            restricted_url(redis_server.url, username, password),
            socket_connect_timeout=0.1,
            socket_timeout=0.1,
            retry_on_timeout=False,
        )
        yield admin, provider, lease_key
    finally:
        if provider is not None:
            provider.close()
        admin.execute_command("ACL", "DELUSER", username)
        admin.close()


@pytest.fixture(scope="module")
def redis_server() -> Iterator[RedisServer]:
    with RedisServer() as server:
        yield server


@pytest.fixture(autouse=True)
def clean_redis(redis_server: RedisServer) -> Iterator[None]:
    client = sync_client(redis_server.url)
    client.flushdb()
    try:
        yield
    finally:
        client.flushdb()
        client.close()


@pytest.fixture
def blackhole_redis_url() -> Iterator[str]:
    listener = socket.create_server(("127.0.0.1", 0))
    listener.settimeout(0.05)
    accepted: list[socket.socket] = []
    stopped = threading.Event()

    def accept_connections() -> None:
        while not stopped.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            accepted.append(connection)

    thread = threading.Thread(target=accept_connections, daemon=True)
    thread.start()
    host, port = listener.getsockname()
    try:
        yield f"redis://{host}:{port}/0"
    finally:
        stopped.set()
        listener.close()
        for connection in accepted:
            connection.close()
        thread.join(timeout=1)
        assert not thread.is_alive()


def timeout_options(namespace: str) -> RedisLoadOptions:
    return RedisLoadOptions(
        namespace=namespace,
        lease_ttl=1.0,
        result_ttl=1.0,
        poll_interval=0.001,
        max_poll_interval=0.01,
        wait_timeout=0.05,
        redis_io_timeout=0.1,
    )


def test_sync_blackhole_timeout_is_bounded_redacted_and_skips_loader(
    blackhole_redis_url: str,
) -> None:
    provider = SyncRedisProvider.from_url(
        blackhole_redis_url,
        socket_connect_timeout=0.05,
        socket_timeout=0.05,
        retry_on_timeout=False,
    )
    coordinator = SyncRedisLoadCoordinator(
        TTLCache(default_ttl=60, max_size=10),
        provider,
        ResultEnvelopeCodec(payload_codec=BytesCodec()),
        options=timeout_options("orders:blackhole-sync:v1"),
    )
    loader_called = False

    def loader(_: str) -> bytes:
        nonlocal loader_called
        loader_called = True
        return b"unexpected"

    started = time.monotonic()
    try:
        with pytest.raises(RedisProviderError) as captured:
            coordinator.get_or_load("sensitive-key", loader)
        elapsed = time.monotonic() - started
        assert captured.value.code in {RedisErrorCode.TIMEOUT, RedisErrorCode.CONNECTION}
        assert "sensitive-key" not in str(captured.value)
        assert elapsed <= 0.4
        assert not loader_called
    finally:
        provider.close()


@pytest.mark.asyncio
async def test_async_blackhole_timeout_is_bounded_redacted_and_skips_loader(
    blackhole_redis_url: str,
) -> None:
    provider = AsyncRedisProvider.from_url(
        blackhole_redis_url,
        socket_connect_timeout=0.05,
        socket_timeout=0.05,
        retry_on_timeout=False,
    )
    coordinator = AsyncRedisLoadCoordinator(
        AsyncTTLCache(default_ttl=60, max_size=10),
        provider,
        ResultEnvelopeCodec(payload_codec=BytesCodec()),
        options=timeout_options("orders:blackhole-async:v1"),
    )
    loader_called = False

    async def loader(_: str) -> bytes:
        nonlocal loader_called
        loader_called = True
        return b"unexpected"

    started = time.monotonic()
    try:
        with pytest.raises(RedisProviderError) as captured:
            await coordinator.get_or_load("sensitive-key", loader)
        elapsed = time.monotonic() - started
        assert captured.value.code in {RedisErrorCode.TIMEOUT, RedisErrorCode.CONNECTION}
        assert "sensitive-key" not in str(captured.value)
        assert elapsed <= 0.4
        assert not loader_called
    finally:
        await provider.aclose()


def test_real_snapshot_is_bounded_and_stale_owner_cannot_publish(
    redis_server: RedisServer,
) -> None:
    client = sync_client(redis_server.url)
    provider = SyncRedisProvider(client)
    try:
        client.set("lease", b"active:new", px=5000)
        client.set("result", b"x" * 20, px=5000)
        snapshot = provider.coordination_snapshot(
            "lease", "result", max_marker_size=6, max_result_size=5
        )
        assert snapshot.marker == b"active"
        assert snapshot.marker_oversized is True
        assert snapshot.result == b"xxxxx"
        assert snapshot.result_oversized is True

        assert (
            provider.publish_if_value(
                "lease",
                b"active:old",
                result_key="result",
                result_value=b"stale",
                completion_value=b"completed:old",
                ttl=1.0,
            )
            is False
        )
        assert client.get("lease") == b"active:new"
        assert client.get("result") == b"x" * 20
    finally:
        provider.close()
        client.close()


def test_abandoned_lease_expires_and_next_owner_loads(redis_server: RedisServer) -> None:
    namespace = "orders:abandoned:v1"
    lease_key, _ = coordination_keys(namespace, "shared")
    client = sync_client(redis_server.url)
    provider = SyncRedisProvider(client)
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    client.set(lease_key, b"active:abandoned", px=10)
    loads = 0

    def loader(_: str) -> bytes:
        nonlocal loads
        loads += 1
        return b"recovered"

    coordinator = SyncRedisLoadCoordinator(
        TTLCache(default_ttl=60, max_size=10),
        provider,
        codec,
        options=RedisLoadOptions(
            namespace=namespace,
            lease_ttl=1.0,
            result_ttl=1.0,
            poll_interval=0.001,
            max_poll_interval=0.005,
            wait_timeout=1.0,
            redis_io_timeout=0.4,
        ),
    )
    try:
        assert coordinator.get_or_load("shared", loader) == b"recovered"
        assert loads == 1
    finally:
        provider.close()
        client.close()


class ReplaceStaleSnapshotProvider(SyncRedisProvider):
    def __init__(
        self,
        client: redis.Redis,
        *,
        codec: ResultEnvelopeCodec[bytes],
        lease_key: str,
        result_key: str,
    ) -> None:
        super().__init__(client)
        self.codec = codec
        self.lease_key = lease_key
        self.result_key = result_key
        self.replaced = False

    def coordination_snapshot(self, marker_key, result_key, **kwargs):
        snapshot = super().coordination_snapshot(marker_key, result_key, **kwargs)
        if not self.replaced:
            self.replaced = True
            self._client.set(self.lease_key, b"completed:new-owner", px=1000)
            self._client.set(
                self.result_key,
                self.codec.encode("new-owner", b"fresh"),
                px=1000,
            )
        return snapshot


def test_stale_completed_envelope_reaches_later_matching_result_without_loader(
    redis_server: RedisServer,
) -> None:
    namespace = "orders:stale-completed:v1"
    lease_key, result_key = coordination_keys(namespace, "shared")
    client = sync_client(redis_server.url)
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    client.set(lease_key, b"completed:old-owner", px=1000)
    client.set(result_key, codec.encode("different-owner", b"stale"), px=1000)
    provider = ReplaceStaleSnapshotProvider(
        client,
        codec=codec,
        lease_key=lease_key,
        result_key=result_key,
    )
    coordinator = SyncRedisLoadCoordinator(
        TTLCache(default_ttl=60, max_size=10),
        provider,
        codec,
        options=options(namespace),
    )
    loader_called = False

    def loader(_: str) -> bytes:
        nonlocal loader_called
        loader_called = True
        return b"unexpected"

    try:
        assert coordinator.get_or_load("shared", loader) == b"fresh"
        assert not loader_called
        assert provider.replaced
    finally:
        provider.close()
        client.close()


class SyncAcquireCounter:
    def __init__(self, target: int) -> None:
        self.target = target
        self.count = 0
        self.condition = threading.Condition()

    def record(self) -> None:
        with self.condition:
            self.count += 1
            self.condition.notify_all()

    def wait(self) -> None:
        with self.condition:
            assert self.condition.wait_for(lambda: self.count >= self.target, timeout=5)


class CountingSyncProvider(SyncRedisProvider):
    def __init__(self, client: redis.Redis, counter: SyncAcquireCounter) -> None:
        super().__init__(client)
        self.counter = counter
        self.acquire_calls = 0
        self.snapshot_calls = 0
        self.publish_calls = 0
        self.cleanup_calls = 0

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        self.acquire_calls += 1
        result = super().set_if_absent(key, value, ttl=ttl)
        self.counter.record()
        return result

    def coordination_snapshot(self, marker_key, result_key, **kwargs):
        self.snapshot_calls += 1
        return super().coordination_snapshot(marker_key, result_key, **kwargs)

    def publish_if_value(self, *args, **kwargs):
        self.publish_calls += 1
        return super().publish_if_value(*args, **kwargs)

    def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        self.cleanup_calls += 1
        return super().delete_if_value(key, expected_value)


def test_independent_sync_coordinators_share_one_loader(redis_server: RedisServer) -> None:
    coordinator_count = 8
    caller_count = 64
    counter = SyncAcquireCounter(coordinator_count)
    clients = [sync_client(redis_server.url) for _ in range(coordinator_count)]
    providers = [CountingSyncProvider(client, counter) for client in clients]
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    coordinators = [
        SyncRedisLoadCoordinator(
            TTLCache(default_ttl=60, max_size=10),
            provider,
            codec,
            options=options(),
        )
        for provider in providers
    ]
    loader_count = 0
    loader_lock = threading.Lock()

    def loader(_: str) -> bytes:
        nonlocal loader_count
        with loader_lock:
            loader_count += 1
        counter.wait()
        return b"value"

    barrier = threading.Barrier(caller_count)
    results: list[bytes] = []

    def call(index: int) -> None:
        barrier.wait()
        results.append(coordinators[index].get_or_load("shared", loader))

    threads = [
        threading.Thread(target=call, args=(index % coordinator_count,))
        for index in range(caller_count)
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert all(not thread.is_alive() for thread in threads)
        assert results == [b"value"] * caller_count
        assert loader_count == 1
        assert counter.count == coordinator_count
        assert all(provider.acquire_calls <= options().max_attempts for provider in providers)
        assert all(
            provider.snapshot_calls <= options().max_attempts + options().max_polls
            for provider in providers
        )
        assert sum(provider.publish_calls for provider in providers) == 1
        assert sum(provider.cleanup_calls for provider in providers) == 0
    finally:
        for provider in providers:
            provider.close()
        for client in clients:
            client.close()


def test_unrelated_keys_load_independently(redis_server: RedisServer) -> None:
    clients = [sync_client(redis_server.url) for _ in range(2)]
    providers = [SyncRedisProvider(client) for client in clients]
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    coordinators = [
        SyncRedisLoadCoordinator(
            TTLCache(default_ttl=60, max_size=10),
            provider,
            codec,
            options=options("orders:independent:v1"),
        )
        for provider in providers
    ]
    barrier = threading.Barrier(2)
    loaded: list[str] = []
    results: list[bytes] = []

    def loader(key: str) -> bytes:
        loaded.append(key)
        barrier.wait(timeout=5)
        return key.encode()

    threads = [
        threading.Thread(
            target=lambda coordinator=coordinator, key=key: results.append(
                coordinator.get_or_load(key, loader)
            )
        )
        for coordinator, key in zip(coordinators, ("alpha", "beta"), strict=True)
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert all(not thread.is_alive() for thread in threads)
        assert sorted(loaded) == ["alpha", "beta"]
        assert sorted(results) == [b"alpha", b"beta"]
    finally:
        for provider in providers:
            provider.close()
        for client in clients:
            client.close()


class AsyncAcquireCounter:
    def __init__(self, target: int) -> None:
        self.target = target
        self.count = 0
        self.ready = asyncio.Event()

    def record(self) -> None:
        self.count += 1
        if self.count >= self.target:
            self.ready.set()


class AcquiredAsyncProvider(AsyncRedisProvider):
    def __init__(self, client: redis_async.Redis) -> None:
        super().__init__(client)
        self.acquired = asyncio.Event()

    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        result = await super().set_if_absent(key, value, ttl=ttl)
        if result:
            self.acquired.set()
        return result


@pytest.mark.asyncio
async def test_real_async_last_waiter_cancellation_cleans_lease_and_flight(
    redis_server: RedisServer,
) -> None:
    namespace = "orders:cancellation:v1"
    lease_key, _ = coordination_keys(namespace, "shared")
    client = async_client(redis_server.url)
    provider = AcquiredAsyncProvider(client)
    cache = AsyncTTLCache(default_ttl=60, max_size=10)
    coordinator = AsyncRedisLoadCoordinator(
        cache,
        provider,
        ResultEnvelopeCodec(payload_codec=BytesCodec()),
        options=options(namespace),
    )
    blocker = asyncio.Event()

    async def loader(_: str) -> bytes:
        await blocker.wait()
        return b"unexpected"

    caller = asyncio.create_task(coordinator.get_or_load("shared", loader))
    try:
        await asyncio.wait_for(provider.acquired.wait(), timeout=1)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        for _ in range(100):
            if (await cache.stats()).inflight_loads == 0:
                break
            await asyncio.sleep(0)
        assert (await cache.stats()).inflight_loads == 0
        assert await client.get(lease_key) is None
    finally:
        if not caller.done():
            caller.cancel()
            await asyncio.gather(caller, return_exceptions=True)
        await provider.aclose()
        await client.aclose()


class CountingAsyncProvider(AsyncRedisProvider):
    def __init__(self, client: redis_async.Redis, counter: AsyncAcquireCounter) -> None:
        super().__init__(client)
        self.counter = counter
        self.acquire_calls = 0
        self.snapshot_calls = 0
        self.publish_calls = 0
        self.cleanup_calls = 0

    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        self.acquire_calls += 1
        result = await super().set_if_absent(key, value, ttl=ttl)
        self.counter.record()
        return result

    async def coordination_snapshot(self, marker_key, result_key, **kwargs):
        self.snapshot_calls += 1
        return await super().coordination_snapshot(marker_key, result_key, **kwargs)

    async def publish_if_value(self, *args, **kwargs):
        self.publish_calls += 1
        return await super().publish_if_value(*args, **kwargs)

    async def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        self.cleanup_calls += 1
        return await super().delete_if_value(key, expected_value)


@pytest.mark.asyncio
async def test_independent_async_coordinators_share_one_loader(
    redis_server: RedisServer,
) -> None:
    coordinator_count = 8
    caller_count = 64
    counter = AsyncAcquireCounter(coordinator_count)
    clients = [async_client(redis_server.url) for _ in range(coordinator_count)]
    providers = [CountingAsyncProvider(client, counter) for client in clients]
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    coordinators = [
        AsyncRedisLoadCoordinator(
            AsyncTTLCache(default_ttl=60, max_size=10),
            provider,
            codec,
            options=options(),
        )
        for provider in providers
    ]
    loader_count = 0

    async def loader(_: str) -> bytes:
        nonlocal loader_count
        loader_count += 1
        await counter.ready.wait()
        return b"value"

    try:
        results = await asyncio.gather(
            *(
                coordinators[index % coordinator_count].get_or_load("shared", loader)
                for index in range(caller_count)
            )
        )
        assert results == [b"value"] * caller_count
        assert loader_count == 1
        assert counter.count == coordinator_count
        assert all(provider.acquire_calls <= options().max_attempts for provider in providers)
        assert all(
            provider.snapshot_calls <= options().max_attempts + options().max_polls
            for provider in providers
        )
        assert sum(provider.publish_calls for provider in providers) == 1
        assert sum(provider.cleanup_calls for provider in providers) == 0
    finally:
        for provider in providers:
            await provider.aclose()
        for client in clients:
            await client.aclose()


@pytest.mark.parametrize("phase", ["snapshot", "publish"])
def test_acl_eval_denial_is_explicit_without_fallback(
    redis_server: RedisServer,
    phase: str,
) -> None:
    namespace = f"orders:acl-{phase}:v1"
    logical_key = "shared"
    username = f"issue55-{phase}"
    password = f"issue55-{phase}-password"
    loader_calls = 0

    def loader(_: str) -> bytes:
        nonlocal loader_calls
        loader_calls += 1
        return b"value"

    with acl_provider(
        redis_server,
        namespace=namespace,
        logical_key=logical_key,
        username=username,
        password=password,
        allow_eval=False,
    ) as (admin, provider, lease_key):
        if phase == "snapshot":
            admin.set(lease_key, b"active:existing", px=5000)
        coordinator = SyncRedisLoadCoordinator(
            TTLCache(default_ttl=60, max_size=10),
            provider,
            ResultEnvelopeCodec(payload_codec=BytesCodec()),
            options=options(namespace),
        )
        with pytest.raises(RedisProviderError) as captured:
            coordinator.get_or_load(logical_key, loader)
        assert captured.value.code is RedisErrorCode.PROVIDER_FAILURE
        assert username not in str(captured.value)
        assert password not in str(captured.value)
        assert logical_key not in str(captured.value)
        assert loader_calls == (0 if phase == "snapshot" else 1)
        assert admin.get(lease_key) is not None


def test_acl_cleanup_denial_preserves_loader_failure_and_has_no_fallback(
    redis_server: RedisServer,
) -> None:
    namespace = "orders:acl-cleanup:v1"
    logical_key = "shared"
    username = "issue55-cleanup"
    password = "issue55-cleanup-password"

    def loader(_: str) -> bytes:
        raise ValueError("caller loader failed")

    with acl_provider(
        redis_server,
        namespace=namespace,
        logical_key=logical_key,
        username=username,
        password=password,
        allow_eval=False,
    ) as (admin, provider, lease_key):
        coordinator = SyncRedisLoadCoordinator(
            TTLCache(default_ttl=60, max_size=10),
            provider,
            ResultEnvelopeCodec(payload_codec=BytesCodec()),
            options=options(namespace),
        )
        with pytest.raises(ValueError, match="caller loader failed") as captured:
            coordinator.get_or_load(logical_key, loader)
        assert captured.value.__notes__ == ["Redis owner cleanup also failed (cleanup-failure)"]
        assert admin.get(lease_key) is not None


def test_least_privilege_acl_can_coordinate_within_derived_prefix(
    redis_server: RedisServer,
) -> None:
    namespace = "orders:acl-success:v1"
    logical_key = "shared"
    username = "issue55-success"
    password = "issue55-success-password"
    with acl_provider(
        redis_server,
        namespace=namespace,
        logical_key=logical_key,
        username=username,
        password=password,
        allow_eval=True,
    ) as (_, provider, _):
        coordinator = SyncRedisLoadCoordinator(
            TTLCache(default_ttl=60, max_size=10),
            provider,
            ResultEnvelopeCodec(payload_codec=BytesCodec()),
            options=options(namespace),
        )
        assert coordinator.get_or_load(logical_key, lambda _: b"value") == b"value"


def test_schema_version_namespaces_do_not_coalesce(redis_server: RedisServer) -> None:
    clients = [sync_client(redis_server.url) for _ in range(2)]
    providers = [SyncRedisProvider(client) for client in clients]
    codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
    barrier = threading.Barrier(2)
    loader_count = 0
    lock = threading.Lock()

    def loader(_: str) -> bytes:
        nonlocal loader_count
        with lock:
            loader_count += 1
        barrier.wait(timeout=5)
        return b"value"

    coordinators = [
        SyncRedisLoadCoordinator(
            TTLCache(default_ttl=60, max_size=10),
            providers[index],
            codec,
            options=options(f"orders:test:v{index + 1}"),
        )
        for index in range(2)
    ]
    results = []
    threads = [
        threading.Thread(
            target=lambda coordinator=coordinator: results.append(
                coordinator.get_or_load("shared", loader)
            )
        )
        for coordinator in coordinators
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert results == [b"value", b"value"]
        assert loader_count == 2
    finally:
        for provider in providers:
            provider.close()
        for client in clients:
            client.close()
