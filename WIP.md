# WIP

스냅숏: 2026-07-20 KST
범위: `v0.1.0` 릴리스 기반 및 `0.2.0` 생태계 패키지 계획.

## 현재 목표

`0.2.0` - 생태계 패키지 계획 및 첫 확장 작업 항목.

`v0.1.0`은 최초의 Python-native bluetape 작업공간으로 릴리스되었다:
<https://github.com/bluetape4k/bluetape-py/releases/tag/v0.1.0>.

릴리스된 기반은 기본 설치를 얇게 유지하고 집중 배포 모델을 정립한다:

- `bluetape`: 얇은 메타 배포판이며 기본 의존성은 `bluetape-core`다.
- `bluetape-core`: 표준 라이브러리만 사용하는 검증 및 기반 헬퍼다.
- `bluetape-collections`: 표준 라이브러리만 사용하는 즉시 평가 iterable/list/dict 헬퍼다. 소스 작업공간에서 issue #7에 따라 추가되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-async`: 표준 라이브러리만 사용하는 제한된 `asyncio` 헬퍼다. 소스 작업공간에서 issue #8에 따라 추가되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-audit`: 표준 라이브러리만 사용하는 불변 감사 값, 명시적 제한 검증, 보존 헬퍼다. issue #25에 따라 구현되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-cache`: 표준 라이브러리만 사용하는 제한된 동기 및 비동기 로컬 TTL 로딩 캐시다. issue #50에 따라 구현 및 병합되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-cache-redis`: 바이트 전용 동기 및 비동기 Redis 제공자, 엄격하고 제한된 결과 envelope, 제한된 Redis lease 기반 로드 조정 기능이다. issues #54와 #55에 따라 구현되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-codec`: 엄격한 URL-safe Base64 및 16진수 헬퍼다. 소스 작업공간에서 issue #9에 따라 추가되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-compression`: #9의 제한된 gzip, zlib, raw-DEFLATE 헬퍼와 #59의 구조적 compressor contract 및 opt-in LZ4, Snappy, Zstandard 제공자다. PyPI 배포는 계속 HOLD 상태다.
- `bluetape-logging`: 표준 라이브러리 `logging` 및 `contextvars` 헬퍼다.
- `bluetape-id`: 표준 라이브러리만 사용하는 UUIDv4/v7 및 random/monotonic ULID 값이다. 프로세스 로컬 generator state와 함께 issue #13에 따라 구현되었다.
- `bluetape-jwt`: issue #18이 `feat/issue-18-jwt-key-rotation`에서 구현 및 로컬 검증되었으며, 아홉 가지 JWS 알고리즘, 불변 claim 및 profile, active/retired/revoked 키 생명주기, 엄격한 검증, issuance-policy 조합, 선택적 제한 verified-result cache를 제공한다. PR review와 merge는 pending 상태로 남아 있으며 PyPI 배포는 계속 HOLD다.
- `bluetape-measure`: 런타임에 차원을 검사하는 불변 선형 측정값이다. 호출자가 소유하는 custom unit definition과 함께 issue #13에 따라 구현되었다.
- `bluetape-money`: 정확한 Decimal money와 현재 ISO 4217 currency다. 호출자가 소유하는 exchange rate와 historical policy를 사용하며 issue #13에 따라 구현되었다. PyPI 배포는 계속 HOLD 상태다.
- `bluetape-observability`: resilience 및 Redis observer event를 위한 API-only OpenTelemetry 어댑터다. 호출자가 소유하는 SDK 및 exporter lifecycle과 함께 issue #24에 따라 구현되었다. PyPI 배포는 계속 HOLD 상태다.
- `bluetape-resilience`: 표준 라이브러리만 사용하는 동기/비동기 retry, circuit breaker, bulkhead, cooperative async timeout 및 불변 fluent pipeline이다. `feat/issue-12-resilience-policies`에서 issue #12에 따라 구현되었으며 PyPI 배포는 계속 HOLD 상태다.
- `bluetape-serde`: 표준 라이브러리만 사용하는 불변 payload contract와 엄격하고 제한된 JSON v1 serialization이다. 소스 작업공간에서 issue #45에 따라 구현되었고, issue #46에 따라 CPython 3.13 전용 Apache Fory extra도 구현되었다. PyPI 배포는 계속 HOLD 상태다.
- `bluetape-testing`: 광범위한 public API를 약속하기 전에 내부 사용부터 시작하는 pytest 헬퍼다.
- `bluetape-testcontainers`: 생태계가 소유하는 Redis 8, PostgreSQL 18 및 caller-selected LocalStack test server wrapper다. dynamic loopback port, 불변 details, 명시적 fixture ownership 및 직렬 Docker verification을 제공한다.

