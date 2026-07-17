from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Protocol, Self

from bluetape.testcontainers._support import (
    TestcontainerStartError,
    _bind_loopback,
    _DependencyMissingError,
    _failure_kind,
    _published_on_loopback,
    _ServerState,
    _StartPhase,
    _stop_after_failure,
    _validated_image,
    _validated_timeout,
)

__all__ = ["DEFAULT_LOCALSTACK_IMAGE", "LocalStackConnectionDetails", "LocalStackServer"]

DEFAULT_LOCALSTACK_IMAGE = "localstack/localstack:4.14.0"
LOCALSTACK_PORT = 4566
_BLUETAPE_LOCALSTACK_LABEL = "com.bluetape.testcontainers.localstack"
_SYNTHETIC_CREDENTIAL = "testcontainers-localstack"
_REGION_PATTERN = re.compile(r"[a-z]{2}(?:-[a-z0-9]+)+-[0-9]")
_SERVICE_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


class _LocalStackContainer(Protocol):
    def with_services(self, *services: str) -> Self: ...

    def with_kwargs(self, **kwargs: Any) -> Self: ...

    def with_bind_ports(self, container_port: int, host: Any = None) -> Self: ...

    def start(self, timeout: float = 60.0) -> Self: ...

    def stop(self) -> None: ...

    def get_container_host_ip(self) -> str: ...

    def get_exposed_port(self, port: int) -> int: ...

    def get_wrapped_container(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class LocalStackConnectionDetails:
    endpoint_url: str
    region_name: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    services: tuple[str, ...]


def _validated_region(region_name: str) -> str:
    if not isinstance(region_name, str):
        raise TypeError("region_name must be a string")
    if _REGION_PATTERN.fullmatch(region_name) is None:
        raise ValueError("region_name must be a lowercase AWS-style region")
    return region_name


def _validated_services(services: Iterable[str]) -> tuple[str, ...]:
    if isinstance(services, (str, bytes)):
        raise TypeError("services must be an iterable of service names")
    try:
        values = tuple(services)
    except TypeError:
        raise TypeError("services must be an iterable of service names") from None
    if not values:
        raise ValueError("at least one LocalStack service is required")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError("each LocalStack service must be a string")
        if _SERVICE_PATTERN.fullmatch(value) is None:
            raise ValueError("LocalStack services must be lowercase ASCII identifiers")
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    return tuple(normalized)


def _load_provider() -> Any:
    try:
        from testcontainers.localstack import LocalStackContainer
    except ModuleNotFoundError as error:
        if error.name == "boto3":
            raise _DependencyMissingError from None
        raise
    return LocalStackContainer


def _new_container(
    image: str,
    region_name: str,
    services: tuple[str, ...],
) -> _LocalStackContainer:
    provider = _load_provider()
    container = provider(image=image, region_name=region_name)
    container.with_services(*services)
    container.with_kwargs(labels={_BLUETAPE_LOCALSTACK_LABEL: "true"})
    _bind_loopback(container, LOCALSTACK_PORT)
    return container


class LocalStackServer:
    """Single-use owner of selected LocalStack services."""

    def __init__(
        self,
        *,
        services: Iterable[str],
        image: str = DEFAULT_LOCALSTACK_IMAGE,
        region_name: str = "us-east-1",
        startup_timeout: float = 60.0,
    ) -> None:
        self._services = _validated_services(services)
        self._image = _validated_image(image)
        self._region_name = _validated_region(region_name)
        self._startup_timeout = _validated_timeout(startup_timeout)
        self._state = _ServerState.NEW
        self._container: _LocalStackContainer | None = None
        self._details: LocalStackConnectionDetails | None = None

    @property
    def running(self) -> bool:
        return self._state is _ServerState.RUNNING

    @property
    def details(self) -> LocalStackConnectionDetails:
        if self._state is not _ServerState.RUNNING or self._details is None:
            raise RuntimeError("LocalStackServer is not running")
        return self._details

    def start(self) -> Self:
        if self._state is _ServerState.RUNNING:
            return self
        if self._state is _ServerState.CLOSED:
            raise RuntimeError("LocalStackServer is closed")
        if self._state is _ServerState.CLEANUP_FAILED:
            raise RuntimeError("LocalStackServer cleanup is pending; call close() to retry")
        if self._state is _ServerState.STARTING:
            raise RuntimeError("LocalStackServer is already starting")

        self._state = _ServerState.STARTING
        container: _LocalStackContainer | None = None
        phase = _StartPhase.CONTAINER
        try:
            container = _new_container(self._image, self._region_name, self._services)
            self._container = container
            phase = _StartPhase.START
            container.start(timeout=self._startup_timeout)
            phase = _StartPhase.DETAILS
            if not _published_on_loopback(container, LOCALSTACK_PORT):
                raise RuntimeError("LocalStack port is not loopback-bound")
            host = container.get_container_host_ip()
            port = int(container.get_exposed_port(LOCALSTACK_PORT))
            authority = f"[{host}]" if ":" in host and not host.startswith("[") else host
            self._details = LocalStackConnectionDetails(
                endpoint_url=f"http://{authority}:{port}",
                region_name=self._region_name,
                access_key_id=_SYNTHETIC_CREDENTIAL,
                secret_access_key=_SYNTHETIC_CREDENTIAL,
                services=self._services,
            )
        except BaseException as error:
            self._details = None
            cleanup_succeeded = _stop_after_failure(container, error, "LocalStack")
            self._container = None if cleanup_succeeded else container
            self._state = _ServerState.CLOSED if cleanup_succeeded else _ServerState.CLEANUP_FAILED
            if not isinstance(error, Exception):
                raise
            start_error = TestcontainerStartError(
                _failure_kind(error, phase),
                self._image,
                service="LocalStack",
            )
            if not cleanup_succeeded:
                start_error.add_note(
                    "LocalStack test container cleanup is pending; call close() to retry"
                )
            raise start_error from None

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
        except Exception:
            raise RuntimeError("LocalStack test container cleanup failed") from None
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
            exc.add_note("LocalStack test container cleanup also failed; call close() to retry")
