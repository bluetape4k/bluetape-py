from __future__ import annotations

import asyncio
import socket
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO

import pytest
from _support import safe_async_client, safe_sync_client
from bluetape.leader.redis._support import (
    _handshake_commands,
    _validated_async_client,
    _validated_sync_client,
)
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError


class RespServer(AbstractContextManager["RespServer"]):
    def __init__(
        self,
        connections: int = 1,
        *,
        stall_after: int | None = None,
        unix_path: Path | None = None,
    ) -> None:
        self._connections = connections
        self._stall_after = stall_after
        self.unix_path = unix_path
        self._listener = socket.socket(socket.AF_UNIX if unix_path is not None else socket.AF_INET)
        if unix_path is None:
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(("127.0.0.1", 0))
        else:
            self._listener.bind(str(unix_path))
        self._listener.listen()
        self.port = self._listener.getsockname()[1] if unix_path is None else 0
        self.commands: list[list[tuple[bytes, ...]]] = []
        self.accepted = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=False)

    def __enter__(self) -> RespServer:
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._listener.close()
        self._thread.join(timeout=1)
        assert not self._thread.is_alive()
        if self.unix_path is not None:
            self.unix_path.unlink(missing_ok=True)

    def _serve(self) -> None:
        try:
            for _ in range(self._connections):
                connection, _address = self._listener.accept()
                self.accepted.set()
                seen: list[tuple[bytes, ...]] = []
                self.commands.append(seen)
                with connection, connection.makefile("rb") as reader:
                    while not self._stop.is_set():
                        command = _read_command(reader)
                        if command is None:
                            break
                        seen.append(command)
                        if self._stall_after is not None and len(seen) > self._stall_after:
                            self._stop.wait(1)
                            break
                        connection.sendall(_response(command))
                        if command[0].upper() == b"PING":
                            break
        except (OSError, ValueError):
            if not self._stop.is_set():
                raise


def _read_command(reader: BinaryIO) -> tuple[bytes, ...] | None:
    first = reader.readline()
    if not first:
        return None
    if not first.startswith(b"*"):
        raise ValueError("expected RESP array")
    count = int(first[1:-2])
    values: list[bytes] = []
    for _ in range(count):
        length_line = reader.readline()
        if not length_line.startswith(b"$"):
            raise ValueError("expected RESP bulk string")
        length = int(length_line[1:-2])
        value = reader.read(length)
        if reader.read(2) != b"\r\n":
            raise ValueError("invalid RESP terminator")
        values.append(value)
    return tuple(values)


def _response(command: tuple[bytes, ...]) -> bytes:
    if command[0].upper() == b"HELLO":
        return b"%1\r\n+proto\r\n:3\r\n"
    if command[0].upper() == b"PING":
        return b"+PONG\r\n"
    return b"+OK\r\n"


@pytest.mark.parametrize("auth", ["none", "password", "username-password"])
@pytest.mark.parametrize("protocol", [2, 3])
@pytest.mark.parametrize("client_name", [None, "leader-test"])
@pytest.mark.parametrize("db", [0, 1])
def test_handshake_matrix_cold_and_reconnect_observe_exact_shape(
    auth: str, protocol: int, client_name: str | None, db: int
) -> None:
    auth_options: dict[str, str] = {}
    if auth == "password":
        auth_options["password"] = "secret"
    elif auth == "username-password":
        auth_options.update(username="user", password="secret")

    with RespServer(connections=2) as server:
        client = safe_sync_client(
            port=server.port,
            protocol=protocol,
            client_name=client_name,
            db=db,
            **auth_options,
        )
        timing = _validated_sync_client(client)
        assert client.ping() is True
        client.connection_pool.disconnect()
        assert client.ping() is True
        client.connection_pool.disconnect()

    expected = list(_handshake_commands(client.connection_pool.connection_kwargs))
    expected.append("PING")
    observed = [
        [_command_name(command) for command in connection] for connection in server.commands
    ]
    assert observed == [expected, expected]
    assert timing.handshake_round_trips == len(expected) - 1


