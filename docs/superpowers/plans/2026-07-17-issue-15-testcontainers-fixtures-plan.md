# Issue #15 Testcontainers Fixture Families Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `bluetape-testcontainers` with explicit PostgreSQL 18 and caller-selected LocalStack fixture families while preserving the delivered Redis API, thin default install, deterministic cleanup, and secret-safe diagnostics.

**Architecture:** Keep the public wrappers synchronous, single-use, and caller-owned. Extract only pure validation/error/loopback helpers from `redis.py`; implement PostgreSQL and LocalStack as separate thin adapters over their official Testcontainers modules, lazy-load optional providers, and duplicate the small lifecycle state machine instead of introducing a shared server base. Package clients remain test-only, Docker-backed tests stay serial, and provider-owned Ryuk is documented but excluded from wrapper-owned cleanup claims.

**Tech Stack:** Python 3.13.14, Testcontainers Python 4.14.2, Docker SDK 7.2.0, PostgreSQL 18, LocalStack 4.14.0, Psycopg 3, boto3, pytest, Ruff, uv, GitHub Actions.

---

## File Map and Ownership

Create:

- `packages/bluetape-testcontainers/src/bluetape/testcontainers/_support.py` — shared enum/error identity, pure validation, failure classification, loopback binding, and cleanup helpers; no server base.
- `packages/bluetape-testcontainers/src/bluetape/testcontainers/postgres.py` — PostgreSQL details, URL encoding, official provider construction, and lifecycle.
- `packages/bluetape-testcontainers/src/bluetape/testcontainers/localstack.py` — LocalStack details, service/region validation, lazy provider loading, and lifecycle.
- `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_postgres_server.py` — Docker-free PostgreSQL contract tests.
- `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_postgres_server_integration.py` — real PostgreSQL 18 query, binding, and cleanup proof.
- `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_localstack_server.py` — Docker-free LocalStack contract and missing-dependency tests.
- `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_localstack_server_integration.py` — real S3 round trip, binding, and cleanup proof.
- `docs/lessons/2026-07-17-issue-15-testcontainers-fixture-families.md` — mandatory Type A reusable findings and evidence.
- `docs/review/2026-07-17-issue-15-testcontainers-fixtures-code-review.md` — final six-lens implemented-diff verdict.
- `docs/review/2026-07-17-issue-15-testcontainers-fixtures-verifier.md` — exact spec/plan/command verification.

Modify:

- `packages/bluetape-testcontainers/src/bluetape/testcontainers/redis.py` — import and re-export shared symbols without changing Redis behavior or messages.
- `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py` — explicit additive exports for both new families and shared errors.
- `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_redis_server.py` — compatibility guards for moved symbols and stronger image validation.
- `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_packaging.py` — extras, dependency-group, wheel metadata, and base-import isolation proof.
- `packages/bluetape-testcontainers/pyproject.toml` — `postgres`, `aws`, and `all` extras plus integration-only `test` group.
- `uv.lock` — locked boto3/Psycopg/Testcontainers extra resolution.
- `.github/workflows/ci.yml` — replace the Redis-only job with one serial service-wrapper job and Docker preflight.
- `packages/bluetape-testcontainers/README.md` and `README.ko.md` — complete service/install/ownership/error examples.
- `README.md` and `README.ko.md` — root package/status/install/test guidance parity.
- `WIP.md` — mark issue #15 delivery and downstream availability.
- `CHANGELOG.md` — unreleased fixture-family entry.

Do not modify:

- `packages/bluetape-testing/**` — it remains Docker-free.
- `packages/bluetape/pyproject.toml` — root `bluetape[testcontainers]` intentionally stays base-only.
- production SQL/AWS client packages — engines, pools, clients, transactions, schemas, and resources remain caller-owned.
- release versions, tags, publish workflows, or release notes.

Tasks are sequential. Tasks 1-3 touch the shared export surface, Task 4 changes dependency state, Task 5 consumes that locked state, and Tasks 6-7 integrate documentation and verification. Do not run these tasks concurrently.

## Current Implementation Anchors

- `redis.py` already owns `_ServerState`, `_StartPhase`, validation, redacted errors, cleanup retry, and the exact Redis error message.
- Testcontainers 4.14.2 `PostgresContainer` accepts `driver=None` but has no public startup-timeout parameter.
- Testcontainers 4.14.2 `LocalStackContainer.start(timeout=...)` owns readiness-log timeout and imports boto3 at module import.
- Docker SDK 7.2.0 converts `{5432: ("127.0.0.1", None)}` to an ephemeral loopback binding; the wrapper uses the provider's public `with_bind_ports` seam and proves the runtime binding after startup.
- Existing package tests use the unique `bluetape_testcontainers_tests` namespace and provider fakes; keep that collision-free shape.

## Predicted Risks and Recovery

| Risk | Signal | Mitigation | Rollback/rerun point |
| --- | --- | --- | --- |
| Provider port-binding behavior changes | Spy mismatch or wildcard `HostIp` in Docker test | Pin 4.14.x, call `with_bind_ports` once, verify runtime attrs before exposing details | Stop after Task 2/3 unit tests; revert the adapter task without touching Redis |
| Provider-owned Ryuk changes startup/resource behavior | Extra support container or first-start delay | Never mutate global Ryuk config; serialize real tests and assert only service-container removal | Rerun Task 5 from a clean Docker preflight; do not weaken cleanup assertions |
| Docker client creation, image pull, provider startup, test, or cleanup stalls outside a wrapper-supported readiness timeout | Serial CI job remains running without test output | Keep provider-supported timeout semantics and cap the whole `testcontainers-services` job with `timeout-minutes: 30` | A Docker preflight failure is infrastructure; a later test-step timeout is ambiguous and blocks retry until container/lifecycle evidence is inspected |
| LocalStack starts all services | Memory/startup spike or spy sees no selected services | Require non-empty normalized tuple and exactly one `with_services(*services)` call | Revert Task 3; no package metadata or docs should claim LocalStack support |
| Optional dependencies leak into base import | base-only smoke imports boto3/Psycopg or metadata adds runtime client | Lazy provider imports and extras/test-group isolation | Return to Task 4 metadata tests and regenerate `uv.lock` |
| Credentials or PostgreSQL URLs enter diagnostics | secret marker appears in repr, error, traceback, or docs | `repr=False`, `from None`, synthetic credentials, explicit redaction tests | Block Task 6 and return to Task 2/3 failure tests |
| Environment sync removes unrelated workspace extras | collection errors after package-focused sync | Use the exact sync ladder and restore `--all-packages --all-extras` before full tests | Treat as environment drift, resync, and rerun the same gate |

### Task 1: Extract the compatible shared contract without refactoring Redis

**Complexity:** Medium

**Depends on:** Approved spec commit `86e7d0a`

