import math
import traceback
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import bluetape.testcontainers.redis as redis_module
import pytest
from bluetape.testcontainers import (
    DEFAULT_REDIS_IMAGE,
    RedisServer,
    StartFailureKind,
)
from bluetape.testcontainers import (
    TestcontainerStartError as RedisStartError,
)
from docker.errors import DockerException, ImageNotFound

from ._support import ContainerFactory, FakeContainer

REAL_PULL_IMAGE = redis_module._pull_image
REAL_START_WITHOUT_REAPER = redis_module._start_without_reaper


@pytest.fixture(autouse=True)
def avoid_real_image_pull(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        redis_module,
        "_pull_image",
        lambda container, image, startup_timeout: None,
    )
    monkeypatch.setattr(
        redis_module,
        "_start_without_reaper",
        lambda container: container.start(),
    )


@pytest.mark.parametrize(
    "image",
    ["", " ", "redis", "redis:", "redis@sha256:", "redis:latest", "registry/redis:latest"],
)
def test_rejects_unpinned_or_blank_image(image: str) -> None:
    with pytest.raises(ValueError):
        RedisServer(image=image)


@pytest.mark.parametrize("image", [None, 42])
def test_rejects_non_string_image(image: object) -> None:
    with pytest.raises(TypeError):
        RedisServer(image=image)  # type: ignore[arg-type]


@pytest.mark.parametrize("image", ["redis:8 forged", "redis:8\nforged", "redis:8\tforged"])
def test_rejects_image_whitespace_and_control_characters(image: str) -> None:
    with pytest.raises(ValueError):
        RedisServer(image=image)


@pytest.mark.parametrize("timeout", [True, "5"])
def test_rejects_non_numeric_startup_timeout(timeout: object) -> None:
    with pytest.raises(TypeError):
        RedisServer(startup_timeout=timeout)  # type: ignore[arg-type]


@pytest.mark.parametrize("timeout", [0, -1, math.inf, math.nan])
def test_rejects_non_positive_or_non_finite_startup_timeout(timeout: float) -> None:
    with pytest.raises(ValueError):
        RedisServer(startup_timeout=timeout)


def test_construction_has_no_container_side_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_factory(image: str, startup_timeout: float) -> FakeContainer:
        raise AssertionError((image, startup_timeout))

    monkeypatch.setattr(redis_module, "_new_container", fail_factory)
    server = RedisServer()

    assert server.running is False
    assert DEFAULT_REDIS_IMAGE == "redis:8"
    with pytest.raises(RuntimeError, match="not running"):
        _ = server.details


def test_container_factory_applies_redis_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strategy = Mock()
    strategy.with_startup_timeout.return_value = strategy
    wait_strategy = Mock(return_value=strategy)
    container = Mock()
    container.with_kwargs.return_value = container
    container.with_exposed_ports.return_value = container
    container.waiting_for.return_value = container
    docker_container = Mock(return_value=container)
    monkeypatch.setattr(redis_module, "_ExecWaitStrategy", wait_strategy)
    monkeypatch.setattr(redis_module, "_DockerContainer", docker_container)

    created = redis_module._new_container("redis:8", 7.0)

    assert created is container
    wait_strategy.assert_called_once_with(["redis-cli", "ping"])
    strategy.with_startup_timeout.assert_called_once_with(timedelta(seconds=7.0))
    docker_container.assert_called_once_with(
        "redis:8",
        docker_client_kw={"timeout": 7.0},
    )
    container.with_kwargs.assert_called_once_with(
        labels={"com.bluetape.testcontainers.redis": "true"}
    )
    container.with_exposed_ports.assert_called_once_with(6379)
    container.waiting_for.assert_called_once_with(strategy)


def test_container_start_skips_ryuk_and_provider_auto_pull() -> None:
    created = Mock()
    containers = Mock()
    containers.create.return_value = created
    docker_client = SimpleNamespace(client=SimpleNamespace(containers=containers))
    wait_strategy = Mock()
    container = SimpleNamespace(
        image="redis:8",
        env={},
        ports={6379: None},
        volumes={},
        _command=None,
        _name=None,
        _kwargs={"labels": {"com.bluetape.testcontainers.redis": "true"}},
        _container=None,
        _wait_strategy=wait_strategy,
        _configure=Mock(),
        get_docker_client=Mock(return_value=docker_client),
    )

    started = REAL_START_WITHOUT_REAPER(container)

    assert started is container
    container._configure.assert_called_once_with()
    containers.create.assert_called_once_with(
        "redis:8",
        command=None,
        environment={},
        ports={6379: None},
        name=None,
        volumes={},
        labels={"com.bluetape.testcontainers.redis": "true"},
    )
    created.start.assert_called_once_with()
    wait_strategy.wait_until_ready.assert_called_once_with(container)
    assert container._container is created


