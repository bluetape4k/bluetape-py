from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

import pytest
import redis
import redis.asyncio as redis_async
from bluetape.testcontainers import RedisServer
from bluetape.testing import eventually
from redis.asyncio.connection import Connection as AsyncConnection
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool
from redis.connection import Connection as SyncConnection
from redis.connection import ConnectionPool as SyncConnectionPool

pytestmark = pytest.mark.testcontainers

_IO_TIMEOUT = 2.0


@pytest.fixture(scope="module")
def redis_url() -> Iterator[str]:
    with RedisServer() as server:

        def host_is_ready() -> bool:
            client = redis.Redis.from_url(
                server.url,
                protocol=3,
                decode_responses=False,
                socket_connect_timeout=_IO_TIMEOUT,
                socket_timeout=_IO_TIMEOUT,
                retry_on_timeout=False,
            )
            try:
                return bool(client.ping())
            except redis.RedisError:
                return False
            finally:
                client.close()

        eventually(host_is_ready, timeout=1.0, interval=0.01)
        yield server.url


def sync_command_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
    )


def sync_reader_pool(url: str) -> SyncConnectionPool:
    return SyncConnectionPool.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
        max_connections=1,
    )


@dataclass(frozen=True, slots=True)
class SyncReader:
    pool: SyncConnectionPool
    connection: SyncConnection
    client_id: int


@contextmanager
def sync_tracking_reader(url: str, prefix: bytes) -> Iterator[SyncReader]:
    pool = sync_reader_pool(url)
    connection = pool.get_connection()
    try:
        connection.connect()
        connection.send_command("CLIENT", "TRACKING", "ON", "BCAST", "PREFIX", prefix)
        assert connection.read_response() == b"OK"
        connection.send_command("CLIENT", "ID")
        client_id = connection.read_response()
        assert type(client_id) is int
        yield SyncReader(pool=pool, connection=connection, client_id=client_id)
    finally:
        connection.disconnect()
        pool.release(connection)
        pool.disconnect()


def async_command_client(url: str) -> redis_async.Redis:
    return redis_async.Redis.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
    )


def async_reader_pool(url: str) -> AsyncConnectionPool:
    return AsyncConnectionPool.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
        max_connections=1,
    )


@dataclass(frozen=True, slots=True)
class AsyncReader:
    pool: AsyncConnectionPool
    connection: AsyncConnection
    client_id: int


@asynccontextmanager
async def async_tracking_reader(url: str, prefix: bytes) -> AsyncIterator[AsyncReader]:
    pool = async_reader_pool(url)
    connection = await pool.get_connection()
    try:
        await connection.connect()
        await connection.send_command(
            "CLIENT",
            "TRACKING",
            "ON",
            "BCAST",
            "PREFIX",
            prefix,
        )
        assert await connection.read_response() == b"OK"
        await connection.send_command("CLIENT", "ID")
        client_id = await connection.read_response()
        assert type(client_id) is int
        yield AsyncReader(pool=pool, connection=connection, client_id=client_id)
    finally:
        await connection.disconnect()
        await pool.release(connection)
        await pool.disconnect()


def assert_key_push(response: object, marker_key: bytes) -> None:
    assert response == [b"invalidate", [marker_key]]


def test_sync_public_resp3_reader_receives_peer_marker_push(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLXN5bmM:"
    marker_key = prefix + b"b3JkZXItNDI"
    command = sync_command_client(redis_url)
    try:
        with sync_tracking_reader(redis_url, prefix) as reader:
            assert reader.pool is not command.connection_pool
            assert command.set(marker_key, b"mutation-token", px=60_000) is True
            response = reader.connection.read_response(
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert_key_push(response, marker_key)
    finally:
        command.close()


@pytest.mark.asyncio
async def test_async_public_resp3_reader_receives_peer_marker_push(
    redis_url: str,
) -> None:
    prefix = b"bluetape:near:Y2FwLWFzeW5j:"
    marker_key = prefix + b"b3JkZXItNDI"
    command = async_command_client(redis_url)
    try:
        async with async_tracking_reader(redis_url, prefix) as reader:
            assert reader.pool is not command.connection_pool
            assert await command.set(marker_key, b"mutation-token", px=60_000) is True
            response = await reader.connection.read_response(
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert_key_push(response, marker_key)
    finally:
        await command.aclose()
