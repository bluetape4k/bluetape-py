import math

import bluetape.testcontainers.redis as redis_module
import pytest
from bluetape.testcontainers import DEFAULT_REDIS_IMAGE, RedisServer

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