def test_start_is_idempotent_and_details_are_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer()
    factory = ContainerFactory(container)
    monkeypatch.setattr(redis_module, "_new_container", factory)
    server = RedisServer(startup_timeout=5)

    assert server.start() is server
    first = server.details
    assert server.start() is server

    assert container.starts == 1
    assert factory.calls == [("redis:8", 5.0)]
    assert first is server.details
    assert (server.host, server.port, server.url) == (
        "127.0.0.1",
        46379,
        "redis://127.0.0.1:46379",
    )


def test_close_is_idempotent_and_prevents_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))
    server = RedisServer().start()

    server.close()
    server.close()

    assert container.stops == 1
    assert server.running is False
    with pytest.raises(RuntimeError, match="closed"):
        server.start()


def test_close_before_start_is_safe_and_terminal() -> None:
    server = RedisServer()

    server.close()
    server.close()

    assert server.running is False
    with pytest.raises(RuntimeError, match="closed"):
        server.start()


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (ImageNotFound("missing"), StartFailureKind.IMAGE_PULL),
        (DockerException("socket path secret-marker"), StartFailureKind.RUNTIME_UNAVAILABLE),
        (TimeoutError("logs secret-marker"), StartFailureKind.READINESS_TIMEOUT),
        (RuntimeError("provider secret-marker"), StartFailureKind.WRAPPER_FAILURE),
    ],
)
def test_start_failure_is_typed_redacted_and_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    kind: StartFailureKind,
) -> None:
    container = FakeContainer(start_error=error)
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))
    server = RedisServer(image="redis:8")

    with pytest.raises(RedisStartError) as raised:
        server.start()

    assert raised.value.kind is kind
    assert raised.value.__cause__ is None
    assert "secret-marker" not in str(raised.value)
    assert "secret-marker" not in "".join(traceback.format_exception(raised.value))
    assert container.stops == 1
    server.close()
    assert container.stops == 1


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(2), GeneratorExit()])
def test_control_flow_exceptions_are_cleaned_and_preserved(
    monkeypatch: pytest.MonkeyPatch,
    interrupt: BaseException,
) -> None:
    container = FakeContainer(start_error=interrupt)
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))

    with pytest.raises(type(interrupt)):
        RedisServer().start()

    assert container.stops == 1


def test_context_body_exception_is_not_masked_by_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakeContainer(stop_error=RuntimeError("cleanup secret-marker"))
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))
    server = RedisServer()

    with pytest.raises(ValueError, match="body failure") as raised:
        with server:
            raise ValueError("body failure")

    assert any("call close() to retry" in note for note in raised.value.__notes__)
    container.stop_error = None
    server.close()
    assert container.stops == 2


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", "redis://127.0.0.1:46379"),
        ("docker.internal", "redis://docker.internal:46379"),
        ("::1", "redis://[::1]:46379"),
        ("[::1]", "redis://[::1]:46379"),
    ],
)
def test_connection_url_formats_ipv4_hostname_and_ipv6(host: str, expected: str) -> None:
    assert redis_module._connection_url(host, 46379) == expected


def test_explicit_close_failure_is_typed_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer(stop_error=RuntimeError("cleanup secret-marker"))
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))
    server = RedisServer().start()

    with pytest.raises(RuntimeError, match="cleanup failed") as raised:
        server.close()

    assert "secret-marker" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert "secret-marker" not in "".join(traceback.format_exception(raised.value))
    assert container.stops == 1
    container.stop_error = None
    server.close()
    assert container.stops == 2


def test_start_failure_cleanup_can_be_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer(
        start_error=RuntimeError("provider secret-marker"),
        stop_error=RuntimeError("cleanup secret-marker"),
    )
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))
    server = RedisServer()

    with pytest.raises(RedisStartError) as raised:
        server.start()

    assert any("cleanup" in note for note in raised.value.__notes__)
    assert container.stops == 1
    with pytest.raises(RuntimeError, match="cleanup"):
        server.start()

    container.stop_error = None
    server.close()
    assert container.stops == 2


