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

이 저장소는 초기 `0.1.0` 개발 트랙에 있습니다. 첫 릴리스 범위는 다음 오픈
이슈로 관리합니다.

| 이슈 | 범위 |
|---:|---|
| [#1](https://github.com/bluetape4k/bluetape-py/issues/1) | `bluetape-core` 기반 헬퍼 확장. |
| [#2](https://github.com/bluetape4k/bluetape-py/issues/2) | `bluetape-logging` 컨텍스트 헬퍼 안정화. |
| [#3](https://github.com/bluetape4k/bluetape-py/issues/3) | 내부 우선 `bluetape-testing` 헬퍼 확장. |
| [#4](https://github.com/bluetape4k/bluetape-py/issues/4) | 초기 패키지 경계와 설치 가이드 공개. |
| [#5](https://github.com/bluetape4k/bluetape-py/issues/5) | `0.1.0` 릴리스와 PyPI 배포 경로 준비. |

## 워크스페이스 구조

![bluetape-py workspace overview](docs/images/readme-diagrams/bluetape-py-workspace-overview.png)

저장소는 하나의 `uv` 워크스페이스이며, 여러 개의 목적별 배포 패키지를 가집니다.
메타 패키지는 의도적으로 작게 유지합니다. `pip install bluetape`는 기본적으로
`bluetape-core`만 설치합니다.

| 배포 패키지 | Import 경로 | 기본 설치 | 상태 | 목적 |
|---|---|---:|---|---|
| `bluetape` | 없음 | yes | active | `bluetape-core`에만 의존하는 얇은 메타 배포 패키지. |
| `bluetape-core` | `bluetape.core` | yes | active | 표준 라이브러리만 사용하는 검증 및 기반 헬퍼. |
| `bluetape-logging` | `bluetape.logging` | no | active | 표준 `logging`, `contextvars`, redaction 헬퍼. |
| `bluetape-testing` | `bluetape.testing` | no | active, internal-first | 이 워크스페이스 내부 테스트를 우선 지원하는 pytest 헬퍼와 작은 공개 안정 API. |
| `bluetape-serde` | `bluetape.serde` | no | planned | core API가 안정화된 뒤 다룰 serialization 경계 헬퍼. |
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

## 설치

첫 PyPI 릴리스 이후의 공개 설치 형태는 다음과 같습니다.

```bash
pip install bluetape
pip install "bluetape[logging]"
pip install "bluetape[testing]"
pip install "bluetape[dev]"
pip install "bluetape[all]"
```

목적별 배포 패키지를 직접 설치할 수도 있습니다.

```bash
pip install bluetape-core
pip install bluetape-logging
pip install bluetape-testing
```

저장소에서 로컬 개발 환경을 만들 때는 다음 명령을 사용합니다.

```bash
uv sync --all-packages
```

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

## 패키지 문서

| 패키지 | 문서 |
|---|---|
| `bluetape` | [packages/bluetape/README.md](packages/bluetape/README.md) |
| `bluetape-core` | [packages/bluetape-core/README.md](packages/bluetape-core/README.md) |
| `bluetape-logging` | [packages/bluetape-logging/README.md](packages/bluetape-logging/README.md) |
| `bluetape-testing` | [packages/bluetape-testing/README.md](packages/bluetape-testing/README.md) |

## 로드맵

| 트랙 | 계획 |
|---|---|
| `0.1.0` | 초기 core, logging, testing, 문서, release preflight 이슈를 안정화합니다. |
| `0.2.x` | 실제 예제를 기준으로 `serde`, cache, Redis, Testcontainers 패키지 경계를 평가합니다. |
| 이후 | 기본 패키지가 안정화된 뒤 FastAPI 헬퍼와 workshop 예제를 추가합니다. |

## 생태계 백로그

`0.2.0` milestone은 bluetape-go와 bluetape4k 생태계에서 이미 검증된 기능을
Python-native 패키지로 옮기기 위한 다음 범위를 추적합니다. Python 패키지 경계나
의존성 선택이 분명하지 않은 항목은 구현 전에 research issue로 먼저 다룹니다.

| 이슈 | 트랙 |
|---:|---|
| [#7](https://github.com/bluetape4k/bluetape-py/issues/7) | Collections 헬퍼. |
| [#8](https://github.com/bluetape4k/bluetape-py/issues/8) | Async 및 bounded concurrency primitives. |
| [#9](https://github.com/bluetape4k/bluetape-py/issues/9) | Codec 및 compression 패키지. |
| [#10](https://github.com/bluetape4k/bluetape-py/issues/10) | Serialization 전략 research. |
| [#11](https://github.com/bluetape4k/bluetape-py/issues/11) | Cache 및 Redis coordination. |
| [#12](https://github.com/bluetape4k/bluetape-py/issues/12) | Resilience policies. |
| [#13](https://github.com/bluetape4k/bluetape-py/issues/13) | ID, measure, money value helpers. |
| [#14](https://github.com/bluetape4k/bluetape-py/issues/14) | SQL, repository, audit outbox research. |
| [#15](https://github.com/bluetape4k/bluetape-py/issues/15) | Testcontainers fixtures. |
| [#16](https://github.com/bluetape4k/bluetape-py/issues/16) | AWS, graph, text, image adapter research. |
| [#17](https://github.com/bluetape4k/bluetape-py/issues/17) | Leader election 및 distributed locks. |
| [#18](https://github.com/bluetape4k/bluetape-py/issues/18) | JWT 및 key rotation. |
| [#19](https://github.com/bluetape4k/bluetape-py/issues/19) | Rules, workflow, batch, work-report primitives. |
| [#20](https://github.com/bluetape4k/bluetape-py/issues/20) | Probabilistic data structure helpers. |

## 개발

```bash
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
