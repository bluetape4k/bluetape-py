# Issue #57 Bluetape Testcontainers Redis Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `bluetape-testcontainers` distribution whose `RedisServer` owns the bluetape ecosystem Redis 8 image, readiness, dynamic connection details, and deterministic cleanup for #54 and #55 integration tests.

**Architecture:** Build the wrapper from Testcontainers core `DockerContainer`, not the official `RedisContainer`, so `redis:latest` and redis-py do not enter the package boundary. Keep all lifecycle state in one synchronous `RedisServer`; use an internal container factory for isolated unit tests and `ExecWaitStrategy(["redis-cli", "ping"])` for bounded readiness. Register the package and meta extra explicitly, while running Docker-backed tests in a dedicated serial CI job.

**Tech Stack:** Python 3.13, uv workspace/build backend, Testcontainers Python 4.14.2+, Docker, pytest 9, Ruff, GitHub Actions.

---

## File Map

Create:

- `packages/bluetape-testcontainers/pyproject.toml` — isolated distribution metadata and Testcontainers core dependency.
- `packages/bluetape-testcontainers/README.md` — English install, lifecycle, image, CI, and operational contract.
- `packages/bluetape-testcontainers/README.ko.md` — Korean source-equivalent documentation.
- `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py` — narrow public exports.
- `packages/bluetape-testcontainers/src/bluetape/testcontainers/redis.py` — validation, lifecycle state, error taxonomy, container construction, readiness, connection details, and cleanup.
- `packages/bluetape-testcontainers/tests/__init__.py` — test package marker.
- `packages/bluetape-testcontainers/tests/_support.py` — fake container and stdlib RESP helpers.
- `packages/bluetape-testcontainers/tests/test_packaging.py` — dependency and namespace isolation contract.
- `packages/bluetape-testcontainers/tests/test_redis_server.py` — Docker-free public/lifecycle/error tests.
- `packages/bluetape-testcontainers/tests/test_redis_server_integration.py` — Redis 8 Docker lifecycle and RESP round trip.

Modify:

- `pyproject.toml` — workspace dependency/source/member and pytest marker.
- `packages/bluetape/pyproject.toml` — explicit `testcontainers` forwarding extra and opt-in aggregate extras.
- `uv.lock` — exact Testcontainers/Docker transitive versions.
- `.github/workflows/ci.yml` — exclude Docker marker from base test and add dedicated serial Redis wrapper job.
- `README.md` — package table, installation extra, and ecosystem-owned Testcontainers boundary.
- `README.ko.md` — Korean parity.
- `CHANGELOG.md` — unreleased feature entry.
- `WIP.md` — mark #57 delivery and #54/#55 prerequisite order.

Do not modify:

- `packages/bluetape-testing/**` — pytest helpers remain Docker-free.
- `packages/bluetape-cache/**` — production local cache remains stdlib-only.
- `.github/workflows/fory-conformance.yml` — unrelated conformance workflow.

### Task 1: Register the isolated distribution and lock its dependency boundary

**Files:**

- Create: `packages/bluetape-testcontainers/pyproject.toml`
- Create: `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`
- Create: `packages/bluetape-testcontainers/tests/__init__.py`
- Create: `packages/bluetape-testcontainers/tests/test_packaging.py`
- Modify: `pyproject.toml`
- Modify: `packages/bluetape/pyproject.toml`
- Modify: `uv.lock`

- [x] **Step 1: Write failing packaging tests**

Create `packages/bluetape-testcontainers/tests/test_packaging.py`:

