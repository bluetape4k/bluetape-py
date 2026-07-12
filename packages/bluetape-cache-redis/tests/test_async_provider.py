import asyncio
import inspect
from types import SimpleNamespace

import pytest
import redis.asyncio as redis_async
from _support import (
    COORDINATION_SNAPSHOT_SCRIPT,
    PUBLISH_IF_VALUE_SCRIPT,
    bounded_command_options,
)
from bluetape.cache.redis import (
    DEFAULT_MAX_ENCODED_SIZE,
    MAX_COORDINATION_MARKER_SIZE,
    AsyncRedisProvider,
    ProviderClosedError,
    RedisCommandPolicy,
    RedisCoordinationSnapshot,
    RedisErrorCode,
    RedisMode,
    RedisOperation,
    RedisOutcome,
    RedisProviderError,
)
from bluetape.cache.redis._provider import COMPARE_AND_DELETE_SCRIPT


class AsyncFakeRedis:
    def __init__(self) -> None:
        self.connection_pool = SimpleNamespace(connection_kwargs=bounded_command_options())
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.responses: dict[str, object] = {
            "get": b"value",
            "set": True,
            "delete": 1,
            "eval": 1,
        }
        self.errors: dict[str, BaseException] = {}
        self.aclose_calls = 0
        self.get_started = asyncio.Event()
        self.get_release: asyncio.Event | None = None
        self.close_started = asyncio.Event()
        self.close_release: asyncio.Event | None = None

    async def _call(self, name: str, *args: object, **kwargs: object) -> object:
        self.calls.append((name, args, kwargs))
        if name == "get":
            self.get_started.set()
            if self.get_release is not None:
                await self.get_release.wait()
        error = self.errors.get(name)
        if error is not None:
            raise error
        return self.responses[name]

    async def get(self, *args: object, **kwargs: object) -> object:
        return await self._call("get", *args, **kwargs)

    async def set(self, *args: object, **kwargs: object) -> object:
        return await self._call("set", *args, **kwargs)

    async def delete(self, *args: object, **kwargs: object) -> object:
        return await self._call("delete", *args, **kwargs)

    async def eval(self, *args: object, **kwargs: object) -> object:
        return await self._call("eval", *args, **kwargs)

    async def aclose(self) -> None:
        self.aclose_calls += 1
        self.close_started.set()
        if self.close_release is not None:
            await self.close_release.wait()
        error = self.errors.get("aclose")
        if error is not None:
            raise error


class RecordingObserver:
    def __init__(self) -> None:
        self.events = []
        self.error: BaseException | None = None

    def on_event(self, event) -> None:
        self.events.append(event)
        if self.error is not None:
            raise self.error


def test_async_provider_public_signatures_are_exact() -> None:
    assert (
        str(inspect.signature(AsyncRedisProvider)) == "(client: redis.asyncio.client.Redis, *, "
        "observer: bluetape.cache.redis._contracts.RedisObserver | None = None) -> None"
    )
    assert (
        str(inspect.signature(AsyncRedisProvider.from_url)) == "(url: str, *, "
        "observer: bluetape.cache.redis._contracts.RedisObserver | None = None, "
        "**redis_options: object) -> Self"
    )
    assert str(inspect.signature(AsyncRedisProvider.get)) == "(self, key: str) -> bytes | None"
    assert (
        str(inspect.signature(AsyncRedisProvider.set))
        == "(self, key: str, value: bytes, *, ttl: float) -> None"
    )
    assert (
        str(inspect.signature(AsyncRedisProvider.set_if_absent))
        == "(self, key: str, value: bytes, *, ttl: float) -> bool"
    )
    assert (
        str(inspect.signature(AsyncRedisProvider.coordination_snapshot))
        == "(self, marker_key: str, result_key: str, *, max_marker_size: int = 138, "
        "max_result_size: int) -> bluetape.cache.redis._contracts.RedisCoordinationSnapshot"
    )
    assert (
        str(inspect.signature(AsyncRedisProvider.publish_if_value))
        == "(self, condition_key: str, expected_value: bytes, *, result_key: str, "
        "result_value: bytes, completion_value: bytes, ttl: float) -> bool"
    )
    assert str(inspect.signature(AsyncRedisProvider.aclose)) == "(self) -> None"


def test_async_command_policy_matches_sync_discovery() -> None:
    client = AsyncFakeRedis()

    assert AsyncRedisProvider(client).command_policy == RedisCommandPolicy(
        connect_timeout=0.1,
        socket_timeout=0.2,
    )


