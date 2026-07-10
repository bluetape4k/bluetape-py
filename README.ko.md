# bluetape-py

[English](README.md) | [한국어](README.ko.md)

![bluetape-py hero](docs/assets/bluetape-py-hero.png)

백엔드 서비스, 테스트, 로깅, 운영 보조 기능을 위한 Python-native bluetape
라이브러리입니다.

`bluetape-py`는 `bluetape4k`, `bluetape-go`, `bluetape-rs`와 같은 생태계
운영 원칙을 따르지만, 다른 언어 구현을 기계적으로 옮기지 않습니다. Python
3.13+를 기준으로 시작하고, 기본 설치는 얇게 유지하며, 무거운 기능은 명시적인
PyPI 배포 패키지와 extras로 분리합니다.

## 현재 상태

`v0.1.0`은 첫 Python-native foundation 릴리스로 공개되었습니다:
[`v0.1.0`](https://github.com/bluetape4k/bluetape-py/releases/tag/v0.1.0).
PyPI 배포는 package ownership과 trusted publishing이 확인될 때까지 보류합니다.
collections, codec, compression, serde 패키지는 source workspace에서 사용할 수
있으며, registry 설치 명령은 PyPI 배포가 활성화된 뒤의 목표 형태를 설명합니다.

현재 계획 트랙은
[`0.2.0`](https://github.com/bluetape4k/bluetape-py/milestone/2) milestone입니다.
#7-#34 이슈로 ecosystem backlog를 확장합니다. 자세한 계획은
[`WIP.md`](WIP.md)에 두고, 완료된 사용자-facing 변경은
[`CHANGELOG.md`](CHANGELOG.md)에 기록합니다.

| 트랙 | 범위 |
|---|---|
| `v0.1.0` | 릴리스 완료: workspace, core, logging, testing, docs, release preflight. |
| `0.2.0` | 진행 중인 ecosystem planning과 #45의 strict JSON serde를 포함한 첫 확장 작업. |
| PyPI publish | project ownership과 trusted publishing 확인 전까지 보류. |

## 워크스페이스 구조

![bluetape-py workspace overview](docs/images/readme-diagrams/bluetape-py-workspace-overview.png)

저장소는 하나의 `uv` 워크스페이스이며, 여러 개의 목적별 배포 패키지를 가집니다.
메타 패키지는 의도적으로 작게 유지합니다. `pip install bluetape`는 기본적으로
`bluetape-core`만 설치합니다.

| 배포 패키지 | Import 경로 | 기본 설치 | 상태 | 목적 |
|---|---|---:|---|---|
| `bluetape` | 없음 | yes | active | `bluetape-core`에만 의존하는 얇은 메타 배포 패키지. |
| `bluetape-core` | `bluetape.core` | yes | active | 표준 라이브러리만 사용하는 검증 및 기반 헬퍼. |
| `bluetape-async` | `bluetape.asyncio` | no | active, source workspace | 표준 라이브러리만 사용하는 bounded structured-concurrency 헬퍼. |
| `bluetape-codec` | `bluetape.codec` | no | active, source workspace | 엄격한 URL-safe Base64와 hexadecimal 헬퍼. |
| `bluetape-collections` | `bluetape.collections` | no | active, source workspace | 표준 라이브러리만 사용하는 eager iterable/list/dict 헬퍼. |
| `bluetape-compression` | `bluetape.compression` | no | active, source workspace | 제한된 gzip, zlib, raw-DEFLATE byte 헬퍼. |
| `bluetape-logging` | `bluetape.logging` | no | active | 표준 `logging`, `contextvars`, redaction 헬퍼. |
| `bluetape-testing` | `bluetape.testing` | no | active, internal-first | 이 워크스페이스 내부 테스트를 우선 지원하는 pytest 헬퍼와 작은 공개 안정 API. |
| `bluetape-serde` | `bluetape.serde` | no | active, source workspace | 엄격한 payload 계약과 bounded JSON v1 serialization. |
| `bluetape-cache` | `bluetape.cache` | no | planned | 캐시 추상화와 인메모리 헬퍼. |
| `bluetape-redis` | `bluetape.redis` | no | planned | cache 계약을 검증한 뒤 추가할 Redis 어댑터. |
| `bluetape-testcontainers` | `bluetape.testcontainers` | no | planned | 통합 테스트가 많은 패키지를 위한 Testcontainers fixture. |
| `bluetape-fastapi` | `bluetape.fastapi` | no | planned | core/logging/testing 계층이 안정화된 뒤 추가할 FastAPI 연동 헬퍼. |

## 설계 방향

- Python-native API를 먼저 설계합니다. Kotlin, Go, Rust 구현은 참고 대상이지
  복사 원본이 아닙니다.
- `bluetape-core`는 표준 라이브러리만 사용합니다.
- `bluetape-logging`은 `logging`과 `contextvars` 기반의 stdlib-first 모듈로
  유지합니다.
- `bluetape-testing`은 `pytest`에 의존할 수 있지만, 넓은 공개 API를 약속하기
  전에 내부 지원 모듈로 먼저 성장시킵니다.
- 루트 `bluetape` 배포 패키지는 extras를 제공하지만, 루트
  `bluetape/__init__.py` import surface는 만들지 않습니다.
- 기본 meta 설치는 계속 core-only입니다. Serde는 opt-in이며 Apache Fory는
  #46의 별도 후속 작업으로 남겨 둡니다.

## 설치

PyPI 배포는 아직 보류 중입니다. 배포가 활성화되기 전에는 registry 설치 명령 대신
아래의 로컬 workspace 명령을 사용합니다.

첫 PyPI 릴리스 이후의 공개 설치 형태는 다음과 같습니다.

```bash
pip install bluetape
pip install "bluetape[asyncio]"
pip install "bluetape[codec]"
pip install "bluetape[collections]"
pip install "bluetape[compression]"
pip install "bluetape[logging]"
pip install "bluetape[serde]"
pip install "bluetape[testing]"
pip install "bluetape[dev]"
pip install "bluetape[all]"
```

목적별 배포 패키지를 직접 설치할 수도 있습니다.

```bash
pip install bluetape-core
pip install bluetape-async
pip install bluetape-codec
pip install bluetape-collections
pip install bluetape-compression
pip install bluetape-logging
pip install bluetape-serde
pip install bluetape-testing
```

저장소에서 로컬 개발 환경을 만들 때는 다음 명령을 사용합니다.

```bash
uv sync --all-packages
uv run --package bluetape-serde python -c "import bluetape.serde"
```

현재 실행 가능한 경로는 로컬 workspace와 로컬 wheel뿐입니다. 위 `pip` 명령과
향후 `serde` extra는 PyPI 배포가 활성화되기 전에는 registry에서 사용할 수 없습니다.

## 사용 예

### Core validation

```python
from bluetape.core import require_not_blank

service_name = require_not_blank("orders", "service_name")
```

### Logging context

```python
import logging

from bluetape.logging import ContextLogFilter, log_context

logger = logging.getLogger("orders")
logger.addFilter(ContextLogFilter())

with log_context(trace_id="trace-123", tenant="blue"):
    logger.info("order accepted")
```

### Testing waits

```python
from bluetape.testing import eventually

eventually(lambda: cache.get("ready"), timeout=2.0)
```

### Collections

```python
from bluetape.collections import chunked, group_by

chunks = chunked(range(5), 2)
by_initial = group_by(["ant", "ape", "bee"], lambda value: value[0])
```

### Codec과 compression

```python
from bluetape.codec import base64url_encode
from bluetape.compression import gzip_compress, gzip_decompress

token = base64url_encode(b"order:42")
assert gzip_decompress(gzip_compress(token.encode("ascii"))) == token.encode("ascii")
```

`bluetape.codec`는 canonical URL-safe Base64와 strict hex text만 decode합니다.
`bluetape.compression`은 기본 64 MiB logical returned-payload 제한을 사용하며,
gzip은 완전한 concatenated member를 허용하고 zlib/raw-DEFLATE는 trailing byte를
거부합니다. 두 패키지 모두 기본 `bluetape` 설치에는 포함되지 않습니다.

### Bounded asyncio 작업

```python
import asyncio

from bluetape.asyncio import map_bounded


async def fetch_order(order_id: int) -> str:
    await asyncio.sleep(0.01)
    return f"order-{order_id}"


async def main() -> None:
    print(await map_bounded([1, 2, 3], fetch_order, limit=2, timeout=1.0))


asyncio.run(main())
```

단순한 순차 작업에는 동기 반복을 사용하고, 이미 작고 범위가 정해진 coroutine
집합에만 `asyncio.gather`를 사용합니다. 입력 iterable이 커질 수 있고 호출자가
cooperative 동시성 상한을 정해야 할 때는 `map_bounded`를 사용합니다.

### Strict JSON serde

```python
from bluetape.serde import (
    PayloadMetadata,
    TrustProfile,
    json_deserialize,
    json_serialize,
)

producer_metadata = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)
payload = json_serialize({"order_id": 42}, metadata=producer_metadata)

# Consumer policy는 인증된 설정으로 별도 구성하며 payload.metadata에서 복사하지 않습니다.
consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)
assert json_deserialize(payload, expected_metadata=consumer_policy) == {"order_id": 42}
```

권장 기본값은 `UNTRUSTED`입니다. `TRUSTED_INTERNAL`은 producer가 인증되고
인가된 폐쇄 경계에서만 허용하며, 네트워크 위치나 payload 주장은 충분하지 않습니다.
두 profile 모두 strict UTF-8 JSON, 정확한 metadata, duplicate key/non-finite number
거부, 기본 input/output 16 MiB, 기본 depth 100, hard ceiling 256을 동일하게 적용합니다.
Byte 제한만으로 process memory 상한이 보장되지는 않습니다. 오류 처리와 버전별
rollout/rollback은 package README를 참고하십시오.

## 패키지 문서

| 패키지 | 문서 |
|---|---|
| `bluetape` | [packages/bluetape/README.md](packages/bluetape/README.md) |
| `bluetape-async` | [packages/bluetape-async/README.md](packages/bluetape-async/README.md) |
| `bluetape-codec` | [packages/bluetape-codec/README.md](packages/bluetape-codec/README.md) |
| `bluetape-collections` | [packages/bluetape-collections/README.md](packages/bluetape-collections/README.md) |
| `bluetape-compression` | [packages/bluetape-compression/README.md](packages/bluetape-compression/README.md) |
| `bluetape-core` | [packages/bluetape-core/README.md](packages/bluetape-core/README.md) |
| `bluetape-logging` | [packages/bluetape-logging/README.md](packages/bluetape-logging/README.md) |
| `bluetape-serde` | [packages/bluetape-serde/README.md](packages/bluetape-serde/README.md) |
| `bluetape-testing` | [packages/bluetape-testing/README.md](packages/bluetape-testing/README.md) |

## 로드맵

| 트랙 | 계획 |
|---|---|
| `v0.1.0` | 초기 core, logging, testing, 문서, release preflight foundation을 릴리스했습니다. |
| `0.2.0` | #7-#34로 ecosystem package planning을 추적하고, broad adapter는 research gate를 먼저 둡니다. |
| 이후 | 기본 패키지가 안정화된 뒤 FastAPI 헬퍼와 workshop 예제를 추가합니다. |

프로젝트 관리와 릴리스 정책은 다음 문서에서 관리합니다.

- [WIP.md](WIP.md)
- [CHANGELOG.md](CHANGELOG.md)
- [Package layout policy](docs/package-layout.md)
- [Release guide](docs/release.md)
- [Research index](docs/research/README.ko.md)

## 생태계 백로그

`0.2.0` milestone은 bluetape-go와 bluetape4k 생태계에서 이미 검증된 기능을
Python-native 패키지로 옮기기 위한 다음 범위를 추적합니다. Python 패키지 경계나
의존성 선택이 분명하지 않은 항목은 구현 전에 research issue로 먼저 다룹니다.
이슈별 task queue는 [`WIP.md`](WIP.md), research gate는
[`docs/research/README.ko.md`](docs/research/README.ko.md)를 봅니다.

## 개발

```bash
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
