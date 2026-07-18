# ruff: noqa: RUF043
from __future__ import annotations

import socket
from datetime import timedelta

import pytest
import redis
from _support import safe_async_client, safe_sync_client
from bluetape.leader import LeaderBackendError
from bluetape.leader.redis._support import (
    _duration_milliseconds,
    _LeaseRecord,
    _new_owner_token,
    _safe_backend_call,
    _safe_backend_call_async,
    _timing,
    _validated_async_client,
    _validated_sync_client,
)


def test_rejected_client_has_no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        observed.append("io")
        raise AssertionError("validation attempted I/O")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(safe_sync_client(host="redis.internal"))
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_async_client(safe_async_client(host="redis.internal"))

    assert observed == []


def test_rejected_client_has_no_io_when_retry_is_enabled() -> None:
    import redis.asyncio as async_redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(safe_sync_client(retry=Retry(NoBackoff(), 1)))
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_async_client(safe_async_client(retry=async_redis.retry.Retry(NoBackoff(), 1)))


def test_rejected_client_has_no_io_for_wrong_family_subclass_and_instance_hook() -> None:
    import redis

    class RedisSubclass(redis.Redis):
        pass

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(safe_async_client())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(RedisSubclass(host="127.0.0.1"))

    client = safe_sync_client()
    client.execute_command = lambda *args, **kwargs: None  # type: ignore[method-assign]
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(client)


@pytest.mark.parametrize("attribute", ["_execute_command", "parse_response"])
def test_rejected_client_has_no_io_for_shadowed_sync_command_path(
    attribute: str,
) -> None:
    observed: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        observed.append("called")
        raise AssertionError("shadow hook executed")

    client = safe_sync_client()
    setattr(client, attribute, forbidden)

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(client)

    assert observed == []


