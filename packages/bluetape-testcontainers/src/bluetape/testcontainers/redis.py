from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from types import TracebackType
from typing import Self

from docker.errors import DockerException as _DockerException
from docker.errors import ImageNotFound as _ImageNotFound

from testcontainers.core.container import DockerContainer as _DockerContainer
from testcontainers.core.wait_strategies import ExecWaitStrategy as _ExecWaitStrategy

__all__ = [
    "DEFAULT_REDIS_IMAGE",
    "RedisConnectionDetails",
    "RedisServer",
    "StartFailureKind",
    "TestcontainerStartError",
]

DEFAULT_REDIS_IMAGE = "redis:8"
REDIS_PORT = 6379


class _ServerState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    CLEANUP_FAILED = "cleanup-failed"
    CLOSED = "closed"


class _StartPhase(StrEnum):
    CONTAINER = "container"
    IMAGE_PULL = "image-pull"
    START = "start"
    DETAILS = "details"


class StartFailureKind(StrEnum):
    """Stable category for a Redis test container startup failure."""

    RUNTIME_UNAVAILABLE = "runtime-unavailable"
    IMAGE_PULL = "image-pull"
    READINESS_TIMEOUT = "readiness-timeout"
    WRAPPER_FAILURE = "wrapper-failure"


class TestcontainerStartError(RuntimeError):
    """Raised when the Redis test container cannot reach the running state."""

    __test__ = False

    def __init__(self, kind: StartFailureKind, image: str) -> None:
        self._kind = kind
        super().__init__(f"Redis test container start failed ({kind.value}, image={image})")

    @property
    def kind(self) -> StartFailureKind:
        return self._kind


@dataclass(frozen=True, slots=True)
class RedisConnectionDetails:
    """Immutable mapped Redis endpoint available while a server is running."""

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


def _new_container(image: str, startup_timeout: float) -> _DockerContainer:
    strategy = _ExecWaitStrategy(["redis-cli", "ping"]).with_startup_timeout(
        timedelta(seconds=startup_timeout)
    )
    return (
        _DockerContainer(image, docker_client_kw={"timeout": startup_timeout})
        .with_exposed_ports(REDIS_PORT)
        .waiting_for(strategy)
    )


def _pull_image(container: _DockerContainer, image: str) -> None:
    container.get_docker_client().client.images.pull(image)


def _failure_kind(error: Exception, phase: _StartPhase) -> StartFailureKind:
    if phase is _StartPhase.IMAGE_PULL or isinstance(error, _ImageNotFound):
        return StartFailureKind.IMAGE_PULL
    if isinstance(error, TimeoutError):
        return StartFailureKind.READINESS_TIMEOUT
    if isinstance(error, _DockerException):
        return StartFailureKind.RUNTIME_UNAVAILABLE
    return StartFailureKind.WRAPPER_FAILURE


def _stop_after_failure(container: _DockerContainer | None, primary: BaseException) -> bool:
    if container is None:
        return True
    try:
        container.stop()
    except Exception:
        primary.add_note("Redis test container cleanup also failed")
        return False
    return True


class RedisServer:
    """Single-use, synchronous owner of an ecosystem Redis test container."""

    def __init__(
        self,
        *,
        image: str = DEFAULT_REDIS_IMAGE,
        startup_timeout: float = 30.0,
    ) -> None:
        self._image = _validated_image(image)
        self._startup_timeout = _validated_timeout(startup_timeout)
        self._state = _ServerState.NEW
        self._container: _DockerContainer | None = None
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
        if self._state is _ServerState.CLEANUP_FAILED:
            raise RuntimeError("RedisServer cleanup is pending; call close() to retry")
        if self._state is _ServerState.STARTING:
            raise RuntimeError("RedisServer is already starting")

        self._state = _ServerState.STARTING
        container: _DockerContainer | None = None
        phase = _StartPhase.CONTAINER
        try:
            container = _new_container(self._image, self._startup_timeout)
            self._container = container
            phase = _StartPhase.IMAGE_PULL
            _pull_image(container, self._image)
            phase = _StartPhase.START
            container.start()
            phase = _StartPhase.DETAILS
            host = container.get_container_host_ip()
            port = int(container.get_exposed_port(REDIS_PORT))
            self._details = RedisConnectionDetails(
                host=host,
                port=port,
                url=f"redis://{host}:{port}",
            )
        except BaseException as error:
            self._details = None
            cleanup_succeeded = _stop_after_failure(container, error)
            self._container = None if cleanup_succeeded else container
            self._state = _ServerState.CLOSED if cleanup_succeeded else _ServerState.CLEANUP_FAILED
            if not isinstance(error, Exception):
                raise
            start_error = TestcontainerStartError(_failure_kind(error, phase), self._image)
            if not cleanup_succeeded:
                start_error.add_note(
                    "Redis test container cleanup is pending; call close() to retry"
                )
            raise start_error from error

        self._state = _ServerState.RUNNING
        return self

    def close(self) -> None:
        if self._state is _ServerState.CLOSED:
            return
        container = self._container
        self._details = None
        if container is None:
            self._state = _ServerState.CLOSED
            return
        self._state = _ServerState.CLEANUP_FAILED
        try:
            container.stop()
        except Exception as error:
            raise RuntimeError("Redis test container cleanup failed") from error
        self._container = None
        self._state = _ServerState.CLOSED

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