**Write scope:**

- Create: `packages/bluetape-testcontainers/src/bluetape/testcontainers/_support.py`
- Modify: `packages/bluetape-testcontainers/src/bluetape/testcontainers/redis.py`
- Modify: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_redis_server.py`

**Required skills:** `test-driven-development`, `bluetape-py-patterns`

- [ ] **Step 1: Add failing compatibility and validation tests**

Append these tests to `test_redis_server.py`:

```python
from bluetape.testcontainers import StartFailureKind, TestcontainerStartError
from bluetape.testcontainers.redis import (
    StartFailureKind as RedisStartFailureKind,
)
from bluetape.testcontainers.redis import (
    TestcontainerStartError as RedisTestcontainerStartError,
)


def test_shared_error_move_preserves_redis_identity_and_message() -> None:
    error = TestcontainerStartError(StartFailureKind.RUNTIME_UNAVAILABLE, "redis:8")

    assert RedisStartFailureKind is StartFailureKind
    assert RedisTestcontainerStartError is TestcontainerStartError
    assert str(error) == (
        "Redis test container start failed "
        "(runtime-unavailable, image=redis:8)"
    )


@pytest.mark.parametrize(
    "image",
    [
        "https://registry.example/redis:8",
        "user:secret@registry.example/redis:8",
        "user:secret@registry.example/redis@sha256:" + "a" * 64,
    ],
)
def test_rejects_uri_or_credential_bearing_image_without_echo(image: str) -> None:
    with pytest.raises(ValueError) as raised:
        RedisServer(image=image)

    assert image not in str(raised.value)


def test_accepts_complete_sha256_image_digest() -> None:
    server = RedisServer(image="redis@sha256:" + "a" * 64)

    assert server.running is False
```

- [ ] **Step 2: Run the focused tests and observe the missing shared module behavior**

Run:

```bash
uv run pytest \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_redis_server.py \
  -q
```

Expected: the new image-validation cases fail before extraction; all existing Redis tests remain collected.

- [ ] **Step 3: Create the complete shared helper module**

Create `_support.py`:

```python
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
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in image
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
```

- [ ] **Step 4: Replace Redis-owned shared definitions with imports and preserve aliases**

In `redis.py`, keep `_PULL_SCRIPT`, `_new_container`, `_start_without_reaper`, `_pull_image`, `_run_bounded_pull`, `_connection_url`, and `RedisServer` in place. Replace the moved imports/definitions with:

```python
from bluetape.testcontainers._support import (
    _ImagePullError,
    _ServerState,
    _StartPhase,
    TestcontainerStartError,
    _failure_kind,
    _stop_after_failure,
    _validated_image,
    _validated_timeout,
)
```

Update the two cleanup calls without changing the Redis public text:

```python
cleanup_succeeded = _stop_after_failure(container, error, "Redis")
```

Keep the current `__all__` list and all Redis methods unchanged.

- [ ] **Step 5: Run the compatibility ladder**

Run:

```bash
uv run pytest \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_redis_server.py \
  -q
uv run pytest -m testcontainers \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_redis_server_integration.py \
  -q
uv run ruff check packages/bluetape-testcontainers
uv run ruff format --check packages/bluetape-testcontainers
```

Expected: all existing Redis unit and integration tests pass; the new identity and image-safety guards pass; Ruff reports no violations. If Docker is unavailable, record the exact integration blocker and do not weaken the test.

- [ ] **Step 6: Commit the shared-contract extraction**

```bash
git add packages/bluetape-testcontainers/src packages/bluetape-testcontainers/tests
git commit -m "Preserve Redis while sharing fixture error contracts" \
  -m "Constraint: New service adapters need common error identity without a generic lifecycle base." \
  -m "Rejected: Refactor Redis into shared server inheritance | It broadens issue #15 and risks delivered behavior." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Directive: Keep lifecycle state in each adapter and shared helpers pure." \
  -m "Tested: Redis unit and serial integration tests; Ruff check and format" \
  -m "Not-tested: PostgreSQL and LocalStack adapters are introduced in later tasks"
```

**Rollback:** Revert this commit if any Redis name, message, lifecycle, or integration assertion changes. Do not continue to Task 2 on a compatibility failure.

### Task 2: Add the PostgreSQL 18 wrapper with driver-neutral details

**Complexity:** High

**Depends on:** Task 1

**Write scope:**

- Create: `packages/bluetape-testcontainers/src/bluetape/testcontainers/postgres.py`
- Create: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_postgres_server.py`
- Modify: `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`

**Required skills:** `test-driven-development`, `bluetape-py-patterns`

- [ ] **Step 1: Write failing PostgreSQL details, validation, and lifecycle tests**

Create `test_postgres_server.py` with provider fakes and these required cases:

```python
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

import bluetape.testcontainers.postgres as postgres_module
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

    def with_kwargs(self, **kwargs: object) -> "FakePostgresContainer":
        self.kwargs_calls.append(kwargs)
        return self

    def with_bind_ports(self, container_port: int, binding: object) -> "FakePostgresContainer":
        self.bindings.append((container_port, binding))
        return self

    def start(self) -> "FakePostgresContainer":
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
    details = PostgresConnectionDetails(
        host="::1",
        port=45432,
        database="db/name",
        username="user@example.com",
        password="secret marker",
    )

    assert details.url == (
        "postgresql://user%40example.com:secret%20marker@[::1]:45432/db%2Fname"
    )
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
    assert container.kwargs_calls == [
        {"labels": {"com.bluetape.testcontainers.postgres": "true"}}
    ]
    assert container.bindings == [(5432, ("127.0.0.1", None))]
```

Add these remaining boundary and failure tests to the same file:

```python
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
```

- [ ] **Step 2: Run the PostgreSQL unit file and observe missing exports**

Run:

```bash
uv run pytest \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_postgres_server.py \
  -q
```

Expected: collection fails because `postgres.py` and its public exports do not exist.

- [ ] **Step 3: Implement the complete PostgreSQL adapter**

Create `postgres.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Protocol, Self
from urllib.parse import quote

from bluetape.testcontainers._support import (
    _ServerState,
    _StartPhase,
    TestcontainerStartError,
    _bind_loopback,
    _failure_kind,
    _published_on_loopback,
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
```

- [ ] **Step 4: Export the PostgreSQL family additively**

Add this import and these names to `bluetape.testcontainers.__all__` without changing existing Redis order or identities:

```python
from bluetape.testcontainers.postgres import (
    DEFAULT_POSTGRES_IMAGE,
    PostgresConnectionDetails,
    PostgresServer,
)
```

```python
"DEFAULT_POSTGRES_IMAGE",
"PostgresConnectionDetails",
"PostgresServer",
```

- [ ] **Step 5: Run unit tests and correct only contract mismatches**

