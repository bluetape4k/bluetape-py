import inspect
import threading
from types import SimpleNamespace

import pytest
import redis
from _support import (
    COORDINATION_SNAPSHOT_SCRIPT,
    PUBLISH_IF_VALUE_SCRIPT,
    bounded_command_options,
)
from bluetape.cache.redis import (
    DEFAULT_MAX_ENCODED_SIZE,
    MAX_COORDINATION_MARKER_SIZE,
    ProviderClosedError,
    RedisCommandPolicy,
    RedisCoordinationSnapshot,
    RedisErrorCode,
    RedisMode,
    RedisOperation,
    RedisOutcome,
    RedisProviderError,
    SyncRedisProvider,
)
from bluetape.cache.redis._provider import COMPARE_AND_DELETE_SCRIPT


class SyncFakeRedis:
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
        self.close_calls = 0
        self.get_started = threading.Event()
        self.get_release: threading.Event | None = None

    def _call(self, name: str, *args: object, **kwargs: object) -> object:
        self.calls.append((name, args, kwargs))
        if name == "get":
            self.get_started.set()
            if self.get_release is not None:
                assert self.get_release.wait(timeout=2)
        error = self.errors.get(name)
        if error is not None:
            raise error
        return self.responses[name]

    def get(self, *args: object, **kwargs: object) -> object:
        return self._call("get", *args, **kwargs)

    def set(self, *args: object, **kwargs: object) -> object:
        return self._call("set", *args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> object:
        return self._call("delete", *args, **kwargs)

    def eval(self, *args: object, **kwargs: object) -> object:
        return self._call("eval", *args, **kwargs)

    def close(self) -> None:
        self.close_calls += 1
        error = self.errors.get("close")
        if error is not None:
            raise error


class RecordingObserver:
    def __init__(self) -> None:
        self.events = []
        self.error: BaseException | None = None
        self.callback = None

    def on_event(self, event) -> None:
        self.events.append(event)
        if self.callback is not None:
            self.callback(event)
        if self.error is not None:
            raise self.error


def test_sync_provider_public_signatures_are_exact() -> None:
    assert (
        str(inspect.signature(SyncRedisProvider)) == "(client: redis.client.Redis, *, "
        "observer: bluetape.cache.redis._contracts.RedisObserver | None = None) -> None"
    )
    assert (
        str(inspect.signature(SyncRedisProvider.from_url)) == "(url: str, *, "
        "observer: bluetape.cache.redis._contracts.RedisObserver | None = None, "
        "**redis_options: object) -> Self"
    )
    assert str(inspect.signature(SyncRedisProvider.get)) == "(self, key: str) -> bytes | None"
    assert (
        str(inspect.signature(SyncRedisProvider.set))
        == "(self, key: str, value: bytes, *, ttl: float) -> None"
    )
    assert (
        str(inspect.signature(SyncRedisProvider.set_if_absent))
        == "(self, key: str, value: bytes, *, ttl: float) -> bool"
    )
    assert str(inspect.signature(SyncRedisProvider.delete)) == "(self, key: str) -> bool"
    assert (
        str(inspect.signature(SyncRedisProvider.delete_if_value))
        == "(self, key: str, expected_value: bytes) -> bool"
    )
    assert (
        str(inspect.signature(SyncRedisProvider.coordination_snapshot))
        == "(self, marker_key: str, result_key: str, *, max_marker_size: int = 138, "
        "max_result_size: int) -> bluetape.cache.redis._contracts.RedisCoordinationSnapshot"
    )
    assert (
        str(inspect.signature(SyncRedisProvider.publish_if_value))
        == "(self, condition_key: str, expected_value: bytes, *, result_key: str, "
        "result_value: bytes, completion_value: bytes, ttl: float) -> bool"
    )
    assert str(inspect.signature(SyncRedisProvider.close)) == "(self) -> None"


def test_sync_command_policy_is_discovered_from_finite_no_retry_pool_options() -> None:
    client = SyncFakeRedis()

    assert SyncRedisProvider(client).command_policy == RedisCommandPolicy(
        connect_timeout=0.1,
        socket_timeout=0.2,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"socket_connect_timeout": None},
        {"socket_connect_timeout": 0},
        {"socket_connect_timeout": float("inf")},
        {"socket_timeout": None},
        {"socket_timeout": -1},
        {"socket_timeout": float("nan")},
        {"retry_on_timeout": True},
        {"retry_on_timeout": 0},
        {"retry_on_error": [TimeoutError]},
        {"retry_on_error": ""},
        {"retry": object()},
    ],
)
def test_sync_command_policy_rejects_unbounded_or_retrying_pool_options(change) -> None:
    client = SyncFakeRedis()
    client.connection_pool.connection_kwargs.update(change)

    assert SyncRedisProvider(client).command_policy is None


