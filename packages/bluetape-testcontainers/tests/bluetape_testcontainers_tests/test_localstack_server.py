from __future__ import annotations

import builtins
import traceback
from dataclasses import dataclass, field
from unittest.mock import Mock

import bluetape.testcontainers.localstack as localstack_module
import pytest
from bluetape.testcontainers import (
    DEFAULT_LOCALSTACK_IMAGE,
    LocalStackServer,
    StartFailureKind,
    TestcontainerStartError,
)


@dataclass
class FakeLocalStackContainer:
    host: str = "127.0.0.1"
    port: int = 45661
    start_error: BaseException | None = None
    stop_error: Exception | None = None
    services_calls: list[tuple[str, ...]] = field(default_factory=list)
    bindings: list[tuple[int, object]] = field(default_factory=list)
    kwargs_calls: list[dict[str, object]] = field(default_factory=list)
    start_timeouts: list[float] = field(default_factory=list)
    stops: int = 0

    def with_services(self, *services: str) -> FakeLocalStackContainer:
        self.services_calls.append(services)
        return self

    def with_bind_ports(
        self,
        container_port: int,
        binding: object,
    ) -> FakeLocalStackContainer:
        self.bindings.append((container_port, binding))
        return self

    def with_kwargs(self, **kwargs: object) -> FakeLocalStackContainer:
        self.kwargs_calls.append(kwargs)
        return self

    def start(self, timeout: float = 60.0) -> FakeLocalStackContainer:
        self.start_timeouts.append(timeout)
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
        assert port == 4566
        return self.port


@pytest.mark.parametrize("services", ["s3", b"s3"])
def test_localstack_rejects_bare_string_or_bytes_services(services: object) -> None:
    with pytest.raises(TypeError):
        LocalStackServer(services=services)  # type: ignore[arg-type]


def test_localstack_normalizes_services_once_and_passes_only_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DEFAULT_LOCALSTACK_IMAGE == "localstack/localstack:4.14.0"
    container = FakeLocalStackContainer()
    provider = Mock(return_value=container)
    monkeypatch.setattr(localstack_module, "_load_provider", Mock(return_value=provider))
    monkeypatch.setattr(localstack_module, "_published_on_loopback", Mock(return_value=True))

    server = LocalStackServer(services=["s3", "sqs", "s3"], startup_timeout=7)
    assert server.start() is server

    assert container.services_calls == [("s3", "sqs")]
    assert container.kwargs_calls == [
        {"labels": {"com.bluetape.testcontainers.localstack": "true"}}
    ]
    assert container.bindings == [(4566, ("127.0.0.1", None))]
    assert container.start_timeouts == [7.0]
    assert server.details.services == ("s3", "sqs")


def test_localstack_ignores_ambient_aws_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ambient-access-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ambient-secret-marker")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-3")
    container = FakeLocalStackContainer()
    monkeypatch.setattr(localstack_module, "_new_container", Mock(return_value=container))
    monkeypatch.setattr(localstack_module, "_published_on_loopback", Mock(return_value=True))

    details = LocalStackServer(services=("s3",), region_name="us-east-1").start().details

    assert details.access_key_id == "testcontainers-localstack"
    assert details.secret_access_key == "testcontainers-localstack"
    assert details.region_name == "us-east-1"
    rendered = repr(details)
    assert "ambient" not in rendered
    assert "testcontainers-localstack" not in rendered


def test_localstack_missing_boto3_is_a_sanitized_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = localstack_module._DependencyMissingError()
    monkeypatch.setattr(localstack_module, "_new_container", Mock(side_effect=missing))

    with pytest.raises(TestcontainerStartError) as raised:
        LocalStackServer(services=("s3",)).start()

    assert raised.value.kind is StartFailureKind.DEPENDENCY_MISSING
    assert raised.value.__cause__ is None
    assert 'pip install "bluetape-testcontainers[aws]"' in str(raised.value)


