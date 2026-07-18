"""Private validation and value helpers for the bounded Redis adapter."""

from __future__ import annotations

import ipaddress
import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from secrets import token_urlsafe
from typing import Any, Never

from bluetape.leader import LeaderBackendError

import redis
import redis.asyncio as async_redis
from redis.client import get_response_callbacks
from redis.connection import (
    SENTINEL,
)
from redis.connection import (
    Connection as SyncConnection,
)
from redis.connection import (
    ConnectionPool as SyncConnectionPool,
)
from redis.connection import (
    UnixDomainSocketConnection as SyncUnixConnection,
)
from redis.driver_info import DriverInfo
from redis.event import EventDispatcher
from redis.maint_notifications import MaintNotificationsConfig
from redis.retry import Retry as SyncRetry

_UNSUPPORTED_CLIENT = "unsupported Redis client configuration"
_INVALID_RECORD = "invalid Redis lease record"
_OWNER_TOKEN_LENGTH = 32
_OWNER_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_MAX_REDIS_INTEGER = 9_223_372_036_854_775_807
_MAX_REDIS_INTEGER_TEXT = str(_MAX_REDIS_INTEGER)
_SYNC_CLIENT_ATTRIBUTES = frozenset(
    {
        "_event_dispatcher",
        "_single_connection_client",
        "auto_close_connection_pool",
        "connection",
        "connection_pool",
        "response_callbacks",
        "single_connection_lock",
    }
)
_ASYNC_CLIENT_ATTRIBUTES = frozenset(
    {
        "_event_dispatcher",
        "_single_conn_lock",
        "_usage_counter",
        "_usage_lock",
        "auto_close_connection_pool",
        "connection",
        "connection_pool",
        "response_callbacks",
        "single_connection_client",
    }
)
_SYNC_POOL_ATTRIBUTES = frozenset(
    {
        "_available_connections",
        "_cache_factory",
        "_connection_kwargs",
        "_created_connections",
        "_event_dispatcher",
        "_fork_lock",
        "_in_use_connections",
        "_lock",
        "_maint_notifications_pool_handler",
        "_oss_cluster_maint_notifications_handler",
        "_pool_id",
        "cache",
        "connection_class",
        "max_connections",
        "pid",
    }
)
_ASYNC_POOL_ATTRIBUTES = frozenset(
    {
        "_available_connections",
        "_event_dispatcher",
        "_in_use_connections",
        "_lock",
        "connection_class",
        "connection_kwargs",
        "encoder_class",
        "max_connections",
    }
)


@dataclass(frozen=True, slots=True, repr=False)
class _LeaseRecord:
    owner_token: str
    fencing_token: int

    def __post_init__(self) -> None:
        if not _is_owner_token(self.owner_token):
            raise ValueError(_INVALID_RECORD)
        if (
            type(self.fencing_token) is not int
            or self.fencing_token <= 0
            or self.fencing_token > _MAX_REDIS_INTEGER
        ):
            raise ValueError(_INVALID_RECORD)

    def __repr__(self) -> str:
        return "_LeaseRecord(<redacted>)"

    def to_bytes(self) -> bytes:
        return f"v1:{self.owner_token}:{self.fencing_token}".encode("ascii")

    @classmethod
    def parse(cls, value: bytes) -> _LeaseRecord:
        if type(value) is not bytes:
            raise ValueError(_INVALID_RECORD)
        try:
            version, owner, fence = value.decode("ascii").split(":")
        except (UnicodeDecodeError, ValueError):
            raise ValueError(_INVALID_RECORD) from None
        if version != "v1" or not _is_owner_token(owner) or not _is_canonical_fence(fence):
            raise ValueError(_INVALID_RECORD)
        return cls(owner, int(fence))


@dataclass(frozen=True, slots=True)
class _Timing:
    handshake_round_trips: int
    connect: float
    command: float
    script: float
    acquire: float
    probe: float
    renew: float
    release: float


