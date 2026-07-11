from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from types import TracebackType
from typing import Self

from docker.errors import DockerException, ImageNotFound

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import ExecWaitStrategy

DEFAULT_REDIS_IMAGE = "redis:8"
REDIS_PORT = 6379


class _ServerState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    CLOSED = "closed"


class StartFailureKind(StrEnum):
    RUNTIME_UNAVAILABLE = "runtime-unavailable"
    IMAGE_PULL = "image-pull"
    READINESS_TIMEOUT = "readiness-timeout"
    WRAPPER_FAILURE = "wrapper-failure"


class TestcontainerStartError(RuntimeError):
    __test__ = False

    def __init__(self, kind: StartFailureKind, image: str) -> None:
        self._kind = kind
        super().__init__(f"Redis test container start failed ({kind.value}, image={image})")

    @property
    def kind(self) -> StartFailureKind:
        return self._kind


@dataclass(frozen=True, slots=True)
class RedisConnectionDetails:
    host: str
    port: int
    url: str


def _validated_image(image: str) -> str:
    if not isinstance(image, str):
        raise TypeError("image must be a string")
    if not image or image != image.strip():
        raise ValueError("image must be non-blank without surrounding whitespace")
    leaf = image.rsplit("/", 1)[-1]
    if "@sha256:" not in image and ":" not in leaf:
        raise ValueError("image must include an explicit tag or digest")
    if leaf.rsplit(":", 1)[-1].casefold() == "latest":
        raise ValueError("image must not use the latest tag")
    return image


def _validated_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("startup_timeout must be a finite positive number")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("startup_timeout must be a finite positive number")
    return timeout


def _new_container(image: str, startup_timeout: float) -> DockerContainer:
    strategy = ExecWaitStrategy(["redis-cli", "ping"]).with_startup_timeout(
        timedelta(seconds=startup_timeout)
    )
    return DockerContainer(image).with_exposed_ports(REDIS_PORT).waiting_for(strategy)


def _failure_kind(error: Exception) -> StartFailureKind:
    if isinstance(error, ImageNotFound):
        return StartFailureKind.IMAGE_PULL
    if isinstance(error, TimeoutError):
        return StartFailureKind.READINESS_TIMEOUT
    if isinstance(error, DockerException):
        return StartFailureKind.RUNTIME_UNAVAILABLE
    return StartFailureKind.WRAPPER_FAILURE


def _stop_after_failure(container: DockerContainer | None, primary: BaseException) -> None:
    if container is None:
        return
    try:
        container.stop()
    except Exception:
        primary.add_note("Redis test container cleanup also failed")


class RedisServer:
    def __init__(
        self,
        *,
        image: str = DEFAULT_REDIS_IMAGE,
        startup_timeout: float = 30.0,
    ) -> None:
        self._image = _validated_image(image)
        self._startup_timeout = _validated_timeout(startup_timeout)
        self._state = _ServerState.NEW
        self._container: DockerContainer | None = None
        self._details: RedisConnectionDetails | None = None

    @property
    def running(self) -> bool:
        return self._state is _ServerState.RUNNING

    @property
    def details(self) -> RedisConnectionDetails:
        if self._state is not _ServerState.RUNNING or self._details is None:
            raise RuntimeError("RedisServer is not running")
        return self._details

    @property
    def host(self) -> str:
        return self.details.host

    @property
    def port(self) -> int:
        return self.details.port

    @property
    def url(self) -> str:
        return self.details.url

    def start(self) -> Self:
        if self._state is _ServerState.RUNNING:
            return self
        if self._state is _ServerState.CLOSED:
            raise RuntimeError("RedisServer is closed")
        if self._state is _ServerState.STARTING:
            raise RuntimeError("RedisServer is already starting")

        self._state = _ServerState.STARTING
        container: DockerContainer | None = None
        try:
            container = _new_container(self._image, self._startup_timeout)
            self._container = container
            container.start()
            host = container.get_container_host_ip()
            port = int(container.get_exposed_port(REDIS_PORT))
            self._details = RedisConnectionDetails(
                host=host,
                port=port,
                url=f"redis://{host}:{port}",
            )
        except BaseException as error:
            self._container = None
            self._details = None
            self._state = _ServerState.CLOSED
            _stop_after_failure(container, error)
            if not isinstance(error, Exception):
                raise
            raise TestcontainerStartError(_failure_kind(error), self._image) from error

        self._state = _ServerState.RUNNING
        return self

    def close(self) -> None:
        if self._state is _ServerState.CLOSED:
            return
        container = self._container
        self._container = None
        self._details = None
        self._state = _ServerState.CLOSED
        if container is None:
            return
        try:
            container.stop()
        except Exception as error:
            raise RuntimeError("Redis test container cleanup failed") from error

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except Exception:
            if exc is None:
                raise
            exc.add_note("Redis test container cleanup also failed")