```python
import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_project(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)["project"]


def test_distribution_owns_testcontainers_namespace_and_dependency() -> None:
    project = load_project(ROOT / "packages/bluetape-testcontainers/pyproject.toml")

    assert project["name"] == "bluetape-testcontainers"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == ["testcontainers>=4.14.2,<4.15"]
    specification = importlib.util.find_spec("bluetape.testcontainers")
    assert specification is not None


def test_meta_distribution_forwards_only_explicit_testcontainers_extra() -> None:
    project = load_project(ROOT / "packages/bluetape/pyproject.toml")
    extras = project["optional-dependencies"]

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert extras["testcontainers"] == ["bluetape-testcontainers==0.1.0"]
    assert "bluetape-testcontainers==0.1.0" in extras["dev"]
    assert "bluetape-testcontainers==0.1.0" in extras["all"]


def test_production_packages_remain_testcontainers_free() -> None:
    for package in ("bluetape-core", "bluetape-cache", "bluetape-testing"):
        project = load_project(ROOT / f"packages/{package}/pyproject.toml")
        dependencies = project["dependencies"]
        assert all("testcontainers" not in dependency for dependency in dependencies)
```

- [x] **Step 2: Run the packaging test and confirm the missing package failure**

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_packaging.py -q
```

Expected: collection fails because `packages/bluetape-testcontainers` and `bluetape.testcontainers` do not exist.

- [x] **Step 3: Create minimal distribution metadata and public placeholder module**

Create `packages/bluetape-testcontainers/pyproject.toml`:

```toml
[project]
name = "bluetape-testcontainers"
version = "0.1.0"
description = "Ecosystem-owned Testcontainers wrappers for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "testcontainers>=4.14.2,<4.15",
]

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.testcontainers"
```

Create `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`:

```python
"""Ecosystem-owned Testcontainers wrappers for bluetape-py."""

__all__: list[str] = []
```

Create an empty `packages/bluetape-testcontainers/tests/__init__.py`.

Add the following entries to root `pyproject.toml`:

```toml
dependencies = [
    # existing entries remain sorted
    "bluetape-testcontainers==0.1.0",
]

[tool.uv.sources]
bluetape-testcontainers = { workspace = true }

[tool.uv.workspace]
members = [
    # existing entries remain sorted
    "packages/bluetape-testcontainers",
]
```

Add to `packages/bluetape/pyproject.toml`:

```toml
[project.optional-dependencies]
testcontainers = ["bluetape-testcontainers==0.1.0"]
dev = [
    # existing entries remain sorted
    "bluetape-testcontainers==0.1.0",
]
all = [
    # existing entries remain sorted
    "bluetape-testcontainers==0.1.0",
]

[tool.uv.sources]
bluetape-testcontainers = { workspace = true }
```

- [x] **Step 4: Lock dependencies and prove the packaging tests pass**

Run:

```bash
uv lock
uv sync --all-packages --extra fory --locked
uv run pytest packages/bluetape-testcontainers/tests/test_packaging.py -q
```

Expected: `3 passed`; `uv.lock` contains exact Testcontainers and Docker SDK resolutions.

- [x] **Step 5: Commit the isolated package boundary**

```bash
git add pyproject.toml uv.lock packages/bluetape/pyproject.toml packages/bluetape-testcontainers
git commit -m "build: isolate ecosystem Testcontainers support" -m "Constraint: Keep Docker support opt-in and outside production packages
Rejected: Add Testcontainers to bluetape-testing | couples lightweight pytest helpers to Docker
Confidence: high
Scope-risk: moderate
Directive: Add future infrastructure wrappers only under bluetape-testcontainers
Tested: uv run pytest packages/bluetape-testcontainers/tests/test_packaging.py -q
Not-tested: Docker lifecycle is added in later tasks"
```

### Task 2: Lock the public validation and lifecycle state contract

**Files:**

- Create: `packages/bluetape-testcontainers/src/bluetape/testcontainers/redis.py`
- Create: `packages/bluetape-testcontainers/tests/_support.py`
- Create: `packages/bluetape-testcontainers/tests/test_redis_server.py`
- Modify: `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`

- [x] **Step 1: Write failing constructor and state tests**

Create the initial `packages/bluetape-testcontainers/tests/_support.py`:

```python
from dataclasses import dataclass, field