Run:

```bash
uv run pytest \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_postgres_server.py \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_redis_server.py \
  -q
uv run ruff check packages/bluetape-testcontainers
uv run ruff format --check packages/bluetape-testcontainers
```

Expected: PostgreSQL and Redis unit files pass; no provider class is publicly exported; Ruff is clean.

- [ ] **Step 6: Commit the PostgreSQL contract**

```bash
git add packages/bluetape-testcontainers/src packages/bluetape-testcontainers/tests
git commit -m "Provide caller-owned PostgreSQL test lifecycles" \
  -m "Constraint: Downstream SQL work needs PostgreSQL 18 coordinates without engine or transaction ownership." \
  -m "Rejected: Expose PostgresContainer | It would leak provider defaults and mutable lifecycle state." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Directive: Keep URLs driver-neutral by default and published ports loopback-only." \
  -m "Tested: PostgreSQL and Redis unit tests; Ruff check and format" \
  -m "Not-tested: Real PostgreSQL query and container removal follow in the serial integration task"
```

**Rollback:** Revert Task 2 if the provider cannot honor loopback dynamic binding or if URL behavior requires a different public signature; return to the written-spec gate before broadening the API.

### Task 3: Add the lazy LocalStack wrapper with explicit service ownership

**Complexity:** High

**Depends on:** Tasks 1-2

**Write scope:**

- Create: `packages/bluetape-testcontainers/src/bluetape/testcontainers/localstack.py`
- Create: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_localstack_server.py`
- Modify: `packages/bluetape-testcontainers/src/bluetape/testcontainers/__init__.py`

**Required skills:** `test-driven-development`, `bluetape-py-patterns`

- [ ] **Step 1: Write failing LocalStack validation, dependency, and lifecycle tests**

Create `test_localstack_server.py` with these exact anchors:

```python
from __future__ import annotations

import builtins
import traceback
from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

import bluetape.testcontainers.localstack as localstack_module
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

    def with_services(self, *services: str) -> "FakeLocalStackContainer":
        self.services_calls.append(services)
        return self

    def with_bind_ports(self, container_port: int, binding: object) -> "FakeLocalStackContainer":
        self.bindings.append((container_port, binding))
        return self

    def with_kwargs(self, **kwargs: object) -> "FakeLocalStackContainer":
        self.kwargs_calls.append(kwargs)
        return self

    def start(self, timeout: float = 60.0) -> "FakeLocalStackContainer":
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
```

Add these remaining boundary and failure tests to the same file:

```python
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
```

- [ ] **Step 2: Run the LocalStack unit file and observe missing module/exports**

Run:

```bash
uv run pytest \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_localstack_server.py \
  -q
```

Expected: collection fails because `localstack.py` and its exports do not exist. The base module import must not install or import boto3 to reach this failure.

- [ ] **Step 3: Implement the complete LocalStack adapter**

Create `localstack.py`:

```python
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Protocol, Self

