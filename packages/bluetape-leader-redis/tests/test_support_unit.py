# ruff: noqa: RUF043
from __future__ import annotations

import asyncio
import socket
import threading
import traceback
from datetime import timedelta

import pytest
import redis
from _support import safe_async_client, safe_sync_client
from bluetape.leader import LeaderBackendError, LeaderExecutionError, RenewBackendFailure
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


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize("mutation", ["bool-retries", "backoff-state", "supported-errors"])
def test_rejected_client_requires_canonical_retry_state(
    client_factory: object,
    mutation: str,
) -> None:
    client = client_factory()  # type: ignore[operator]
    retry = client.connection_pool.connection_kwargs["retry"]
    if mutation == "bool-retries":
        retry._retries = False
    elif mutation == "backoff-state":
        retry._backoff._backoff = False
    else:
        retry._supported_errors = (Exception,)
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]


def test_rejected_client_requires_exact_retry_family() -> None:
    import redis.asyncio as async_redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(safe_sync_client(retry=async_redis.retry.Retry(NoBackoff(), 0)))
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_async_client(safe_async_client(retry=Retry(NoBackoff(), 0)))


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize("field", ["_backoff", "_supported_errors"])
def test_rejected_client_has_no_io_for_mutated_retry_internals(
    client_factory: object,
    field: str,
) -> None:
    observed: list[str] = []

    class Hostile:
        def reset(self) -> None:
            observed.append("reset")

        def __bool__(self) -> bool:
            observed.append("bool")
            return False

        def __ne__(self, other: object) -> bool:
            del other
            observed.append("ne")
            return False

    client = client_factory()  # type: ignore[operator]
    setattr(client.connection_pool.connection_kwargs["retry"], field, Hostile())
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("field", ["pid", "_pool_id"])
def test_rejected_client_has_no_io_for_hostile_sync_pool_identity(field: str) -> None:
    observed: list[str] = []

    class Hostile:
        def __bool__(self) -> bool:
            observed.append("bool")
            return False

        def __ne__(self, other: object) -> bool:
            del other
            observed.append("ne")
            return False

    client = safe_sync_client()
    setattr(client.connection_pool, field, Hostile())

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(client)

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_has_no_io_for_hostile_response_callback_container(
    client_factory: object,
) -> None:
    observed: list[str] = []

    class HostileCallbacks:
        def __len__(self) -> int:
            observed.append("len")
            return 0

        def get(self, key: object) -> object:
            del key
            observed.append("get")
            return None

    client = client_factory()  # type: ignore[operator]
    client.response_callbacks = HostileCallbacks()
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_checks_every_response_callback_key_before_lookup(
    client_factory: object,
) -> None:
    observed: list[str] = []
    client = client_factory()  # type: ignore[operator]
    callbacks = client.response_callbacks
    target = next(iter(callbacks))
    callback = dict.__getitem__(callbacks, target)

    class HostileKey:
        def __hash__(self) -> int:
            observed.append("hash")
            return hash(target)

        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

    dict.__delitem__(callbacks, target)
    dict.__setitem__(callbacks, HostileKey(), callback)
    observed.clear()
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize("target", ["client", "pool"])
def test_rejected_client_checks_every_event_mapping_key_before_lookup(
    client_factory: object,
    target: str,
) -> None:
    observed: list[str] = []
    client = client_factory()  # type: ignore[operator]
    dispatcher = (
        client._event_dispatcher if target == "client" else client.connection_pool._event_dispatcher
    )
    mapping = vars(dispatcher)["_event_listeners_mapping"]
    event = next(iter(mapping))
    listeners = dict.__getitem__(mapping, event)

    class HostileKey:
        def __hash__(self) -> int:
            observed.append("hash")
            return hash(event)

        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

    dict.__delitem__(mapping, event)
    dict.__setitem__(mapping, HostileKey(), listeners)
    observed.clear()

    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize(
    "field",
    [
        "socket_connect_timeout",
        "socket_timeout",
        "health_check_interval",
        "retry_on_error",
        "retry",
        "redis_connect_func",
        "credential_provider",
        "decode_responses",
        "encoding",
        "encoding_errors",
        "legacy_responses",
        "socket_read_size",
        "driver_info",
        "protocol",
        "db",
        "client_name",
        "username",
        "password",
        "host",
        "port",
        "socket_keepalive",
        "socket_keepalive_options",
    ],
)
def test_rejected_client_never_invokes_hostile_scalar_option(
    client_factory: object,
    field: str,
) -> None:
    observed: list[str] = []

    class Hostile:
        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

        def __ne__(self, other: object) -> bool:
            del other
            observed.append("ne")
            return True

        def __bool__(self) -> bool:
            observed.append("bool")
            return False

        def __len__(self) -> int:
            observed.append("len")
            return 0

        def __iter__(self):  # type: ignore[no-untyped-def]
            observed.append("iter")
            return iter(())

        def __contains__(self, item: object) -> bool:
            del item
            observed.append("contains")
            return False

        def __lt__(self, other: object) -> bool:
            del other
            observed.append("lt")
            return False

        def __le__(self, other: object) -> bool:
            del other
            observed.append("le")
            return False

        def __gt__(self, other: object) -> bool:
            del other
            observed.append("gt")
            return False

        def __ge__(self, other: object) -> bool:
            del other
            observed.append("ge")
            return False

        def __float__(self) -> float:
            observed.append("float")
            return 1.0

    client = client_factory()  # type: ignore[operator]
    client.connection_pool.connection_kwargs[field] = Hostile()
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_never_hashes_or_compares_hostile_option_key(
    client_factory: object,
) -> None:
    observed: list[str] = []

    class HostileKey:
        def __hash__(self) -> int:
            observed.append("hash")
            return 0

        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

    client = client_factory()  # type: ignore[operator]
    options = client.connection_pool.connection_kwargs
    del options["client_name"]
    options[HostileKey()] = None
    observed.clear()
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize("field", ["connection_class", "max_connections"])
def test_rejected_client_never_invokes_hostile_pool_scalar(
    client_factory: object,
    field: str,
) -> None:
    observed: list[str] = []

    class Hostile:
        def __bool__(self) -> bool:
            observed.append("bool")
            return False

        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

        def __le__(self, other: object) -> bool:
            del other
            observed.append("le")
            return False

    client = client_factory()  # type: ignore[operator]
    setattr(client.connection_pool, field, Hostile())
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize("field", ["name", "lib_version", "_upstream"])
def test_rejected_client_checks_driver_info_field_types_before_values(
    client_factory: object,
    field: str,
) -> None:
    observed: list[str] = []

    class Hostile:
        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

        def __bool__(self) -> bool:
            observed.append("bool")
            return False

    client = client_factory()  # type: ignore[operator]
    driver_info = client.connection_pool.connection_kwargs["driver_info"]
    setattr(driver_info, field, Hostile())
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize(
    "field", ["_maint_notifications_pool_handler", "_oss_cluster_maint_notifications_handler"]
)
def test_rejected_client_has_no_io_for_hostile_sync_pool_handler(field: str) -> None:
    observed: list[str] = []

    class Hostile:
        def __bool__(self) -> bool:
            observed.append("bool")
            return False

        def __eq__(self, other: object) -> bool:
            del other
            observed.append("eq")
            return False

    client = safe_sync_client()
    setattr(client.connection_pool, field, Hostile())

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        _validated_sync_client(client)

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize("pool_state", ["available", "in-use"])
def test_rejected_client_has_no_io_for_nonempty_pool_and_registered_callback(
    client_factory: object,
    pool_state: str,
) -> None:
    observed: list[str] = []

    class Listener:
        def connected(self, connection: object) -> None:
            del connection
            observed.append("called")

    client = client_factory()  # type: ignore[operator]
    connection = client.connection_pool.make_connection()
    listener = Listener()
    connection.register_connect_callback(listener.connected)
    if pool_state == "available":
        client.connection_pool._available_connections.append(connection)
    else:
        client.connection_pool._in_use_connections.add(connection)

    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    assert observed == []


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("user", None),
        ("", "secret"),
        (b"", b"secret"),
        (None, ""),
        (None, b""),
        ("user", ""),
        (b"user", b""),
    ],
)
def test_rejected_client_has_no_io_for_invalid_auth_shape(
    client_factory: object,
    username: object,
    password: object,
) -> None:
    client = client_factory(username=username, password=password)  # type: ignore[operator]
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
@pytest.mark.parametrize(
    ("username", "password"),
    [
        (None, None),
        (None, "secret"),
        (None, b"secret"),
        ("user", "secret"),
        (b"user", b"secret"),
    ],
)
def test_validated_client_accepts_only_complete_auth_shapes(
    client_factory: object,
    username: object,
    password: object,
) -> None:
    client = client_factory(username=username, password=password)  # type: ignore[operator]
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client

    assert validator(client).handshake_round_trips >= 2  # type: ignore[arg-type]


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
    ("client_factory", "target", "attribute"),
    [
        (safe_sync_client, "client", "single_connection_lock"),
        (safe_sync_client, "pool", "_fork_lock"),
        (safe_sync_client, "pool", "_lock"),
        (safe_async_client, "client", "_single_conn_lock"),
        (safe_async_client, "client", "_usage_lock"),
        (safe_async_client, "pool", "_lock"),
        (safe_sync_client, "client_dispatcher", "_lock"),
        (safe_async_client, "pool_dispatcher", "_lock"),
    ],
)
def test_rejected_client_has_no_io_for_mutated_lock_primitive(
    client_factory: object,
    target: str,
    attribute: str,
) -> None:
    client = client_factory()  # type: ignore[operator]
    subject = {
        "client": client,
        "pool": client.connection_pool,
        "client_dispatcher": client._event_dispatcher,
        "pool_dispatcher": client.connection_pool._event_dispatcher,
    }[target]
    if type(client) is redis.Redis or "dispatcher" in target:
        lock = threading.RLock()
        lock.acquire()
    else:
        lock = asyncio.Lock()
        lock._locked = True
    setattr(subject, attribute, lock)

    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    try:
        with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
            validator(client)  # type: ignore[arg-type]
    finally:
        if type(lock) is type(threading.RLock()):
            lock.release()


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
@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_has_no_io_for_unbounded_or_opaque_configuration(
    overrides: dict[str, object],
    client_factory: object,
) -> None:
    client = client_factory(**overrides)  # type: ignore[operator]
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]