@pytest.mark.parametrize(
    "error",
    [
        DockerException("registry auth secret-marker"),
        RuntimeError("registry rate-limit secret-marker"),
    ],
)
def test_pull_phase_failures_are_classified_as_image_pull(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    container = FakeContainer()
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))

    def fail_pull(fake: FakeContainer, image: str, startup_timeout: float) -> None:
        assert fake is container
        assert image == "redis:8"
        assert startup_timeout == 30.0
        try:
            raise error
        except Exception as provider_error:
            raise redis_module._ImagePullError from provider_error

    monkeypatch.setattr(redis_module, "_pull_image", fail_pull)

    with pytest.raises(RedisStartError) as raised:
        RedisServer().start()

    assert raised.value.kind is StartFailureKind.IMAGE_PULL
    assert raised.value.__cause__ is None
    assert "secret-marker" not in str(raised.value)
    assert "secret-marker" not in "".join(traceback.format_exception(raised.value))


def test_daemon_failure_during_image_lookup_is_runtime_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = DockerException("socket secret-marker")
    container = FakeContainer()
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))

    def fail_lookup(fake: FakeContainer, image: str, startup_timeout: float) -> None:
        raise error

    monkeypatch.setattr(redis_module, "_pull_image", fail_lookup)

    with pytest.raises(RedisStartError) as raised:
        RedisServer().start()

    assert raised.value.kind is StartFailureKind.RUNTIME_UNAVAILABLE
    assert raised.value.__cause__ is None
    assert "secret-marker" not in str(raised.value)
    assert "secret-marker" not in "".join(traceback.format_exception(raised.value))


def test_image_resolution_uses_cached_image_without_registry_pull() -> None:
    images = Mock()
    container = Mock()
    container.get_docker_client.return_value = SimpleNamespace(
        client=SimpleNamespace(images=images)
    )

    REAL_PULL_IMAGE(container, "redis:8", 7.0)

    images.get.assert_called_once_with("redis:8")
    images.pull.assert_not_called()


def test_missing_image_is_pulled_and_registry_failure_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_error = DockerException("registry secret-marker")
    images = Mock()
    images.get.side_effect = ImageNotFound("missing")
    container = Mock()
    container.get_docker_client.return_value = SimpleNamespace(
        client=SimpleNamespace(images=images)
    )

    bounded_pull = Mock(side_effect=provider_error)
    monkeypatch.setattr(redis_module, "_run_bounded_pull", bounded_pull)

    with pytest.raises(redis_module._ImagePullError) as raised:
        REAL_PULL_IMAGE(container, "redis:8", 7.0)

    assert raised.value.__cause__ is provider_error
    images.get.assert_called_once_with("redis:8")
    bounded_pull.assert_called_once_with("redis:8", 7.0)


def test_bounded_pull_uses_isolated_process_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock()
    monkeypatch.setattr(redis_module._subprocess, "run", run)

    redis_module._run_bounded_pull("redis:8", 7.0)

    command = run.call_args.args[0]
    assert command[0] == redis_module._sys.executable
    assert command[-1] == "redis:8"
    assert run.call_args.kwargs == {
        "check": True,
        "stdout": redis_module._subprocess.DEVNULL,
        "stderr": redis_module._subprocess.DEVNULL,
        "timeout": 7.0,
    }


def test_public_submodule_does_not_export_provider_types() -> None:
    assert redis_module.__all__ == [
        "DEFAULT_REDIS_IMAGE",
        "RedisConnectionDetails",
        "RedisServer",
        "StartFailureKind",
        "TestcontainerStartError",
    ]
    assert "DockerContainer" not in vars(redis_module)
    assert "DockerException" not in vars(redis_module)
    assert "ExecWaitStrategy" not in vars(redis_module)
    assert "ImageNotFound" not in vars(redis_module)


def test_container_factory_failure_is_runtime_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    error = DockerException("socket secret-marker")

    def fail_factory(image: str, startup_timeout: float) -> FakeContainer:
        raise error

    monkeypatch.setattr(redis_module, "_new_container", fail_factory)

    with pytest.raises(RedisStartError) as raised:
        RedisServer().start()

    assert raised.value.kind is StartFailureKind.RUNTIME_UNAVAILABLE
    assert raised.value.__cause__ is None
    assert "secret-marker" not in str(raised.value)
    assert "secret-marker" not in "".join(traceback.format_exception(raised.value))