@pytest.mark.parametrize("retry_on_error", [[], (), set(), frozenset()])
def test_sync_command_policy_accepts_supported_empty_retry_error_collections(
    retry_on_error,
) -> None:
    client = SyncFakeRedis()
    client.connection_pool.connection_kwargs["retry_on_error"] = retry_on_error

    assert SyncRedisProvider(client).command_policy is not None


def test_sync_command_policy_is_none_for_opaque_connection_pool() -> None:
    client = SyncFakeRedis()
    client.connection_pool = object()

    assert SyncRedisProvider(client).command_policy is None


def test_sync_coordination_snapshot_uses_one_bounded_eval() -> None:
    client = SyncFakeRedis()
    client.responses["eval"] = [1, 6, b"active", 0, 0, b""]
    provider = SyncRedisProvider(client)

    assert provider.coordination_snapshot(
        "marker",
        "result",
        max_marker_size=6,
        max_result_size=7,
    ) == RedisCoordinationSnapshot(
        marker=b"active",
        result=None,
        marker_oversized=False,
        result_oversized=False,
    )
    assert client.calls == [
        ("eval", (COORDINATION_SNAPSHOT_SCRIPT, 2, "marker", "result", 6, 7), {})
    ]


def test_sync_coordination_snapshot_marks_bounded_oversized_prefixes() -> None:
    client = SyncFakeRedis()
    client.responses["eval"] = [1, 7, b"active", 1, 4, b"res"]

    snapshot = SyncRedisProvider(client).coordination_snapshot(
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
    assert len(snapshot.marker or b"") <= 6
    assert len(snapshot.result or b"") <= 3


@pytest.mark.parametrize(
    "response",
    [
        None,
        [1, 1, b"a"],
        [True, 1, b"a", 0, 0, b""],
        [1, -1, b"a", 0, 0, b""],
        [1, 1, "a", 0, 0, b""],
        [0, 1, b"a", 0, 0, b""],
        [1, 2, b"a", 0, 0, b""],
        [1, 8, b"too-long", 0, 0, b""],
    ],
)
def test_sync_coordination_snapshot_rejects_malformed_response(response) -> None:
    client = SyncFakeRedis()
    client.responses["eval"] = response

    with pytest.raises(RedisProviderError) as captured:
        SyncRedisProvider(client).coordination_snapshot(
            "marker", "result", max_marker_size=7, max_result_size=8
        )

    assert captured.value.operation is RedisOperation.COORDINATION_SNAPSHOT
    assert captured.value.code is RedisErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("marker_key", "result_key", "max_marker_size", "max_result_size"),
    [
        ("same", "same", 1, 1),
        ("marker", "result", True, 1),
        ("marker", "result", 0, 1),
        ("marker", "result", MAX_COORDINATION_MARKER_SIZE + 1, 1),
        ("marker", "result", 1, True),
        ("marker", "result", 1, 0),
        ("marker", "result", 1, DEFAULT_MAX_ENCODED_SIZE + 1),
    ],
)
def test_sync_coordination_snapshot_rejects_invalid_limits_before_eval(
    marker_key,
    result_key,
    max_marker_size,
    max_result_size,
) -> None:
    client = SyncFakeRedis()

    with pytest.raises((TypeError, ValueError)):
        SyncRedisProvider(client).coordination_snapshot(
            marker_key,
            result_key,
            max_marker_size=max_marker_size,
            max_result_size=max_result_size,
        )

    assert client.calls == []


