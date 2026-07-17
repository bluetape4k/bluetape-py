from __future__ import annotations

import math
import re
from enum import StrEnum
from typing import Any, cast

from docker.errors import DockerException, ImageNotFound

__all__ = ["StartFailureKind", "TestcontainerStartError"]

_SHA256_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


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


class _DependencyMissingError(RuntimeError):
    pass


class _ImagePullError(RuntimeError):
    pass


class StartFailureKind(StrEnum):
    """Stable category for a Bluetape test-container startup failure."""

    DEPENDENCY_MISSING = "dependency-missing"
    RUNTIME_UNAVAILABLE = "runtime-unavailable"
    IMAGE_PULL = "image-pull"
    READINESS_TIMEOUT = "readiness-timeout"
    WRAPPER_FAILURE = "wrapper-failure"


class TestcontainerStartError(RuntimeError):
    """Raised when a Bluetape test container cannot reach RUNNING."""

    __test__ = False

    def __init__(
        self,
        kind: StartFailureKind,
        image: str,
        *,
        service: str = "Redis",
    ) -> None:
        self._kind = kind
        message = f"{service} test container start failed ({kind.value}, image={image})"
        if kind is StartFailureKind.DEPENDENCY_MISSING:
            message += '; install with pip install "bluetape-testcontainers[aws]"'
        super().__init__(message)

    @property
    def kind(self) -> StartFailureKind:
        return self._kind


def _validated_image(image: str) -> str:
    if not isinstance(image, str):
        raise TypeError("image must be a string")
    if not image or image != image.strip():
        raise ValueError("image must be non-blank without surrounding whitespace")
    if not image.isascii():
        raise ValueError("image must use an ASCII Docker reference")
    if "://" in image:
        raise ValueError("image must be a Docker reference, not a URI")
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in image
    ):
        raise ValueError("image must not contain whitespace or control characters")
    name, separator, digest = image.partition("@")
    if separator:
        if "@" in digest or not digest.startswith("sha256:"):
            raise ValueError("image credentials belong in Docker configuration")
        if _SHA256_DIGEST_PATTERN.fullmatch(digest.removeprefix("sha256:")) is None:
            raise ValueError("image digest must be a complete sha256 digest")
    else:
        leaf = name.rsplit("/", 1)[-1]
        if ":" not in leaf or not leaf.rpartition(":")[2]:
            raise ValueError("image must include a non-empty tag or digest")
    leaf = name.rsplit("/", 1)[-1]
    if not separator and leaf.rsplit(":", 1)[-1].casefold() == "latest":
        raise ValueError("image must not use the latest tag")
    if not name:
        raise ValueError("image must include a non-empty tag or digest")
    return image


def _validated_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("startup_timeout must be a finite positive number")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("startup_timeout must be a finite positive number")
    return timeout


def _bind_loopback(container: Any, container_port: int) -> None:
    binding = cast(Any, ("127.0.0.1", None))
    container.with_bind_ports(container_port, binding)


def _published_on_loopback(container: Any, container_port: int) -> bool:
    if container.get_container_host_ip() not in {"localhost", "127.0.0.1", "::1"}:
        return False
    wrapped = container.get_wrapped_container()
    wrapped.reload()
    bindings = wrapped.attrs["NetworkSettings"]["Ports"].get(f"{container_port}/tcp")
    return bool(bindings) and all(
        binding.get("HostIp") in {"127.0.0.1", "::1"} for binding in bindings
    )


def _failure_kind(error: Exception, phase: _StartPhase) -> StartFailureKind:
    if isinstance(error, _DependencyMissingError):
        return StartFailureKind.DEPENDENCY_MISSING
    if isinstance(error, (_ImagePullError, ImageNotFound)):
        return StartFailureKind.IMAGE_PULL
    if phase is _StartPhase.DETAILS:
        return StartFailureKind.WRAPPER_FAILURE
    if isinstance(error, TimeoutError):
        return StartFailureKind.READINESS_TIMEOUT
    if isinstance(error, DockerException):
        return StartFailureKind.RUNTIME_UNAVAILABLE
    return StartFailureKind.WRAPPER_FAILURE


def _stop_after_failure(container: Any | None, primary: BaseException, service: str) -> bool:
    if container is None:
        return True
    try:
        container.stop()
    except Exception:
        primary.add_note(f"{service} test container cleanup also failed")
        return False
    return True
