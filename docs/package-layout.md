# Package Layout Policy

## 목표

- public package를 작고 Python-native이며 독립적으로 유용하게 유지합니다.
- 모든 것을 담는 catch-all utility package를 만들지 않습니다.
- default `bluetape` install을 얇게 유지합니다.
- 광범위한 wrapper를 추가하기 전에 Python standard library와 집중된 optional dependency를 우선합니다.
- 명확한 public contract가 생길 때까지 implementation detail을 private으로 유지합니다.

## Public distribution

Distribution은 `packages/` 아래에 두고 집중된 import path에 대응시킵니다.

Current public distributions: 현재 public distribution:

- `bluetape`
- `bluetape-async`
- `bluetape-audit`
- `bluetape-cache`
- `bluetape-cache-redis`
- `bluetape-leader`
- `bluetape-leader-redis`
- `bluetape-codec`
- `bluetape-collections`
- `bluetape-compression`
- `bluetape-core`
- `bluetape-id`
- `bluetape-jwt`
- `bluetape-logging`
- `bluetape-measure`
- `bluetape-money`
- `bluetape-observability`
- `bluetape-resilience`
- `bluetape-serde`
- `bluetape-testing`

Private workspace distributions: Private workspace distribution:

- `bluetape-benchmark`는 `bluetape.benchmark`를 소유합니다. 표준 라이브러리 전용이며 workspace와 함께 build/test하지만 source-only이고 모든 publish allowlist와 meta extra에서 금지합니다. `Private :: Do Not Upload` classifier는 defense in depth이며 release-selection mechanism이 아닙니다.

`bluetape` distribution은 meta package입니다. root `bluetape/__init__.py` import surface를 만들지 않습니다. 집중 package는 `bluetape.core`, `bluetape.logging`, `bluetape.testing`처럼 각자 import path를 소유합니다. async package는 `bluetape.asyncio`, codec은 `bluetape.codec`, collections는 `bluetape.collections`, compression은 `bluetape.compression`을 소유합니다. Serde는 `bluetape.serde`를 소유하며 focused `bluetape-serde` distribution 또는 명시적인 향후 `serde` meta extra에서만 제공하고 core-only default install에는 포함하지 않습니다. Async package는 cooperative ownership, cancellation, timeout, cleanup 동작을 문서화해야 하며 compression package는 wire format, output bound, malformed-input error, optional backend availability를 문서화해야 합니다.

`bluetape-compression`의 provider-free base distribution은 gzip, zlib-wrapped, raw-DEFLATE를 지원합니다. 구조적 `Compressor` Protocol은 inheritance 없이 application-owned implementation을 허용합니다. LZ4 frame, raw Snappy, Zstandard frame implementation은 `bluetape.compression.native` 아래에 있으며 `lz4`, `snappy`, `zstd` focused extra 또는 aggregate `native` extra가 필요합니다. Meta distribution은 이를 `compression-lz4`, `compression-snappy`, `compression-zstd`, `compression-native`으로 전달하지만 default, `dev`, `all` dependency set에는 넣지 않습니다. 누락된 provider는 package 또는 native namespace를 import할 때가 아니라 해당 compressor를 생성할 때 실패합니다.

모든 bundled decompressor는 음이 아닌 logical output bound를 강제하고 invalid 또는 incomplete payload를 거부하며 payload를 포함한 error message나 log를 남기지 않습니다. Application composition은 명시적이어야 합니다. serialize한 뒤 compress하고 store하며, 읽을 때는 deserialize 전에 decompress합니다. Sibling language implementation은 feature와 failure rule의 semantic reference일 뿐 cross-language wire-compatibility를 보장하지 않습니다.

`bluetape-cache`는 `bluetape.cache`를 소유하며 focused distribution 또는 명시적인 `bluetape[cache]` meta extra에서 제공합니다. 표준 라이브러리 전용 bounded sync/async local TTL loading cache를 제공하고 core-only default meta install에는 포함하지 않으며 root `bluetape` import surface를 추가하지 않습니다.

`bluetape-jwt`는 `bluetape.jwt`를 소유하고 focused distribution 또는 `bluetape[jwt]`에서 제공합니다. 정확히 `bluetape-cache==0.1.0`과 `joserfc>=1.7.4,<2`에 의존하며 default meta install은 core-only입니다. Strict synchronous JWS issue/verify, immutable claim/profile, in-memory active/retired/revoked key lifecycle, optional bounded verified-result cache, issuance-policy decorator를 제공합니다. JWS payload는 계속 읽을 수 있습니다. Async provider, JWE encryption, versioned compression envelope는 후속 issue #88, #89, #90으로 남깁니다.