def test_rejected_client_has_no_io_for_shadowed_async_command_path() -> None:
    observed: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        observed.append("called")
        raise AssertionError("shadow hook executed")

    client = safe_async_client()
    client.parse_response = forbidden  # type: ignore[method-assign]

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_async_client(client)

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_has_no_io_for_shadowed_pool_command_path(
    client_factory: object,
) -> None:
    observed: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        observed.append("called")
        raise AssertionError("shadow hook executed")

    client = client_factory()  # type: ignore[operator]
    client.connection_pool.get_connection = forbidden  # type: ignore[method-assign]

    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_has_no_io_for_shadowed_event_dispatch(
    client_factory: object,
) -> None:
    observed: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        observed.append("called")
        raise AssertionError("shadow hook executed")

    client = client_factory()  # type: ignore[operator]
    client._event_dispatcher.dispatch = forbidden  # type: ignore[method-assign]

    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"socket_timeout": None},
        {"socket_timeout": 0},
        {"socket_timeout": float("inf")},
        {"socket_connect_timeout": float("nan")},
        {"health_check_interval": 1},
        {"decode_responses": True},
        {"ssl": True},
        {"host": "redis.internal"},
    ],
)
def test_rejected_client_has_no_io_for_unbounded_or_opaque_configuration(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(safe_sync_client(**overrides))


def test_rejected_client_has_no_io_for_callback_and_command_response_hook() -> None:
    callback_calls: list[str] = []

    def callback() -> tuple[str, str]:
        callback_calls.append("called")
        raise AssertionError("callback executed")

    from _support import HostileCallback

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(safe_sync_client(credential_provider=HostileCallback(callback)))

    client = safe_sync_client()
    client.set_response_callback("EVALSHA", lambda value: value)
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(client)

    event_client = safe_sync_client()
    listeners = vars(event_client._event_dispatcher)["_event_listeners_mapping"]
    listeners[object] = [object()]
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(event_client)

    assert callback_calls == []


def test_validated_client_accepts_numeric_tcp_and_unix_socket_shapes() -> None:
    sync_tcp = _validated_sync_client(safe_sync_client(host="::1"))
    async_tcp = _validated_async_client(safe_async_client(host="127.0.0.1"))
    sync_unix = _validated_sync_client(safe_sync_client(unix_socket_path="/tmp/redis.sock"))
    async_unix = _validated_async_client(safe_async_client(unix_socket_path="/tmp/redis.sock"))

    assert sync_tcp.handshake_round_trips == 2
    assert async_tcp.handshake_round_trips == 2
    assert sync_unix.connect > sync_tcp.connect
    assert async_unix.connect > async_tcp.connect


def test_record_round_trips_canonical_private_value() -> None:
    record = _LeaseRecord("A" * 32, 9)

    assert record.to_bytes() == b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:9"
    assert _LeaseRecord.parse(record.to_bytes()) == record
    assert repr(record) == "_LeaseRecord(<redacted>)"
    assert not hasattr(record, "__dict__")


def test_record_accepts_redis_signed_maximum_fence() -> None:
    record = _LeaseRecord("A" * 32, 9_223_372_036_854_775_807)

    assert _LeaseRecord.parse(record.to_bytes()) == record


@pytest.mark.parametrize(
    "value",
    [
        b"",
        b"v2:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:1",
        b"v1:short:1",
        b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:0",
        b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:01",
        b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:+1",
        b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:9223372036854775808",
        b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:1:extra",
        b"v1:\xff:1",
        "v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:1",
    ],
)
def test_record_rejects_noncanonical_value(value: object) -> None:
    with pytest.raises(ValueError, match="^invalid Redis lease record$"):
        _LeaseRecord.parse(value)  # type: ignore[arg-type]


def test_timing_arithmetic_uses_exact_envelopes() -> None:
    timing = _timing(5, 0.1, 0.05, pool_wait=0.02)

    assert timing.handshake_round_trips == 5
    assert timing.connect == pytest.approx(0.35)
    assert timing.command == pytest.approx(0.42)
    assert timing.script == pytest.approx(0.84)
    assert timing.acquire == pytest.approx(1.26)
    assert timing.probe == pytest.approx(0.84)
    assert timing.renew == pytest.approx(0.84)
    assert timing.release == pytest.approx(2.1)


def test_timing_arithmetic_matches_validated_handshake_shape() -> None:
    sync = _validated_sync_client(
        safe_sync_client(protocol=3, username="user", password="secret", client_name="x", db=1)
    )
    async_timing = _validated_async_client(
        safe_async_client(protocol=3, username="user", password="secret", client_name="x", db=1)
    )

    assert sync.handshake_round_trips == 5
    assert async_timing.handshake_round_trips == 5
    assert sync == async_timing


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (timedelta(milliseconds=1), 1),
        (timedelta(microseconds=1_999), 1),
        (timedelta(seconds=2, microseconds=999_999), 2_999),
    ],
)
def test_timing_arithmetic_converts_positive_whole_milliseconds(
    duration: timedelta, expected: int
) -> None:
    assert _duration_milliseconds(duration) == expected


@pytest.mark.parametrize(
    "duration", [timedelta(0), timedelta(microseconds=999), timedelta(microseconds=-1)]
)
def test_timing_arithmetic_rejects_nonpositive_millisecond_value(
    duration: timedelta,
) -> None:
    with pytest.raises(ValueError, match="^Redis duration is invalid$"):
        _duration_milliseconds(duration)


def test_sanitized_exception_graph_sync_has_no_raw_backend_canary() -> None:
    marker = "redis://user:secret@127.0.0.1:6379 owner-raw-canary"

    def fail() -> None:
        raise RuntimeError(marker)

    with pytest.raises(LeaderBackendError) as caught:
        _safe_backend_call(fail)

    _assert_sanitized(caught.value, marker)


@pytest.mark.asyncio
async def test_sanitized_exception_graph_async_has_no_raw_backend_canary() -> None:
    marker = "redis://user:secret@127.0.0.1:6379 owner-raw-canary"

    async def fail() -> None:
        raise RuntimeError(marker)

    with pytest.raises(LeaderBackendError) as caught:
        await _safe_backend_call_async(fail)

    _assert_sanitized(caught.value, marker)


def _assert_sanitized(error: LeaderBackendError, marker: str) -> None:
    assert error.args == ("leader backend operation failed",)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert getattr(error, "__notes__", []) == []
    assert marker not in str(error)
    assert marker not in repr(error)


def test_owner_token_uses_one_24_byte_urlsafe_entropy_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_token_urlsafe(size: int) -> str:
        calls.append(size)
        return "A" * 32

    monkeypatch.setattr("bluetape.leader.redis._support.token_urlsafe", fake_token_urlsafe)

    assert _new_owner_token() == "A" * 32
    assert calls == [24]
