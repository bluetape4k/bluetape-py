import asyncio
import threading
from collections.abc import Iterator

import pytest
import redis
import redis.asyncio as redis_async
from _support import sample_metadata
from bluetape.cache import AsyncTTLCache, TTLCache
from bluetape.cache.redis import (
    AsyncRedisLoadCoordinator,
    AsyncRedisProvider,
    RedisLoadOptions,
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

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        result = super().set_if_absent(key, value, ttl=ttl)
        self.counter.record()
        return result


def test_independent_sync_coordinators_share_one_loader(redis_server: RedisServer) -> None:
    count = 8
    counter = SyncAcquireCounter(count)
    clients = [sync_client(redis_server.url) for _ in range(count)]
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

    barrier = threading.Barrier(count)
    results: list[bytes] = []

    def call(index: int) -> None:
        barrier.wait()
        results.append(coordinators[index].get_or_load("shared", loader))

    threads = [threading.Thread(target=call, args=(index,)) for index in range(count)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert all(not thread.is_alive() for thread in threads)
        assert results == [b"value"] * count
        assert loader_count == 1
        assert counter.count == count
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


class CountingAsyncProvider(AsyncRedisProvider):
    def __init__(self, client: redis_async.Redis, counter: AsyncAcquireCounter) -> None:
        super().__init__(client)
        self.counter = counter

    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        result = await super().set_if_absent(key, value, ttl=ttl)
        self.counter.record()
        return result


@pytest.mark.asyncio
async def test_independent_async_coordinators_share_one_loader(
    redis_server: RedisServer,
) -> None:
    count = 8
    counter = AsyncAcquireCounter(count)
    clients = [async_client(redis_server.url) for _ in range(count)]
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
            *(coordinator.get_or_load("shared", loader) for coordinator in coordinators)
        )
        assert results == [b"value"] * count
        assert loader_count == 1
        assert counter.count == count
    finally:
        for provider in providers:
            await provider.aclose()
        for client in clients:
            await client.aclose()


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