def test_sync_publish_if_value_uses_one_atomic_eval() -> None:
    client = SyncFakeRedis()

    assert (
        SyncRedisProvider(client).publish_if_value(
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


def test_sync_stale_owner_cannot_publish() -> None:
    client = SyncFakeRedis()
    client.responses["eval"] = 0

    assert (
        SyncRedisProvider(client).publish_if_value(
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


@pytest.mark.parametrize("response", [None, True, b"1", 2])
def test_sync_publish_if_value_rejects_invalid_script_response(response) -> None:
    client = SyncFakeRedis()
    client.responses["eval"] = response

    with pytest.raises(RedisProviderError) as captured:
        SyncRedisProvider(client).publish_if_value(
            "lease",
            b"active:owner",
            result_key="result",
            result_value=b"encoded",
            completion_value=b"completed:owner",
            ttl=1.0,
        )

    assert captured.value.operation is RedisOperation.PUBLISH_IF_VALUE
    assert captured.value.code is RedisErrorCode.INVALID_RESPONSE


def test_sync_publish_if_value_rejects_identical_keys_before_eval() -> None:
    client = SyncFakeRedis()

    with pytest.raises(ValueError, match="distinct"):
        SyncRedisProvider(client).publish_if_value(
            "same",
            b"active:owner",
            result_key="same",
            result_value=b"encoded",
            completion_value=b"completed:owner",
            ttl=1.0,
        )

    assert client.calls == []


def test_sync_command_semantics_are_exact() -> None:
    client = SyncFakeRedis()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]

    assert provider.get("key") == b"value"
    provider.set("key", b"value", ttl=1.25)
    assert provider.set_if_absent("key", b"value", ttl=0.000_1) is True
    assert provider.delete("key") is True
    assert provider.delete_if_value("key", b"token") is True
    assert client.calls == [
        ("get", ("key",), {}),
        ("set", ("key", b"value"), {"px": 1250}),
        ("set", ("key", b"value"), {"nx": True, "px": 1}),
        ("delete", ("key",), {}),
        ("eval", (COMPARE_AND_DELETE_SCRIPT, 1, "key", b"token"), {}),
    ]


def test_sync_missing_and_nx_miss_are_normal_results() -> None:
    client = SyncFakeRedis()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]
    client.responses["get"] = None
    client.responses["set"] = None

    assert provider.get("key") is None
    assert provider.set_if_absent("key", b"value", ttl=1.0) is False


@pytest.mark.parametrize(
    ("method", "response"),
    [
        ("get", "decoded"),
        ("set", b"OK"),
        ("set_if_absent", 1),
        ("delete", True),
        ("delete_if_value", 2),
    ],
)
def test_sync_provider_rejects_incompatible_responses(method: str, response: object) -> None:
    client = SyncFakeRedis()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]
    response_key = (
        "set" if method == "set_if_absent" else "eval" if method == "delete_if_value" else method
    )
    client.responses[response_key] = response
    arguments = {
        "get": ("key",),
        "set": ("key", b"value"),
        "set_if_absent": ("key", b"value"),
        "delete": ("key",),
        "delete_if_value": ("key", b"value"),
    }[method]
    kwargs = {"ttl": 1.0} if method in {"set", "set_if_absent"} else {}

    with pytest.raises(RedisProviderError) as captured:
        getattr(provider, method)(*arguments, **kwargs)

    assert captured.value.code is RedisErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize("key", [b"key", "", " key", "key ", "key\n", "한글\x00"])
def test_sync_provider_rejects_invalid_keys_without_client_access(key: object) -> None:
    client = SyncFakeRedis()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]

    with pytest.raises((TypeError, ValueError)):
        provider.get(key)  # type: ignore[arg-type]
    assert client.calls == []


@pytest.mark.parametrize("value", [bytearray(), memoryview(b"x"), "x"])
def test_sync_provider_rejects_non_exact_values(value: object) -> None:
    client = SyncFakeRedis()
    with pytest.raises(TypeError, match="exact bytes"):
        SyncRedisProvider(client).set("key", value, ttl=1.0)  # type: ignore[arg-type]
    assert client.calls == []


@pytest.mark.parametrize("ttl", [True, 0, -1, float("inf"), float("nan"), "1"])
def test_sync_provider_rejects_invalid_ttl(ttl: object) -> None:
    client = SyncFakeRedis()
    with pytest.raises((TypeError, ValueError)):
        SyncRedisProvider(client).set("key", b"value", ttl=ttl)  # type: ignore[arg-type]
    assert client.calls == []


@pytest.mark.parametrize(
    ("cause", "code"),
    [
        (redis.ConnectionError("sensitive-provider-text"), RedisErrorCode.CONNECTION),
        (redis.TimeoutError("sensitive-provider-text"), RedisErrorCode.TIMEOUT),
        (redis.ResponseError("sensitive-provider-text"), RedisErrorCode.PROVIDER_FAILURE),
    ],
)
def test_sync_provider_maps_failures_with_redacted_wrapper_and_cause(cause, code) -> None:
    client = SyncFakeRedis()
    client.errors["get"] = cause

    with pytest.raises(RedisProviderError) as captured:
        SyncRedisProvider(client).get("sensitive-key")  # type: ignore[arg-type]

    assert captured.value.code is code
    assert captured.value.__cause__ is cause
    assert "sensitive" not in str(captured.value)
    assert "sensitive" not in repr(captured.value)