## 현재 상태

- 이 저장소는 `packages/` 아래에 집중 패키지를 둔 Python 3.13+ `uv` 작업공간이다.
- `develop`은 통합 브랜치이고 `main`은 release-only다.
- `v0.1.0`은 `main`에 tag가 생성되었고 GitHub Release가 있다.
- `0.1.0` 기반, 문서 및 릴리스 preflight 범위에 해당하는 issues #1부터 #5까지는 closed 상태다.
- 이 저장소 외부에서 프로젝트 ownership과 trusted publishing을 확인할 때까지 PyPI 배포는 HOLD 상태다.
- 마일스톤 `0.2.0`은 생태계 issues #7부터 #34, serialization 후속 작업 #45/#46, local cache #50, 완료된 Redis provider 및 coordination 상위 범위 #51을 추적한다. issues #35부터 #44와 #47부터 #49는 이 명시적 범위에 포함된다고 볼 수 없다.
- research-first issues #10과 #23에는 source-backed decision이 있다. issues #14, #16, #21, #31 및 #34는 구현을 시작하기 전에 package boundary decision을 산출해야 한다.
- Issue #45 strict JSON serde는 소스 작업공간에서 사용할 수 있다. Issue #46 Apache Fory는 Python, Go, Rust 및 Kotlin fixture로 구현 및 로컬 검증되었으며 PR review와 merge는 pending 상태다. PyPI 배포는 계속 HOLD다.
- Issue #11 cache/Redis delivery는 #50 local cache와 #51 Redis coordination 상위 범위를 통해 완료되었으며, merge된 #57 Testcontainers, #54 Redis provider 및 #55 sync/async load coordination을 포함한다. Issue #56 near-cache invalidation은 독립된 upstream-blocked 작업 항목이며 #11 또는 #51 완료의 요구사항이 아니다. Issue #59는 Redis payload를 줄이는 데 사용하는 compressor contract를 제공한다.
- Issue #12 resilience policy는 feature branch에서 구현 및 로컬 검증되었다. PR review와 merge는 pending 상태로 남아 있으며 PyPI 배포는 계속 HOLD다.
- Issue #13 ID, measure 및 money value package는 feature branch에서 구현 및 로컬 검증되었다. 기본 meta install은 여전히 core-only이며 PyPI 배포는 계속 HOLD다.

## `0.1.0` 범위

1. 작업공간 레이아웃, package naming, Python version policy 및 uv build/test/release command를 정립한다.
2. 공용 validation 및 foundation helper를 위한 `bluetape-core`를 추가한다.
3. package-owned global logger state 없이 쉽게 사용할 수 있는 context-aware logging helper를 위해 `bluetape-logging`을 추가한다.
4. 내부 우선 pytest helper, eventual wait 및 향후 async/test-fixture boundary를 위해 `bluetape-testing`을 추가한다.
5. localized README가 있는 경우 root 및 package README 문서를 영어와 한국어로 제공한다.
6. 로컬 및 GitHub CI validation이 안정화된 뒤 첫 PyPI release path를 준비한다.

## `v0.1.0` 릴리스 기록

브랜치 정책:

- 기본 통합 브랜치로 `develop`을 사용한다.
- 안정 릴리스 브랜치로 `main`을 사용한다.
- 안정 tag를 만들고 PyPI에 배포하기 전에 검증된 `develop` 트리를 `main`으로 승격한다.