`bluetape-cache-redis`는 `bluetape.cache.redis`를 소유합니다. 부모 `bluetape.cache` package가 namespace path를 확장하므로 focused Redis wheel이 `bluetape-cache`에 Redis를 추가하지 않고 nested import를 제공할 수 있습니다. 이 package는 direct focused install 또는 `bluetape[cache-redis]`로만 제공하며 `bluetape-cache==0.1.0`, redis-py, serde, compression에 의존하고 default, `dev`, `all` dependency set에서는 제외합니다.

Milestone release는 lock과 wheel metadata의 정확한 cache pin을 조정한 뒤 `bluetape-cache` artifact를 publish하고 검증한 다음 `bluetape-cache-redis`를 처리해야 합니다.

Redis surface는 byte-only이며 application serialization, compression, key naming, rollout policy를 명시적으로 유지합니다. 내장 binary와 JSON v1 envelope는 complete parsing과 encoded-size bound를 강제합니다. Sync/async provider는 positive TTL write, atomic `SET NX PX`, 고정된 Lua compare-and-delete operation을 사용하고 race가 있는 fallback을 두지 않습니다. Factory가 만든 client는 package가 소유하고 constructor로 주입된 client는 borrowed로 취급합니다. Issue #55는 expiring Redis lease, atomic token-checked publication, bounded polling, 명시적 failure semantics를 사용하는 bounded sync/async same-key load coordination을 추가합니다. 이는 L2 cache, fencing primitive, distributed invalidation system이 아닙니다.

`bluetape-leader`는 표준 라이브러리 전용 `bluetape.leader` namespace, generic option, lease, result value, sanitized error, sync/async protocol을 소유합니다. 직접 또는 `bluetape[leader]`로 제공하며 default meta install은 core-only입니다. Redis에 의존하지 않고 backend-specific timing, topology, key behavior를 정의하지 않습니다.

`bluetape-leader-redis`는 namespace를 `bluetape.leader.redis`로 확장합니다. 정확히 `bluetape-leader==0.1.0`과 `redis==8.0.1`에 의존하고 direct install 또는 명시적인 `bluetape[leader-redis]` extra로 제공합니다. default, `dev`, `all` set에는 포함하지 않습니다. 첫 slice는 하나의 authoritative writable single-primary, 정확한 borrowed client, bounded operation, owner-checked Lua lifecycle, fencing token을 지원합니다. Redlock, Sentinel, Cluster, multi-primary routing, group lock, strategic election, 추가 backend는 별도 future work입니다.

`bluetape-serde`는 strict JSON v1 contract를 위해 표준 라이브러리만 사용합니다. root public surface는 `bluetape.serde`에서 import하며 25개 ordered export와 안정적인 `SerdeErrorCode` 23개로 고정합니다. JSON integer는 encode와 decode에서 640 decimal digit로 제한합니다. Apache Fory adapter는 provider-dependent `bluetape.serde.fory` module에 있고 CPython 3.13의 `bluetape-serde[fory]` 또는 forwarding `bluetape[fory]` extra에서만 제공합니다. base, `serde`, `dev`, `all` dependency set으로 유출하거나 implicit decoder fallback으로 만들지 않습니다.

`bluetape-resilience`는 `bluetape.resilience`를 소유하고 focused distribution 또는 명시적인 `bluetape[resilience]` meta extra로 제공합니다. 표준 라이브러리 전용이며 sync/async retry, circuit breaker, bulkhead policy family를 분리하고 cooperative async timeout과 immutable fluent pipeline을 제공합니다. core-only default install에는 포함하지 않습니다. synchronous timeout, hidden worker, detached task, reset scheduler, global registry, package-owned logger를 추가하지 않습니다. Policy instance는 자체 state/capacity를 유지하고 pipeline은 caller가 명시적으로 보유한 instance를 유지할 때만 이를 공유합니다.

`bluetape-observability`는 `bluetape.observability`를 소유하고 직접 설치한 focused distribution으로만 제공합니다. runtime에 `opentelemetry-api`가 필요하며 resilience, Redis, OpenTelemetry SDK, provider, exporter, shutdown lifecycle은 caller가 소유합니다. default meta install이나 어떤 meta extra에도 포함하지 않습니다.