@pytest.mark.asyncio
async def test_async_command_policy_rejects_blocking_connection_pool() -> None:
    client = redis_async.Redis(
        connection_pool=redis_async.BlockingConnectionPool(
            max_connections=1,
            timeout=0.1,
            **bounded_command_options(),
        )
    )
    try:
        assert AsyncRedisProvider(client).command_policy is None
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "change",
    [
        {"socket_connect_timeout": None},
        {"socket_timeout": float("inf")},
        {"retry_on_timeout": True},
        {"retry_on_error": [TimeoutError]},
        {"retry": object()},
    ],
)
def test_async_command_policy_rejects_unbounded_or_retrying_options(change) -> None:
    client = AsyncFakeRedis()
    client.connection_pool.connection_kwargs.update(change)

    assert AsyncRedisProvider(client).command_policy is None


@pytest.mark.asyncio
async def test_async_coordination_snapshot_uses_one_bounded_eval() -> None:
    client = AsyncFakeRedis()
    client.responses["eval"] = [1, 7, b"active", 1, 4, b"res"]

    snapshot = await AsyncRedisProvider(client).coordination_snapshot(
        "marker",
        "result",
        max_marker_size=6,
        max_result_size=3,
    )

    assert snapshot == RedisCoordinationSnapshot(
        marker=b"active",
        result=b"res",
        marker_oversized=True,
        result_oversized=True,
    )
    assert client.calls == [
        ("eval", (COORDINATION_SNAPSHOT_SCRIPT, 2, "marker", "result", 6, 3), {})
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        None,
        [1, 1, b"a"],
        [1, 1, b"a", False, 0, b""],
        [1, 2, b"a", 0, 0, b""],
        [1, 8, b"too-long", 0, 0, b""],
    ],
)
async def test_async_coordination_snapshot_rejects_malformed_response(response) -> None:
    client = AsyncFakeRedis()
    client.responses["eval"] = response

    with pytest.raises(RedisProviderError) as captured:
        await AsyncRedisProvider(client).coordination_snapshot(
            "marker", "result", max_marker_size=7, max_result_size=8
        )

    assert captured.value.operation is RedisOperation.COORDINATION_SNAPSHOT
    assert captured.value.code is RedisErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("marker_key", "result_key", "max_marker_size", "max_result_size"),
    [
        ("same", "same", 1, 1),
        ("marker", "result", True, 1),
        ("marker", "result", MAX_COORDINATION_MARKER_SIZE + 1, 1),
        ("marker", "result", 1, True),
        ("marker", "result", 1, DEFAULT_MAX_ENCODED_SIZE + 1),
    ],
)
async def test_async_coordination_snapshot_rejects_invalid_limits_before_eval(
    marker_key,
    result_key,
    max_marker_size,
    max_result_size,
) -> None:
    client = AsyncFakeRedis()

    with pytest.raises((TypeError, ValueError)):
        await AsyncRedisProvider(client).coordination_snapshot(
            marker_key,
            result_key,
            max_marker_size=max_marker_size,
            max_result_size=max_result_size,
        )

    assert client.calls == []


@pytest.mark.asyncio
async def test_async_publish_if_value_uses_one_atomic_eval() -> None:
    client = AsyncFakeRedis()

    assert (
        await AsyncRedisProvider(client).publish_if_value(
            "lease",
            b"active:owner",
            result_key="result",
            result_value=b"encoded",
            completion_value=b"completed:owner",
            ttl=1.25,
        )
        is True
    )
    assert client.calls == [
        (
            "eval",
            (
                PUBLISH_IF_VALUE_SCRIPT,
                2,
                "lease",
                "result",
                b"active:owner",
                b"encoded",
                1250,
                b"completed:owner",
            ),
            {},
        )
    ]


@pytest.mark.asyncio
async def test_async_stale_owner_cannot_publish() -> None:
    client = AsyncFakeRedis()
    client.responses["eval"] = 0

    assert (
        await AsyncRedisProvider(client).publish_if_value(
            "lease",
            b"active:old",
            result_key="result",
            result_value=b"old",
            completion_value=b"completed:old",
            ttl=1.0,
        )
        is False
    )
    assert [call[0] for call in client.calls] == ["eval"]


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [None, True, b"1", 2])
async def test_async_publish_if_value_rejects_invalid_script_response(response) -> None:
    client = AsyncFakeRedis()
    client.responses["eval"] = response

    with pytest.raises(RedisProviderError) as captured:
        await AsyncRedisProvider(client).publish_if_value(
            "lease",
            b"active:owner",
            result_key="result",
            result_value=b"encoded",
            completion_value=b"completed:owner",
            ttl=1.0,
        )

    assert captured.value.operation is RedisOperation.PUBLISH_IF_VALUE
    assert captured.value.code is RedisErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