@dataclass
class FakeContainer:
    host: str = "127.0.0.1"
    mapped_port: int = 46379
    start_error: BaseException | None = None
    stop_error: Exception | None = None
    starts: int = 0
    stops: int = 0

    def start(self) -> "FakeContainer":
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
        assert port == 6379
        return self.mapped_port


@dataclass
class ContainerFactory:
    container: FakeContainer
    calls: list[tuple[str, float]] = field(default_factory=list)

    def __call__(self, image: str, startup_timeout: float) -> FakeContainer:
        self.calls.append((image, startup_timeout))
        return self.container
```

Create `packages/bluetape-testcontainers/tests/test_redis_server.py` with these tests first:

```python
import math

import pytest

import bluetape.testcontainers.redis as redis_module
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
        RedisServer(startup_timeout=timeout)  # type: ignore[arg-type]


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
```

- [x] **Step 2: Run the state tests and confirm missing API failures**

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_redis_server.py -q
```

Expected: collection fails because `DEFAULT_REDIS_IMAGE` and `RedisServer` are not exported.

- [x] **Step 3: Implement validation, immutable details, and state transitions**

Create `packages/bluetape-testcontainers/src/bluetape/testcontainers/redis.py` with the following complete first slice:

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from types import TracebackType
from typing import Self

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import ExecWaitStrategy

DEFAULT_REDIS_IMAGE = "redis:8"
REDIS_PORT = 6379


class _ServerState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    CLOSED = "closed"


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
    return (
        DockerContainer(image)
        .with_exposed_ports(REDIS_PORT)
        .waiting_for(strategy)
    )


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
        container = _new_container(self._image, self._startup_timeout)
        self._container = container
        container.start()
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(REDIS_PORT))
        self._details = RedisConnectionDetails(host=host, port=port, url=f"redis://{host}:{port}")
        self._state = _ServerState.RUNNING
        return self

    def close(self) -> None:
        if self._state is _ServerState.CLOSED:
            return
        container = self._container
        self._container = None
        self._details = None
        self._state = _ServerState.CLOSED
        if container is not None:
            container.stop()

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
```

Update `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`:

```python
"""Ecosystem-owned Testcontainers wrappers for bluetape-py."""

from bluetape.testcontainers.redis import (
    DEFAULT_REDIS_IMAGE,
    RedisConnectionDetails,
    RedisServer,
)

__all__ = [
    "DEFAULT_REDIS_IMAGE",
    "RedisConnectionDetails",
    "RedisServer",
]
```

- [x] **Step 4: Run focused tests and fix only contract mismatches**

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_redis_server.py -q
uv run ruff check packages/bluetape-testcontainers
uv run ruff format --check packages/bluetape-testcontainers
```

Expected: all constructor/state tests pass and Ruff reports no violations.

- [x] **Step 5: Commit the public lifecycle skeleton**

```bash
git add packages/bluetape-testcontainers
git commit -m "feat: define Redis test server lifecycle" -m "Constraint: Avoid import-time Docker access and hidden global containers
Rejected: Auto-start constructor | hides expensive external side effects
Confidence: high
Scope-risk: moderate
Directive: Preserve explicit single-use lifecycle and immutable running details
Tested: targeted RedisServer tests; Ruff check and format
Not-tested: failure classification and real Docker lifecycle follow"
```

### Task 3: Make startup failure and cleanup behavior deterministic

**Files:**

- Modify: `packages/bluetape-testcontainers/src/bluetape/testcontainers/redis.py`
- Modify: `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`
- Modify: `packages/bluetape-testcontainers/tests/test_redis_server.py`

- [x] **Step 1: Add failing cleanup and typed-error tests**

Append tests that cover these exact outcomes:

```python
from docker.errors import DockerException, ImageNotFound

from bluetape.testcontainers import (
    StartFailureKind,
    TestcontainerStartError,
)


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
```

