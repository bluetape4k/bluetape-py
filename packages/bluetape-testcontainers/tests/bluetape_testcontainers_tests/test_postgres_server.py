from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from unittest.mock import Mock

import bluetape.testcontainers.postgres as postgres_module
import pytest
from bluetape.testcontainers import (
    DEFAULT_POSTGRES_IMAGE,
    PostgresConnectionDetails,
    PostgresServer,
    StartFailureKind,
    TestcontainerStartError,
)


@dataclass
class FakePostgresContainer:
    host: str = "127.0.0.1"
    port: int = 45432
    start_error: BaseException | None = None
    stop_error: Exception | None = None
    starts: int = 0
    stops: int = 0
    bindings: list[tuple[int, object]] = field(default_factory=list)
    kwargs_calls: list[dict[str, object]] = field(default_factory=list)

    def with_kwargs(self, **kwargs: object) -> FakePostgresContainer:
        self.kwargs_calls.append(kwargs)
        return self

    def with_bind_ports(
        self,
        container_port: int,
        binding: object,
    ) -> FakePostgresContainer:
        self.bindings.append((container_port, binding))
        return self

    def start(self) -> FakePostgresContainer:
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
        assert port == 5432
        return self.port


def test_postgres_details_encode_values_and_hide_password() -> None:
    assert DEFAULT_POSTGRES_IMAGE == "postgres:18-alpine"
    details = PostgresConnectionDetails(
        host="::1",
        port=45432,
        database="db/name",
        username="user@example.com",
        password="secret marker",
    )

    assert details.url == ("postgresql://user%40example.com:secret%20marker@[::1]:45432/db%2Fname")
    assert details.connection_url(driver=None) == details.url
    assert details.connection_url(driver="psycopg").startswith("postgresql+psycopg://")
    assert "secret marker" not in repr(details)


@pytest.mark.parametrize("driver", ["", "Psycopg", "+psycopg", "psy-copg"])
def test_postgres_rejects_invalid_driver(driver: str) -> None:
    details = PostgresConnectionDetails("127.0.0.1", 5432, "test", "test", "test")
    with pytest.raises(ValueError):
        details.connection_url(driver=driver)


def test_postgres_lifecycle_is_single_use_and_cleanup_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakePostgresContainer(stop_error=RuntimeError("secret cleanup"))
    factory = Mock(return_value=container)
    monkeypatch.setattr(postgres_module, "_new_container", factory)
    monkeypatch.setattr(postgres_module, "_published_on_loopback", Mock(return_value=True))
    server = PostgresServer(database="db", username="user", password="pass")

    assert server.start() is server
    assert server.start() is server
    assert server.details.database == "db"
    assert container.starts == 1
    with pytest.raises(RuntimeError, match="PostgreSQL test container cleanup failed"):
        server.close()
    with pytest.raises(RuntimeError, match="cleanup is pending"):
        server.start()
    container.stop_error = None
    server.close()
    server.close()
    with pytest.raises(RuntimeError, match="closed"):
        server.start()


def test_postgres_start_failure_is_redacted_and_cleans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakePostgresContainer(start_error=RuntimeError("provider secret-marker"))
    monkeypatch.setattr(postgres_module, "_new_container", Mock(return_value=container))

    with pytest.raises(TestcontainerStartError) as raised:
        PostgresServer().start()

    assert raised.value.kind is StartFailureKind.WRAPPER_FAILURE
    assert raised.value.__cause__ is None
    assert "secret-marker" not in "".join(traceback.format_exception(raised.value))
    assert container.stops == 1


def test_postgres_provider_receives_driver_none_and_loopback_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Mock(return_value=FakePostgresContainer())
    monkeypatch.setattr(postgres_module, "_load_provider", Mock(return_value=provider))

    container = postgres_module._new_container("postgres:18-alpine", "db", "user", "pass")

    provider.assert_called_once_with(
        image="postgres:18-alpine",
        dbname="db",
        username="user",
        password="pass",
        driver=None,
    )
    assert container.kwargs_calls == [{"labels": {"com.bluetape.testcontainers.postgres": "true"}}]
    assert container.bindings == [(5432, ("127.0.0.1", None))]


@pytest.mark.parametrize(
    ("field_name", "value", "error_type"),
    [
        ("database", 1, TypeError),
        ("username", "", ValueError),
        ("password", " secret ", ValueError),
        ("database", "bad\x00name", ValueError),
    ],
)
def test_postgres_rejects_invalid_constructor_values(
    field_name: str,
    value: object,
    error_type: type[Exception],
) -> None:
    arguments: dict[str, object] = {
        "database": "test",
        "username": "test",
        "password": "test",
    }
    arguments[field_name] = value
    with pytest.raises(error_type):
        PostgresServer(**arguments)  # type: ignore[arg-type]


def test_postgres_close_before_start_is_terminal() -> None:
    server = PostgresServer()
    with pytest.raises(RuntimeError, match="not running"):
        _ = server.details
    server.close()
    server.close()
    with pytest.raises(RuntimeError, match="closed"):
        server.start()


def test_postgres_body_exception_remains_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakePostgresContainer(stop_error=RuntimeError("cleanup secret"))
    monkeypatch.setattr(postgres_module, "_new_container", Mock(return_value=container))
    monkeypatch.setattr(postgres_module, "_published_on_loopback", Mock(return_value=True))
    server = PostgresServer()

    with pytest.raises(ValueError, match="body failure") as raised:
        with server:
            raise ValueError("body failure")

    assert any("call close() to retry" in note for note in raised.value.__notes__)


def test_postgres_rejects_wildcard_binding_and_cleans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakePostgresContainer()
    monkeypatch.setattr(postgres_module, "_new_container", Mock(return_value=container))
    monkeypatch.setattr(postgres_module, "_published_on_loopback", Mock(return_value=False))

    with pytest.raises(TestcontainerStartError) as raised:
        PostgresServer().start()

    assert raised.value.kind is StartFailureKind.WRAPPER_FAILURE
    assert container.stops == 1


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(2), GeneratorExit()])
def test_postgres_control_flow_is_preserved_and_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    interrupt: BaseException,
) -> None:
    container = FakePostgresContainer(start_error=interrupt)
    monkeypatch.setattr(postgres_module, "_new_container", Mock(return_value=container))
    with pytest.raises(type(interrupt)):
        PostgresServer().start()
    assert container.stops == 1


def test_postgres_control_flow_and_cleanup_failure_remain_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakePostgresContainer(
        start_error=KeyboardInterrupt(),
        stop_error=RuntimeError("cleanup secret"),
    )
    monkeypatch.setattr(postgres_module, "_new_container", Mock(return_value=container))
    server = PostgresServer()

    with pytest.raises(KeyboardInterrupt) as raised:
        server.start()

    assert any("cleanup also failed" in note for note in raised.value.__notes__)
    with pytest.raises(RuntimeError, match="cleanup is pending"):
        server.start()
    container.stop_error = None
    server.close()
    with pytest.raises(RuntimeError, match="closed"):
        server.start()


def test_postgres_module_does_not_export_provider_types() -> None:
    assert "PostgresContainer" not in postgres_module.__all__
    assert "PostgresContainer" not in dir(postgres_module)
