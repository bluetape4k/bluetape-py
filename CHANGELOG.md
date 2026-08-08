# 변경 기록

이 프로젝트의 모든 주요 변경 사항을 이 파일에 기록한다.

형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며,
첫 tag를 게시한 뒤에는 시맨틱 버전 관리를 사용한다.

## [Unreleased]

### 변경

- 원자적 스냅숏이 활성 마커를 관찰할 때 Redis 조정 결과 키를 읽고 반환하는 동작을 중단한다. 동기 및 비동기 제공자는 여전히 하나의 `EVAL`을 사용하며, 마커가 완료되었거나 없을 때는 제한된 result-prefix 동작을 유지하고 public API와 Redis ACL 요구사항은 변경하지 않는다.
- API를 안정화하기 전에 실제로 발생하지 않는 `RedisCoordinationErrorCode.CLEANUP_FAILURE`를 제거한다. Cleanup failure는 계속 원래 exception 또는 cancellation을 보존하며 정적 note와 카디널리티가 낮은 `cleanup_failed` observation을 통해서만 보고한다. Consumer는 삭제된 member를 대상으로 하는 enum match를 제거하고 원래 exception 또는 cancellation을 처리하며 cleanup-failure telemetry에는 `event.cleanup_failed`를 사용해야 한다.

### 추가

- 아홉 가지 엄격한 JWS 알고리즘, 불변 typed claim 및 profile, 원자적 인메모리 키 순환, active/retired/revoked 생명주기, 생성자에 바인딩된 검증, issuance-policy decorator 및 선택적인 제한 verified-result cache를 제공하는 opt-in `bluetape-jwt` 배포판을 추가한다. JWS payload는 계속 읽을 수 있으며, 비동기 provider, JWE encryption 및 versioned compression은 각각 #88, #89 및 #90에서 별도로 추적한다. 기본 meta install은 core-only로 유지되고 PyPI 배포는 계속 HOLD다.
- 표준 라이브러리만 사용하는 `bluetape-leader` contract package와 opt-in `bluetape-leader-redis` adapter로 Issue #17을 구현한다. 첫 Redis 단계는 제한된 sync/async lock 및 elector, 정확한 borrowed-client validation, owner-safe Lua lifecycle, fencing token, cancellation cleanup, 실제 Redis 8 contention evidence, 격리된 wheel check 및 bilingual migration, rollback, ACL, topology와 operator guidance를 제공한다. 기본 install은 core-only로 유지하며 Redis leader support는 `dev`와 `all`에서 제외한다.
- 불변 저장소 중립 audit value, 호출자가 명시적으로 제공하는 limit, value-safe error 및 결정적인 adapter preservation helper를 제공하는 opt-in 표준 라이브러리 전용 `bluetape-audit` 배포판을 추가한다. Application이 serialization, repository, transaction, history, outbox, relay, transport, redaction 및 logging ownership을 계속 가지며 기본 install은 core-only로 유지한다.
- opt-in 독립 표준 라이브러리 전용 `bluetape-id`, `bluetape-measure` 및 `bluetape-money` value distribution과 opt-in `id`, `measure`, `money` 및 aggregate `values` meta extra를 추가한다. package는 UUIDv4/v7 및 random/monotonic ULID value, 런타임 dimension-checked linear measure, 재현 가능한 현재 ISO 4217 snapshot 기반의 정확한 Decimal money를 제공한다. 기본 install은 core-only로 유지하며 distributed ID policy, custom unit, historical currency 및 exchange-rate provider는 application이 소유한다.
- resilience policy, Redis provider 및 Redis coordination event를 위한 fail-safe OpenTelemetry API adapter를 제공하는 opt-in `bluetape-observability` package를 추가한다. package는 카디널리티가 낮은 고정 signal을 사용하고 SDK/exporter lifecycle은 application이 소유하도록 하며, PyPI 배포가 hold인 동안 모든 meta extra에서 제외한다.
- sync/async retry, circuit breaker 및 bulkhead policy를 분리하고 cooperative async timeout, deterministic backoff, typed cardinality-low event, 불변 state snapshot 및 불변 fluent decorator pipeline을 제공하는 opt-in 표준 라이브러리 전용 `bluetape-resilience` package를 추가한다. package에는 synchronous timeout, hidden worker, reset scheduler, detached task 또는 global registry가 없으며 저장소 전체 PyPI publication hold를 따른다.
- private 표준 라이브러리 전용 `bluetape-benchmark` workspace distribution과 sync/async correctness evidence, spawn/cancellation containment, atomic schema-v1 report, paired comparison 및 검증된 smoke artifact를 제공하는 제한된 Redis coordination benchmark를 추가한다. package는 build와 test를 수행하지만 publication은 금지되며 benchmark result는 production-capacity claim이 아니다.
- byte-only sync 및 async redis-py provider, 엄격하고 제한된 binary/JSON v1 result envelope, 명시적인 compression migration reader, atomic TTL/NX/compare-delete operation, redacted stable failure 및 owned/borrowed lifecycle contract를 제공하는 opt-in `bluetape-cache-redis` package를 추가한다. 이 집중 package와 `cache-redis` meta extra는 default, `dev` 및 `all` dependency set에서 계속 제외한다.
- local same-key coalescing, expiring lease, atomic token-checked result publication, 제한된 polling, redacted observation, cancellation-safe cleanup 및 실제 Redis contention verification을 제공하는 제한된 sync 및 async Redis load coordinator를 추가한다. `ResultEnvelopeCodec.decode_matching()`은 tagged `ResultEnvelopeMatch`를 반환하므로 decode된 `None`과 owner-token mismatch를 구분할 수 있다.
- 명시적인 lifecycle, 제한된 readiness, dynamic connection detail 및 직렬 Docker CI coverage를 제공하는 opt-in `bluetape-testcontainers` Redis 8 wrapper를 추가한다.
- opt-in PostgreSQL 18 및 선택된 service용 LocalStack wrapper, 집중된 `postgres`/`aws`/`all` extra, lazy provider import, loopback-only dynamic port 및 결정적인 cleanup을 제공하도록 `bluetape-testcontainers`를 확장한다.
- `bluetape.asyncio` 아래에 제한된 structured-concurrency helper를 제공하는 `bluetape-async` 소스 작업공간 package를 추가하며, 여기에는 순서가 보장되는 `map_bounded` 실행이 포함된다.
- `bluetape.collections` 아래에 chunking, grouping, distinct, partitioning 및 exception-transparent map/filter transform을 제공하는 eager 표준 라이브러리 전용 helper인 `bluetape-collections` 소스 작업공간 package를 추가한다.
- `bluetape.codec` 아래에 strict canonical URL-safe Base64 및 hexadecimal helper를 제공하는 `bluetape-codec` 소스 작업공간 package를 추가한다.
- `bluetape.compression` 아래에 제한된 gzip, zlib-wrapped 및 raw-DEFLATE helper를 제공하는 `bluetape-compression` 소스 작업공간 package를 추가한다.
- 안정적인 algorithm ID, 제한된 decompression, 엄격한 malformed/trailing-data failure 및 provider-isolated `lz4`, `snappy`, `zstd` 및 `native` extra를 제공하는 구조적 `Compressor` Protocol과 불변 gzip, zlib, raw-DEFLATE, LZ4 frame, raw Snappy 및 Zstandard frame 구현을 추가한다. meta distribution은 native 선택지를 전달하지만 이를 default, `dev` 또는 `all` dependency set에 추가하지 않는다.
- `bluetape.cache` 아래에 LRU capacity, same-key load coalescing, mutation supersession, in-flight load limit 및 불변 statistic을 포함하는 제한된 동기 및 비동기 local TTL loading cache를 제공하는 표준 라이브러리 전용 `bluetape-cache` 소스 작업공간 package를 추가한다. 이는 새로운 API이므로 migration alias 또는 compatibility shim이 필요하지 않다. opt-in Redis provider 및 load coordination은 `bluetape-cache-redis`가 별도로 제공하며 near-cache invalidation은 독립적인 upstream-blocked issue #56으로 남아 있다.
- `bluetape.serde` 아래에 불변 payload contract, caller-owned trust policy, 고정된 typed error 및 제한된 JSON v1 serialization을 제공하는 `bluetape-serde` 소스 작업공간 package를 추가한다. 여기에는 제한된 `bytearray` output assembly, source-free public error traceback 및 결정적인 640-digit JSON integer limit가 포함된다.
- trusted-internal Apache Fory adapter, 고정된 schema/type envelope, 제한된 runtime concurrency, 안정적인 error 및 Python/Go/Rust/Kotlin conformance artifact를 제공하는 선택적 `bluetape-serde[fory]` 및 `bluetape[fory]` CPython 3.13 extra를 추가한다. Fory는 base, `serde`, `dev` 및 `all` extra에서 계속 제외한다.

