from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[3]
ENGLISH = ROOT / "packages/bluetape-leader-redis/README.md"
KOREAN = ROOT / "packages/bluetape-leader-redis/README.ko.md"


def snippet(text: str, name: str) -> str:
    match = re.search(
        rf"<!-- {re.escape(name)} -->\n```python\n(?P<code>.*?)\n```",
        text,
        re.DOTALL,
    )
    assert match is not None, f"missing {name}"
    return match.group("code")


def test_bilingual_sync_constructor_example_is_identical_and_executes() -> None:
    english = snippet(ENGLISH.read_text(), "sync-constructor-example")
    korean = snippet(KOREAN.read_text(), "sync-constructor-example")

    assert english == korean
    namespace: dict[str, object] = {}
    exec(english, namespace)
    client = namespace["client"]
    lock = namespace["lock"]
    assert client.connection_pool.connection_kwargs["host"] == "127.0.0.1"
    assert repr(lock) == "RedisDistributedLock(<redacted>)"
    client.close()


def test_bilingual_async_constructor_example_is_identical_and_executes() -> None:
    english = snippet(ENGLISH.read_text(), "async-constructor-example")
    korean = snippet(KOREAN.read_text(), "async-constructor-example")

    assert english == korean
    namespace: dict[str, object] = {}
    exec(english, namespace)
    client = namespace["client"]
    lock = namespace["lock"]
    assert client.connection_pool.connection_kwargs["host"] == "127.0.0.1"
    assert repr(lock) == "AsyncRedisDistributedLock(<redacted>)"


def test_adapter_readmes_pin_supported_client_and_operator_boundaries() -> None:
    required = (
        "pip install bluetape-leader-redis",
        'pip install "bluetape[leader-redis]"',
        "127.0.0.1",
        "UnixDomainSocketConnection",
        "TLS",
        "hostname",
        "retry",
        "health_check_interval",
        "event_dispatcher",
        "borrowed",
        "single-primary",
        "Sentinel",
        "Cluster",
        "ACL",
        "EVALSHA",
        "PEXPIRE",
        "fencing_token",
        "high-watermark",
        "LeaderBackendError",
        "pool timeout",
        "command failure",
        "reconnect",
    )
    for path in (ENGLISH, KOREAN):
        text = path.read_text()
        for value in required:
            assert value in text, f"{value!r} missing from {path}"
