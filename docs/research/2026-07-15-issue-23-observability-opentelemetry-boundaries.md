# Issue #23 Python Observability와 OpenTelemetry 경계

Issue: [#23](https://github.com/bluetape4k/bluetape-py/issues/23)
Milestone: `0.2.0`
Date: 2026-07-15

## 결정

`bluetape-logging`, `bluetape-resilience`, `bluetape-cache`, provider package는 OpenTelemetry dependency 없이 유지합니다. 각 package의 local event와 context contract가 source of truth입니다.

Issue #24를 진행한다면 별도의 opt-in `bluetape-observability` distribution을 canonical bridge boundary로 사용합니다. Production dependency는 `opentelemetry-api`로 제한하고 domain-specific bridge module이 Redis 또는 다른 provider package를 base install으로 끌어오지 않게 합니다. 향후 `bluetape[observability]` meta extra가 이 distribution을 전달할 수 있지만 logging은 tracing/metrics owner가 아니므로 `bluetape-logging` extra는 거부합니다.

Application이 `opentelemetry-sdk`, provider, processor와 reader, sampling, exporter, endpoint, credential, resource detection, propagator 선택, shutdown을 소유합니다. Bluetape package와 bridge는 global provider를 설치하거나 교체하거나 exporter를 만들거나 telemetry network I/O를 수행하거나 exporter queue와 background worker를 소유하지 않습니다.

검토한 Python status에서 OpenTelemetry Logs는 여전히 Development signal입니다. 따라서 첫 bridge slice는 stable public Logs API를 약속하지 않아야 합니다. Signal과 repository의 concrete use case가 성숙할 때까지 stdlib logging example은 application-owned로 둡니다.

이 research decision은 implementation을 승인하지 않습니다. Code를 추가하기 전에 issue #24가 정확한 package metadata, bridge API, optional dependency group, test, release impact를 정의해야 합니다.

## 현재 repository contract

| Surface | 현재 contract | 결정 |
|---|---|---|
| `bluetape.logging` | Stdlib `logging`, private `ContextVar` 하나, caller가 제공하는 context field, redaction helper. | stdlib-only로 유지합니다. Logging context를 OpenTelemetry context나 baggage store로 바꾸지 않습니다. |
| `PolicyEvent` | Immutable typed resilience event를 callable observer로 inline 전달합니다. Observer failure는 policy cleanup 후 전파합니다. | Package-local로 유지하고 failure semantics를 보존합니다. Bridge가 event를 대체하거나 넓히지 않습니다. |
| `RedisEvent` | Low-cardinality immutable terminal provider event를 `RedisObserver`로 전달합니다. Observer failure는 provider result를 바꾸지 않습니다. | Package-local로 유지하고 failure isolation을 보존합니다. |
| `RedisCoordinationEvent` | Bounded counter와 `cleanup_failed`를 가진 redacted immutable coordination event. | Package-local로 유지하고 allowlist field만 telemetry로 매핑합니다. |
| `bluetape.cache` | Stable public telemetry event contract가 없습니다. | Generic bridge에서 만들지 않습니다. Concrete cache requirement가 field와 lifecycle을 입증할 때만 local event를 추가합니다. |
| Leader election 및 AWS adapter | Stable Python package-local event contract가 없습니다. | Generic hook을 보류합니다. Concrete lifecycle과 field requirement가 생긴 뒤 typed/redacted event를 정의하고 AWS SDK instrumentation은 application이 소유합니다. |
| Web middleware | Stable repository middleware contract가 없습니다. | Generic hook을 보류합니다. Framework adapter가 request lifecycle과 carrier injection/extraction을 소유하고 future package-local event는 독립적으로 정당화해야 합니다. |

Observer shape와 failure rule은 의도적으로 다릅니다. Universal event union, global observer registry, shared async dispatcher는 domain contract를 지우고 현재 owning package에 없는 lifecycle behavior를 추가합니다.

## Issue #24를 위한 최소 bridge contract

1. Production에서는 `opentelemetry-api`만 의존합니다. SDK package는 application integration을 입증하는 test와 example에서만 허용합니다.
2. API로 named/versioned tracer 또는 meter를 얻습니다. Test와 application composition을 위해 명시적인 provider injection을 허용하되 global을 설정하지 않습니다.
3. 기존 package-local event를 class, observer signature, ordering, synchrony, cleanup, failure behavior를 바꾸지 않고 adapt합니다.
4. Typed enum, boolean, bounded numeric field의 fixed allowlist를 사용합니다. Raw key/value, argument, result, exception text, URL, credential, request/user/account/session identifier, arbitrary logging context는 제외합니다. Caller-controlled name은 caller가 bounded cardinality를 명시적으로 보장할 때만 metric attribute로 사용합니다.
5. Bridge instrumentation failure가 보호되는 domain operation을 바꾸지 않게 합니다. 임의 caller observer는 각 package의 기존 failure semantics를 유지하지만 bridge adapter는 observer boundary를 통해 돌아가기 전에 자체 OpenTelemetry/API error를 containment해야 합니다. Isolation을 위해 package-owned queue, retry, exporter, detached task를 추가하지 않습니다.
6. Trace context, baggage, logging context를 구분합니다. Baggage 또는 logging field를 span, metric, log attribute로 승격하는 것은 명시적 allowlist를 따라야 하며 자동으로 하지 않습니다.
7. Transport propagation을 정의하지 않습니다. HTTP, messaging, job, RPC boundary의 carrier injection/extraction은 framework와 application adapter가 소유합니다.

## Python 3.13 context 호환성

- `asyncio.Task`는 생성 시 현재 `contextvars.Context`를 복사합니다. Task-local 변경은 다른 task의 context를 바꾸지 않으며 explicit task context는 caller-owned입니다.
- `asyncio.to_thread()`는 현재 context를 worker thread로 전파합니다.
- Raw thread와 `loop.run_in_executor()`에는 같은 propagation guarantee가 없습니다. 전파가 필요하면 `copy_context()`를 capture하고 concurrent call마다 별도의 `ctx.run(...)`을 submit합니다.
- `copy_context()`는 O(1)이지만 하나의 `Context`는 concurrent 또는 recursive하게 enter할 수 없습니다. 동일한 captured object를 concurrent submission에 재사용하면 안 됩니다.
- Callback, detached/background work, transport boundary는 context를 capture, clear, reconstruct하는지 문서화해야 합니다. Cancellation cleanup은 package-owned `ContextVar` token을 reset해야 합니다.

`bluetape.logging`은 local logging field에 `contextvars`를 계속 사용해야 합니다. Active OpenTelemetry context는 별도의 execution-scoped contract이며 arbitrary log field를 위한 replacement dictionary가 아닙니다.

## Metric과 민감 데이터 policy

OpenTelemetry SDK cardinality limit은 overflow guard이지 design target이 아닙니다. Bridge metric은 fixed attribute key와 low-cardinality value를 사용합니다. 기존 typed event enum과 boolean은 후보가 될 수 있지만 raw identifier와 caller payload는 대상이 아닙니다.

Baggage는 process 밖으로 전파될 수 있고 기본 integrity guarantee가 없습니다. Credential, access token, Redis key, exception text, health/financial data, 기타 sensitive value를 baggage에 넣거나 telemetry attribute로 자동 복사하지 않습니다. Application은 untrusted boundary 전에 baggage를 비울 수 있습니다.

## 향후 bridge 필수 검증

- SDK를 설정하지 않은 API-only smoke test에서도 instrumentation이 유효한 no-op이어야 합니다.
- Global provider를 변경하지 않는 explicit injected-provider test.
- Attribute allowlist, cardinality, redaction, hostile marker test.
- 기존 observer ordering/failure semantics를 바꾸지 않는 sync/async event mapping parity.
- Normal task creation, explicit task context, `asyncio.to_thread()`, raw thread, 명시적 `copy_context()`를 사용하는 `run_in_executor()`, cancellation, context cleanup에 대한 Python 3.13 test.
- 승인된 package policy가 명시적으로 바뀌지 않는 한 default `bluetape`, `bluetape-logging`, `bluetape-resilience`, cache, Redis, `dev`, `all` install에 OpenTelemetry dependency가 추가되지 않음을 입증하는 packaging test.
- Logs-facing API 전에 version recheck. 검토한 signal은 stable하지 않습니다.

## 거부한 대안

| Alternative | 거부 이유 |
|---|---|
| Canonical integration으로 `bluetape-logging[otel]` | Trace와 metric을 logging ownership에 결합하고 logging context를 telemetry context로 오해하게 합니다. |
| Domain package에 OpenTelemetry dependency 추가 | stdlib/provider isolation을 깨고 generic domain behavior가 telemetry stack에 의존하게 합니다. |
| SDK, exporter, collector endpoint, shutdown 소유 | Application과 operator가 결정하는 lifecycle입니다. |
| Universal event 또는 observer facade | 기존 package가 서로 다른 event field와 observer-failure contract를 갖습니다. |
| Logging-context 또는 baggage 자동 승격 | Cardinality, privacy, trust-boundary risk를 만듭니다. |
| 첫 slice의 stable OTel Logs bridge | 검토한 Python signal이 여전히 Development입니다. |

## Non-goal

- Vendor backend 또는 collector 선택.
- Exporter retry, batching, buffering, shutdown management.
- Automatic instrumentation 또는 monkey-patching.
- Framework middleware, HTTP/message carrier propagation, cross-process baggage policy.
- Existing package event contract 대체.
- Generic logging facade 또는 package-owned global logger state 추가.

## Source

공식 Python source:

- [Python 3.13 `asyncio` tasks and `to_thread`](https://docs.python.org/3.13/library/asyncio-task.html)
- [Python 3.13 `contextvars`](https://docs.python.org/3.13/library/contextvars.html)
- [Python 3.13 `run_in_executor`](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.run_in_executor)
- [PEP 567 thread-offloading guidance](https://peps.python.org/pep-0567/#offloading-execution-to-other-threads)

공식 OpenTelemetry source:

- [OpenTelemetry Python repository](https://github.com/open-telemetry/opentelemetry-python)
- [Python manual instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [Python status](https://opentelemetry.io/docs/languages/python/)
- [Library instrumentation guidance](https://opentelemetry.io/docs/concepts/instrumentation/libraries/)
- [Client library design principles](https://opentelemetry.io/docs/specs/otel/library-guidelines/)
- [Context specification](https://opentelemetry.io/docs/specs/otel/context/)
- [Python propagation](https://opentelemetry.io/docs/languages/python/propagation/)
- [Baggage concepts](https://opentelemetry.io/docs/concepts/signals/baggage/)
- [Baggage API](https://opentelemetry.io/docs/specs/otel/baggage/api/)
- [Metrics cardinality limits](https://opentelemetry.io/docs/specs/otel/metrics/sdk/#cardinality-limits)
- [Handling sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/)

Repository와 sibling 근거:

- `packages/bluetape-logging/src/bluetape/logging/__init__.py`
- `packages/bluetape-resilience/src/bluetape/resilience/_core.py`
- `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py`
- [`bluetape-go` issue #275 observability scope](https://github.com/bluetape4k/bluetape-go/blob/develop/docs/research/2026-06-26-issue-275-observability-scope.md)
- [`bluetape-go` issue #422 OTel bridge guidance](https://github.com/bluetape4k/bluetape-go/blob/develop/docs/research/2026-07-09-issue-422-otel-bridge-guidance.md)
- [`bluetape-go` issue #21 observability hook spec](https://github.com/bluetape4k/bluetape-go/blob/develop/docs/superpowers/specs/2026-06-03-issue-21-observability-hooks-spec.md)

## Version과 retrieval note

- 2026-07-15에 Python 3.13 documentation을 기준으로 가져왔습니다.
- 검토한 OpenTelemetry specification은 `1.59.0`이며, 공식 Python repository는 2026-06-24 날짜의 [`1.43.0` / `0.64b0`](https://github.com/open-telemetry/opentelemetry-python/releases/tag/v1.43.0)를 최신 release로 열거했습니다.
- Issue #24를 구현하기 전에 OpenTelemetry version과 signal maturity를 갱신해야 합니다. 외부 image는 필요하지 않았습니다.
