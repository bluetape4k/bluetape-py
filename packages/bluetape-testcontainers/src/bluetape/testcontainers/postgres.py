from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Protocol, Self
from urllib.parse import quote

from bluetape.testcontainers._support import (
    TestcontainerStartError,
    _bind_loopback,
    _failure_kind,
    _published_on_loopback,
    _ServerState,
    _StartPhase,
    _stop_after_failure,
    _validated_image,
)

__all__ = ["DEFAULT_POSTGRES_IMAGE", "PostgresConnectionDetails", "PostgresServer"]

DEFAULT_POSTGRES_IMAGE = "postgres:18-alpine"
POSTGRES_PORT = 5432
_BLUETAPE_POSTGRES_LABEL = "com.bluetape.testcontainers.postgres"
_DRIVER_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


class _PostgresContainer(Protocol):
    def with_kwargs(self, **kwargs: Any) -> Self: ...

    def with_bind_ports(self, container_port: int, host: Any = None) -> Self: ...

    def start(self) -> Self: ...

    def stop(self) -> None: ...

    def get_container_host_ip(self) -> str: ...

    def get_exposed_port(self, port: int) -> int: ...

    def get_wrapped_container(self) -> Any: ...


def _validated_value(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank without surrounding whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def _validated_driver(driver: str | None) -> str | None:
    if driver is None:
        return None
    if not isinstance(driver, str):
        raise TypeError("driver must be a string or None")
    if _DRIVER_PATTERN.fullmatch(driver) is None:
        raise ValueError("driver must be a lowercase ASCII identifier")
    return driver


def _authority(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


@dataclass(frozen=True, slots=True)
class PostgresConnectionDetails:
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)

    @property
    def url(self) -> str:
        return self.connection_url(driver=None)

    def connection_url(self, *, driver: str | None = None) -> str:
        selected = _validated_driver(driver)
        dialect = "postgresql" if selected is None else f"postgresql+{selected}"
        username = quote(self.username, safe="")
        password = quote(self.password, safe="")
        database = quote(self.database, safe="")
        return f"{dialect}://{username}:{password}@{_authority(self.host)}:{self.port}/{database}"


def _load_provider() -> Any:
    from testcontainers.postgres import PostgresContainer

    return PostgresContainer


def _new_container(
    image: str,
    database: str,
    username: str,
    password: str,
) -> _PostgresContainer:
    provider = _load_provider()
    container = provider(
        image=image,
        dbname=database,
        username=username,
        password=password,
        driver=None,
    )
    container.with_kwargs(labels={_BLUETAPE_POSTGRES_LABEL: "true"})
    _bind_loopback(container, POSTGRES_PORT)
    return container


class PostgresServer:
    """Single-use owner of an ecosystem PostgreSQL test container."""

    def __init__(
        self,
        *,
        image: str = DEFAULT_POSTGRES_IMAGE,
        database: str = "test",
        username: str = "test",
        password: str = "test",
    ) -> None:
        self._image = _validated_image(image)
        self._database = _validated_value("database", database)
        self._username = _validated_value("username", username)
        self._password = _validated_value("password", password)
        self._state = _ServerState.NEW
        self._container: _PostgresContainer | None = None
        self._details: PostgresConnectionDetails | None = None

    @property
    def running(self) -> bool:
        return self._state is _ServerState.RUNNING

    @property
    def details(self) -> PostgresConnectionDetails:
        if self._state is not _ServerState.RUNNING or self._details is None:
            raise RuntimeError("PostgresServer is not running")
        return self._details

    def start(self) -> Self:
        if self._state is _ServerState.RUNNING:
            return self
        if self._state is _ServerState.CLOSED:
            raise RuntimeError("PostgresServer is closed")
        if self._state is _ServerState.CLEANUP_FAILED:
            raise RuntimeError("PostgresServer cleanup is pending; call close() to retry")
        if self._state is _ServerState.STARTING:
            raise RuntimeError("PostgresServer is already starting")

        self._state = _ServerState.STARTING
        container: _PostgresContainer | None = None
        phase = _StartPhase.CONTAINER
        try:
            container = _new_container(
                self._image,
                self._database,
                self._username,
                self._password,
            )
            self._container = container
            phase = _StartPhase.START
            container.start()
            phase = _StartPhase.DETAILS
            if not _published_on_loopback(container, POSTGRES_PORT):
                raise RuntimeError("PostgreSQL port is not loopback-bound")
            self._details = PostgresConnectionDetails(
                host=container.get_container_host_ip(),
                port=int(container.get_exposed_port(POSTGRES_PORT)),
                database=self._database,
                username=self._username,
                password=self._password,
            )
        except BaseException as error:
            self._details = None
            cleanup_succeeded = _stop_after_failure(container, error, "PostgreSQL")
            self._container = None if cleanup_succeeded else container
            self._state = _ServerState.CLOSED if cleanup_succeeded else _ServerState.CLEANUP_FAILED
            if not isinstance(error, Exception):
                raise
            start_error = TestcontainerStartError(
                _failure_kind(error, phase),
                self._image,
                service="PostgreSQL",
            )
            if not cleanup_succeeded:
                start_error.add_note(
                    "PostgreSQL test container cleanup is pending; call close() to retry"
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
            raise RuntimeError("PostgreSQL test container cleanup failed") from None
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
            exc.add_note("PostgreSQL test container cleanup also failed; call close() to retry")
