# bluetape-testcontainers

[English](README.md) | 한국어

`bluetape-testcontainers`는 bluetape Python 생태계의 재사용 가능한 Docker 기반
테스트 서버 경계를 관리합니다. 프로덕션 Redis, PostgreSQL, AWS client 패키지가
아니라 테스트 인프라입니다.

## 설치

현재 PyPI 배포는 보류 중입니다. 아래 명령은 배포가 시작된 뒤의 설치 형태입니다.
지금 source workspace에서 검증하려면 이 저장소에서 `uv sync --package
bluetape-testcontainers --extra all --group test --python 3.13.14 --locked`를
실행합니다.

| 필요 항목 | 명령 |
| --- | --- |
| Redis/base wrapper | `pip install "bluetape[testcontainers]"` 또는 `pip install bluetape-testcontainers` |
| PostgreSQL | `pip install "bluetape-testcontainers[postgres]"` |
| LocalStack | `pip install "bluetape-testcontainers[aws]"` |
| PostgreSQL과 LocalStack | `pip install "bluetape-testcontainers[all]"` |

루트 `bluetape[testcontainers]` extra는 계속 base-only입니다. 이 루트 extra는
PostgreSQL driver, boto3, SQLAlchemy, 프로덕션 client를 설치하지 않습니다.
테스트에서 사용할 client library는 caller가 설치하고 관리합니다.

## 지원 서비스

| Wrapper | 기본 image | Caller가 소유하는 항목 |
| --- | --- | --- |
| `RedisServer` | `redis:8` | key/data reset과 client lifecycle |
| `PostgresServer` | `postgres:18-alpine` | connection, pool, schema, transaction, migration, seed data |
| `LocalStackServer` | `localstack/localstack:4.14.0` | 선택 서비스, SDK client, AWS resource 정리 |

## Pytest 픽스처

이 패키지는 pytest plugin이나 자동 fixture를 등록하지 않습니다. 더 넓은 scope에
명시적인 reset policy가 없다면 function scope fixture를 사용합니다.

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

테스트 사이의 database와 AWS resource 삭제는 caller가 맡습니다. 비밀 정보가 든
PostgreSQL URL을 log에 남기면 안 되며, 더 넓은 fixture scope에는 명시적인 reset
policy가 필요합니다. 각 서버는 동기식이고 single-use이며 thread-safe하지 않습니다.
한 서버 객체는 정확히 하나의 fixture나 caller가 소유해야 합니다. CI capability
proof는 S3만 다룹니다. 문법상 유효한 다른 LocalStack service 이름은 고정 provider와
image에 전달되므로, 도입 전에 caller가 직접 capability test를 수행해야 합니다.

객체 생성은 Docker에 접근하지 않습니다. 실행 중 `start()`를 다시 호출하는 것은
안전하지만 `close()` 뒤에는 다시 시작할 수 없습니다. 공개 service port는 동적으로
할당하고 loopback에만 bind합니다. 이 계약을 증명할 수 없는 remote/shared Docker
daemon은 거절합니다. 종료에 실패하면 같은 wrapper에서 `close()`를 다시 호출해
정리를 완료합니다.

## 시작 및 정리 실패

시작 실패는 정제된 `TestcontainerStartError`와 안정적인 `StartFailureKind`로
노출됩니다. 잡힌 exception, connection URL, credential, 거절된 image 값, raw
provider output을 log에 남기면 안 됩니다.

| 상태/category | Caller 조치 |
| --- | --- |
| `dependency-missing` | `bluetape-testcontainers[aws]`를 설치하고 새 wrapper를 만듭니다. |
| `runtime-unavailable` | `docker info`를 실행하고 runtime 접근을 복구한 뒤 다시 시도합니다. |
| `image-pull` | 신뢰하는 고정 image를 명시적으로 pull하고 새 wrapper를 만듭니다. |
| `readiness-timeout` | Runtime capacity와 선택 service 집합을 확인하되 raw provider output은 기록하지 않습니다. |
| `wrapper-failure` | Contract/configuration 실패로 취급하고 정제된 입력을 확인합니다. |
| cleanup pending | 정리가 성공할 때까지 같은 wrapper에서 `close()`를 다시 호출합니다. |

Caller 진단에서는 안정적인 category만 처리합니다.

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

## Timeout 소유권

| Wrapper | Timeout contract |
| --- | --- |
| `RedisServer` | `startup_timeout`은 image/start/readiness operation 각각에 적용되며 하나의 전체 deadline이 아닙니다. |
| `PostgresServer` | Testcontainers 4.14.2에 공개 PostgreSQL readiness-timeout 입력이 없으므로 wrapper timeout을 제공한다고 약속하지 않습니다. |
| `LocalStackServer` | `startup_timeout`은 provider의 readiness log 대기에만 전달됩니다. Docker client 생성, image 획득, container 생성은 이 범위 밖입니다. |
| CI service job | `timeout-minutes: 30`은 workflow 바깥쪽의 safety cap이며 wrapper API 보장이 아닙니다. |

## Docker 운영과 orphan 정리

Runtime preflight는 `docker info`입니다. 필요하면 신뢰하는 고정 image를 명시적으로
pull합니다.

```bash
docker pull postgres:18-alpine
docker pull localstack/localstack:4.14.0
```

Testcontainers가 활성화한 경우 PostgreSQL과 LocalStack은 provider-owned Ryuk을
사용합니다. Ryuk은 process 범위에서 남아 있을 수 있지만, 각 wrapper는 자신이 만든
service container만 제거합니다. 관리 대상 service container에는 다음 label이
붙습니다.

- `com.bluetape.testcontainers.postgres=true`
- `com.bluetape.testcontainers.localstack=true`

Process가 비정상 종료되면 관련 label로 조회한 뒤 image와 container identity를 모두
확인하고 해당 service container만 제거합니다.

```bash
docker ps -a --filter label=com.bluetape.testcontainers.postgres=true
docker ps -a --filter label=com.bluetape.testcontainers.localstack=true
```

이 service-label 절차로 Ryuk을 제거하면 안 됩니다.

## Redis 호환성

Redis-only caller는 code나 dependency를 바꿀 필요가 없습니다. `RedisServer`, 오류
문구, 루트 `bluetape[testcontainers]` 동작은 그대로입니다. `redis:8`을 사용하고
operation별 image/start/readiness 제한을 관리하며 dynamic loopback port를 공개하고
Ryuk을 초기화하지 않습니다. Service label은 계속
`com.bluetape.testcontainers.redis=true`이고 Redis key 정리와 client lifecycle은
caller가 맡습니다.

Docker 기반 테스트에는 Docker-compatible runtime이 필요하며 직렬로 실행합니다.

```bash
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m testcontainers packages/bluetape-testcontainers -q
```