@pytest.mark.parametrize("client_factory", [safe_sync_client, safe_async_client])
def test_rejected_client_has_no_io_for_callback_and_command_response_hook(
    client_factory: object,
) -> None:
    callback_calls: list[str] = []

    def callback() -> tuple[str, str]:
        callback_calls.append("called")
        raise AssertionError("callback executed")

    from _support import HostileCallback

    client = client_factory(credential_provider=HostileCallback(callback))  # type: ignore[operator]
    validator = _validated_sync_client if type(client) is redis.Redis else _validated_async_client
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    client = client_factory()  # type: ignore[operator]
    client.set_response_callback("EVALSHA", lambda value: value)
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(client)  # type: ignore[arg-type]

    event_client = client_factory()  # type: ignore[operator]
    listeners = vars(event_client._event_dispatcher)["_event_listeners_mapping"]
    listeners[object] = [object()]
    with pytest.raises(TypeError, match="^unsupported Redis client configuration$"):
        validator(event_client)  # type: ignore[arg-type]

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


def test_sanitized_exception_graph_covers_traceback_and_composite_properties() -> None:
    marker = "redis://user:secret@127.0.0.1:6379 owner-raw-canary"
    action_marker = "caller-owned-action-canary"

    def fail() -> None:
        raise RuntimeError(marker)

    with pytest.raises(LeaderBackendError) as caught:
        _safe_backend_call(fail)

    backend_error = caught.value
    renewal = RenewBackendFailure(backend_error)
    action_error = ValueError(action_marker)
    execution = LeaderExecutionError(action_error, backend_error)
    try:
        raise execution from None
    except LeaderExecutionError as raised:
        execution_traceback = "".join(
            traceback.format_exception(type(raised), raised, raised.__traceback__)
        )

    assert renewal.cause is backend_error
    assert not isinstance(renewal, BaseException)
    assert getattr(renewal, "args", ()) == ()
    assert getattr(renewal, "__cause__", None) is None
    assert getattr(renewal, "__context__", None) is None
    assert getattr(renewal, "__notes__", []) == []
    assert execution.lifecycle_cause is backend_error
    assert execution.action_cause is action_error
    assert execution.args == ("leader action and lifecycle both failed",)
    assert execution.__cause__ is None
    assert execution.__context__ is None
    assert getattr(execution, "__notes__", []) == []
    _assert_sanitized(renewal.cause, marker)
    _assert_sanitized(execution.lifecycle_cause, marker)
    _assert_public_surface_sanitized(renewal, marker)
    _assert_public_surface_sanitized(execution, marker)
    _assert_public_surface_sanitized(execution, action_marker)
    assert marker not in execution_traceback
    assert action_marker not in execution_traceback


def _assert_sanitized(error: LeaderBackendError, marker: str) -> None:
    assert error.args == ("leader backend operation failed",)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert getattr(error, "__notes__", []) == []
    _assert_public_surface_sanitized(error, marker)


def _assert_public_surface_sanitized(value: object, marker: str) -> None:
    args = getattr(value, "args", ())
    for argument in args:
        assert marker not in str(argument)
        assert marker not in repr(argument)
    for attribute in ("__cause__", "__context__"):
        linked = getattr(value, attribute, None)
        assert marker not in str(linked)
        assert marker not in repr(linked)
    notes = getattr(value, "__notes__", [])
    for note in notes:
        assert marker not in str(note)
        assert marker not in repr(note)
    assert marker not in str(value)
    assert marker not in repr(value)
    if isinstance(value, BaseException):
        rendered = "".join(traceback.format_exception(type(value), value, value.__traceback__))
        assert marker not in rendered


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
