import socket
from dataclasses import dataclass, field
from typing import Any

import docker


@dataclass
class FakeContainer:
    host: str = "127.0.0.1"
    mapped_port: int = 46379
    start_error: BaseException | None = None
    stop_error: Exception | None = None
    starts: int = 0
    stops: int = 0

    def start(self) -> "FakeContainer":
        self.starts += 1
        if self.start_error is not None:
            raise self.start_error
        return self

    def stop(self) -> None:
        self.stops += 1
        if self.stop_error is not None:
            raise self.stop_error

    def get_container_host_ip(self) -> str:
        return self.host

    def get_exposed_port(self, port: int) -> int:
        assert port == 6379
        return self.mapped_port


@dataclass
class ContainerFactory:
    container: FakeContainer
    calls: list[tuple[str, float]] = field(default_factory=list)

    def __call__(self, image: str, startup_timeout: float) -> FakeContainer:
        self.calls.append((image, startup_timeout))
        return self.container


def redis_command(host: str, port: int, *parts: str) -> bytes | None:
    encoded = [part.encode() for part in parts]
    request = [f"*{len(encoded)}\r\n".encode()]
    for part in encoded:
        request.extend((f"${len(part)}\r\n".encode(), part, b"\r\n"))

    with socket.create_connection((host, port), timeout=2.0) as stream:
        stream.sendall(b"".join(request))
        prefix = stream.recv(1)
        line = _read_line(stream)
        if prefix == b"+":
            return line
        if prefix == b"$":
            size = int(line)
            if size == -1:
                return None
            payload = _read_exact(stream, size)
            assert _read_exact(stream, 2) == b"\r\n"
            return payload
        raise AssertionError(f"unexpected RESP prefix: {prefix!r}")


def _read_line(stream: socket.socket) -> bytes:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = stream.recv(1)
        if not chunk:
            raise AssertionError("Redis closed the connection")
        data.extend(chunk)
    return bytes(data[:-2])


def _read_exact(stream: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.recv(size - len(data))
        if not chunk:
            raise AssertionError("Redis closed the connection")
        data.extend(chunk)
    return bytes(data)


def published_host_ips(provider: Any, port: int) -> set[str]:
    wrapped = provider.get_wrapped_container()
    wrapped.reload()
    bindings = wrapped.attrs["NetworkSettings"]["Ports"][f"{port}/tcp"]
    return {binding["HostIp"] for binding in bindings}


def assert_container_removed(container_id: str) -> None:
    client = docker.from_env()
    try:
        assert client.containers.list(all=True, filters={"id": container_id}) == []
    finally:
        client.close()
