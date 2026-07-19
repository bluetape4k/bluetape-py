from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from ipaddress import ip_address
from itertools import count
from typing import Any

import pytest
import redis
import redis.asyncio as async_redis
from bluetape.leader.redis._keys import _redis_keys
from bluetape.leader.redis._support import _validated_async_client, _validated_sync_client
from bluetape.testcontainers import RedisServer
from redis.backoff import NoBackoff
from redis.maint_notifications import MaintNotificationsConfig
from redis.retry import Retry

if os.environ.get("PYTEST_XDIST_WORKER") is not None:
    raise RuntimeError("Redis integration tests require one serial pytest process")

TESTCONTAINERS_MARK = pytest.mark.testcontainers

_CONNECT_TIMEOUT = 0.10
_SOCKET_TIMEOUT = 0.05
_READINESS_TIMEOUT = 15.0
_READINESS_INTERVAL = 0.05
_logical_name_counter = count()
_logical_name_lock = threading.Lock()
_FIXED_CLIENT_OPTIONS = frozenset(
    {
        "decode_responses",
        "health_check_interval",
        "host",
        "maint_notifications_config",
        "port",
        "retry",
        "retry_on_error",
        "retry_on_timeout",
        "socket_connect_timeout",
        "socket_timeout",
    }
)


@dataclass(frozen=True, slots=True)
class RedisEndpoint:
    """Numeric, credential-free address for one module-owned Redis server."""

    host: str
    port: int
    startup_seconds: float

    def __repr__(self) -> str:
        return "RedisEndpoint(<redacted>)"


@dataclass(frozen=True, slots=True)
class ObservedTiming:
    """Adapter deadline envelope derived from the client's observed handshake shape."""

    handshake_round_trips: int
    connect: float
    command: float
    script: float
    acquire: float
    probe: float
    renew: float
    release: float

    def __repr__(self) -> str:
        return "ObservedTiming(<redacted>)"


@pytest.fixture(scope="module")
def redis_endpoint() -> Iterator[RedisEndpoint]:
    """Own one isolated Redis server per importing integration-test module.

    Each sync, async, or concurrency module imports this fixture directly. Its
    module scope therefore shares one server only within that module and never
    collides with another integration module's database.
    """

    started = time.monotonic()
    with RedisServer() as server:
        numeric_host = str(ip_address(socket.gethostbyname(server.host)))
        readiness_deadline = time.monotonic() + _READINESS_TIMEOUT
        while True:
            probe = new_sync_client(RedisEndpoint(numeric_host, server.port, 0.0))
            try:
                if probe.ping() is True:
                    break
            except redis.RedisError:
                pass
            finally:
                probe.close()
            if time.monotonic() >= readiness_deadline:
                pytest.fail("Redis readiness deadline exceeded", pytrace=False)
            time.sleep(_READINESS_INTERVAL)
        yield RedisEndpoint(numeric_host, server.port, time.monotonic() - started)


@pytest.fixture
def clean_redis_database(redis_endpoint: RedisEndpoint) -> Iterator[None]:
    """Flush the isolated module database before and after one scenario."""

    with borrowed_sync_client(redis_endpoint) as client:
        client.flushdb()
        try:
            yield
        finally:
            client.flushdb()


def new_sync_client(endpoint: RedisEndpoint, **overrides: Any) -> redis.Redis:
    """Create an unopened caller-owned sync client with the supported finite shape."""

    _validate_client_overrides(overrides)
    return safe_sync_client(
        host=endpoint.host,
        port=endpoint.port,
        decode_responses=False,
        socket_connect_timeout=_CONNECT_TIMEOUT,
        socket_timeout=_SOCKET_TIMEOUT,
        **overrides,
    )


def new_async_client(endpoint: RedisEndpoint, **overrides: Any) -> async_redis.Redis:
    """Create an unopened caller-owned async client with the supported finite shape."""

    _validate_client_overrides(overrides)
    return safe_async_client(
        host=endpoint.host,
        port=endpoint.port,
        decode_responses=False,
        socket_connect_timeout=_CONNECT_TIMEOUT,
        socket_timeout=_SOCKET_TIMEOUT,
        **overrides,
    )


@contextmanager
def borrowed_sync_client(endpoint: RedisEndpoint, **overrides: Any) -> Iterator[redis.Redis]:
    """Yield a caller-owned sync client and close it explicitly."""

    client = new_sync_client(endpoint, **overrides)
    try:
        yield client
    finally:
        client.close()


@asynccontextmanager
async def borrowed_async_client(
    endpoint: RedisEndpoint,
    **overrides: Any,
) -> AsyncIterator[async_redis.Redis]:
    """Yield a caller-owned async client and close it explicitly."""

    client = new_async_client(endpoint, **overrides)
    try:
        yield client
    finally:
        await client.aclose()