- GitHub Release: <https://github.com/bluetape4k/bluetape-py/releases/tag/v0.1.0>
- Tag target: `596e4898c915b55339521814ae7303953b50f4d2`
- Foundation issues #1부터 #5까지: closed.
- Milestone `0.1.0`: closed.
- PyPI 배포: ownership과 trusted publishing 확인 전까지 HOLD.

## `0.2.0` 작업 규칙

1. 광범위한 dependency 또는 package boundary 선택에는 research-first issue를 사용한다.
2. 기본 `bluetape` install은 얇게 유지한다.
3. import path, distribution name, dependency boundary, test 및 README shape를 명시한 후에만 새로운 package family를 추가한다.
4. 사용자에게 노출되는 동작이 변경되면 active package README와 root README locale file의 내용을 맞춘다.
5. 완료된 사용자 대상 변경 사항은 `CHANGELOG.md`에 기록한다.

## 마일스톤 로드맵

| 마일스톤 | 주제 | 비고 |
|---|---|---|
| `v0.1.0` | 릴리스된 core helper, logging, testing, docs 및 release preflight | 기본 install을 얇게 유지하고 API를 Python-native로 설계했다. |
| `0.2.0` | 생태계 패키지 계획 및 첫 확장 작업 항목 | issues #7-#34와 serialization 후속 작업 #45/#46을 추적하며, research-first 작업이 광범위한 adapter를 통제한다. |
| `0.3.0` | research gate 이후 첫 구현 단계 | 후보 범위는 #21, #31 및 #34의 pending decision에 따라 달라진다. #10, #14, #16 및 #23은 현재 구현 후속 작업의 제약 조건이다. |

## 작업 큐

### `v0.1.0` - 릴리스된 기반

과거 릴리스 범위이며 모든 항목이 closed 상태다.

- #1 - `bluetape-core` foundation helper 확장. PR #35에서 구현되었다.
- #2 - `bluetape-logging` context helper 안정화. PR #35에서 구현되었다.
- #3 - 내부 우선 `bluetape-testing` helper 확장. PR #35에서 구현되었다.
- #4 - 초기 package boundary 및 install guide 공개. PR #6에서 닫혔다.
- #5 - `v0.1.0` release 및 PyPI publishing path 준비. PR #35에서 구현되었다.

### `0.2.0` - 생태계 백로그

