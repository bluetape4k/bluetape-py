"""Private validation and value helpers for the bounded Redis adapter."""

from __future__ import annotations

import asyncio
import ipaddress
import math
import os
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from secrets import token_urlsafe
from typing import Any, Never

from bluetape.leader import LeaderBackendError

import redis
import redis.asyncio as async_redis
from redis.backoff import NoBackoff
from redis.client import CaseInsensitiveDict, get_response_callbacks
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
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
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
    _validate_sync_lock(client.single_connection_lock)
    pool = client.connection_pool
    if (
        type(pool) is not SyncConnectionPool
        or not _has_exact_attribute_names(pool, _SYNC_POOL_ATTRIBUTES)
        or pool.cache is not None
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    _validate_sync_pool_identity(pool)
    _validate_sync_lock(pool._fork_lock)
    _validate_sync_lock(pool._lock)
    _validate_empty_pool(pool)
    _validate_event_dispatcher(getattr(client, "_event_dispatcher", None))
    _validate_event_dispatcher(getattr(pool, "_event_dispatcher", None))
    timing = _validate_pool(
        pool.connection_class,
        pool.connection_kwargs,
        pool.max_connections,
        sync=True,
    )
    _validate_response_callbacks(client, pool.connection_kwargs)
    return timing


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
    _validate_async_lock(client._single_conn_lock)
    _validate_async_lock(client._usage_lock)
    pool = client.connection_pool
    if type(pool) is not AsyncConnectionPool or not _has_exact_attribute_names(
        pool, _ASYNC_POOL_ATTRIBUTES
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    _validate_async_lock(pool._lock)
    _validate_empty_pool(pool)
    _validate_event_dispatcher(getattr(client, "_event_dispatcher", None))
    _validate_event_dispatcher(getattr(pool, "_event_dispatcher", None))
    connection_class = pool.connection_class
    if connection_class is not AsyncConnection and connection_class is not AsyncUnixConnection:
        raise TypeError(_UNSUPPORTED_CLIENT)
    timing = _validate_pool(
        connection_class,
        pool.connection_kwargs,
        pool.max_connections,
        sync=False,
    )
    _validate_response_callbacks(client, pool.connection_kwargs)
    return timing


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

    is_sync_tcp = sync and connection_class is SyncConnection
    is_sync_unix = sync and connection_class is SyncUnixConnection
    is_async_tcp = not sync and connection_class is AsyncConnection
    is_async_unix = not sync and connection_class is AsyncUnixConnection
    if not (is_sync_tcp or is_sync_unix or is_async_tcp or is_async_unix):
        raise TypeError(_UNSUPPORTED_CLIENT)
    required_keys = _required_option_keys(connection_class)
    if (
        type(options) is not dict
        or len(options) != len(required_keys)
        or any(type(key) is not str or key not in required_keys for key in options)
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    if type(max_connections) is not int or max_connections <= 0:
        raise TypeError(_UNSUPPORTED_CLIENT)

    connect_timeout = _positive_finite(
        options.get("socket_connect_timeout", 5.0)
        if is_sync_unix or is_async_unix
        else options.get("socket_connect_timeout")
    )
    socket_timeout = _positive_finite(options.get("socket_timeout"))
    if connect_timeout is None or socket_timeout is None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    health_check_interval = options.get("health_check_interval")
    if type(health_check_interval) is not int or health_check_interval != 0:
        raise TypeError(_UNSUPPORTED_CLIENT)
    retry_errors = options.get("retry_on_error")
    if retry_errors is not None and (type(retry_errors) is not list or retry_errors):
        raise TypeError(_UNSUPPORTED_CLIENT)

    _validate_retry(options.get("retry"), sync=sync)

    if options.get("redis_connect_func") is not None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("credential_provider") is not None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("decode_responses") is not False:
        raise TypeError(_UNSUPPORTED_CLIENT)
    encoding = options.get("encoding")
    encoding_errors = options.get("encoding_errors")
    if type(encoding) is not str or encoding != "utf-8":
        raise TypeError(_UNSUPPORTED_CLIENT)
    if type(encoding_errors) is not str or encoding_errors != "strict":
        raise TypeError(_UNSUPPORTED_CLIENT)
    if options.get("legacy_responses") is not True:
        raise TypeError(_UNSUPPORTED_CLIENT)
    read_size = options.get("socket_read_size")
    if type(read_size) is not int or read_size <= 0:
        raise TypeError(_UNSUPPORTED_CLIENT)
    driver_info = options.get("driver_info")
    if not _valid_driver_info(driver_info):
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
    username = options.get("username")
    password = options.get("password")
    if username is None:
        if password is not None and not _nonempty_credential(password):
            raise TypeError(_UNSUPPORTED_CLIENT)
    elif not _nonempty_credential(username) or not _nonempty_credential(password):
        raise TypeError(_UNSUPPORTED_CLIENT)

    if is_sync_tcp or is_async_tcp:
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
    if is_async_unix:
        handshake *= 2
    return _timing(handshake, connect_timeout, socket_timeout, pool_wait=0.0)


def _handshake_commands(options: Mapping[str, Any]) -> tuple[str, ...]:
    commands: list[str] = []
    username = options.get("username")
    password = options.get("password")
    has_auth = password is not None
    protocol = options.get("protocol")
    if has_auth and protocol == 3:
        commands.append("HELLO AUTH")
    elif has_auth:
        commands.append("AUTH")
        if (
            type(protocol) is int
            and protocol == 2
            and _nonempty_credential(username)
            and _nonempty_credential(password)
        ):
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
    if value is None:
        return True
    if type(value) is not MaintNotificationsConfig or not _has_exact_attribute_names(
        value, frozenset({"enabled", "relaxed_timeout", "proactive_reconnect", "endpoint_type"})
    ):
        return False
    state = vars(value)
    relaxed_timeout = state["relaxed_timeout"]
    return (
        state["enabled"] is False
        and state["proactive_reconnect"] is False
        and type(relaxed_timeout) is int
        and relaxed_timeout == -1
        and state["endpoint_type"] is None
    )


def _valid_driver_info(value: object) -> bool:
    if type(value) is not DriverInfo or not _has_exact_attribute_names(
        value, frozenset({"name", "lib_version", "_upstream"})
    ):
        return False
    state = vars(value)
    name = state["name"]
    lib_version = state["lib_version"]
    upstream = state["_upstream"]
    return (
        type(name) is str
        and name == "redis-py"
        and type(lib_version) is str
        and lib_version == redis.__version__
        and type(upstream) is list
        and not upstream
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
    if connection_class is SyncConnection:
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
    if type(actual) is not CaseInsensitiveDict:
        raise TypeError(_UNSUPPORTED_CLIENT)
    expected = get_response_callbacks(
        options.get("protocol"), options.get("legacy_responses", True)
    )
    if len(actual) != len(expected):
        raise TypeError(_UNSUPPORTED_CLIENT)
    actual_names = tuple(actual)
    if any(type(name) is not str for name in actual_names):
        raise TypeError(_UNSUPPORTED_CLIENT)
    if any(name not in expected for name in actual_names):
        raise TypeError(_UNSUPPORTED_CLIENT)
    for name, callback in expected.items():
        if actual.get(name) is not callback:
            raise TypeError(_UNSUPPORTED_CLIENT)


def _validate_sync_pool_identity(pool: object) -> None:
    state = vars(pool)
    pid = state.get("pid")
    pool_id = state.get("_pool_id")
    if type(pid) is not int or pid != os.getpid():
        raise TypeError(_UNSUPPORTED_CLIENT)
    if (
        state.get("_maint_notifications_pool_handler") is not None
        or state.get("_oss_cluster_maint_notifications_handler") is not None
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    if (
        type(pool_id) is not str
        or len(pool_id) != 8
        or any(character not in "0123456789abcdef" for character in pool_id)
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)


def _validate_retry(value: object, *, sync: bool) -> None:
    from redis.asyncio.retry import Retry as AsyncRetry

    retry_type = SyncRetry if sync else AsyncRetry
    if type(value) is not retry_type or not _has_exact_attribute_names(
        value, frozenset({"_backoff", "_retries", "_supported_errors"})
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)

    state = vars(value)
    retries = state["_retries"]
    backoff = state["_backoff"]
    supported_errors = state["_supported_errors"]
    if type(retries) is not int or retries != 0 or type(backoff) is not NoBackoff:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if not _has_exact_attribute_names(backoff, frozenset({"_backoff"})):
        raise TypeError(_UNSUPPORTED_CLIENT)
    backoff_value = vars(backoff)["_backoff"]
    if type(backoff_value) is not int or backoff_value != 0:
        raise TypeError(_UNSUPPORTED_CLIENT)

    expected_errors = (
        (RedisConnectionError, RedisTimeoutError, TimeoutError)
        if sync
        else (RedisConnectionError, RedisTimeoutError)
    )
    if type(supported_errors) is not tuple or len(supported_errors) != len(expected_errors):
        raise TypeError(_UNSUPPORTED_CLIENT)
    if any(
        actual is not expected
        for actual, expected in zip(supported_errors, expected_errors, strict=True)
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)


def _validate_event_dispatcher(value: object) -> None:
    if type(value) is not EventDispatcher or not _has_exact_attribute_names(
        value, frozenset({"_event_listeners_mapping", "_lock", "_async_lock"})
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)
    _validate_sync_lock(value._lock)
    if value._async_lock is not None:
        raise TypeError(_UNSUPPORTED_CLIENT)
    expected = EventDispatcher()
    actual_mapping = vars(value).get("_event_listeners_mapping")
    expected_mapping = vars(expected).get("_event_listeners_mapping")
    if type(actual_mapping) is not dict or type(expected_mapping) is not dict:
        raise TypeError(_UNSUPPORTED_CLIENT)
    if len(actual_mapping) != len(expected_mapping):
        raise TypeError(_UNSUPPORTED_CLIENT)
    actual_events = tuple(actual_mapping)
    expected_events = tuple(expected_mapping)
    if any(type(event) is not type for event in actual_events):
        raise TypeError(_UNSUPPORTED_CLIENT)
    if any(
        not any(actual_event is expected_event for expected_event in expected_events)
        for actual_event in actual_events
    ):
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


def _validate_sync_lock(value: object) -> None:
    if type(value) is not type(threading.RLock()) or value._is_owned():  # type: ignore[attr-defined]
        raise TypeError(_UNSUPPORTED_CLIENT)
    if not value.acquire(blocking=False):  # type: ignore[attr-defined]
        raise TypeError(_UNSUPPORTED_CLIENT)
    value.release()  # type: ignore[attr-defined]


def _validate_async_lock(value: object) -> None:
    if (
        type(value) is not asyncio.Lock
        or value.locked()
        or vars(value) != {"_waiters": None, "_locked": False}
    ):
        raise TypeError(_UNSUPPORTED_CLIENT)


def _validate_empty_pool(value: object) -> None:
    available = getattr(value, "_available_connections", None)
    in_use = getattr(value, "_in_use_connections", None)
    if type(available) is not list or available or type(in_use) is not set or in_use:
        raise TypeError(_UNSUPPORTED_CLIENT)
    created = getattr(value, "_created_connections", 0)
    if type(created) is not int or created != 0:
        raise TypeError(_UNSUPPORTED_CLIENT)


def _nonempty_credential(value: object) -> bool:
    return type(value) in (str, bytes) and len(value) > 0


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