async def test_async_publish_if_value_rejects_identical_keys_before_eval() -> None:
    client = AsyncFakeRedis()

    with pytest.raises(ValueError, match="distinct"):
        await AsyncRedisProvider(client).publish_if_value(
            "same",
            b"active:owner",
            result_key="same",
            result_value=b"encoded",
            completion_value=b"completed:owner",
            ttl=1.0,
        )

    assert client.calls == []


@pytest.mark.asyncio
async def test_async_command_semantics_are_exact() -> None:
    client = AsyncFakeRedis()
    provider = AsyncRedisProvider(client)  # type: ignore[arg-type]

    assert await provider.get("key") == b"value"
    await provider.set("key", b"value", ttl=1.25)
    assert await provider.set_if_absent("key", b"value", ttl=0.000_1) is True
    assert await provider.delete("key") is True
    assert await provider.delete_if_value("key", b"token") is True
    assert client.calls == [
        ("get", ("key",), {}),
        ("set", ("key", b"value"), {"px": 1250}),
        ("set", ("key", b"value"), {"nx": True, "px": 1}),
        ("delete", ("key",), {}),
        ("eval", (COMPARE_AND_DELETE_SCRIPT, 1, "key", b"token"), {}),
    ]


@pytest.mark.asyncio
async def test_async_operation_cancellation_is_unchanged_and_provider_remains_usable() -> None:
    client = AsyncFakeRedis()
    client.errors["get"] = asyncio.CancelledError()
    observer = RecordingObserver()
    provider = AsyncRedisProvider(client, observer=observer)  # type: ignore[arg-type]

    with pytest.raises(asyncio.CancelledError):
        await provider.get("key")

    assert client.calls == [("get", ("key",), {})]
    assert observer.events[0].outcome is RedisOutcome.CANCELLED
    client.errors.clear()
    assert await provider.get("key") == b"value"


@pytest.mark.asyncio
async def test_async_failures_are_redacted_and_retain_causes() -> None:
    client = AsyncFakeRedis()
    cause = redis_async.ConnectionError("sensitive-provider-text")
    client.errors["get"] = cause

    with pytest.raises(RedisProviderError) as captured:
        await AsyncRedisProvider(client).get("sensitive-key")  # type: ignore[arg-type]

    assert captured.value.code is RedisErrorCode.CONNECTION
    assert captured.value.__cause__ is cause
    assert "sensitive" not in str(captured.value)


@pytest.mark.asyncio
async def test_borrowed_aclose_preserves_client_and_rejects_operations() -> None:
    client = AsyncFakeRedis()
    provider = AsyncRedisProvider(client)  # type: ignore[arg-type]
    await provider.aclose()
    await provider.aclose()

    assert client.aclose_calls == 0
    with pytest.raises(ProviderClosedError):
        await provider.get("key")


@pytest.mark.asyncio
async def test_from_url_forwards_options_and_closes_owned_client_once(monkeypatch) -> None:
    client = AsyncFakeRedis()
    captured = {}

    def from_url(url: str, **options: object):
        captured.update(url=url, **options)
        return client

    monkeypatch.setattr(redis_async.Redis, "from_url", from_url)
    provider = AsyncRedisProvider.from_url("redis://sensitive.invalid/0", socket_timeout=2.0)
    await provider.aclose()
    await provider.aclose()

    assert captured == {
        "url": "redis://sensitive.invalid/0",
        "socket_timeout": 2.0,
        "decode_responses": False,
    }
    assert client.aclose_calls == 1


@pytest.mark.asyncio
async def test_concurrent_aclose_joins_one_cleanup(monkeypatch) -> None:
    client = AsyncFakeRedis()
    client.close_release = asyncio.Event()
    monkeypatch.setattr(redis_async.Redis, "from_url", lambda *args, **kwargs: client)
    provider = AsyncRedisProvider.from_url("redis://localhost")
    first = asyncio.create_task(provider.aclose())
    await client.close_started.wait()
    second = asyncio.create_task(provider.aclose())
    client.close_release.set()
    await asyncio.gather(first, second)

    assert client.aclose_calls == 1