## [v0.1.0] - 2026-07-10

### 추가

- 얇은 `bluetape` meta distribution과 집중된 `bluetape-core`, `bluetape-logging` 및 `bluetape-testing` package를 위한 최초의 Python-native workspace 문서를 추가했다.
- 초기 package boundary, install policy, usage example, package documentation link 및 roadmap에 대한 한국어 root README parity를 추가했다.
- README bitmap hero와 workspace overview diagram asset을 추가했다.
- release planning, milestone scope 및 생태계 backlog를 위한 `WIP.md`를 추가했다.
- `docs/` 아래에 release 및 package-layout documentation을 추가했다.
- 향후 research-first package decision을 위한 research index documentation을 추가했다.
- research gate #10, #14, #16, #21, #23, #31 및 #34를 포함하여 ecosystem issues #7부터 #34까지를 통해 milestone `0.2.0` planning visibility를 추가했다.
- `bluetape-core`에 `require_instance`를 추가했다.
- `log_context(override=False)`의 duplicate-key protection과 case-insensitive logging redaction default를 추가했다.
- falsy non-`None` value 및 양수 timeout/interval validation을 처리하도록 `eventually`와 `eventually_async`를 추가했다.
- 예정된 `v0.1.0` distribution을 위한 PyPI preflight documentation을 추가했다.

### 변경

- Root README는 전체 planning model을 인라인으로 담는 대신 상세 planning 및 release state를 `WIP.md`, `CHANGELOG.md` 및 `docs/release.md`로 연결하도록 변경했다.
- GitHub Actions CI가 `uv build --all-packages`를 사용하여 모든 workspace distribution을 build하도록 변경했다.