@pytest.mark.parametrize(
    ("missing_name", "translated"),
    [("boto3", True), ("testcontainers.core", False)],
)
def test_localstack_loader_translates_only_missing_boto3(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
    translated: bool,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "testcontainers.localstack":
            raise ModuleNotFoundError("provider dependency missing", name=missing_name)
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    expected = localstack_module._DependencyMissingError if translated else ModuleNotFoundError
    with pytest.raises(expected):
        localstack_module._load_provider()


def test_localstack_cleanup_failure_is_retryable_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakeLocalStackContainer(stop_error=RuntimeError("secret cleanup"))
    monkeypatch.setattr(localstack_module, "_new_container", Mock(return_value=container))
    monkeypatch.setattr(localstack_module, "_published_on_loopback", Mock(return_value=True))
    server = LocalStackServer(services=("s3",)).start()

    with pytest.raises(RuntimeError, match="LocalStack test container cleanup failed") as raised:
        server.close()
    assert raised.value.__cause__ is None
    assert "secret" not in "".join(traceback.format_exception(raised.value))
    container.stop_error = None
    server.close()
    server.close()


@pytest.mark.parametrize(
    "services",
    [(), (1,), ("",), ("S3",), ("-s3",), ("s3-",)],
)
def test_localstack_rejects_invalid_service_selection(services: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        LocalStackServer(services=services)  # type: ignore[arg-type]


@pytest.mark.parametrize("region", ["", "US-EAST-1", "us_east_1", "us-east"])
def test_localstack_rejects_invalid_region(region: str) -> None:
    with pytest.raises(ValueError):
        LocalStackServer(services=("s3",), region_name=region)


@pytest.mark.parametrize("timeout", [True, "5", 0, -1, float("inf"), float("nan")])
def test_localstack_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        LocalStackServer(services=("s3",), startup_timeout=timeout)  # type: ignore[arg-type]


def test_localstack_construction_does_not_load_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = Mock(side_effect=AssertionError("provider loaded"))
    monkeypatch.setattr(localstack_module, "_load_provider", loader)
    server = LocalStackServer(services=("s3",))

    assert server.running is False
    loader.assert_not_called()


def test_localstack_close_before_start_is_terminal() -> None:
    server = LocalStackServer(services=("s3",))
    with pytest.raises(RuntimeError, match="not running"):
        _ = server.details
    server.close()
    server.close()
    with pytest.raises(RuntimeError, match="closed"):
        server.start()


def test_localstack_rejects_wildcard_binding_and_cleans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakeLocalStackContainer()
    monkeypatch.setattr(localstack_module, "_new_container", Mock(return_value=container))
    monkeypatch.setattr(localstack_module, "_published_on_loopback", Mock(return_value=False))

    with pytest.raises(TestcontainerStartError) as raised:
        LocalStackServer(services=("s3",)).start()

    assert raised.value.kind is StartFailureKind.WRAPPER_FAILURE
    assert container.stops == 1


def test_localstack_body_exception_remains_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakeLocalStackContainer(stop_error=RuntimeError("cleanup secret"))
    monkeypatch.setattr(localstack_module, "_new_container", Mock(return_value=container))
    monkeypatch.setattr(localstack_module, "_published_on_loopback", Mock(return_value=True))
    server = LocalStackServer(services=("s3",))

    with pytest.raises(ValueError, match="body failure") as raised:
        with server:
            raise ValueError("body failure")

    assert any("call close() to retry" in note for note in raised.value.__notes__)


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(2), GeneratorExit()])
def test_localstack_control_flow_is_preserved_and_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    interrupt: BaseException,
) -> None:
    container = FakeLocalStackContainer(start_error=interrupt)
    monkeypatch.setattr(localstack_module, "_new_container", Mock(return_value=container))
    with pytest.raises(type(interrupt)):
        LocalStackServer(services=("s3",)).start()
    assert container.stops == 1


def test_localstack_control_flow_and_cleanup_failure_remain_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakeLocalStackContainer(
        start_error=KeyboardInterrupt(),
        stop_error=RuntimeError("cleanup secret"),
    )
    monkeypatch.setattr(localstack_module, "_new_container", Mock(return_value=container))
    server = LocalStackServer(services=("s3",))

    with pytest.raises(KeyboardInterrupt) as raised:
        server.start()

    assert any("cleanup also failed" in note for note in raised.value.__notes__)
    with pytest.raises(RuntimeError, match="cleanup is pending"):
        server.start()
    container.stop_error = None
    server.close()
    with pytest.raises(RuntimeError, match="closed"):
        server.start()