def observed_timing(client: redis.Redis | async_redis.Redis) -> ObservedTiming:
    """Compute H/E/P/S/A/N/R before the unopened client is first used."""

    if type(client) is redis.Redis:
        timing = _validated_sync_client(client)
    elif type(client) is async_redis.Redis:
        timing = _validated_async_client(client)
    else:
        raise TypeError("unsupported Redis integration client")
    return ObservedTiming(
        timing.handshake_round_trips,
        timing.connect,
        timing.command,
        timing.script,
        timing.acquire,
        timing.probe,
        timing.renew,
        timing.release,
    )


def unique_logical_name(scenario: str) -> str:
    """Return a process-unique logical name containing no credential or capability."""

    if (
        type(scenario) is not str
        or not scenario
        or len(scenario) > 48
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in scenario)
    ):
        raise ValueError("integration scenario name is invalid")
    with _logical_name_lock:
        sequence = next(_logical_name_counter)
    return f"leader-integration-{scenario}-{sequence}"


def leader_keys(logical_name: str, prefix: str = "bluetape-leader") -> tuple[bytes, bytes]:
    """Return private lease/fence keys for cleanup without rendering their values."""

    keys = _redis_keys(logical_name, prefix)
    return keys.lease.encode(), keys.fence.encode()


def clean_sync_keys(client: redis.Redis, keys: Iterable[bytes]) -> None:
    """Delete test-owned keys without including them in failure output."""

    values = tuple(keys)
    if values:
        client.delete(*values)


async def clean_async_keys(client: async_redis.Redis, keys: Iterable[bytes]) -> None:
    """Delete async test-owned keys without including them in failure output."""

    values = tuple(keys)
    if values:
        await client.delete(*values)


def assert_database_clean(client: redis.Redis) -> None:
    """Fail with a fixed message when the isolated database retains keys."""

    if client.dbsize() != 0:
        pytest.fail("Redis test database was not cleaned", pytrace=False)


async def assert_async_database_clean(client: async_redis.Redis) -> None:
    """Async counterpart of :func:`assert_database_clean`."""

    if await client.dbsize() != 0:
        pytest.fail("Redis test database was not cleaned", pytrace=False)


def task_baseline() -> frozenset[asyncio.Task[Any]]:
    """Capture the current event-loop task set without rendering task details."""

    return frozenset(asyncio.all_tasks())


async def cancel_and_await_tasks(tasks: Iterable[asyncio.Task[Any]]) -> None:
    """Cancel and await every registered test-owned task."""

    current = asyncio.current_task()
    owned = tuple(task for task in tasks if task is not current)
    for task in owned:
        if not task.done():
            task.cancel()
    if owned:
        await asyncio.gather(*owned, return_exceptions=True)


def assert_task_baseline(baseline: frozenset[asyncio.Task[Any]]) -> None:
    """Require exact pending-task restoration with a fixed secret-free failure."""

    if frozenset(asyncio.all_tasks()) != baseline:
        pytest.fail("async task baseline was not restored", pytrace=False)


def join_threads(threads: Iterable[threading.Thread], timeout: float = 1.0) -> None:
    """Bounded-join every registered test thread without rendering thread state."""

    deadline = time.monotonic() + timeout
    owned = tuple(threads)
    for thread in owned:
        thread.join(max(0.0, deadline - time.monotonic()))
    if any(thread.is_alive() for thread in owned):
        pytest.fail("test worker thread cleanup deadline exceeded", pytrace=False)


def _validate_client_overrides(overrides: dict[str, Any]) -> None:
    if any(key in _FIXED_CLIENT_OPTIONS or key.startswith("ssl") for key in overrides):
        raise TypeError("integration client safety options are fixed")


def safe_sync_client(**overrides: Any) -> redis.Redis:
    options: dict[str, Any] = {
        "host": "127.0.0.1",
        "socket_connect_timeout": 0.05,
        "socket_timeout": 0.05,
        "health_check_interval": 0,
        "retry": Retry(NoBackoff(), 0),
        "retry_on_error": [],
        "maint_notifications_config": MaintNotificationsConfig(
            enabled=False,
            proactive_reconnect=False,
            relaxed_timeout=-1,
        ),
    }
    options.update(overrides)
    return redis.Redis(**options)


def safe_async_client(**overrides: Any) -> async_redis.Redis:
    from redis.asyncio.retry import Retry as AsyncRetry

    options: dict[str, Any] = {
        "host": "127.0.0.1",
        "socket_connect_timeout": 0.05,
        "socket_timeout": 0.05,
        "health_check_interval": 0,
        "retry": AsyncRetry(NoBackoff(), 0),
        "retry_on_error": [],
    }
    options.update(overrides)
    return async_redis.Redis(**options)


class HostileCallback:
    def __init__(self, callback: Callable[[], Any]) -> None:
        self._callback = callback

    def get_credentials(self) -> Any:
        return self._callback()

    async def get_credentials_async(self) -> Any:
        return self._callback()
