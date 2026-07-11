import math

import bluetape.testcontainers.redis as redis_module
import pytest
from bluetape.testcontainers import (
    DEFAULT_REDIS_IMAGE,
    RedisServer,
    StartFailureKind,
    TestcontainerStartError,
)
from docker.errors import DockerException, ImageNotFound

from ._support import ContainerFactory, FakeContainer


@pytest.mark.parametrize("image", ["", " ", "redis", "redis:latest", "registry/redis:latest"])
def test_rejects_unpinned_or_blank_image(image: str) -> None:
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

    with pytest.raises(TestcontainerStartError) as raised:
        server.start()

    assert raised.value.kind is kind
    assert raised.value.__cause__ is error
    assert "secret-marker" not in str(raised.value)
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

    with pytest.raises(ValueError, match="body failure") as raised:
        with RedisServer():
            raise ValueError("body failure")

    assert any("cleanup also failed" in note for note in raised.value.__notes__)


def test_explicit_close_failure_is_typed_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer(stop_error=RuntimeError("cleanup secret-marker"))
    monkeypatch.setattr(redis_module, "_new_container", ContainerFactory(container))
    server = RedisServer().start()

    with pytest.raises(RuntimeError, match="cleanup failed") as raised:
        server.close()

    assert "secret-marker" not in str(raised.value)
    server.close()
    assert container.stops == 1