def _validated_sync_client(client: redis.Redis) -> _Timing:
    if (
        type(client) is not redis.Redis
        or not _has_exact_attribute_names(client, _SYNC_CLIENT_ATTRIBUTES)
        or client.connection is not None
        or client._single_connection_client is not False
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    pool = client.connection_pool
    if (
        type(pool) is not SyncConnectionPool
        or not _has_exact_attribute_names(pool, _SYNC_POOL_ATTRIBUTES)
        or pool.cache is not None
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    _validate_event_dispatcher(getattr(client, "_event_dispatcher", None))
    _validate_event_dispatcher(getattr(pool, "_event_dispatcher", None))
    _validate_response_callbacks(client, pool.connection_kwargs)
    return _validate_pool(
        pool.connection_class,
        pool.connection_kwargs,
        pool.max_connections,
        sync=True,
    )


def _validated_async_client(client: async_redis.Redis) -> _Timing:
    from redis.asyncio.connection import (
        Connection as AsyncConnection,
    )
    from redis.asyncio.connection import (
        ConnectionPool as AsyncConnectionPool,
    )
    from redis.asyncio.connection import (
        UnixDomainSocketConnection as AsyncUnixConnection,
    )

    if (
        type(client) is not async_redis.Redis
        or not _has_exact_attribute_names(client, _ASYNC_CLIENT_ATTRIBUTES)
        or client.connection is not None
        or client.single_connection_client is not False
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    pool = client.connection_pool
    if type(pool) is not AsyncConnectionPool or not _has_exact_attribute_names(
        pool, _ASYNC_POOL_ATTRIBUTES
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    _validate_event_dispatcher(getattr(client, "_event_dispatcher", None))
    _validate_event_dispatcher(getattr(pool, "_event_dispatcher", None))
    _validate_response_callbacks(client, pool.connection_kwargs)
    connection_class = pool.connection_class
    if connection_class not in (AsyncConnection, AsyncUnixConnection):
        raise TypeError(_UNSUPPORTED_CLIENT)
    return _validate_pool(
        connection_class,
        pool.connection_kwargs,
        pool.max_connections,
        sync=False,
    )


def _validate_pool(
    connection_class: type[object],
    options: Mapping[str, Any],
    max_connections: object,
    *,
    sync: bool,
) -> _Timing:
    from redis.asyncio.connection import (
        Connection as AsyncConnection,
    )
    from redis.asyncio.connection import (
        UnixDomainSocketConnection as AsyncUnixConnection,
    )
    from redis.asyncio.retry import Retry as AsyncRetry

    allowed_classes = (
        (SyncConnection, SyncUnixConnection) if sync else (AsyncConnection, AsyncUnixConnection)
    )
    if connection_class not in allowed_classes:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if type(options) is not dict or set(options) != _required_option_keys(connection_class):
        raise TypeError(_UNSUPPORTED_CLIENT)
    if type(max_connections) is not int or max_connections <= 0:
        raise TypeError(_UNSUPPORTED_CLIENT)

    connect_timeout = _positive_finite(
        options.get("socket_connect_timeout", 5.0)
        if connection_class in (SyncUnixConnection, AsyncUnixConnection)
        else options.get("socket_connect_timeout")
    )
    socket_timeout = _positive_finite(options.get("socket_timeout"))
    if connect_timeout is None or socket_timeout is None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("health_check_interval") != 0:
        raise TypeError(_UNSUPPORTED_CLIENT)
    retry_errors = options.get("retry_on_error")
    if retry_errors is not None and (type(retry_errors) is not list or retry_errors):
        raise TypeError(_UNSUPPORTED_CLIENT)

    retry = options.get("retry")
    retry_type = SyncRetry if sync else AsyncRetry
    if type(retry) is not retry_type or vars(retry).get("_retries") != 0:
        raise TypeError(_UNSUPPORTED_CLIENT)

    if options.get("redis_connect_func") is not None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("credential_provider") is not None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("decode_responses") is not False:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("encoding") != "utf-8" or options.get("encoding_errors") != "strict":
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("legacy_responses") is not True:
        raise TypeError(_UNSUPPORTED_CLIENT)
    read_size = options.get("socket_read_size")
    if type(read_size) is not int or read_size <= 0:
        raise TypeError(_UNSUPPORTED_CLIENT)
    driver_info = options.get("driver_info")
    if type(driver_info) is not DriverInfo or vars(driver_info) != {
        "name": "redis-py",
        "lib_version": redis.__version__,
        "_upstream": [],
    }:
        raise TypeError(_UNSUPPORTED_CLIENT)

    protocol = options.get("protocol")
    if protocol is not None and (type(protocol) is not int or protocol not in (2, 3)):
        raise TypeError(_UNSUPPORTED_CLIENT)
    db = options.get("db", 0)
    if type(db) is not int or db < 0:
        raise TypeError(_UNSUPPORTED_CLIENT)
    client_name = options.get("client_name")
    if client_name is not None and (type(client_name) is not str or not client_name):
        raise TypeError(_UNSUPPORTED_CLIENT)
    for credential in (options.get("username"), options.get("password")):
        if credential is not None and type(credential) not in (str, bytes):
            raise TypeError(_UNSUPPORTED_CLIENT)

    if connection_class in (SyncConnection, AsyncConnection):
        host = options.get("host")
        if type(host) is not str:
            raise TypeError(_UNSUPPORTED_CLIENT)
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise TypeError(_UNSUPPORTED_CLIENT) from None
        port = options.get("port")
        if type(port) is not int or not 1 <= port <= 65_535:
            raise TypeError(_UNSUPPORTED_CLIENT)
        keepalive = options.get("socket_keepalive")
        if type(keepalive) is not bool:
            raise TypeError(_UNSUPPORTED_CLIENT)
        keepalive_options = options.get("socket_keepalive_options")
        if keepalive_options is not SENTINEL and not _safe_keepalive_options(keepalive_options):
            raise TypeError(_UNSUPPORTED_CLIENT)
    else:
        path = options.get("path")
        if type(path) is not str or not path or "\x00" in path:
            raise TypeError(_UNSUPPORTED_CLIENT)

    if sync:
        config = options.get("maint_notifications_config")
        if not _maintenance_disabled(config):
            raise TypeError(_UNSUPPORTED_CLIENT)

    handshake = len(_handshake_commands(options))
    return _timing(handshake, connect_timeout, socket_timeout, pool_wait=0.0)


def _handshake_commands(options: Mapping[str, Any]) -> tuple[str, ...]:
    commands: list[str] = []
    has_auth = options.get("username") is not None or options.get("password") is not None
    protocol = options.get("protocol")
    if has_auth and protocol == 3:
        commands.append("HELLO AUTH")
    elif has_auth:
        commands.append("AUTH")
    elif protocol == 3:
        commands.append("HELLO")
    if options.get("client_name") is not None:
        commands.append("CLIENT SETNAME")
    commands.extend(("CLIENT SETINFO LIB-NAME", "CLIENT SETINFO LIB-VER"))
    if options.get("db", 0):
        commands.append("SELECT")
    return tuple(commands)


def _maintenance_disabled(value: object) -> bool:
    return value is None or (
        type(value) is MaintNotificationsConfig
        and value.enabled is False
        and value.proactive_reconnect is False
        and value.relaxed_timeout == -1
        and value.endpoint_type is None
    )


def _safe_keepalive_options(value: object) -> bool:
    return type(value) is dict and all(
        type(key) is int and type(option) in (int, bytes) for key, option in value.items()
    )


def _required_option_keys(connection_class: type[object]) -> set[str]:
    common = {
        "client_name",
        "credential_provider",
        "db",
        "decode_responses",
        "driver_info",
        "encoding",
        "encoding_errors",
        "health_check_interval",
        "legacy_responses",
        "password",
        "protocol",
        "redis_connect_func",
        "retry",
        "retry_on_error",
        "socket_read_size",
        "socket_timeout",
        "username",
    }
    if connection_class in (SyncConnection,):
        return common | {
            "host",
            "port",
            "socket_connect_timeout",
            "socket_keepalive",
            "socket_keepalive_options",
        }
    from redis.asyncio.connection import Connection as AsyncConnection

    if connection_class is AsyncConnection:
        return common | {
            "host",
            "port",
            "socket_connect_timeout",
            "socket_keepalive",
            "socket_keepalive_options",
        }
    return common | {"path"}


def _validate_response_callbacks(client: object, options: Mapping[str, Any]) -> None:
    actual = getattr(client, "response_callbacks", None)
    if actual is None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    expected = get_response_callbacks(
        options.get("protocol"), options.get("legacy_responses", True)
    )
    if len(actual) != len(expected):
        raise TypeError(_UNSUPPORTED_CLIENT)
    for name, callback in expected.items():
        if actual.get(name) is not callback:
            raise TypeError(_UNSUPPORTED_CLIENT)


def _validate_event_dispatcher(value: object) -> None:
    if type(value) is not EventDispatcher or not _has_exact_attribute_names(
        value, frozenset({"_event_listeners_mapping", "_lock", "_async_lock"})
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    expected = EventDispatcher()
    actual_mapping = vars(value).get("_event_listeners_mapping")
    expected_mapping = vars(expected).get("_event_listeners_mapping")
    if type(actual_mapping) is not dict or type(expected_mapping) is not dict:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if len(actual_mapping) != len(expected_mapping):
        raise TypeError(_UNSUPPORTED_CLIENT)
    for event, expected_listeners in expected_mapping.items():
        actual_listeners = actual_mapping.get(event)
        if type(actual_listeners) is not list or len(actual_listeners) != len(expected_listeners):
            raise TypeError(_UNSUPPORTED_CLIENT)
        for actual_listener, expected_listener in zip(
            actual_listeners, expected_listeners, strict=True
        ):
            if type(actual_listener) is not type(expected_listener) or not _has_exact_default_state(
                actual_listener, expected_listener
            ):
                raise TypeError(_UNSUPPORTED_CLIENT)


def _has_exact_attribute_names(value: object, expected: frozenset[str]) -> bool:
    state = vars(value)
    return (
        type(state) is dict
        and len(state) == len(expected)
        and all(type(name) is str and name in expected for name in state)
    )


def _has_exact_default_state(actual: object, expected: object) -> bool:
    actual_state = vars(actual)
    expected_state = vars(expected)
    if type(actual_state) is not dict or type(expected_state) is not dict:
        return False
    if not _has_exact_attribute_names(actual, frozenset(expected_state)):
        return False
    return all(actual_state[name] is expected_state[name] for name in expected_state)


def _positive_finite(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    converted = float(value)
    return converted if converted > 0 and math.isfinite(converted) else None


def _timing(
    handshake_round_trips: int,
    socket_connect_timeout: float,
    socket_timeout: float,
    *,
    pool_wait: float = 0.0,
) -> _Timing:
    if type(handshake_round_trips) is not int or handshake_round_trips < 0:
        raise ValueError(_UNSUPPORTED_CLIENT)
    for value in (socket_connect_timeout, socket_timeout):
        if _positive_finite(value) is None:
            raise ValueError(_UNSUPPORTED_CLIENT)
    if type(pool_wait) not in (int, float) or pool_wait < 0 or not math.isfinite(pool_wait):
        raise ValueError(_UNSUPPORTED_CLIENT)
    connect = float(socket_connect_timeout) + handshake_round_trips * float(socket_timeout)
    command = float(pool_wait) + connect + float(socket_timeout)
    script = 2 * command
    return _Timing(
        handshake_round_trips=handshake_round_trips,
        connect=connect,
        command=command,
        script=script,
        acquire=script + command,
        probe=script,
        renew=script,
        release=2 * script + command,
    )


def _duration_milliseconds(value: timedelta) -> int:
    if type(value) is not timedelta or value <= timedelta(0):
        raise ValueError("Redis duration is invalid")
    milliseconds = (
        (value.days * 86_400_000) + (value.seconds * 1_000) + (value.microseconds // 1_000)
    )
    if milliseconds <= 0:
        raise ValueError("Redis duration is invalid")
    return milliseconds


def _is_owner_token(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == _OWNER_TOKEN_LENGTH
        and all(character in _OWNER_ALPHABET for character in value)
    )


def _is_canonical_fence(value: str) -> bool:
    return (
        bool(value)
        and value[0] in "123456789"
        and value.isascii()
        and value.isdigit()
        and (
            len(value) < len(_MAX_REDIS_INTEGER_TEXT)
            or (len(value) == len(_MAX_REDIS_INTEGER_TEXT) and value <= _MAX_REDIS_INTEGER_TEXT)
        )
    )


def _new_owner_token() -> str:
    value = token_urlsafe(24)
    if not _is_owner_token(value):
        raise RuntimeError("owner token generation failed")
    return value


def _backend_failure() -> LeaderBackendError:
    return LeaderBackendError()


def _safe_backend_call[T](call: Callable[[], T]) -> T:
    failure: LeaderBackendError | None = None
    try:
        return call()
    except Exception:
        failure = _backend_failure()
    raise failure from None


async def _safe_backend_call_async[T](call: Callable[[], Awaitable[T]]) -> T:
    failure: LeaderBackendError | None = None
    try:
        return await call()
    except Exception:
        failure = _backend_failure()
    raise failure from None


def _raise_backend_failure() -> Never:
    raise _backend_failure() from None


__all__: list[str] = []