- [x] **Step 2: Run focused tests and confirm missing error types/cleanup failures**

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_redis_server.py -q
```

Expected: new tests fail because error taxonomy and failure cleanup are not implemented.

- [x] **Step 3: Implement stable failure classification and non-masking cleanup**

Add to `redis.py`:

```python
from docker.errors import DockerException, ImageNotFound


class StartFailureKind(StrEnum):
    RUNTIME_UNAVAILABLE = "runtime-unavailable"
    IMAGE_PULL = "image-pull"
    READINESS_TIMEOUT = "readiness-timeout"
    WRAPPER_FAILURE = "wrapper-failure"


class TestcontainerStartError(RuntimeError):
    def __init__(self, kind: StartFailureKind, image: str) -> None:
        self._kind = kind
        super().__init__(f"Redis test container start failed ({kind.value}, image={image})")

    @property
    def kind(self) -> StartFailureKind:
        return self._kind


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
```

Replace `start`, `close`, and `__exit__` terminal paths with:

```python
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
            self._details = RedisConnectionDetails(host=host, port=port, url=f"redis://{host}:{port}")
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
```

Export `StartFailureKind` and `TestcontainerStartError` from `__init__.py` and include them in `__all__`.

- [x] **Step 4: Run lifecycle/error tests and static checks**

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_redis_server.py -q
uv run ruff check packages/bluetape-testcontainers
uv run ruff format --check packages/bluetape-testcontainers
```

Expected: every fake-container lifecycle/error test passes; error strings contain no fake provider detail.

- [x] **Step 5: Commit deterministic cleanup behavior**

```bash
git add packages/bluetape-testcontainers
git commit -m "fix: bound Redis test server failure cleanup" -m "Constraint: Startup and cleanup failures must preserve the primary cause without leaking provider output
Rejected: Stringify Docker exceptions | exposes unstable and possibly sensitive environment detail
Confidence: high
Scope-risk: moderate
Directive: Keep error labels stable and raw provider diagnostics in the cause chain only
Tested: targeted lifecycle/error tests; Ruff check and format
Not-tested: real Docker failure injection is outside issue #57"
```

### Task 4: Prove the ecosystem Redis 8 wrapper against Docker and wire it into CI

**Files:**

- Modify: `packages/bluetape-testcontainers/tests/_support.py`
- Create: `packages/bluetape-testcontainers/tests/test_redis_server_integration.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Add a stdlib RESP helper and failing Docker integration test**

Append to `_support.py`:

```python
import socket


def redis_command(host: str, port: int, *parts: str) -> bytes | None:
    encoded = [part.encode() for part in parts]
    request = [f"*{len(encoded)}\r\n".encode()]
    for part in encoded:
        request.extend((f"${len(part)}\r\n".encode(), part, b"\r\n"))

    with socket.create_connection((host, port), timeout=2.0) as stream:
        stream.sendall(b"".join(request))
        prefix = stream.recv(1)
        line = _read_line(stream)
        if prefix == b"+":
            return line
        if prefix == b"$":
            size = int(line)
            if size == -1:
                return None
            payload = _read_exact(stream, size)
            assert _read_exact(stream, 2) == b"\r\n"
            return payload
        raise AssertionError(f"unexpected RESP prefix: {prefix!r}")


def _read_line(stream: socket.socket) -> bytes:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = stream.recv(1)
        if not chunk:
            raise AssertionError("Redis closed the connection")
        data.extend(chunk)
    return bytes(data[:-2])


