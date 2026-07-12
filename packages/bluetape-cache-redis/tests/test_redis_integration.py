from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
import redis
import redis.asyncio as redis_async
from bluetape.cache.redis import (
    AsyncRedisProvider,
    BinaryEnvelopeFormat,
    JsonEnvelopeFormat,
    RedisErrorCode,
    RedisProviderError,
    ResultEnvelopeCodec,
    SyncRedisProvider,
)
from bluetape.serde import SerializedPayload
from bluetape.testcontainers import RedisServer

pytestmark = pytest.mark.testcontainers


class BytesPayloadCodec:
    def encode(self, value: bytes) -> SerializedPayload:
        from _support import sample_metadata

        return SerializedPayload(metadata=sample_metadata(), data=value)

    def decode(self, payload: SerializedPayload) -> bytes:
        return payload.data


@pytest.fixture(scope="module")
def redis_server() -> Iterator[RedisServer]:
    with RedisServer() as server:
        yield server


@pytest.fixture(autouse=True)
def clean_redis(redis_server: RedisServer) -> Iterator[None]:
    client = redis.Redis.from_url(redis_server.url, decode_responses=False)
    client.flushdb()
    try:
        yield
    finally:
        client.flushdb()
        client.close()


def test_real_sync_commands_ttl_nx_and_compare_delete(redis_server: RedisServer) -> None:
    with SyncRedisProvider.from_url(redis_server.url) as provider:
        provider.set("issue:54:value", b"value", ttl=5.0)
        assert provider.get("issue:54:value") == b"value"
        assert provider.set_if_absent("issue:54:value", b"other", ttl=5.0) is False
        assert provider.delete_if_value("issue:54:value", b"other") is False
        assert provider.get("issue:54:value") == b"value"
        assert provider.delete_if_value("issue:54:value", b"value") is True
        assert provider.get("issue:54:value") is None


def test_real_sync_expiry_and_delete(redis_server: RedisServer) -> None:
    with SyncRedisProvider.from_url(redis_server.url) as provider:
        provider.set("issue:54:short", b"value", ttl=0.001)
        for _ in range(100):
            if provider.get("issue:54:short") is None:
                break
        else:
            pytest.fail("Redis PX key did not expire within the bounded polling loop")
        provider.set("issue:54:delete", b"value", ttl=5.0)
        assert provider.delete("issue:54:delete") is True
        assert provider.delete("issue:54:delete") is False


@pytest.mark.asyncio
async def test_real_async_commands_and_borrowed_client_lifecycle(
    redis_server: RedisServer,
) -> None:
    client = redis_async.Redis.from_url(redis_server.url, decode_responses=False)
    provider = AsyncRedisProvider(client)
    await provider.set("issue:54:async", b"value", ttl=5.0)
    assert await provider.get("issue:54:async") == b"value"
    assert await provider.set_if_absent("issue:54:async", b"other", ttl=5.0) is False
    assert await provider.delete_if_value("issue:54:async", b"value") is True
    await provider.aclose()
    assert await client.ping() is True
    await client.aclose()


def test_real_borrowed_sync_client_remains_open(redis_server: RedisServer) -> None:
    client = redis.Redis.from_url(redis_server.url, decode_responses=False)
    provider = SyncRedisProvider(client)
    provider.close()
    assert client.ping() is True
    client.close()


@pytest.mark.parametrize("formatter", [BinaryEnvelopeFormat(), JsonEnvelopeFormat()])
def test_real_redis_round_trips_both_envelope_formats(redis_server: RedisServer, formatter) -> None:
    codec = ResultEnvelopeCodec(payload_codec=BytesPayloadCodec(), envelope_format=formatter)
    with SyncRedisProvider.from_url(redis_server.url) as provider:
        provider.set(
            f"issue:54:{formatter.format_id}",
            codec.encode("owner-42", b"payload"),
            ttl=5.0,
        )
        stored = provider.get(f"issue:54:{formatter.format_id}")
        assert stored is not None
        assert codec.decode(stored, expected_owner_token="owner-42") == b"payload"


def test_real_script_acl_denial_has_no_racy_fallback(redis_server: RedisServer) -> None:
    admin = redis.Redis.from_url(redis_server.url, decode_responses=False)
    username = "issue54-noscript"
    password = "issue54-password"
    admin.execute_command(
        "ACL",
        "SETUSER",
        username,
        "on",
        f">{password}",
        "~*",
        "+@all",
        "-eval",
        "-evalsha",
    )
    parsed = urlsplit(redis_server.url)
    host = parsed.hostname or "localhost"
    authority = f"[{host}]" if ":" in host else host
    restricted_url = f"redis://{username}:{password}@{authority}:{parsed.port}/0"
    try:
        admin.set("issue:54:acl", b"owner", px=5000)
        with SyncRedisProvider.from_url(restricted_url) as provider:
            with pytest.raises(RedisProviderError) as captured:
                provider.delete_if_value("issue:54:acl", b"owner")
        assert captured.value.code is RedisErrorCode.PROVIDER_FAILURE
        assert "issue54" not in str(captured.value)
        assert admin.get("issue:54:acl") == b"owner"
    finally:
        admin.execute_command("ACL", "DELUSER", username)
        admin.close()


def test_real_connection_failure_is_redacted() -> None:
    provider = SyncRedisProvider.from_url(
        "redis://sensitive-user:sensitive-password@127.0.0.1:1/0",
        socket_connect_timeout=0.05,
        socket_timeout=0.05,
    )
    try:
        with pytest.raises(RedisProviderError) as captured:
            provider.get("sensitive-key")
        assert captured.value.code in {RedisErrorCode.CONNECTION, RedisErrorCode.TIMEOUT}
        assert "sensitive" not in str(captured.value)
        assert "sensitive" not in repr(captured.value)
    finally:
        provider.close()