def test_borrowed_close_never_closes_client_and_is_idempotent() -> None:
    client = SyncFakeRedis()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]
    provider.close()
    provider.close()

    assert client.close_calls == 0
    with pytest.raises(ProviderClosedError):
        provider.get("key")
    assert client.calls == []


def test_from_url_forwards_options_owns_client_and_closes_once(monkeypatch) -> None:
    client = SyncFakeRedis()
    captured = {}

    def from_url(url: str, **options: object):
        captured.update(url=url, **options)
        return client

    monkeypatch.setattr(redis.Redis, "from_url", from_url)
    provider = SyncRedisProvider.from_url("redis://sensitive.invalid/0", socket_timeout=2.0)
    provider.close()
    provider.close()

    assert captured == {
        "url": "redis://sensitive.invalid/0",
        "socket_timeout": 2.0,
        "decode_responses": False,
    }
    assert client.close_calls == 1


@pytest.mark.parametrize(
    "options",
    [{"connection_pool": object()}, {"decode_responses": True}],
)
def test_from_url_rejects_options_that_break_ownership_or_binary_contract(options) -> None:
    with pytest.raises((TypeError, ValueError)):
        SyncRedisProvider.from_url("redis://localhost", **options)


def test_constructor_rejects_borrowed_text_client() -> None:
    client = SyncFakeRedis()
    client.connection_pool.connection_kwargs["decode_responses"] = True
    with pytest.raises(ValueError, match="decode_responses"):
        SyncRedisProvider(client)  # type: ignore[arg-type]


def test_owned_close_failure_is_shared_with_joiners_but_not_replayed(monkeypatch) -> None:
    client = SyncFakeRedis()
    cause = RuntimeError("sensitive-close")
    client.errors["close"] = cause
    monkeypatch.setattr(redis.Redis, "from_url", lambda *args, **kwargs: client)
    provider = SyncRedisProvider.from_url("redis://sensitive.invalid")

    with pytest.raises(RedisProviderError) as captured:
        provider.close()
    assert captured.value.__cause__ is cause
    provider.close()
    assert client.close_calls == 1


def test_close_waits_for_admitted_operation_without_holding_io_lock() -> None:
    client = SyncFakeRedis()
    client.get_release = threading.Event()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]
    operation = threading.Thread(target=provider.get, args=("key",))
    operation.start()
    assert client.get_started.wait(timeout=2)
    closed = threading.Event()
    closer = threading.Thread(target=lambda: (provider.close(), closed.set()))
    closer.start()

    assert not closed.wait(timeout=0.05)
    with pytest.raises(ProviderClosedError):
        provider.get("other")
    client.get_release.set()
    operation.join(timeout=2)
    closer.join(timeout=2)
    assert not operation.is_alive() and not closer.is_alive()


def test_observer_receives_one_redacted_terminal_event_and_failure_is_isolated() -> None:
    client = SyncFakeRedis()
    observer = RecordingObserver()
    observer.error = RuntimeError("observer")
    provider = SyncRedisProvider(client, observer=observer)  # type: ignore[arg-type]

    assert provider.get("sensitive-key") == b"value"
    assert len(observer.events) == 1
    event = observer.events[0]
    assert event.mode is RedisMode.SYNC
    assert event.operation is RedisOperation.GET
    assert event.outcome is RedisOutcome.SUCCESS
    assert event.error_code is None
    assert "sensitive" not in repr(event)


def test_observer_can_close_after_operation_releases_admission() -> None:
    client = SyncFakeRedis()
    observer = RecordingObserver()
    provider = SyncRedisProvider(client, observer=observer)  # type: ignore[arg-type]
    observer.callback = lambda event: (
        provider.close() if event.operation is RedisOperation.GET else None
    )

    assert provider.get("key") == b"value"
    with pytest.raises(ProviderClosedError):
        provider.get("key")


def test_sync_context_manager_returns_self_and_closes() -> None:
    client = SyncFakeRedis()
    provider = SyncRedisProvider(client)  # type: ignore[arg-type]
    with provider as entered:
        assert entered is provider
    with pytest.raises(ProviderClosedError):
        provider.get("key")