def _read_exact(stream: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.recv(size - len(data))
        if not chunk:
            raise AssertionError("Redis closed the connection")
        data.extend(chunk)
    return bytes(data)
```

Create `test_redis_server_integration.py`:

```python
import pytest

from bluetape.testcontainers import DEFAULT_REDIS_IMAGE, RedisServer
from ._support import redis_command


@pytest.mark.testcontainers
def test_redis_8_server_supports_dynamic_port_and_resp_round_trip() -> None:
    with RedisServer() as server:
        assert DEFAULT_REDIS_IMAGE == "redis:8"
        assert server.port > 0
        assert server.url == f"redis://{server.host}:{server.port}"
        assert redis_command(server.host, server.port, "PING") == b"PONG"
        assert redis_command(server.host, server.port, "SET", "issue:57", "ok") == b"OK"
        assert redis_command(server.host, server.port, "GET", "issue:57") == b"ok"

    assert server.running is False
    with pytest.raises(RuntimeError, match="not running"):
        _ = server.details
```

Add to root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "testcontainers: requires a Docker-compatible Testcontainers runtime and runs serially",
]
```

- [x] **Step 2: Run the Docker test before CI changes**

Run:

```bash
uv run pytest -m testcontainers packages/bluetape-testcontainers -q
```

Expected: pass with a locally available Docker runtime. If Docker is unavailable, preserve the failure as a blocker; do not add an unconditional skip.

- [x] **Step 3: Separate base and Docker-backed CI execution**

In `.github/workflows/ci.yml`, change the base test command to:

```yaml
      - name: Test
        run: uv run --package bluetape-serde --extra fory --python 3.13.14 pytest -m "not testcontainers"
```

Add the dedicated job:

```yaml
  testcontainers-redis:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd

      - name: Set up uv
        uses: astral-sh/setup-uv@94527f2e458b27549849d47d273a16bec83a01e9

      - name: Set up Python
        uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
        with:
          python-version: "3.13.14"

      - name: Sync wrapper dependencies
        run: uv sync --all-packages --locked --python 3.13.14

      - name: Test Redis wrapper serially
        run: uv run --python 3.13.14 pytest -m testcontainers packages/bluetape-testcontainers -q
```

Do not add a matrix, xdist, service container, fixed port, or direct `redis` Docker image declaration to the workflow.

- [x] **Step 4: Validate both test lanes and workflow syntax**

Run sequentially:

```bash
uv run pytest -m "not testcontainers"
uv run pytest -m testcontainers packages/bluetape-testcontainers -q
actionlint
```

Expected: the existing 857-test baseline plus all new non-Docker tests pass in the first lane; the Redis 8 integration test passes in the second; `actionlint` is silent.

- [x] **Step 5: Commit Docker and CI evidence**

```bash
git add pyproject.toml .github/workflows/ci.yml packages/bluetape-testcontainers/tests
git commit -m "test: prove Redis wrapper on the ecosystem image" -m "Constraint: Docker-backed checks must be explicit and serial
Rejected: GitHub service container | bypasses the reusable wrapper contract
Confidence: high
Scope-risk: moderate
Directive: Route all Redis integration consumers through RedisServer
Tested: non-Testcontainers suite; serial Redis 8 integration test; actionlint
Not-tested: Redis Cluster, Sentinel, TLS, and failure injection are out of scope"
```

### Task 5: Document adoption and prove wheel/default-install isolation

**Files:**

- Create: `packages/bluetape-testcontainers/README.md`
- Create: `packages/bluetape-testcontainers/README.ko.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `CHANGELOG.md`
- Modify: `WIP.md`
- Modify: `packages/bluetape-testcontainers/tests/test_packaging.py`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Add wheel/default-install packaging assertions**

Extend `test_packaging.py` to assert:

```python
def test_meta_default_does_not_forward_testcontainers() -> None:
    project = load_project(ROOT / "packages/bluetape/pyproject.toml")

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert "bluetape-testcontainers" not in project["dependencies"]


def test_wrapper_does_not_depend_on_redis_py() -> None:
    project = load_project(ROOT / "packages/bluetape-testcontainers/pyproject.toml")

    assert all(not dependency.startswith("redis") for dependency in project["dependencies"])
```

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_packaging.py -q
```

Expected: pass after Task 1 metadata; these tests prevent later dependency leakage.

- [x] **Step 2: Add English and Korean package documentation**

Both package READMEs must include, in source-equivalent form:

```markdown
# bluetape-testcontainers

English | [한국어](README.ko.md)

`bluetape-testcontainers` owns reusable Docker-backed test server boundaries for
the bluetape Python ecosystem. It is test infrastructure, not a production
Redis client package.

## Install

```bash
pip install "bluetape[testcontainers]"
```

## Redis

```python
from bluetape.testcontainers import RedisServer

with RedisServer() as redis:
    configure_test(redis_url=redis.url)
```

- Default image: `redis:8`
- Dynamic host port only
- Explicit start/close or context-manager ownership
- `redis-cli ping` readiness bounded by `startup_timeout`
- Docker-backed suites run serially
- Explicit tagged/digest image overrides are allowed; `latest` is rejected
```

The Korean README uses `[English](README.md) | 한국어` and natural Korean prose. Do not add a diagram: the approved spec records the linear lifecycle as text and code.

- [x] **Step 3: Update root docs, changelog, and roadmap state**

Update root README locale files with:

- package table row for `bluetape-testcontainers`;
- `pip install "bluetape[testcontainers]"` example;
- one sentence that #54/#55 Docker tests consume the ecosystem wrapper;
- no claim that #54/#55 production features are complete.

Add an Unreleased entry to `CHANGELOG.md`:

```markdown
- Add the opt-in `bluetape-testcontainers` Redis 8 wrapper with explicit lifecycle, bounded readiness, dynamic connection details, and serial Docker CI coverage.
```

Update `WIP.md` so #57 is the active completed prerequisite in this branch and #54/#55 remain follow-ups.

- [x] **Step 4: Add an actual default-wheel smoke check to CI**

After the existing build step in the base CI job, add:

```yaml
      - name: Assert default wheel is Docker-provider-free
        run: |
          tmp_dir="$(mktemp -d)"
          uv build --package bluetape-core --out-dir "$tmp_dir/dist"
          uv build --package bluetape --out-dir "$tmp_dir/dist"
          uv venv "$tmp_dir/venv" --python 3.13.14
          uv pip install --python "$tmp_dir/venv/bin/python" --no-index \
            --find-links "$tmp_dir/dist" bluetape==0.1.0
          "$tmp_dir/venv/bin/python" -c \
            'import importlib.util; assert importlib.util.find_spec("testcontainers") is None; assert importlib.util.find_spec("docker") is None; assert importlib.util.find_spec("redis") is None'
```

- [x] **Step 5: Validate bilingual parity and packaging**

Run:

```bash
uv run pytest packages/bluetape-testcontainers/tests/test_packaging.py -q
uv build --all-packages
git diff --check
```

Manually compare README headings, install commands, public API names, default image, and lifecycle/error claims across both locales. Expected: no missing section or contradictory claim.

- [x] **Step 6: Commit adoption documentation and isolation evidence**

```bash
git add README.md README.ko.md CHANGELOG.md WIP.md .github/workflows/ci.yml packages/bluetape-testcontainers
git commit -m "docs: make Redis test infrastructure adoption explicit" -m "Constraint: Public install and lifecycle guidance must remain bilingual and provider-free by default
Rejected: Document direct RedisContainer usage | bypasses ecosystem image authority
Confidence: high
Scope-risk: narrow
Directive: Keep README locale files source-equivalent when wrapper behavior changes
Tested: packaging tests; all-package build; git diff --check
Not-tested: Published-index installation awaits release workflow"
```

### Task 6: Run the full workflow verification and close P0/P1 review findings

**Files:**

- Create: `docs/superpowers/reviews/2026-07-11-issue-57-testcontainers-redis-review.md`
- Create: `docs/superpowers/reviews/2026-07-11-issue-57-testcontainers-redis-verifier.md`
- Create when durable learning exists: `docs/lessons/2026-07-11-issue-57-testcontainers-redis.md`
- Modify: implementation/docs/tests only when review produces evidence-backed findings.

- [x] **Step 1: Run targeted verification from a clean dependency state**

```bash
uv sync --all-packages --extra fory --locked
uv run pytest packages/bluetape-testcontainers/tests/test_packaging.py -q
uv run pytest packages/bluetape-testcontainers/tests/test_redis_server.py -q
uv run pytest -m testcontainers packages/bluetape-testcontainers -q
```

Expected: packaging/unit/Docker integration tests pass; Docker tests run sequentially.

- [x] **Step 2: Run repository-wide static, test, build, and workflow checks**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not testcontainers"
uv build --all-packages
actionlint
git diff --check
```

Expected: all commands exit 0. Record exact test counts and built wheel names in the verifier artifact.

- [x] **Step 3: Audit the full package registration chain**

Verify and record evidence for:

```text
root pyproject dependency/source/workspace member
bluetape forwarding extra/dev/all
uv.lock exact dependency resolution
package README English/Korean
root README English/Korean package/install state
CHANGELOG and WIP state
CI base exclusion and dedicated serial Docker job
default-wheel provider-free smoke
uv build --all-packages artifact
```

Any missing, stale, or `UNKNOWN` item is FAIL; do not use `SKIPPED`.

- [x] **Step 4: Run independent code review until P0=0 and P1=0**

Use the repository `code-review` workflow against `origin/develop...HEAD`. Record every finding with severity, file, line, evidence, disposition, and verification in `docs/superpowers/reviews/2026-07-11-issue-57-testcontainers-redis-review.md`.

For each P0/P1 finding:

1. reproduce or prove it from code/test evidence;
2. add a failing regression test;
3. implement the smallest safe fix;
4. rerun targeted and affected full checks;
5. repeat review.

Stop only when the current diff has `P0=0 P1=0`.

- [x] **Step 5: Write verifier evidence and workflow counts**

Create `docs/superpowers/reviews/2026-07-11-issue-57-testcontainers-redis-verifier.md` with:

```markdown
# Issue #57 Verifier

- Commit: `<current HEAD>`
- Required checks: X/X
- N/A: N
- Blocked: 0
- P0: 0
- P1: 0
- Targeted unit: `<count> passed`
- Docker integration: `<count> passed`
- Full non-Docker suite: `<count> passed`
- Ruff check/format: PASS
- All-package build: PASS
- actionlint: PASS
- git diff --check: PASS
- Default-wheel provider isolation: PASS
```

N/A is allowed only for:

- benchmark: one container startup dominates and no throughput contract exists;
- diagram: one linear lifecycle is clearer in code/text;
- nightly workflow: this repository has no nightly workflow and dedicated CI owns Docker proof.

- [x] **Step 6: Commit final review and verification evidence**

```bash
git add docs/superpowers/reviews packages pyproject.toml uv.lock .github README.md README.ko.md CHANGELOG.md WIP.md
# If Task 6 created the optional lesson, add its exact path separately:
git add docs/lessons/2026-07-11-issue-57-testcontainers-redis.md
git commit -m "test: close Redis wrapper delivery evidence" -m "Constraint: Merge readiness requires fresh Docker, packaging, full-suite, and P0/P1 evidence
Rejected: Treat Docker unavailability as a skip | leaves the core wrapper contract unproven
Confidence: high
Scope-risk: moderate
Directive: Re-run serial Redis integration after any image or lifecycle change
Tested: targeted and full tests; Ruff; build; actionlint; diff check; independent review
Not-tested: Publication is outside issue #57"
```

- [x] **Step 7: Confirm the branch is ready for PR creation**

```bash
repo-status
git log --oneline origin/develop..HEAD
git diff --check origin/develop...HEAD
```

Expected: clean worktree, intentional Lore-compliant commits only, no P0/P1 findings, no blocked required check.
