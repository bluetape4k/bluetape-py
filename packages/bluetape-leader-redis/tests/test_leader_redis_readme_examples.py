from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any

from bluetape.leader import FencedLeaderLease, LeaderElectionOptions

ROOT = Path(__file__).parents[3]
ENGLISH = ROOT / "packages/bluetape-leader-redis/README.md"
KOREAN = ROOT / "packages/bluetape-leader-redis/README.ko.md"


class _ExampleHandle:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._lease = FencedLeaderLease("7", None, now, now + timedelta(seconds=1), 7)
        self._entered = False

    @property
    def lease(self) -> FencedLeaderLease:
        assert self._entered
        return self._lease

    def __enter__(self) -> _ExampleHandle:
        self._entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def __aenter__(self) -> _ExampleHandle:
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback


class _ExampleSyncLock:
    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions,
    ) -> _ExampleHandle:
        del lock_name, options
        return _ExampleHandle()


class _ExampleAsyncLock:
    async def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions,
    ) -> _ExampleHandle:
        del lock_name, options
        return _ExampleHandle()


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
    assert "async def main(" in english
    assert "await lock.try_acquire(" in english
    assert "finally:" in english
    assert "await client.aclose()" in english
    assert "return client, lock" not in english
    compile(english, "<async-constructor-example>", "exec")


def test_bilingual_elector_example_is_identical_and_complete() -> None:
    english = snippet(ENGLISH.read_text(), "elector-example")
    korean = snippet(KOREAN.read_text(), "elector-example")

    assert english == korean
    assert "RedisLeaderElector" in english
    assert "AsyncRedisLeaderElector" in english
    assert english.count("run_if_leader_result(") == 2
    assert "Elected" in english
    assert "Skipped" in english
    assert "ActionFailed" in english
    namespace: dict[str, Any] = {}
    exec(english, namespace)
    sync_elector_type = namespace["RedisLeaderElector"]
    async_elector_type = namespace["AsyncRedisLeaderElector"]

    def sync_elector(_client: object) -> Any:
        elector = object.__new__(sync_elector_type)
        elector._lock = _ExampleSyncLock()
        return elector

    def async_elector(_client: object) -> Any:
        elector = object.__new__(async_elector_type)
        elector._lock = _ExampleAsyncLock()
        return elector

    namespace["RedisLeaderElector"] = sync_elector
    namespace["AsyncRedisLeaderElector"] = async_elector
    options = LeaderElectionOptions()

    assert namespace["run_sync"](object(), options) == "completed"
    assert asyncio.run(namespace["run_async"](object(), options)) == "completed"


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


def test_bilingual_readmes_warn_about_plaintext_tcp_at_construction_and_deployment() -> None:
    expectations = {
        ENGLISH: (
            "caller-controlled protected network",
            "Prefer a local Unix socket whenever possible",
            "TLS is unsupported",
            "Redis credentials, owner tokens, and capability-bearing lock material",
            "network observers",
        ),
        KOREAN: (
            "호출자가 통제하는 보호된 네트워크",
            "가능하면 로컬 Unix socket을 우선",
            "TLS를 지원하지 않습니다",
            "Redis 자격 증명, owner token, capability 역할을 하는 lock material",
            "네트워크 관찰자",
        ),
    }

    for path, required in expectations.items():
        text = path.read_text()
        constructor = text.split("<!-- leader-scenario:constructor -->", 1)[1].split(
            "<!-- sync-constructor-example -->", 1
        )[0]
        deployment = text.split("<!-- leader-scenario:deployment-checklist -->", 1)[1]

        for section in (constructor, deployment):
            section = " ".join(section.split())
            for value in required:
                assert value in section, f"{value!r} missing from {path} section"


def test_bilingual_readmes_preserve_fence_history_restore_contract() -> None:
    expectations = {
        ENGLISH: (
            "`lease`/`fence`/`history` suffix set",
            "persistent `v1` history marker",
            "counter and history marker together",
            "marker exists but the counter is missing",
            "counter exists but the marker is missing",
        ),
        KOREAN: (
            "`lease`/`fence`/`history` suffix set",
            "persistent `v1` history marker",
            "Counter와 history marker를 함께",
            "Marker는 있지만 counter가 없거나",
            "counter는 있지만 marker가 없으면",
        ),
    }
    for path, required in expectations.items():
        text = " ".join(path.read_text().split())
        for value in required:
            assert value in text, f"{value!r} missing from {path}"


def test_bilingual_operator_tables_cover_each_lifecycle_condition() -> None:
    required = (
        "Contention",
        "Lease loss",
        "Renewal failure",
        "Release failure",
        "Connection",
        "Permission denial",
    )
    for path in (ENGLISH, KOREAN):
        table = (
            path.read_text()
            .split("<!-- leader-scenario:operator-actions -->", 1)[1]
            .split("<!-- leader-scenario:deployment-checklist -->", 1)[0]
        )
        for value in required:
            assert f"| {value}" in table, f"{value!r} row missing from {path}"