@pytest.mark.parametrize("client_family", ["sync", "async"])
@pytest.mark.parametrize("transport", ["tcp", "unix"])
def test_handshake_matrix_covers_sync_async_numeric_tcp_and_unix(
    client_family: str,
    transport: str,
    tmp_path: Path,
) -> None:
    unix_path = _unix_path(tmp_path) if transport == "unix" else None
    with RespServer(connections=2, unix_path=unix_path) as server:
        options = _server_options(server)
        if client_family == "sync":
            client = safe_sync_client(protocol=3, password="secret", db=1, **options)
            timing = _validated_sync_client(client)
            assert client.ping() is True
            client.connection_pool.disconnect()
            assert client.ping() is True
            client.connection_pool.disconnect()
        else:
            timing = asyncio.run(_exercise_async_reconnect(options))

    assert len(server.commands) == 2
    assert server.commands[0] == server.commands[1]
    assert timing.handshake_round_trips == len(server.commands[0]) - 1


async def _exercise_async_reconnect(options: dict[str, object]) -> object:
    client = safe_async_client(protocol=3, password="secret", db=1, **options)
    timing = _validated_async_client(client)
    assert await client.ping() is True
    await client.connection_pool.disconnect()
    assert await client.ping() is True
    await client.connection_pool.disconnect()
    return timing


def _server_options(server: RespServer) -> dict[str, object]:
    if server.unix_path is not None:
        return {"unix_socket_path": str(server.unix_path)}
    return {"host": "127.0.0.1", "port": server.port}


def _unix_path(tmp_path: Path) -> Path:
    return Path("/tmp") / f"bt-{tmp_path.name[-24:]}.sock"


def _command_name(command: tuple[bytes, ...]) -> str:
    first = command[0].decode().upper()
    if first == "HELLO" and b"AUTH" in command:
        return "HELLO AUTH"
    if first == "CLIENT":
        if command[1].upper() == b"SETNAME":
            return "CLIENT SETNAME"
        return f"CLIENT SETINFO {command[2].decode().upper()}"
    return first


def test_stalled_stage_sync_terminates_inside_computed_command_bound() -> None:
    with RespServer(stall_after=0) as server:
        client = safe_sync_client(
            port=server.port, socket_connect_timeout=0.05, socket_timeout=0.05
        )
        timing = _validated_sync_client(client)
        started = time.monotonic()
        with pytest.raises(RedisTimeoutError):
            client.ping()
        elapsed = time.monotonic() - started
        client.connection_pool.disconnect()

    assert elapsed <= timing.command + 0.10


@pytest.mark.parametrize("client_family", ["sync", "async"])
@pytest.mark.parametrize("transport", ["tcp", "unix"])
@pytest.mark.parametrize("stall_after", [0, 1, 2])
def test_stalled_handshake_and_primitive_responses_respect_e_p_bound(
    client_family: str,
    transport: str,
    stall_after: int,
    tmp_path: Path,
) -> None:
    unix_path = _unix_path(tmp_path) if transport == "unix" else None
    with RespServer(stall_after=stall_after, unix_path=unix_path) as server:
        options = _server_options(server)
        started = time.monotonic()
        if client_family == "sync":
            client = safe_sync_client(socket_connect_timeout=0.03, socket_timeout=0.03, **options)
            timing = _validated_sync_client(client)
            with pytest.raises((RedisTimeoutError, RedisConnectionError)):
                client.ping()
            client.connection_pool.disconnect()
        else:
            timing = asyncio.run(_stalled_async_command(options))
        elapsed = time.monotonic() - started

    expected_connect_timeout = 5.0 if transport == "unix" else 0.03
    assert timing.connect == pytest.approx(
        expected_connect_timeout + timing.handshake_round_trips * 0.03
    )
    assert elapsed <= timing.command + 0.10


async def _stalled_async_command(options: dict[str, object]) -> object:
    client = safe_async_client(socket_connect_timeout=0.03, socket_timeout=0.03, **options)
    timing = _validated_async_client(client)
    with pytest.raises((RedisTimeoutError, RedisConnectionError)):
        await client.ping()
    await client.connection_pool.disconnect()
    return timing


@pytest.mark.asyncio
async def test_stalled_stage_cancelled_async_command_is_terminal_within_100ms() -> None:
    with RespServer(stall_after=0) as server:
        client = safe_async_client(port=server.port, socket_connect_timeout=0.5, socket_timeout=0.5)
        _validated_async_client(client)
        command = asyncio.create_task(client.ping())
        accepted = await asyncio.to_thread(server.accepted.wait, 0.5)
        assert accepted
        started = time.monotonic()
        command.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(command, timeout=0.1)
        elapsed = time.monotonic() - started
        assert command.done()
        await client.aclose()

    assert elapsed <= 0.1