@pytest.mark.asyncio
async def test_cancelled_aclose_finishes_owned_cleanup_before_rethrow(monkeypatch) -> None:
    client = AsyncFakeRedis()
    client.close_release = asyncio.Event()
    monkeypatch.setattr(redis_async.Redis, "from_url", lambda *args, **kwargs: client)
    provider = AsyncRedisProvider.from_url("redis://sensitive.invalid/0")
    tasks_before = set(asyncio.all_tasks())
    caller = asyncio.create_task(provider.aclose())
    await client.close_started.wait()
    caller.cancel()
    await asyncio.sleep(0)
    assert not caller.done()
    client.close_release.set()

    with pytest.raises(asyncio.CancelledError):
        await caller

    assert client.aclose_calls == 1
    with pytest.raises(ProviderClosedError):
        await provider.get("key")
    await asyncio.sleep(0)
    assert not ({task for task in asyncio.all_tasks() if not task.done()} - tasks_before)


@pytest.mark.asyncio
async def test_cancelled_aclose_wins_over_shared_cleanup_failure(monkeypatch) -> None:
    client = AsyncFakeRedis()
    client.close_release = asyncio.Event()
    client.errors["aclose"] = RuntimeError("sensitive-close")
    monkeypatch.setattr(redis_async.Redis, "from_url", lambda *args, **kwargs: client)
    observer = RecordingObserver()
    provider = AsyncRedisProvider.from_url("redis://localhost", observer=observer)
    cancelled = asyncio.create_task(provider.aclose())
    await client.close_started.wait()
    joined = asyncio.create_task(provider.aclose())
    cancelled.cancel()
    client.close_release.set()

    with pytest.raises(asyncio.CancelledError):
        await cancelled
    with pytest.raises(RedisProviderError):
        await joined
    close_events = [event for event in observer.events if event.operation is RedisOperation.CLOSE]
    cancelled_event = next(
        event for event in close_events if event.outcome is RedisOutcome.CANCELLED
    )
    assert cancelled_event.error_code is RedisErrorCode.PROVIDER_FAILURE
    assert any(event.outcome is RedisOutcome.FAILURE for event in close_events)
    await provider.aclose()


@pytest.mark.asyncio
async def test_aclose_waits_for_admitted_operation_and_rejects_new_work() -> None:
    client = AsyncFakeRedis()
    client.get_release = asyncio.Event()
    provider = AsyncRedisProvider(client)  # type: ignore[arg-type]
    operation = asyncio.create_task(provider.get("key"))
    await client.get_started.wait()
    closer = asyncio.create_task(provider.aclose())
    await asyncio.sleep(0)
    assert not closer.done()
    with pytest.raises(ProviderClosedError):
        await provider.get("other")
    client.get_release.set()
    assert await operation == b"value"
    await closer


@pytest.mark.asyncio
async def test_provider_rejects_cross_loop_use_before_client_access() -> None:
    client = AsyncFakeRedis()
    provider = AsyncRedisProvider(client)  # type: ignore[arg-type]
    assert await provider.get("first") == b"value"
    calls = list(client.calls)

    def use_other_loop() -> None:
        with pytest.raises(RuntimeError, match="event loop"):
            asyncio.run(provider.get("second"))

    await asyncio.to_thread(use_other_loop)
    assert client.calls == calls


@pytest.mark.asyncio
async def test_async_observer_failure_is_isolated_and_event_is_low_cardinality() -> None:
    client = AsyncFakeRedis()
    observer = RecordingObserver()
    observer.error = RuntimeError("observer")
    provider = AsyncRedisProvider(client, observer=observer)  # type: ignore[arg-type]

    assert await provider.get("sensitive-key") == b"value"
    event = observer.events[0]
    assert event.mode is RedisMode.ASYNC
    assert event.operation is RedisOperation.GET
    assert event.outcome is RedisOutcome.SUCCESS
    assert "sensitive" not in repr(event)


@pytest.mark.asyncio
async def test_async_context_manager_returns_self_and_closes() -> None:
    client = AsyncFakeRedis()
    provider = AsyncRedisProvider(client)  # type: ignore[arg-type]
    async with provider as entered:
        assert entered is provider
    with pytest.raises(ProviderClosedError):
        await provider.get("key")