from bluetape.testcontainers._support import (
    _DependencyMissingError,
    _ServerState,
    _StartPhase,
    TestcontainerStartError,
    _bind_loopback,
    _failure_kind,
    _published_on_loopback,
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
```

- [ ] **Step 4: Export the LocalStack family without eager provider imports**

Add to the package root:

```python
from bluetape.testcontainers.localstack import (
    DEFAULT_LOCALSTACK_IMAGE,
    LocalStackConnectionDetails,
    LocalStackServer,
)
```

Add the three names to `__all__`, then add this subprocess test to `test_packaging.py`:

```python
def test_base_import_does_not_load_optional_providers() -> None:
    script = """
import importlib.abc
import sys

blocked = {"boto3", "psycopg", "sqlalchemy", "testcontainers.localstack", "testcontainers.postgres"}

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked or any(fullname.startswith(name + ".") for name in blocked):
            raise AssertionError(f"optional provider imported: {fullname}")
        return None

sys.meta_path.insert(0, Blocker())
import bluetape.testcontainers as tc
for name in tc.__all__:
    getattr(tc, name)
print("base-import-ok")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "base-import-ok"
```

Add `import sys` to the existing import block in `test_packaging.py`.

- [ ] **Step 5: Run all Docker-free wrapper tests**

Run:

```bash
uv run pytest -m "not testcontainers" packages/bluetape-testcontainers -q
uv run ruff check packages/bluetape-testcontainers
uv run ruff format --check packages/bluetape-testcontainers
```

Expected: all package unit/import tests pass without Docker access; LocalStack selected-service and missing-boto3 paths are deterministic; Ruff is clean.

- [ ] **Step 6: Commit the LocalStack contract**

```bash
git add packages/bluetape-testcontainers/src packages/bluetape-testcontainers/tests
git commit -m "Constrain LocalStack fixtures to caller-selected services" \
  -m "Constraint: AWS-compatible tests need stable endpoints without real credential or client ownership." \
  -m "Rejected: Default all LocalStack services | It increases startup cost and hides resource scope." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Directive: Keep provider loading lazy and ambient AWS credentials outside returned details." \
  -m "Tested: Docker-free testcontainers package tests; Ruff check and format" \
  -m "Not-tested: Real LocalStack S3 behavior follows after dependency locking"
```

**Rollback:** Revert Task 3 if base import requires boto3, service selection is not forwarded exactly once, or provider errors expose environment/credential data.

### Task 4: Lock extras, integration clients, and wheel isolation

**Complexity:** Medium

**Depends on:** Tasks 1-3

**Write scope:**

- Modify: `packages/bluetape-testcontainers/pyproject.toml`
- Modify: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_packaging.py`
- Modify: `uv.lock`

**Required skills:** `test-driven-development`, `bluetape-py-patterns`

- [ ] **Step 1: Write failing extras and test-group metadata tests**

Extend `test_packaging.py` with a document loader and these assertions:

```python
def load_document(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_wrapper_extras_and_test_clients_are_isolated() -> None:
    document = load_document(ROOT / "packages/bluetape-testcontainers/pyproject.toml")
    project = document["project"]
    extras = project["optional-dependencies"]
    test_group = document["dependency-groups"]["test"]

    assert project["dependencies"] == ["testcontainers>=4.14.2,<4.15"]
    assert extras == {
        "postgres": ["testcontainers[postgres]>=4.14.2,<4.15"],
        "aws": ["testcontainers[localstack]>=4.14.2,<4.15"],
        "all": [
            "testcontainers[postgres]>=4.14.2,<4.15",
            "testcontainers[localstack]>=4.14.2,<4.15",
        ],
    }
    assert test_group == [
        "boto3>=1,<2",
        "psycopg[binary]>=3.2,<4",
        "pytest>=8.4.0",
    ]


def test_root_meta_extra_stays_base_only() -> None:
    project = load_project(ROOT / "packages/bluetape/pyproject.toml")

    assert project["optional-dependencies"]["testcontainers"] == [
        "bluetape-testcontainers==0.1.0"
    ]
    assert "[aws]" not in project["optional-dependencies"]["testcontainers"][0]
    assert "[postgres]" not in project["optional-dependencies"]["testcontainers"][0]
```

Extend the wheel metadata test with:

```python
assert "Provides-Extra: postgres\n" in metadata
assert "Provides-Extra: aws\n" in metadata
assert "Provides-Extra: all\n" in metadata
assert "boto3" not in metadata.split("Provides-Extra:", 1)[0]
assert "psycopg" not in metadata.split("Provides-Extra:", 1)[0]
```

- [ ] **Step 2: Run packaging tests and observe the missing extras/group failure**

Run:

```bash
uv run pytest \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_packaging.py \
  -q
```

Expected: the new TOML assertions fail because the extras and package `test` group are absent.

- [ ] **Step 3: Add the exact focused package metadata**

Append to `packages/bluetape-testcontainers/pyproject.toml`:

```toml
[project.optional-dependencies]
postgres = ["testcontainers[postgres]>=4.14.2,<4.15"]
aws = ["testcontainers[localstack]>=4.14.2,<4.15"]
all = [
    "testcontainers[postgres]>=4.14.2,<4.15",
    "testcontainers[localstack]>=4.14.2,<4.15",
]

[dependency-groups]
test = [
    "boto3>=1,<2",
    "psycopg[binary]>=3.2,<4",
    "pytest>=8.4.0",
]
```

Do not change `packages/bluetape/pyproject.toml`.

- [ ] **Step 4: Regenerate the lock and run package tests in the authoritative environment**

Run:

```bash
uv lock
uv sync --package bluetape-testcontainers --extra all --group test \
  --python 3.13.14 --locked
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m "not testcontainers" packages/bluetape-testcontainers -q
```

Expected: the lock records boto3/Psycopg and the focused Docker-free package suite passes.

- [ ] **Step 5: Build and smoke the base and extra wheel shapes in isolated environments**

Run:

```bash
rm -rf dist/issue-15
uv build --package bluetape-testcontainers --wheel --out-dir dist/issue-15
wheel=$(find dist/issue-15 -name 'bluetape_testcontainers-*.whl' -print -quit)
tmp=$(mktemp -d)

uv venv --python 3.13.14 "$tmp/base"
uv pip install --python "$tmp/base/bin/python" "$wheel"
"$tmp/base/bin/python" -I -c \
  'import importlib.util; import bluetape.testcontainers as tc; assert importlib.util.find_spec("boto3") is None; assert tc.DEFAULT_POSTGRES_IMAGE == "postgres:18-alpine"; print("base-import-ok")'

uv venv --python 3.13.14 "$tmp/postgres"
uv pip install --python "$tmp/postgres/bin/python" "${wheel}[postgres]"
"$tmp/postgres/bin/python" -I -c \
  'import bluetape.testcontainers as tc; assert tc.PostgresServer'

uv venv --python 3.13.14 "$tmp/aws"
uv pip install --python "$tmp/aws/bin/python" "${wheel}[aws]"
"$tmp/aws/bin/python" -I -c \
  'import boto3; import bluetape.testcontainers as tc; assert tc.LocalStackServer'

uv venv --python 3.13.14 "$tmp/all"
uv pip install --python "$tmp/all/bin/python" "${wheel}[all]"
"$tmp/all/bin/python" -I -c \
  'import boto3; import bluetape.testcontainers as tc; assert tc.PostgresServer and tc.LocalStackServer'

rm -rf "$tmp" dist/issue-15
```

Expected: each command exits zero; only the focused extras install provider clients; no temporary environment or build directory remains.

- [ ] **Step 6: Commit the dependency boundary**

```bash
git add packages/bluetape-testcontainers/pyproject.toml \
  packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_packaging.py \
  uv.lock
git commit -m "Keep fixture providers behind focused extras" \
  -m "Constraint: The root meta extra remains base-only while real integration tests need Psycopg and boto3." \
  -m "Rejected: Add clients to runtime dependencies | It leaks provider SDKs into Redis-only callers." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Directive: Update wheel isolation and lock evidence whenever provider extras change." \
  -m "Tested: focused package tests; base/postgres/aws/all isolated wheel imports" \
  -m "Not-tested: real service round trips follow in the serial integration task"
```

**Rollback:** Revert metadata and `uv.lock` together. Resync the full workspace before diagnosing any collection failure caused by the focused package sync.

### Task 5: Prove real PostgreSQL and LocalStack behavior and serialize CI

**Complexity:** High

**Depends on:** Task 4 and a reachable Docker-compatible runtime

**Write scope:**

- Create: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_postgres_server_integration.py`
- Create: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/test_localstack_server_integration.py`
- Modify: `packages/bluetape-testcontainers/tests/bluetape_testcontainers_tests/_support.py`
- Modify: `.github/workflows/ci.yml`

**Required skills:** `test-driven-development`, `bluetape-py-patterns`

- [ ] **Step 1: Add reusable Docker assertion helpers**

Add `Any` and `docker` to the existing import block in the test `_support.py`,
then append the helper functions below. Keep imports at the top so Ruff's E402
gate remains meaningful:

```python
from typing import Any

import docker


def published_host_ips(provider: Any, port: int) -> set[str]:
    wrapped = provider.get_wrapped_container()
    wrapped.reload()
    bindings = wrapped.attrs["NetworkSettings"]["Ports"][f"{port}/tcp"]
    return {binding["HostIp"] for binding in bindings}


def assert_container_removed(container_id: str) -> None:
    client = docker.from_env()
    try:
        assert client.containers.list(all=True, filters={"id": container_id}) == []
    finally:
        client.close()
```

The integration tests below may inspect `server._container` only as test-only
evidence for Docker binding and wrapper-owned service cleanup. No public API or
documentation may expose that provider reference, and Ryuk is not part of this
cleanup assertion.

- [ ] **Step 2: Write the real PostgreSQL 18 integration test**

Create `test_postgres_server_integration.py`:

```python
import psycopg
import pytest

from bluetape.testcontainers import DEFAULT_POSTGRES_IMAGE, PostgresServer

from ._support import assert_container_removed, published_host_ips

pytestmark = pytest.mark.testcontainers


def test_postgres_18_query_loopback_binding_and_cleanup() -> None:
    server = PostgresServer()
    with server:
        provider = server._container
        assert provider is not None
        wrapped = provider.get_wrapped_container()
        container_id = wrapped.id

        assert DEFAULT_POSTGRES_IMAGE == "postgres:18-alpine"
        host_ips = published_host_ips(provider, 5432)
        assert host_ips
        assert host_ips <= {"127.0.0.1", "::1"}
        with psycopg.connect(server.details.url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select current_setting('server_version_num')")
                version = int(cursor.fetchone()[0])
        assert version >= 180000
        assert server.details.connection_url(driver="psycopg").startswith(
            "postgresql+psycopg://"
        )

    assert_container_removed(container_id)
```

- [ ] **Step 3: Write the real selected-service LocalStack S3 integration test**

Create `test_localstack_server_integration.py`:

```python
import boto3
import pytest

from bluetape.testcontainers import DEFAULT_LOCALSTACK_IMAGE, LocalStackServer

from ._support import assert_container_removed, published_host_ips

pytestmark = pytest.mark.testcontainers


def test_localstack_s3_round_trip_loopback_binding_and_cleanup() -> None:
    server = LocalStackServer(services=("s3",))
    with server:
        provider = server._container
        assert provider is not None
        wrapped = provider.get_wrapped_container()
        container_id = wrapped.id
        details = server.details

        assert DEFAULT_LOCALSTACK_IMAGE == "localstack/localstack:4.14.0"
        assert details.services == ("s3",)
        host_ips = published_host_ips(provider, 4566)
        assert host_ips
        assert host_ips <= {"127.0.0.1", "::1"}
        client = boto3.client(
            "s3",
            endpoint_url=details.endpoint_url,
            region_name=details.region_name,
            aws_access_key_id=details.access_key_id,
            aws_secret_access_key=details.secret_access_key,
        )
        try:
            client.create_bucket(Bucket="bluetape-issue-15")
            buckets = {bucket["Name"] for bucket in client.list_buckets()["Buckets"]}
            assert "bluetape-issue-15" in buckets
        finally:
            client.close()

    assert_container_removed(container_id)
```

- [ ] **Step 4: Run Docker preflight and the complete serial service suite**

Run sequentially:

```bash
docker info
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m testcontainers packages/bluetape-testcontainers -q
```

Expected: Redis, PostgreSQL, and LocalStack integration tests pass in one process; service containers are removed; provider-owned Ryuk may remain process-scoped and is not counted as a wrapper leak.

- [ ] **Step 5: Replace the Redis-only CI job with the exact bounded service job**

Rename `testcontainers-redis` to `testcontainers-services`, add the job-level
timeout directly beside the existing runner declaration, and replace its
sync/test steps with:

```yaml
  testcontainers-services:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Sync all fixture providers and integration clients
        run: >-
          uv sync --package bluetape-testcontainers --extra all --group test
          --python 3.13.14 --locked

      - name: Verify Docker runtime
        run: docker info

      - name: Test service wrappers serially
        run: >-
          uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest
          -m testcontainers packages/bluetape-testcontainers -q
```

Keep the existing pinned action SHAs and do not add matrices, retries, parallel workers, or semantic-failure skips.

- [ ] **Step 6: Validate the workflow and commit real-service proof**

Run:

```bash
actionlint
rg -n -U 'testcontainers-services:\n(?:.*\n){0,4}\s+timeout-minutes: 30' .github/workflows/ci.yml
git diff --check
```

Expected: all commands exit zero and the service job has an explicit 30-minute
whole-job cap. This cap bounds Docker client creation, image acquisition,
provider startup, tests, and cleanup without redefining either provider's
public readiness-timeout semantics. A failed `docker info` step is an
infrastructure failure. A timeout after preflight, during the service test step,
is ambiguous and blocks automatic retry until service-container state, wrapper
lifecycle, and cleanup evidence are inspected.

```bash
git add .github/workflows/ci.yml packages/bluetape-testcontainers/tests
git commit -m "Prove fixture families against real services" \
  -m "Constraint: Docker-backed service tests must be serialized and distinguish runtime preflight from semantic failures." \
  -m "Rejected: Parallel service jobs | They amplify image, Ryuk, and cleanup contention." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Directive: Keep service-container removal assertions scoped separately from provider-owned Ryuk." \
  -m "Tested: Docker preflight; serial Redis/PostgreSQL/LocalStack tests; actionlint; diff check" \
  -m "Not-tested: GitHub-hosted runner execution remains pending CI"
```

**Rollback:** If either official provider cannot produce a loopback binding or clean service removal, revert its adapter and integration test together; do not relax the security/cleanup acceptance criteria.

### Task 6: Document adoption, compatibility, operations, and reusable lessons

**Complexity:** Medium

**Depends on:** Tasks 1-5 green

**Write scope:**

- Modify: `packages/bluetape-testcontainers/README.md`
- Modify: `packages/bluetape-testcontainers/README.ko.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`
- Create: `docs/lessons/2026-07-17-issue-15-testcontainers-fixture-families.md`

**Required skills:** `bluetape-py-patterns`, `bluetape-writer`

- [ ] **Step 1: Replace package README install, service, and fixture sections in both locales**

The English package README must retain the current PyPI publication hold and
contain this exact install matrix and ownership table. Label the matrix as the
intended post-publication install shape, not as a currently published artifact:

```markdown
## Install

PyPI publication is currently on hold. The commands below are the intended
post-publication install shapes. For current source-workspace validation, use
`uv sync --package bluetape-testcontainers --extra all --group test --python
3.13.14 --locked` from this repository.

| Need | Command |
| --- | --- |
| Redis/base wrapper | `pip install "bluetape[testcontainers]"` or `pip install bluetape-testcontainers` |
| PostgreSQL | `pip install "bluetape-testcontainers[postgres]"` |
| LocalStack | `pip install "bluetape-testcontainers[aws]"` |
| PostgreSQL and LocalStack | `pip install "bluetape-testcontainers[all]"` |

The root `bluetape[testcontainers]` extra remains base-only. PostgreSQL drivers,
boto3, SQLAlchemy, and production clients are not installed by that root extra.

## Supported services

| Wrapper | Default image | Caller owns |
| --- | --- | --- |
| `RedisServer` | `redis:8` | key/data reset and client lifecycle |
| `PostgresServer` | `postgres:18-alpine` | connections, pools, schema, transactions, migrations, and seed data |
| `LocalStackServer` | `localstack/localstack:4.14.0` | selected services, SDK clients, and AWS resource cleanup |
```

Add copy-paste function-scoped fixtures:

```python
import boto3
import psycopg
import pytest

from bluetape.testcontainers import LocalStackServer, PostgresServer


@pytest.fixture
def postgres_connection():
    with PostgresServer() as server:
        with psycopg.connect(server.details.url) as connection:
            yield connection


@pytest.fixture
def s3_client():
    with LocalStackServer(services=("s3",)) as server:
        details = server.details
        client = boto3.client(
            "s3",
            endpoint_url=details.endpoint_url,
            region_name=details.region_name,
            aws_access_key_id=details.access_key_id,
            aws_secret_access_key=details.secret_access_key,
        )
        try:
            yield client
        finally:
            client.close()
```

Translate both complete fixture examples and the install/ownership tables
source-equivalently into `README.ko.md`; do not replace executable code with a
summary or a link back to English.

State immediately after the example that callers delete database/AWS resources between tests, secret-bearing PostgreSQL URLs must not be logged, and wider fixture scopes require explicit reset policy.
Also state that each server is synchronous, single-use, not thread-safe, and
must belong to exactly one fixture or caller. The CI capability proof covers S3;
other syntactically valid LocalStack service names are forwarded to the pinned
provider/image and must be capability-tested by the caller before adoption.

- [ ] **Step 2: Add exact error, Ryuk, and Redis-upgrade guidance in both package READMEs**

Add this English error table and translate it source-equivalently into Korean:

```markdown
| State/category | Caller action |
| --- | --- |
| `dependency-missing` | Install `bluetape-testcontainers[aws]` and create a new wrapper. |
| `runtime-unavailable` | Run `docker info`; repair runtime access before retrying. |
| `image-pull` | Pull the trusted pinned image explicitly and create a new wrapper. |
| `readiness-timeout` | Inspect runtime capacity and the selected service set; do not log raw provider output. |
| `wrapper-failure` | Treat it as a contract/configuration failure and inspect sanitized inputs. |
| cleanup pending | Call `close()` again on the same wrapper until cleanup succeeds. |
```

Add this copy-paste stable-kind handling example to both locales, translating
only prose and caller messages. It must never print or interpolate the caught
exception, a connection URL, credentials, or a rejected image value:

```python
from bluetape.testcontainers import (
    LocalStackServer,
    StartFailureKind,
    TestcontainerStartError,
)

server = LocalStackServer(services=("s3",))
try:
    with server:
        pass  # create and close caller-owned SDK clients inside this block
except TestcontainerStartError as error:
    if error.kind is StartFailureKind.DEPENDENCY_MISSING:
        raise RuntimeError(
            'Install "bluetape-testcontainers[aws]" before running this test.'
        ) from None
    if error.kind is StartFailureKind.RUNTIME_UNAVAILABLE:
        raise RuntimeError("Verify Docker access with docker info.") from None
    raise RuntimeError(
        f"LocalStack test setup failed in category: {error.kind.value}"
    ) from None
```

Add this timeout-ownership table source-equivalently to both locales:

```markdown
| Wrapper | Timeout contract |
| --- | --- |
| `RedisServer` | `startup_timeout` bounds individual image/start/readiness operations; it is not one total deadline. |
| `PostgresServer` | No wrapper timeout is advertised because Testcontainers 4.14.2 exposes no public PostgreSQL readiness-timeout input. |
| `LocalStackServer` | `startup_timeout` is passed only to provider readiness-log waiting; Docker client creation, image acquisition, and container creation are outside it. |
| CI service job | `timeout-minutes: 30` is an outer workflow safety cap, not a wrapper API guarantee. |
```

The docs must also state:

- PostgreSQL and LocalStack use provider-owned Ryuk when Testcontainers enables it; Ryuk may persist process-wide, while each wrapper removes only its service container.
- `docker info` is the preflight; explicit trusted pulls are `docker pull postgres:18-alpine` and `docker pull localstack/localstack:4.14.0`.
- Published service ports are dynamic and loopback-only; remote/shared Docker daemons that cannot prove this contract are rejected.
- Managed PostgreSQL and LocalStack service containers carry, respectively,
  `com.bluetape.testcontainers.postgres=true` and
  `com.bluetape.testcontainers.localstack=true`. After an abnormal process exit,
  inspect with `docker ps -a --filter
  label=com.bluetape.testcontainers.postgres=true` or `docker ps -a --filter
  label=com.bluetape.testcontainers.localstack=true`, confirm the image and
  container identity, and remove only that confirmed service container. Never
  remove Ryuk through these service-label procedures.
- Redis-only callers need no code or dependency change; `RedisServer`, its error text, and root `bluetape[testcontainers]` behavior remain unchanged.

- [ ] **Step 3: Update root English/Korean status and commands in parity**

Change the root package-table description from Redis-only to:

```markdown
Ecosystem-owned Redis 8, PostgreSQL 18, and selected-service LocalStack test-server lifecycles and connection details.
```

Use this Korean equivalent:

```markdown
생태계가 관리하는 Redis 8, PostgreSQL 18, 선택 서비스 LocalStack 테스트 서버 수명주기와 연결 정보.
```

Keep the root installation command base-only, add focused package-extra commands next to it, and retain the one serial command:

```bash
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m testcontainers packages/bluetape-testcontainers -q
```

- [ ] **Step 4: Record delivery in WIP and CHANGELOG**

Replace the Redis-only `WIP.md` package status with:

```markdown
- `bluetape-testcontainers`: ecosystem-owned Redis 8, PostgreSQL 18, and
  caller-selected LocalStack test server wrappers with dynamic loopback ports,
  immutable details, explicit fixture ownership, and serial Docker verification.
```

Add under the unreleased `CHANGELOG.md` feature section:

```markdown
- Extend `bluetape-testcontainers` with opt-in PostgreSQL 18 and selected-service
  LocalStack wrappers, focused `postgres`/`aws`/`all` extras, lazy provider
  imports, loopback-only dynamic ports, and deterministic cleanup.
```

- [ ] **Step 5: Create the mandatory Type A lesson**

Create `docs/lessons/2026-07-17-issue-15-testcontainers-fixture-families.md` with this evidence-backed content after Tasks 1-5 pass:

```markdown
# Issue #15 Testcontainers Fixture Families Lessons

## Context and decision

Issue #15 extended the existing Redis-only fixture distribution without turning
it into a generic container framework. PostgreSQL and LocalStack use their
official Testcontainers modules, while Bluetape owns a smaller immutable details,
validation, error, loopback-binding, and cleanup contract.

## Reusable findings

### Advertise only provider-supported timeouts

PostgreSQL provider readiness has no public timeout input in Testcontainers
4.14.2, so the wrapper exposes no false total-deadline promise. LocalStack's
timeout is passed only to its public readiness-log wait; image pull and container
creation remain provider-owned phases.

### Optional providers must be lazy at the public import boundary

`testcontainers.localstack` imports boto3 at module import. Importing the
Bluetape package root therefore loads only the thin adapter module; the official
provider loads inside `start()`, where missing boto3 becomes a sanitized
`dependency-missing` category with the focused install command.

### Selected services and loopback bindings are security and capacity contracts

LocalStack's provider default starts all services, and Docker's ordinary dynamic
publishing can bind wildcard interfaces. The wrappers forward the normalized
service tuple exactly once, request an ephemeral loopback binding, and verify the
actual runtime binding before exposing connection details.

### Provider-owned support containers are not wrapper-owned resources

The adapters do not mutate global Ryuk configuration. Verification distinguishes
the wrapper-owned PostgreSQL/LocalStack service container, which must be removed,
from provider-owned process-wide Ryuk, which may remain until process shutdown.

## Verification evidence

- Docker-free tests cover validation, lifecycle, failure redaction, cleanup
  retry, optional-import isolation, selected services, ambient credentials, and
  URL encoding.
- Serial Docker tests cover Redis, a real PostgreSQL 18 query, a LocalStack S3
  round trip, loopback bindings, and service-container removal.
- Focused wheel smokes prove base, PostgreSQL, AWS, and all-provider install
  shapes without changing the root meta extra.
- The verifier artifact records full pytest, Ruff, build, actionlint, diff, and
  exact-head review evidence.

## Future guard

On provider upgrades, re-check constructor imports, readiness timeout ownership,
port-binding conversion, selected-service forwarding, Ryuk behavior, error
classification, and wheel extras before changing the pinned compatibility line.
```

- [ ] **Step 6: Validate locale alignment and commit documentation/lessons**

Run:

```bash
for anchor in \
  'PostgresServer' \
  'LocalStackServer' \
  'bluetape-testcontainers[postgres]' \
  'bluetape-testcontainers[aws]' \
  'postgres_connection' \
  's3_client' \
  'dependency-missing' \
  'readiness-timeout' \
  'timeout-minutes: 30' \
  'com.bluetape.testcontainers.postgres=true' \
  'com.bluetape.testcontainers.localstack=true'; do
  rg -q -F "$anchor" packages/bluetape-testcontainers/README.md
  rg -q -F "$anchor" packages/bluetape-testcontainers/README.ko.md
done
rg -n "PostgresServer|LocalStackServer|postgres:18-alpine|localstack/localstack:4.14.0" \
  README.md README.ko.md WIP.md CHANGELOG.md
git diff --check
```

Expected: every shared executable anchor appears in both package locales, every
root status anchor appears where applicable, and diff hygiene passes. Then read
the English and Korean package sections side by side and record manual parity
for install availability, both fixtures, ownership/reset warnings, stable error
kinds, timeout scope, Ryuk/orphan cleanup, and Redis compatibility in the final
review artifact.

```bash
git add README.md README.ko.md WIP.md CHANGELOG.md \
  packages/bluetape-testcontainers/README.md \
  packages/bluetape-testcontainers/README.ko.md \
  docs/lessons/2026-07-17-issue-15-testcontainers-fixture-families.md
git commit -m "Make fixture ownership explicit for callers" \
  -m "Constraint: New provider families require install, cleanup, credential, and CI guidance in both locales." \
  -m "Rejected: Automatic pytest fixtures | They would silently choose scope and reset behavior." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Directive: Keep examples caller-owned and root testcontainers installation base-only." \
  -m "Tested: locale anchor scan; git diff --check" \
  -m "Not-tested: Documentation rendering is plain Markdown without a separate site build"
```

**Rollback:** Revert the documentation commit if it claims behavior not proven by Tasks 1-5; never keep future-tense provider claims in active package tables.

### Task 7: Run full verification, six-lens review, and create the exact-head PR

**Complexity:** High

**Depends on:** Tasks 1-6 committed

**Write scope:**

- Create: `docs/review/2026-07-17-issue-15-testcontainers-fixtures-code-review.md`
- Create: `docs/review/2026-07-17-issue-15-testcontainers-fixtures-verifier.md`
- Modify only files required to resolve review findings within the approved spec.

**Required skills:** `verification-before-completion`, `bluetape-py-patterns`, `bluetape-workflow`

- [ ] **Step 1: Restore and run the full local validation ladder**

Run in this exact order:

```bash
uv sync --package bluetape-testcontainers --extra all --group test \
  --python 3.13.14 --locked
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m "not testcontainers" packages/bluetape-testcontainers -q
docker info
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m testcontainers packages/bluetape-testcontainers -q

uv sync --all-packages --all-extras --python 3.13.14 --locked
uv run pytest -m "not observability_sdk"
uv sync --package bluetape-observability --group test --python 3.13.14 --locked
uv run pytest -m observability_sdk packages/bluetape-observability -q
uv sync --all-packages --all-extras --python 3.13.14 --locked

uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
rg -n -U 'testcontainers-services:\n(?:.*\n){0,4}\s+timeout-minutes: 30' .github/workflows/ci.yml
git diff --check
```

Expected: all commands exit zero. Record exact test/build counts and any Docker image digests in the verifier artifact. A failed command blocks progression; fix the cause and restart this ladder at the earliest affected sync/test boundary.

- [ ] **Step 2: Run six independent implemented-diff perspectives plus main integration**

Review `origin/develop...HEAD` against the approved spec and plan with these exact lenses:

1. Performance — service selection, provider startup cost, Ryuk scope, repeated work.
2. Stability — full lifecycle table, cleanup retry, interrupts, service-container leaks.
3. Security — loopback bindings, image input, secret/URL/credential redaction, ambient AWS isolation.
4. Operator/Ops — Docker preflight, serial CI, diagnostics, cleanup/runbook, rollback.
5. Developer/API — imports, typing, exact exports, extras, Redis compatibility, test seams.
6. Caller/User — install matrix, fixture examples, resource ownership, locale parity.

Each lane returns file:line evidence and P0/P1/P2/P3. Main integration resolves every P0/P1, records P2/P3 as fixed or explicitly deferred, reruns only affected lenses, and writes the code-review artifact with final `P0=0 P1=0`.

- [ ] **Step 3: Verify every spec and plan requirement and write the verifier artifact**

The verifier artifact must record:

```markdown
# Issue #15 Testcontainers Fixture Families Verifier

- Compared range: `origin/develop...HEAD`
- Approved spec: `docs/superpowers/specs/2026-07-17-issue-15-testcontainers-fixtures-design.md`
- Approved plan: `docs/superpowers/plans/2026-07-17-issue-15-testcontainers-fixtures-plan.md`
- Package boundary: base, `postgres`, `aws`, and `all` wheel shapes verified
- Runtime boundary: Redis, PostgreSQL, and LocalStack serial Docker paths verified
- Documentation: English/Korean package and root guidance aligned
- Review gate: P0=0 P1=0
- Known gaps: GitHub-hosted CI pending until PR checks run
```

Append exact command outputs/counts, acceptance-criterion traceability, changed files, image digests, and proof that no wrapper-owned service container remains.

- [ ] **Step 4: Commit review evidence and any bounded corrections**

Run the affected targeted tests after every correction, then rerun Step 1 in full. Commit only after final P0=0/P1=0:

```bash
git add docs/review packages/bluetape-testcontainers .github/workflows/ci.yml \
  README.md README.ko.md WIP.md CHANGELOG.md uv.lock
git commit -m "Converge fixture families on verified contracts" \
  -m "Constraint: Type A delivery requires exact spec, plan, test, packaging, documentation, and six-lens evidence." \
  -m "Rejected: Defer P1 findings to follow-up | Required lifecycle and security gaps block issue #15." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Directive: Re-run provider, wheel, and serial Docker gates on every compatibility upgrade." \
  -m "Tested: full issue #15 validation ladder and implemented-diff review P0=0/P1=0" \
  -m "Not-tested: GitHub-hosted CI remains pending PR execution"
```

- [ ] **Step 5: Prove exact head, push the authorized branch, and create the issue-linked PR**

Run:

```bash
repo-status
git log --oneline --decorate origin/develop..HEAD
git diff --check origin/develop...HEAD
git push -u origin feat/issue-15-testcontainers-fixtures
gh pr create \
  --repo bluetape4k/bluetape-py \
  --base develop \
  --head feat/issue-15-testcontainers-fixtures \
  --title "feat: add PostgreSQL and LocalStack fixture families" \
  --body 'Closes #15

Adds caller-owned PostgreSQL 18 and selected-service LocalStack wrappers while preserving the existing Redis contract and base-only meta extra.

Validation and six-lens review evidence are committed under docs/review.

## DoD Status

- [x] Approved spec and plan committed
- [x] Targeted, serial Docker, full workspace, Ruff, build, actionlint, and diff checks pass
- [x] English/Korean documentation and mandatory Type A lesson committed
- [x] Six implemented-diff perspectives and main integration report P0=0/P1=0
- [ ] GitHub CI and current review/thread state verified at exact PR head
- [ ] Fresh user merge approval obtained'
```

Expected: one open PR targeting `develop` from the exact local head. Do not enable auto-merge and do not merge.

- [ ] **Step 6: Verify exact-head CI/review state and stop for merge approval**

Run:

```bash
local_head=$(git rev-parse HEAD)
pr_json=$(gh pr view --repo bluetape4k/bluetape-py \
  --json number,url,baseRefName,headRefName,headRefOid,state,mergeStateStatus,reviewDecision,statusCheckRollup)
jq -e --arg head "$local_head" '
  .baseRefName == "develop" and
  .headRefName == "feat/issue-15-testcontainers-fixtures" and
  .headRefOid == $head and
  .state == "OPEN"
' <<<"$pr_json"

pr_number=$(jq -r '.number' <<<"$pr_json")
threads_json=$(gh api graphql \
  -f query='query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){pageInfo{hasNextPage} nodes{isResolved isOutdated comments(first:1){nodes{author{login}body url}}}}}}}' \
  -F owner=bluetape4k \
  -F name=bluetape-py \
  -F number="$pr_number")
jq -e '
  .data.repository.pullRequest.reviewThreads as $threads |
  ($threads.pageInfo.hasNextPage == false) and
  ([$threads.nodes[] |
    select(.isResolved == false and .isOutdated == false)] | length == 0)
' <<<"$threads_json"

ci-status
```

Expected: PR head OID equals local `HEAD`, required checks are green, the
exact-head GraphQL result contains zero unresolved non-outdated review threads,
and merge state is ready. More than 100 review threads is a blocking evidence
gap rather than permission to ignore pagination. Report the PR number, URL,
exact head, local validation, CI/review evidence, and `P0=0/P1=0`; then stop for
a fresh explicit merge approval.

**Rollback:** Before PR creation, revert the smallest failing task commit. After PR creation, push only reviewed correction commits and refresh exact-head evidence. Never merge, tag, release, publish, or delete branches/worktrees without the corresponding gate.

## Acceptance-Criterion Traceability

| Approved requirement | Implemented by | Proved by |
| --- | --- | --- |
| Redis API/lifecycle compatibility | Task 1 | Redis unit/integration suite and identity/message tests |
| Official PostgreSQL/LocalStack providers remain private | Tasks 2-3 | provider-spy tests, root `__all__`, base import smoke |
| LocalStack selected services exactly once | Task 3 | `services_calls == [("s3", "sqs")]` and real S3-only round trip |
| Immutable encoded/redacted details | Tasks 2-3 | URL/IPv6/reserved-character and repr/traceback tests |
| Dynamic loopback-only ports | Tasks 1-3, 5 | Docker SDK conversion seam, spy tests, runtime `HostIp` assertions |
| Ambient AWS isolation | Task 3 | sentinel environment test and synthetic returned details |
| Base import without clients | Tasks 3-4 | blocked-import subprocess and isolated base wheel environment |
| `postgres`/`aws`/`all` extras | Task 4 | TOML/metadata tests, lock, four isolated wheel smokes |
| Success/failure/boundary/lifecycle/cleanup paths | Tasks 1-5 | Docker-free matrices plus serial real-service tests |
| Wrapper-owned service identification and abnormal-exit cleanup | Tasks 2-3, 5-6 | label spy tests, service removal, and bilingual inspect-confirm-remove runbook |
| Provider-specific timeout ownership | Tasks 3, 5-6 | timeout spy, no PostgreSQL timeout, CI cap assertion, and bilingual timeout table |
| Reproducible CI and Docker preflight | Task 5 | actionlint, 30-minute job cap, and `testcontainers-services` job contract |
| English/Korean docs and examples | Task 6 | paired anchors, exact examples, diff check |
| Full validation, Type A review, lesson, exact-head PR | Tasks 6-7 | lesson, code review, verifier, CI metadata, and GraphQL review-thread evidence |

## Plan Self-Review Checklist

- Spec coverage: every acceptance criterion maps to a task and command above.
- Ordering: shared error identity precedes adapters; adapters precede extras; extras precede real-service tests; proven behavior precedes docs and PR.
- Shared-file hazards: Tasks 1-3 are sequential; no concurrent edit is permitted on `_support.py`, `__init__.py`, or package tests.
- Test families: success, invalid input, empty/boundary input, lifecycle, cleanup retry, control-flow interruption, provider failure, dependency absence, secret redaction, real backend capability, and packaging isolation are explicit.
- Documentation/release: both locale sets, WIP, CHANGELOG, mandatory lesson, workflow, and PR DoD are assigned; versions/tags/releases remain out of scope.
- Rollback: every external-provider, metadata, Docker, documentation, and PR stage has a named stop/revert point.
- Risk prediction: required because this work crosses external providers, Docker networking, credentials, and resource cleanup; risks and signals are assigned above.

## Implementation Hold

Commit this reviewed plan before Task 1. Implementation begins only after the
user approves this written plan. Plan approval authorizes local TDD execution and
the already-scoped PR creation to `develop`; merge remains a separate fresh gate.