- #7 - Collections helper package. 소스 작업공간의 `bluetape-collections`로 구현되었으며 PyPI 배포는 release hold 범위에 남아 있다.
- #8 - Async 및 제한된 concurrency primitive. 소스 작업공간의 `bluetape-async`로 구현되었으며 PyPI 배포는 계속 HOLD다.
- #9 - Codec 및 compression package. 소스 작업공간의 `bluetape-codec`와 `bluetape-compression`으로 구현되었으며 PyPI 배포는 계속 HOLD다.
- #59 - 조합 가능한 compressor contract 및 optional native provider. 구조적 Python Protocol, 불변 gzip/zlib/DEFLATE/LZ4/Snappy/Zstandard 구현, 제한된 decompression 및 격리된 extra로 구현되었다. 이는 #54가 사용하는 compression prerequisite다.
- #10 - Serialization strategy research. Decision은 `docs/research/2026-07-10-issue-10-serialization-strategy.md`에 기록되었으며 후속 작업은 #45 (contract/strict JSON)와 #46 (Apache Fory adapter)다.
- #45 - 불변 payload contract 및 엄격하고 제한된 JSON v1 serde. 소스 작업공간에서 구현 및 로컬 검증되었으며 PR review와 merge는 pending 상태다.
- #46 - Apache Fory adapter 및 Python/Go/Rust/Kotlin conformance. 신뢰된 내부용 CPython 3.13 extra가 소스 작업공간에서 구현 및 로컬 검증되었으며 PyPI 배포는 계속 HOLD다.
- #11 - Cache 및 Redis coordination 상위 범위. 필요한 delivery는 #50 local cache와 #51 Redis provider/load coordination을 통해 완료되었으며, 명시적으로 독립된 #56 near-cache invalidation 작업 항목은 upstream-blocked 상태이고 #11 완료를 막지 않는다.
- #50 - 제한된 sync 및 async local TTL loading cache. `bluetape-cache`로 구현 및 merge되었다.
- #51 - Redis cache coordination 및 provider boundary. 필요한 delivery는 #57, #54 및 #55를 통해 완료되었다. 명시적으로 독립된 #56 near-cache invalidation 작업 항목은 upstream-blocked 상태이고 #51 완료를 막지 않는다.
- #54 - Redis byte provider 및 제한된 result-envelope substrate. `develop`에 구현 및 merge되었으며 #55가 사용하는 provider substrate다.
- #55 - 제한된 sync/async Redis load coordination. #54 provider substrate 위에 expiring lease와 atomic token-checked publish를 사용하여 구현 및 merge되었다.
- #56 - RESP3 client-tracking near-cache invalidation. #51 coordination delivery와 독립되어 있으며 현재 upstream client behavior에 의해 blocked 상태다.
- #57 - 생태계 소유 Testcontainers Redis 8 wrapper. 구현 및 merge되었고 #54 및 #55 integration suite에서 사용된다.
- #12 - 표준 라이브러리만 사용하는 resilience policy. `feat/issue-12-resilience-policies`에서 sync/async retry, circuit breaker, bulkhead, cooperative async timeout, typed event, 불변 state snapshot 및 fluent decorator pipeline을 분리하여 구현되었다. PR review와 merge는 pending 상태이며 PyPI 배포는 계속 HOLD다.
- #13 - ID, measure 및 money value package. `id`, `measure`, `money` 및 aggregate `values` extra를 제공하는 세 개의 독립적인 표준 라이브러리 전용 distribution으로 구현되었다. KSUID에는 호환 consumer가 필요하고, Snowflake에는 machine/epoch ownership이 필요하며, compound/affine measure, locale money 및 provider FX는 별도의 trigger-gated issue로 남아 있다.
- #14 - SQL, repository 및 audit outbox strategy research. Decision은 `docs/research/2026-07-16-issue-14-sql-repository-audit-outbox-strategy.md`에 기록되었다. caller-owned SQLAlchemy Core sync/async connection을 사용하고 audit를 storage-neutral로 유지하며, PostgreSQL transactional outbox 동작은 caller-driven relay execution을 사용하는 별도 adapter로 격리한다.
- #15 - Testcontainers fixture 패키지.
- #16 - AWS, graph, text 및 image adapter boundary research. Decision은 `docs/research/2026-07-18-issue-16-adapter-boundaries.md`에 기록되었다. 제한된 동기 AWS batch 동작, literal text matching/masking 및 Pillow single-image transform을 위한 좁은 optional wrapper만 유지하며, 공통 graph API를 공개하기 전에 example을 통해 graph value와 Neo4j interoperability를 입증한다.
- Issue #17 - Leader election 및 distributed lock contract. 표준 라이브러리만 사용하는 `bluetape-leader` contract package와 명시적인 `bluetape-leader-redis` single-primary adapter로 구현되었다. sync/async bounded lifecycle, fencing, 격리된 wheel, Redis 8 contention evidence 및 bilingual operating guidance를 포함하며 PR #83을 `develop`에 rebase merge하여 완료되었다.
- #18 - JWT 및 key-rotation helper. `feat/issue-18-jwt-key-rotation`에서 구현 및 로컬 검증되었으며 PR review와 merge는 pending 상태다. Async provider, JWE encryption 및 versioned compression은 별도 issues #88, #89 및 #90으로 남아 있다.
- #19 - 규칙, 워크플로, 배치 및 작업 보고 primitive.
- #20 - 확률적 자료 구조 헬퍼.
- #21 - Python 웹 API 어댑터 경계 연구.
- #22 - Web API helper 및 ASGI/FastAPI adapter.
- #23 - Observability 및 OpenTelemetry boundary research. Decision은 `docs/research/2026-07-15-issue-23-observability-opentelemetry-boundaries.md`에 기록되었다. domain package는 OTel-free로 유지하고 #24가 진행되면 별도의 API-only opt-in bridge를 사용하며, SDK/exporter/global lifecycle ownership은 application에 남긴다.
- #24 - Observability hook 및 telemetry helper. API-only bridge인 `bluetape-observability`로 구현되었으며 PR review와 merge는 pending 상태다.
- #25 - Storage-neutral audit event 및 conformance package. 불변 값, 명시적 제한 검증, 안전한 error 및 결정적인 preservation helper를 제공하는 표준 라이브러리 전용 opt-in `bluetape-audit`로 구현되었다. SQL outbox와 broker publisher는 별도의 adapter issue로 남아 있다.
- #77 - caller-transaction enqueue, 제한된 lease 기반 claim/mark operation, at-least-once delivery 및 caller-driven relay execution을 제공하는 PostgreSQL transactional audit outbox adapter.
- #26 - SQS partial result, DynamoDB unprocessed-item handling 및 검증된 S3 envelope/checksum helper를 최대 하나까지 제공하는 좁은 동기 Boto3 proof.
- #27 - 직접 NetworkX 및 공식 Neo4j driver integration을 사용하는 제한된 graph value 및 interoperability proof. 다중 backend conformance는 보류한다.
- #28 - 선택적인 제한 literal multi-pattern matching 및 union 기반 masking. tokenizer와 language-detection abstraction은 제외한다.
- #29 - 선택적인 제한 Pillow single-image transform proof. pyvips, barcode, OCR, CAPTCHA, storage 및 framework integration은 제외한다.
- #30 - SQLAlchemy Core toolkit 및 명시적인 application repository helper. 첫 단계에서는 outbox storage와 encrypted-column 작업을 제외한다.
- #31 - Geo, spatial 및 statistics utility scope research.
- #32 - Provider conformance 및 benchmark suite.
- #33 - `bluetape-go`와 `bluetape-py`의 생태계 parity matrix.
- #34 - Config, secret 및 credential provider boundary research.

