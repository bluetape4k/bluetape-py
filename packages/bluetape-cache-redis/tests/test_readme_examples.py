import re
from pathlib import Path

import pytest
from bluetape.cache.redis import (
    AsyncRedisProvider,
    RedisCommandPolicy,
    SyncRedisProvider,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile

ROOT = Path(__file__).parents[3]
ENGLISH = ROOT / "packages/bluetape-cache-redis/README.md"
KOREAN = ROOT / "packages/bluetape-cache-redis/README.ko.md"


def snippet(text: str, name: str) -> str:
    match = re.search(
        rf"<!-- {re.escape(name)} -->\n```python\n(?P<code>.*?)\n```",
        text,
        re.DOTALL,
    )
    assert match is not None, f"missing {name}"
    return match.group("code")


class Utf8Codec:
    def encode(self, value: str) -> SerializedPayload:
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="text",
                version=1,
                content_type="text/plain",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=value.encode(),
        )

    def decode(self, payload: SerializedPayload) -> str:
        return payload.data.decode()


class RecordingSyncProvider(SyncRedisProvider):
    def __init__(self) -> None:
        self.closed = False

    @property
    def command_policy(self) -> RedisCommandPolicy:
        return RedisCommandPolicy(connect_timeout=0.1, socket_timeout=0.1)

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        return True

    def publish_if_value(self, *args: object, **kwargs: object) -> bool:
        return True

    def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class RecordingAsyncProvider(AsyncRedisProvider):
    def __init__(self) -> None:
        self.closed = False

    @property
    def command_policy(self) -> RedisCommandPolicy:
        return RedisCommandPolicy(connect_timeout=0.1, socket_timeout=0.1)

    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        return True

    async def publish_if_value(self, *args: object, **kwargs: object) -> bool:
        return True

    async def delete_if_value(self, key: str, expected_value: bytes) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.parametrize("name", ["sync-coordination-example", "async-coordination-example"])
def test_bilingual_coordination_examples_are_identical_and_compile(name: str) -> None:
    english = snippet(ENGLISH.read_text(), name)
    korean = snippet(KOREAN.read_text(), name)

    assert english == korean
    compile(english, f"<{name}>", "exec")


@pytest.mark.parametrize("path", [ENGLISH, KOREAN])
def test_focused_readme_records_coordination_security_and_operations(path: Path) -> None:
    text = path.read_text()
    for required in (
        "SyncRedisLoadCoordinator",
        "AsyncRedisLoadCoordinator",
        "orders:prod:tenant-a:order-v3",
        "pip install bluetape-cache-redis",
        'pip install "bluetape[cache-redis]"',
        "bluetape-cache==0.1.0",
        "core-only",
        "pseudonym",
        "unauthenticated",
        "TLS",
        "ACL",
        "EVAL",
        "SCAN",
        "UNLINK",
        "max(lease_ttl, result_ttl) + redis_io_timeout",
        "cleanup_failed",
        "no L2",
        "no fencing",
        "transitively",
        "Conflicting configurations",
        "distributed invalidation",
        "loader_count == 2",
        "Local hit",
        "terminal event",
        "zero retry",
        "unsafe deserialization",
        "sha256(namespace)",
        "RedisCoordinationError",
        "quiescence",
    ):
        if path == KOREAN and required == "Conflicting configurations":
            assert "서로 충돌하는 설정" in text
        else:
            assert required in text


def test_root_readmes_record_focused_extra_and_default_isolation() -> None:
    for path in (ROOT / "README.md", ROOT / "README.ko.md"):
        text = path.read_text()
        assert 'pip install "bluetape[cache-redis]"' in text
        assert "bluetape-cache" in text
        assert "core-only" in text
        assert "Redis-free" in text


def test_sync_readme_example_executes_public_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = RecordingSyncProvider()
    monkeypatch.setattr(
        SyncRedisProvider,
        "from_url",
        classmethod(lambda cls, *args, **kwargs: provider),
    )
    namespace = {"Utf8Codec": Utf8Codec, "load_order": lambda key: f"loaded:{key}"}

    exec(snippet(ENGLISH.read_text(), "sync-coordination-example"), namespace)

    assert namespace["value"] == "loaded:order-42"
    assert provider.closed


@pytest.mark.asyncio
async def test_async_readme_example_executes_public_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = RecordingAsyncProvider()
    monkeypatch.setattr(
        AsyncRedisProvider,
        "from_url",
        classmethod(lambda cls, *args, **kwargs: provider),
    )

    async def load_order(key: str) -> str:
        return f"loaded:{key}"

    namespace = {"Utf8Codec": Utf8Codec, "load_order": load_order}
    exec(snippet(ENGLISH.read_text(), "async-coordination-example"), namespace)

    assert await namespace["coordinated_load"]() == "loaded:order-42"
    assert provider.closed