Application은 Fory route identity를 고정된 `(schema_id, schema_version, type_id)` tuple로 소유하고 하나의 정확한 registered root type에 매핑합니다. Schema 변경에는 새 tuple과 versioned route, reader-first deployment, 명시적 compatibility review, 기존 reader를 retire하기 전 drain evidence가 필요합니다. Fory는 trusted-internal 전용이며 hard CPU/RSS containment는 byte limit만으로 해결하지 말고 별도 constrained process에 둡니다.

`bluetape-id`, `bluetape-measure`, `bluetape-money`는 독립적인 표준 라이브러리 전용 value distribution이며 명시적인 `id`, `measure`, `money`, aggregate `values` meta extra로 제공합니다. 어느 것도 core-only default install에 들어가지 않습니다. Identifier는 canonical string으로 저장하고 monotonic generator state는 process-local이며 restart, fork, upgrade, rollback 때 reset됩니다. Measure는 정확한 versionless `amount`/`unit` primitive schema로 저장하고 application이 custom immutable unit definition을 소유하여 deserialize할 때 제공합니다. Money는 정확한 versionless `amount`/`currency` schema로 저장하고 committed current ISO 4217 snapshot을 사용합니다. Historical currency policy와 모든 exchange-rate source, freshness rule, cache, lifecycle은 application이 소유합니다.

KSUID는 구체적인 compatibility consumer가 생길 때까지 보류합니다. Snowflake ID, compound/affine measurement, locale money, provider-backed FX는 구현 전에 각각 source-backed design issue가 필요합니다.

## Future package

새 distribution은 다음 조건을 갖출 때만 만듭니다.

- 명확한 domain boundary;
- package README documentation;
- success, failure, boundary behavior test;
- dependency와 extra impact의 명시;
- user-facing scope에 영향을 주면 root README와 WIP에 노출.

Optional integration은 default `bluetape` dependency list에 넣지 않습니다. 무거운 capability는 extra 또는 direct focused distribution install을 사용합니다.

Issue #14는 세 가지 data boundary를 확립했습니다.

- `bluetape-sql`은 `bluetape.sql` 아래에서 SQLAlchemy Core 2.x sync/async helper를 소유할 수 있습니다. Helper는 caller-owned transaction-bound `Connection` 또는 `AsyncConnection`을 받고 engine, pool, commit, rollback, migration, ORM session, generic repository lifecycle을 소유하지 않습니다.
- `bluetape-audit`은 `bluetape.audit` 아래에서 표준 라이브러리 전용 immutable audit value, 명시적 bounded validation, safe error, deterministic preservation helper를 소유합니다. Serialization, SQL schema, repository, transaction, durable history store, outbox, relay process, broker는 소유하지 않습니다. Caller-owned adapter가 첫 side effect 직전에 authoritative validation을 수행합니다.
- Issue #77의 focused PostgreSQL audit adapter는 transactional enqueue와 bounded outbox claim/mark 동작을 소유할 수 있습니다. At-least-once delivery와 duplicate 가능성을 문서화하고 caller-driven relay execution을 사용하며 hidden worker나 scheduler를 두지 않습니다.

Psycopg는 PostgreSQL DB-API baseline이자 escape hatch이고 asyncpg는 처음 검증된 SQLAlchemy async driver입니다. 어느 것도 두 번째 public query toolkit을 만들지 않습니다. 첫 conformance backend는 PostgreSQL뿐입니다. 추가 database에는 각각 source-backed design과 test가 필요합니다.

## Internal code

Public API가 아닌 implementation detail은 package-local private module을 사용합니다. 예시는 다음과 같습니다.

- 공용이 아닌 validation internal;
- serializer/compressor implementation detail;
- 사용자에게 공개하지 않는 fixture helper;
- public API가 정착하기 전의 compatibility shim.

사용자가 import해야 한다면 docs와 test를 갖춘 public package에 포함해야 합니다.

## Package documentation

모든 public package는 release-ready로 보기 전에 다음 package documentation을 갖춰야 합니다.

- package purpose;
- primary API example;
- 관련된 경우 sync/async ownership rule;
- exception과 error semantics;
- dependency와 optional-extra note;
- 해당되는 경우 sibling bluetape4k, bluetape-go, bluetape-rs 동작과의 compatibility note.

## 예시

실제 backend 문제를 해결하는 예시를 우선합니다.

- API boundary의 validation;
- request/task log context;
- test의 eventual consistency wait;
- cache loading과 invalidation;
- resilience policy wrapping;
- Testcontainers 기반 integration fixture;
- SQL transaction과 outbox handoff pattern.