## 연구 게이트

Research note는 광범위한 구현을 시작하기 전에 `docs/research/` 아래에 두고 `docs/research/README.md`에서 연결해야 한다.

- #10은 serialization baseline, optional adapter, trust profile, typed error 및 cross-language compatibility expectation을 결정해야 한다.
- #14는 SQL/transaction ownership, repository helper scope, audit model boundary, PostgreSQL outbox isolation 및 필요한 Testcontainers fixture boundary를 결정했다. 구현은 #15, 범위를 좁힌 #25, 범위를 좁힌 #30 및 전용 PostgreSQL outbox issue #77로 나뉘어 있다.
- #16은 AWS, literal text matching 및 Pillow transform이 제한된 optional light wrapper로만 진행될 수 있다고 결정했다. graph는 직접 dependency example으로 시작하며 두 개의 독립 consumer가 생긴 뒤에야 공용 value를 확보한다. 기존 issues #26-#29가 범위를 좁힌 proof를 담당하고 광범위한 service/backend/model/codec surface는 0.2.x의 비목표로 남는다.
- #21은 ASGI/FastAPI/framework adapter boundary, request-context ownership, RFC 7807 scope 및 middleware conformance expectation을 결정해야 한다.
- #23은 표준 라이브러리 logging hook boundary, 별도의 API-only optional bridge 방향, application-owned SDK/exporter lifecycle 및 명시적인 Python 3.13 context propagation expectation을 결정했다.
- #31은 geo, spatial, statistics, histogram 및 geocoding helper를 owned API, light wrapper, example 전용 또는 거부 중 어느 범위로 둘지 결정해야 한다.
- #34는 security-sensitive helper를 구현하기 전에 configuration, secret, credential, KMS/envelope encryption 및 cloud provider boundary 정책을 결정해야 한다.
