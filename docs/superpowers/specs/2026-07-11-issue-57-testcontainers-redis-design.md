# Issue #57 Bluetape Testcontainers Redis Wrapper Design

- Issue: [#57](https://github.com/bluetape4k/bluetape-py/issues/57)
- Parent: [#11](https://github.com/bluetape4k/bluetape-py/issues/11)
- Blocks: [#54](https://github.com/bluetape4k/bluetape-py/issues/54), [#55](https://github.com/bluetape4k/bluetape-py/issues/55)
- Date: 2026-07-11
- Work type: Type A - Full Feature

## Problem

`bluetape-py`의 Redis 통합 테스트가 Testcontainers Python API를 직접 사용하면 Docker image, readiness, 동적 port, connection detail, startup error, cleanup 규칙이 consumer package마다 반복된다. 공식 wrapper의 기본 image가 바뀌거나 테스트마다 서로 다른 Redis line을 선택하면 bluetape ecosystem의 호환성 증거도 분산된다.

#57은 production Redis provider와 분리된 test-only distribution에서 ecosystem-owned Redis server wrapper를 제공한다. #54와 #55는 이 wrapper만 사용하고 직접 `RedisContainer`를 생성하지 않는다.

## Evidence and Alternatives

### Ecosystem evidence

- `bluetape4k-projects/testing/testcontainers/.../RedisServer.kt`는 `redis:8`, dynamic port, `host`/`port`/`url`, explicit `start()`, reusable launcher를 한 경계에 둔다.
- `bluetape-go/testcontainers/redis`는 image, readiness, connection details, startup diagnostics, test cleanup을 consumer에서 제거한다.
- 현재 `bluetape-testing`은 pytest assertion/polling helper에 집중하며 infrastructure container dependency를 갖지 않는다.

### Alternatives

1. **새 `bluetape-testcontainers` distribution** — 채택. Redis wrapper를 먼저 제공하고 이후 다른 infrastructure wrapper가 필요할 때 같은 distribution에 독립 submodule로 추가한다.
2. **#54 test directory 안에 private helper 배치** — 거절. #55와 미래 Redis consumer가 image와 lifecycle을 다시 복제한다.
3. **`bluetape-testing`에 Testcontainers 추가** — 거절. 가벼운 pytest helper 설치에 Docker client dependency가 따라오고 package 책임이 섞인다.
4. **공식 `RedisContainer` 직접 사용** — 거절. ecosystem image authority와 공통 diagnostics/cleanup 계약을 제공하지 않는다.

## Package Boundary

새 distribution:

```text
packages/bluetape-testcontainers/
├── README.md
├── README.ko.md
├── pyproject.toml
├── src/bluetape/testcontainers/
│   ├── __init__.py
│   └── redis.py
└── tests/
    ├── test_redis_server.py
    ├── test_redis_server_integration.py
    └── test_packaging.py
```

계약:

- distribution: `bluetape-testcontainers==0.1.0`
- import: `bluetape.testcontainers`
- Python: `>=3.13`
- production dependency: `testcontainers>=4.14.2,<5`
- default Redis image: `redis:8`
- `bluetape` default dependency: 변경 없음 (`bluetape-core` only)
- `bluetape[testcontainers]`: explicit forwarding extra
- `bluetape[dev]`와 `bluetape[all]`: wrapper 포함
- `bluetape-testing`: dependency와 API 변경 없음

`uv.lock`은 실제 선택된 Testcontainers/Docker dependency version을 고정한다. Image는 dependency가 아니라 wrapper constant가 권위이며 consumer test에서 literal Redis image를 선언하지 않는다.

## Public API

```python
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Self

DEFAULT_REDIS_IMAGE = "redis:8"


@dataclass(frozen=True, slots=True)
class RedisConnectionDetails:
    host: str
    port: int
    url: str


class StartFailureKind(StrEnum):
    RUNTIME_UNAVAILABLE = "runtime-unavailable"
    IMAGE_PULL = "image-pull"
    READINESS_TIMEOUT = "readiness-timeout"
    WRAPPER_FAILURE = "wrapper-failure"


class TestcontainerStartError(RuntimeError):
    @property
    def kind(self) -> StartFailureKind: ...


class RedisServer:
    def __init__(
        self,
        *,
        image: str = DEFAULT_REDIS_IMAGE,
        startup_timeout: float = 30.0,
    ) -> None: ...

    @property
    def running(self) -> bool: ...
    @property
    def details(self) -> RedisConnectionDetails: ...
    @property
    def host(self) -> str: ...
    @property
    def port(self) -> int: ...
    @property
    def url(self) -> str: ...

    def start(self) -> Self: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
```

위 코드는 공개 signature 표기다. `...`는 미정 요구사항이 아니라 구현 생략이다.

`bluetape.testcontainers.__all__`은 다음만 노출한다.

- `DEFAULT_REDIS_IMAGE`
- `RedisConnectionDetails`
- `RedisServer`
- `StartFailureKind`
- `TestcontainerStartError`

Testcontainers Python의 container 객체와 Docker client는 공개 API로 노출하지 않는다. Consumer가 lower-level control이 필요하면 공식 Testcontainers API를 직접 사용할 수 있지만, 그런 test는 #54/#55의 표준 검증 경로가 아니다.

## Lifecycle Contract

`RedisServer`는 동기 resource다. Docker startup/termination은 blocking operation이므로 v1에서 async context manager를 추가하지 않는다. Async cache/provider test도 fixture setup/teardown에서는 동일한 동기 server를 사용한다.

상태 전이:

```text
NEW --start--> STARTING --ready--> RUNNING --close--> CLOSED
                    |                 |             ^
                    +--failure--------+             |
                    |                               |
                    +--> CLEANUP_FAILED --close-----+
```

- constructor는 Docker에 연결하거나 container를 시작하지 않는다.
- `start()`는 `NEW`에서만 container를 생성하고 readiness까지 기다린다.
- 성공한 `start()`는 `self`를 반환한다.
- `RUNNING`에서 다시 `start()`하면 같은 instance를 반환하며 container를 추가 생성하지 않는다.
- `CLOSED`에서 `start()`하면 `RuntimeError`다. 한 wrapper instance를 재사용해 새 container를 만드는 동작은 지원하지 않는다.
- startup 중간 실패는 생성된 container가 있으면 Docker client timeout으로 제한된 termination을 시도한 뒤 typed error를 발생시킨다.
- `close()`는 `NEW`, partial failure, `RUNNING`, `CLEANUP_FAILED`, `CLOSED`에서 안전하다. termination 성공 뒤의 반복 호출은 no-op이며, termination 실패 시에는 container 참조를 보존해 다음 `close()`가 정리를 재시도한다.
- context manager 진입은 `start()`, 이탈은 `close()`를 호출한다.
- `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`는 category error로 바꾸지 않고 cleanup 후 원래 exception을 전파한다.

숨은 process-global singleton은 제공하지 않는다. Pytest session scope가 필요한 consumer는 명시적 fixture에서 한 `RedisServer` instance를 소유한다. 이는 Kotlin launcher의 재사용 효과를 Python의 fixture ownership으로 표현하면서 import-time Docker side effect를 피한다.

`RedisServer`는 thread-safe하지 않다. 하나의 fixture/caller가 instance를 소유하고, concurrent test worker 사이에서 같은 instance를 공유하지 않는다.

## Image and Port Authority

- 기본 image는 Kotlin `bluetape4k-testcontainers`와 같은 compatibility line인 `redis:8`이다.
- `image` override는 explicit constructor argument로만 허용한다. environment variable이나 global mutable setting으로 암묵적으로 바꾸지 않는다.
- blank image와 `latest` tag는 `ValueError`로 거절한다. 테스트 증거가 시간에 따라 무단 변경되는 것을 막는다.
- default Redis container port는 internal `6379`이며 host port는 항상 dynamic mapping이다.
- fixed host port API는 제공하지 않는다. local parallel run과 CI collision을 피하기 위한 invariant다.
- consumer는 container 내부 port나 `localhost`를 가정하지 않고 wrapper의 connection details만 사용한다.

## Readiness and Connection Details

Wrapper는 Testcontainers core `DockerContainer`에 `redis:8`과 internal port `6379`를 직접 구성한다. 공식 `RedisContainer`는 `redis:latest`와 redis-py client를 결합하므로 사용하지 않는다. Container start 전에 Docker SDK local image cache를 확인하고 없을 때만 격리된 bounded pull process를 실행한다. Local image lookup의 daemon/socket 실패는 `runtime-unavailable`, 실제 pull process의 registry 인증, throttling, resolution 실패는 `image-pull`로 분류한다. Readiness는 `ExecWaitStrategy(["redis-cli", "ping"])`에 configured startup timeout을 적용한다. `startup_timeout`은 각 Docker client operation, missing-image pull process, readiness에 적용하며 전체 startup wall-clock deadline을 뜻하지 않는다. Testcontainers의 global Ryuk initialization은 wrapper timeout 밖에서 별도 image pull과 connection loop를 수행하므로 사용하지 않는다. Wrapper가 bounded Docker client로 Redis container를 직접 시작하고 `com.bluetape.testcontainers.redis=true` label과 explicit cleanup을 소유한다. 비정상 process 종료 뒤에는 label로 orphan container를 확인하고 명시적으로 제거해야 한다. `start()`는 readiness command가 성공한 뒤에만 완료되며 redis-py dependency를 추가하지 않는다.

`RedisConnectionDetails`는 successful startup 후 한 번 계산한 immutable snapshot이다.

- `host`: Testcontainers가 보고한 Docker host
- `port`: mapped host port
- `url`: `redis://{host}:{port}`

`NEW`, `STARTING`, failed, `CLOSED` 상태에서 connection property를 읽으면 `RuntimeError`다. `RUNNING` 동안 같은 snapshot identity와 값을 유지한다.

## Error Contract

Startup failure는 `TestcontainerStartError`와 stable failure kind로 변환한다. Raw provider exception은 credential, daemon path, registry response, container log를 traceback으로 노출할 수 있으므로 public cause chain에서 제거한다.

- `runtime-unavailable`: Docker socket/daemon/runtime 접근 실패
- `image-pull`: image resolution, authentication, registry, pull 실패
- `readiness-timeout`: configured startup timeout 안에 Redis readiness가 완료되지 않음
- `wrapper-failure`: mapped port/detail 계산 또는 예상하지 못한 wrapper 단계 실패

Error message는 failure kind와 validated image identifier만 포함한다. Docker daemon URL, registry credential, environment, full provider response, container log 전체를 문자열화하거나 public traceback에 연결하지 않는다.

Constructor validation taxonomy:

- non-string image/startup timeout: `TypeError`
- blank/whitespace/control-character image, `latest`, non-finite/non-positive timeout: `ValueError`
- connection details before/after live interval: `RuntimeError`

## Pytest Integration

v1은 pytest plugin이나 자동 fixture를 배포하지 않는다. 자동 plugin loading은 import-time side effect와 fixture-name collision을 만들 수 있다. Consumer는 다음처럼 ownership scope를 명시한다.

```python
import pytest
from bluetape.testcontainers import RedisServer


@pytest.fixture(scope="session")
def redis_server():
    with RedisServer() as server:
        yield server
```

Function/session scope 선택과 Redis key cleanup은 consumer test suite가 소유한다. #54와 #55는 동일 worktree에서 Docker-backed suite를 직렬 실행하며, shared server를 쓸 경우 test namespace를 고유하게 만들고 suite teardown 전에 만든 key를 제거한다.

## CI and Test Selection

Docker가 필요 없는 unit/package tests와 Docker-backed integration tests를 분리한다.

- marker: `testcontainers`
- 기본 CI test job: `pytest -m "not testcontainers"`
- 별도 `testcontainers-redis` job: targeted package test를 `pytest -m testcontainers`로 한 process에서 실행
- Docker-backed job은 병렬 matrix나 pytest-xdist를 사용하지 않는다.
- wrapper integration이 실패하면 #54/#55를 실행하지 않는다.
- Docker runtime이 없는 developer 환경의 기본 unit run은 성공해야 하지만, merge-ready 증거에는 Docker-backed job 성공이 필수다.

CI는 base/default install에서 `testcontainers`, `docker`, `redis` import가 불가능함을 wheel-based smoke test로 검증한다. Workspace development environment에 package가 설치되어 있다는 사실을 default distribution 의존성 증거로 사용하지 않는다.

## Documentation

`README.md`와 `README.ko.md`는 다음을 source-equivalent하게 설명한다.

- install extra와 direct distribution install
- ecosystem image authority와 explicit override
- construction/start/close/context-manager lifecycle
- dynamic port와 connection details
- Docker/runtime requirement
- serial integration-test requirement
- startup failure categories
- production dependency가 아니라는 경계

별도 diagram asset은 만들지 않는다. v1은 단일 wrapper의 선형 lifecycle이고 상태 전이와 usage code가 더 정확하고 유지비가 낮다.

## Test Design

### Unit tests without Docker

- default image, explicit image, blank/latest rejection
- startup timeout type, finite/positive boundary
- constructor has no Docker side effect
- start success state transition with fake container
- repeated start returns same instance and does not create another container
- close before start, after start, after partial failure, repeated close
- start after close rejection
- details unavailable outside running interval
- immutable/stable connection detail snapshot
- context manager success and body exception cleanup
- `KeyboardInterrupt`/`SystemExit` cleanup and propagation
- each startup failure category and provider-diagnostic traceback redaction
- error string redaction
- public `__all__` and absence of lower-level container/client leakage

### Docker-backed tests

- `redis:8` starts and reaches readiness
- mapped port is positive, dynamic, and not assumed to be 6379
- URL has `redis://host:port` form
- stdlib socket으로 RESP `PING`, `SET`, `GET` round trip을 수행한다
- context exit terminates the container
- two sequential server lifecycles do not reuse stale details
- tests are marked `testcontainers` and run serially

### Packaging tests

- wheel name/version/Python requirement
- Testcontainers dependency exists only in `bluetape-testcontainers`
- redis-py dependency is absent from `bluetape-testcontainers`
- default `bluetape` wheel still depends only on `bluetape-core`
- `bluetape[testcontainers]` forwards exactly `bluetape-testcontainers==0.1.0`
- `bluetape-testing`, `bluetape-cache`, and production cache/provider distributions do not acquire Testcontainers dependencies
- namespace packages coexist without root `bluetape/__init__.py`

## Performance and Stability

Container startup dominates wrapper overhead, so a benchmark is not a merge gate. Stability evidence is lifecycle based:

- no import-time Docker access
- bounded startup timeout
- deterministic single-container creation per wrapper
- cleanup after success, test-body failure, and partial startup failure
- no fixed host port
- serial Docker-backed CI

## Rollout and Rollback

Rollout order:

1. merge and publish-ready validate #57;
2. make #54 tests depend on the wrapper;
3. make #55 tests depend on the same wrapper;
4. add future server wrappers only as separate reviewed submodules.

Rollback removes the `bluetape[testcontainers]` forwarding extra and workspace member, reverts #54/#55 test dependency changes, and leaves production cache packages unchanged. No production runtime or persistent Redis data migration exists.

## Non-Goals

- production Redis client/configuration ownership
- process-global launcher singleton
- async container lifecycle API
- fixed host port
- Redis Cluster, Sentinel, TLS, authentication, or fault injection
- Kafka, database, object-store, or broker wrappers
- hidden fallback to a locally installed Redis process
- automatic image upgrades

## Required Verification

- targeted unit and packaging tests
- Docker-backed `redis:8` integration test
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pytest -m "not testcontainers"`
- targeted serial `uv run pytest -m testcontainers packages/bluetape-testcontainers`
- `uv build --all-packages`
- wheel metadata/default-install isolation smoke tests
- `actionlint`
- `git diff --check`
- independent review with P0=0 and P1=0
