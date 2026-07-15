# Issue #24 Observability Adapters Design

Date: 2026-07-15 KST
Target issue: #24 - `feat: add observability hooks and telemetry helpers`
Target milestone: `0.2.0`
Research prerequisite: #23

## Problem

`bluetape-py`의 resilience와 Redis 패키지는 이미 호출자가 주입할 수 있는 typed
observer event를 제공하지만, 이 event를 OpenTelemetry trace와 metric으로 안전하게
변환하는 Python-native integration package는 없다. 애플리케이션이 매번 직접 bridge를
작성하면 event 의미와 metric 이름이 달라지고, Redis key나 policy name 같은
고카디널리티·민감 값을 attribute로 승격하거나, telemetry 실패가 보호 대상 호출의
결과를 바꾸는 문제가 생길 수 있다.

이 이슈는 별도 focused distribution인 `bluetape-observability`와 기존 observer 계약에
맞는 세 어댑터를 추가한다. 첫 버전은 현재 저장소에 실제로 존재하는 `PolicyEvent`,
`RedisEvent`, `RedisCoordinationEvent`만 연결한다. OpenTelemetry SDK, exporter, 전역
provider, logging bridge, 새로운 domain hook은 애플리케이션 또는 후속 이슈의
소유권으로 남긴다.

## Current Evidence

- GitHub issue #24는 thin default install, optional telemetry dependency isolation,
  sync/async context tests, logging 및 향후 service-package integration 문서를 요구한다.
- Issue #23 연구는 instrumented library가 `opentelemetry-api`에만 의존하고 application이
  SDK, provider, exporter, sampling, endpoint, shutdown을 소유하는 경계를 채택했다.
- `packages/bluetape-resilience/src/bluetape/resilience/_core.py`의 `PolicyEvent`는
  frozen/slotted typed event이며 observer는 `Callable[[PolicyEvent], None]`이다. 일반
  observer 오류는 현재 호출자에게 전파되므로 이 integration adapter 자체가 telemetry
  오류를 격리해야 한다.
- `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py`의 `RedisEvent`와
  `RedisCoordinationEvent`는 이미 low-cardinality terminal observation으로 정의된다.
  sync/async Redis provider와 coordination 구현은 같은 observer protocol을 사용한다.
- `packages/bluetape-logging`은 stdlib `logging`과 `contextvars`만 소유한다. logging context를
  OTel baggage 또는 span/metric attribute로 자동 승격하는 계약은 없다.
- OpenTelemetry Python은 traces와 metrics를 stable로 표시하고 logs를 development로
  표시한다. 공식 library guidance는 library가 API에만 의존하고 provider injection을
  허용하며 SDK configuration은 application에 남기도록 안내한다.
- 2026-07-15 확인 기준 OpenTelemetry Python 최신 stable API/SDK release는 `1.43.0`이며,
  이 설계는 `opentelemetry-api>=1.43,<2` 호환선을 사용한다.

Primary references:

- [Issue #24](https://github.com/bluetape4k/bluetape-py/issues/24)
- [Issue #23 research](../../research/2026-07-15-issue-23-observability-opentelemetry-boundaries.md)
- [OpenTelemetry library instrumentation guidance](https://opentelemetry.io/docs/concepts/instrumentation/libraries/)
- [OpenTelemetry Python status](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry Python 1.43.0 release](https://github.com/open-telemetry/opentelemetry-python/releases/tag/v1.43.0)

## Approved Scope Decisions

The user approved these decisions in sequence:

1. First release installation is the focused `pip install bluetape-observability`; no
   `bluetape[observability]` meta extra is added.
2. Use domain-native adapters matching the three existing observer shapes instead of a
   universal event facade or mapper-only toolkit.
3. Record a span event on the current span and fixed metrics; do not create synthetic spans
   after a terminal event has already occurred.
4. Use a fixed low-cardinality allowlist and exclude `policy_name`, raw errors, Redis data,
   logging context, baggage, and arbitrary caller attributes.
5. Keep production dependencies to `opentelemetry-api`; keep SDK and exporters out of the
   runtime dependency graph.
6. Cover API-only, SDK-injected, sync/async context, isolation, packaging, documentation,
   and compatibility behavior in tests and delivery evidence.

## Goals

1. Add `bluetape-observability` as a Python 3.13+ focused distribution with import modules
   under `bluetape.observability`.
2. Convert existing resilience and Redis typed events into stable OTel span events and
   metrics without changing their producers or observer protocols.
3. Preserve domain results when valid-event telemetry operations fail.
4. Keep attribute cardinality and sensitive-data exposure bounded by a closed allowlist.
5. Work in API-only environments and permit local `Meter` injection for deterministic tests
   and application composition.
6. Use the same adapters in sync and async call paths by reading the current OTel context at
   observer invocation time.
7. Register, build, document, and verify the new distribution without changing the default
   `bluetape` meta-package dependency set.

## Non-Goals

- `bluetape[observability]` or any other root meta-package extra
- OpenTelemetry SDK, exporter, collector, provider, sampler, reader, processor, endpoint,
  resource detector, view, propagation, or shutdown configuration
- OpenTelemetry Logs API/SDK bridge or stdlib logging handler
- automatic promotion of `bluetape.logging` context, OTel baggage, request metadata, or
  caller attributes
- new events or hooks for local cache, leader election, web adapters, AWS, infrastructure,
  or packages that do not yet expose a stable Python observer contract
- new spans around completed operations, automatic monkey-patching, transport propagation,
  queues, retry, background workers, detached tasks, or network I/O
- semantic-convention claims for custom Bluetape instrument and attribute names
- cross-language telemetry-name compatibility
- PyPI publication, release, tag, PR, or merge in the design step

## Chosen Architecture

The focused distribution has two public bridge modules and private shared recording helpers:

```text
packages/bluetape-observability/
├── pyproject.toml
├── README.md
├── README.ko.md
├── src/bluetape/observability/
│   ├── __init__.py
│   ├── resilience.py
│   ├── redis.py
│   └── _recording.py
└── tests/
```

- `resilience.py` owns the `PolicyEvent` mapping and callable observer.
- `redis.py` owns provider and coordination mappings plus `on_event` observers.
- `_recording.py` owns fixed OTel attribute normalization, current-span event recording,
  safe instrument construction, and isolated metric calls. It is not public.
- Domain event imports occur only under `TYPE_CHECKING`; runtime recording uses the stable
  structural fields already guaranteed by each producer. Installing the bridge therefore
  does not pull resilience or Redis distributions into an otherwise API-only environment.
- `bluetape.observability.__init__` does not re-export domain adapters. Callers import from
  the explicit `resilience` or `redis` module, keeping optional domain ownership visible. Its
  exact public export contract is an empty `__all__`.
- Adapter instances cache their instruments at construction and hold no per-call mutable
  state. They create no lock, registry, thread, task, queue, or network client.
- Every event first passes a closed fail-safe normalizer that returns bounded private scalar
  values or drops the whole event. Runtime structural access therefore does not turn arbitrary
  duck objects into an open attribute channel.

## Public API

### Resilience

```python
from opentelemetry.metrics import Meter

class OpenTelemetryPolicyObserver:
    def __init__(self, *, meter: Meter | None = None) -> None: ...
    def __call__(self, event: PolicyEvent) -> None: ...
```

Usage:

```python
from bluetape.observability.resilience import OpenTelemetryPolicyObserver
from bluetape.resilience import Retry

retry = Retry(
    name="catalog-read",
    max_attempts=3,
    observer=OpenTelemetryPolicyObserver(),
)
```

### Redis

```python
from opentelemetry.metrics import Meter

class OpenTelemetryRedisObserver:
    def __init__(self, *, meter: Meter | None = None) -> None: ...
    def on_event(self, event: RedisEvent) -> None: ...

class OpenTelemetryRedisCoordinationObserver:
    def __init__(self, *, meter: Meter | None = None) -> None: ...
    def on_event(self, event: RedisCoordinationEvent) -> None: ...
```

The exact public exports are:

- `bluetape.observability.resilience.__all__ = ["OpenTelemetryPolicyObserver"]`
- `bluetape.observability.redis.__all__ = ["OpenTelemetryRedisObserver",
  "OpenTelemetryRedisCoordinationObserver"]`

All constructors are keyword-only. Supplying `meter=None` obtains a versioned instrumentation
scope with `opentelemetry.metrics.get_meter("bluetape.observability", package_version)`, where
`package_version` is read once from `importlib.metadata.version("bluetape-observability")`.
Supplying a `Meter` uses that exact instance and never changes the global provider. There is no
tracer or provider setter: trace recording uses `opentelemetry.trace.get_current_span()` because
the adapter adds an event to caller-owned current work rather than starting a new span.

The first version has no feature flags, custom instrument names, custom attributes, callback,
or subclassing contract. Installing and passing an adapter is the explicit opt-in.

Every public module uses `from __future__ import annotations`, and domain event names are imported
only under `TYPE_CHECKING`. `inspect.signature()` therefore exposes postponed string annotations
without importing domain packages. Runtime `typing.get_type_hints()` without a caller-supplied
`globalns` mapping is not a supported introspection contract for these methods; tests pin both
the postponed signatures and API-only import behavior.

## Telemetry Data Flow

For each valid domain event, the adapter performs this bounded synchronous flow:

```text
domain producer
  -> existing inline observer call
  -> closed fail-safe normalization of every consumed field
  -> attempt current-span add_event
  -> independently attempt counter.add
  -> independently attempt histogram.record when the event has duration
  -> return None
```

The adapter does not retain events or defer work. It normalizes once into bounded private
scalars, builds the metric attribute mapping once only when at least one metric instrument was
created, and builds span-only detail only for a recording span. Span and metric recording are
isolated so one failed signal does not prevent attempting the other. An API no-op instrument
cannot be distinguished through the public OTel API, so an existing no-op instrument still
receives the bounded metric mapping. SDK/exporter execution behind OTel API calls remains
application-owned.

### Span events

| Domain event | Span event name |
|---|---|
| `PolicyEvent` | `bluetape.resilience.policy` |
| `RedisEvent` | `bluetape.redis.operation` |
| `RedisCoordinationEvent` | `bluetape.redis.coordination` |

The adapter calls `get_current_span()`, then records only when `span.is_recording()` is true.
No active or recording span is a valid trace no-op. Metric recording is still attempted.

### Metrics

| Instrument | Type | Unit | Recorded for |
|---|---|---|---|
| `bluetape.resilience.policy.events` | Counter | `{event}` | every `PolicyEvent` |
| `bluetape.redis.operations` | Counter | `{operation}` | every `RedisEvent` |
| `bluetape.redis.operation.duration` | Histogram | `s` | every `RedisEvent` |
| `bluetape.redis.coordination.operations` | Counter | `{operation}` | every `RedisCoordinationEvent` |
| `bluetape.redis.coordination.duration` | Histogram | `s` | every `RedisCoordinationEvent` |

Instrument construction is exact and occurs once during adapter construction:

```python
meter.create_counter(
    "bluetape.resilience.policy.events",
    unit="{event}",
    description="Number of observed Bluetape resilience policy events.",
)
meter.create_counter(
    "bluetape.redis.operations",
    unit="{operation}",
    description="Number of observed Bluetape Redis operations.",
)
meter.create_histogram(
    "bluetape.redis.operation.duration",
    unit="s",
    description="Duration of observed Bluetape Redis operations.",
)
meter.create_counter(
    "bluetape.redis.coordination.operations",
    unit="{operation}",
    description="Number of observed Bluetape Redis coordination operations.",
)
meter.create_histogram(
    "bluetape.redis.coordination.duration",
    unit="s",
    description="Duration of observed Bluetape Redis coordination operations.",
)
```

Redis duration is `elapsed_ns / 1_000_000_000`. Resilience events do not contain elapsed
execution time, so the bridge does not fabricate a duration metric. Retry delay, configured
timeout, attempts, in-flight count, and waiters may be span-event detail but are not metric
measurements or dimensions in v1.

## Attribute Contract

All attribute keys are package-owned and custom; the package does not claim that they are
OpenTelemetry semantic conventions.

### Resilience attributes

Metric and span-event allowlist:

- `bluetape.resilience.policy.type` from `policy_type.value`
- `bluetape.resilience.event.kind` from `kind.value`
- `bluetape.resilience.outcome` from `outcome.value` when present
- `bluetape.resilience.failure.category` from `failure_category.value`

Additional span-event-only detail when present:

- `bluetape.resilience.attempt`
- `bluetape.resilience.delay`
- `bluetape.resilience.timeout`
- `bluetape.resilience.state`
- `bluetape.resilience.previous_state`
- `bluetape.resilience.in_flight`
- `bluetape.resilience.waiters`

`delay` and `timeout` span-event attributes are seconds, matching the existing resilience
event contract. Integer count attributes preserve their existing event values.

`PolicyEvent.policy_name` is deliberately excluded from both signals. It is caller-controlled
and cannot be proven bounded or non-sensitive by the bridge.

Exact resilience mapping:

| Source field | Span event | Counter attributes | Transformation |
|---|---|---|---|
| `policy_name` | omitted | omitted | never read into telemetry |
| `policy_type` | `bluetape.resilience.policy.type` | same | closed `.value` string |
| `kind` | `bluetape.resilience.event.kind` | same | closed `.value` string |
| `outcome` | `bluetape.resilience.outcome` | same | closed `.value` or omit when `None` |
| `failure_category` | `bluetape.resilience.failure.category` | same | closed `.value` string |
| `attempt` | `bluetape.resilience.attempt` | omitted | positive exact `int`, or omit |
| `delay` | `bluetape.resilience.delay` | omitted | finite non-negative seconds `float`, or omit |
| `timeout` | `bluetape.resilience.timeout` | omitted | finite non-negative seconds `float`, or omit |
| `state` | `bluetape.resilience.state` | omitted | closed `.value` or omit |
| `previous_state` | `bluetape.resilience.previous_state` | omitted | closed `.value` or omit |
| `in_flight` | `bluetape.resilience.in_flight` | omitted | non-negative exact `int`, or omit |
| `waiters` | `bluetape.resilience.waiters` | omitted | non-negative exact `int`, or omit |

### Redis attributes

Provider metric and span-event allowlist:

- `bluetape.redis.mode`
- `bluetape.redis.operation`
- `bluetape.redis.outcome`
- `bluetape.redis.error.code` when present

Coordination additionally allows:

- `bluetape.redis.coordination.cleanup_failed`

Span-event-only numeric detail:

- `bluetape.redis.elapsed_ns`
- `bluetape.redis.coordination.attempts`
- `bluetape.redis.coordination.polls`

`bluetape.redis.elapsed_ns` remains an exact integer nanosecond value on the span event while
the histogram receives the converted floating-point seconds value.

Exact Redis provider mapping:

| Source field | Span event | Counter/histogram attributes | Histogram value |
|---|---|---|---|
| `mode` | `bluetape.redis.mode` | same | N/A; closed `.value` string |
| `operation` | `bluetape.redis.operation` | same | N/A; closed `.value` string |
| `outcome` | `bluetape.redis.outcome` | same | N/A; closed `.value` string |
| `error_code` | `bluetape.redis.error.code` | same | N/A; closed `.value` or omit |
| `elapsed_ns` | `bluetape.redis.elapsed_ns` | omitted | `elapsed_ns / 1_000_000_000` seconds |

Exact Redis coordination mapping uses the same mode/operation/outcome/error attribute keys and
the coordination-specific instrument names:

| Source field | Span event | Counter/histogram attributes | Histogram value |
|---|---|---|---|
| `mode` | `bluetape.redis.mode` | same | N/A; closed `.value` string |
| `operation` | `bluetape.redis.operation` | same | N/A; closed `.value` string |
| `outcome` | `bluetape.redis.outcome` | same | N/A; closed `.value` string |
| `error_code` | `bluetape.redis.error.code` | same | N/A; closed `.value` or omit |
| `attempts` | `bluetape.redis.coordination.attempts` | omitted | N/A; non-negative exact `int` |
| `polls` | `bluetape.redis.coordination.polls` | omitted | N/A; non-negative exact `int` |
| `cleanup_failed` | `bluetape.redis.coordination.cleanup_failed` | same | N/A; exact `bool` |
| `elapsed_ns` | `bluetape.redis.elapsed_ns` | omitted | `elapsed_ns / 1_000_000_000` seconds |

Numeric measurements never become metric attributes. Absent optional values are omitted,
not encoded as empty strings. The bridge never adds Redis keys, values, result payloads,
lease tokens, namespaces, raw exceptions, exception messages, stack traces, generated IDs,
logging context, baggage, or arbitrary caller attributes.

### Fail-safe normalization

Before any signal emission, the adapter reads and validates every field it consumes. A field
access or conversion that raises `Exception`, an unsupported enum value, an invalid scalar
type, a non-finite number, or an out-of-range integer drops the entire event and returns
`None`. No partial span or metric emission occurs for a rejected event. `BaseException` is not
caught.

- Enum-like `.value` fields must resolve to the exact closed value sets already published by
  the three domain events.
- `bool` is never accepted as an integer. Counts and `elapsed_ns` must be exact non-negative
  integers no greater than `2**63 - 1`; resilience `attempt` must additionally be positive.
- Resilience `delay` and `timeout` must be finite non-negative `int` or `float` values and are
  normalized to `float`. Optional values may be `None`.
- `cleanup_failed` must be an exact `bool`.
- Required fields may not be absent or `None`; optional fields are either validated or omitted.

This defensive behavior does not make arbitrary duck objects a supported public input. It
ensures that a forged or malformed object cannot create an open telemetry attribute channel or
change a protected domain call through an adapter exception.

## Error and Lifecycle Semantics

- Exact domain event producers remain unchanged and continue to validate event values.
- For a valid domain event, each OTel interaction catches `Exception` locally and returns
  `None`; `BaseException` subclasses such as `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit` are not swallowed.
- Default meter acquisition and every required instrument creation occur in the constructor.
  Any setup `Exception` propagates immediately and no usable adapter is returned. This is an
  application-wiring failure, not an inline domain-event failure, and is therefore observable
  without package logging, mutable health state, or a diagnostic callback.
- Current-span lookup, `is_recording`, `add_event`, counter `add`, and histogram `record` are
  isolated independently. A trace failure does not suppress metrics, and one metric failure
  does not suppress another metric call. Runtime calls retry naturally on the next domain event;
  a transient runtime failure does not disable an instrument.
- The package intentionally does not log telemetry failures. Logging here risks recursion and
  would make the bridge own application diagnostics. Applications observe SDK/exporter health
  through their OTel configuration.
- Adapter construction and calls create no owned resource and require no close, flush, or
  shutdown method. Application-owned providers/exporters retain lifecycle ownership.

Each domain API has one observer slot. V1 does not provide a fan-out/composite observer. Passing
an OTel adapter where another observer was installed replaces that observer. A caller that needs
both must own the composite function/object, call order, and failure policy; the OTel adapter
guarantees isolation only for its own runtime telemetry operations. Migration documentation must
warn against silently replacing an existing observer.

## Sync and Async Context Semantics

The same observer instance may be used by sync and async producers. It reads the current span
at the exact inline observer call, so normal Python `contextvars`/OTel context active in a sync
call or coroutine is observed without a separate async adapter.

This package does not promise automatic context propagation across raw threads,
`run_in_executor`, detached/background tasks, process boundaries, callbacks invoked after the
originating context ends, or remote transports. Applications must use the propagation behavior
and explicit context capture appropriate to those boundaries. `bluetape.logging.log_context`
and OTel context remain separate; README examples may show them used in the same request scope
but never copy values between them automatically.

## Package and Dependency Boundary

- Distribution: `bluetape-observability`
- Distribution version: `0.1.0`, matching the current independent workspace package line
- Import root: `bluetape.observability`
- Python: `>=3.13`
- Runtime dependency: `opentelemetry-api>=1.43,<2`
- Test-only dependency group: `bluetape-resilience==0.1.0`,
  `bluetape-cache-redis==0.1.0`, `opentelemetry-sdk>=1.43,<2`, `pytest>=8.4.0`,
  `pytest-asyncio>=1.1.0`
- Build backend: repository-standard `uv_build>=0.11.28,<0.12`
- No distribution extras in v1
- No root `bluetape[observability]` extra
- No dependency from the `bluetape` default distribution
- No runtime dependency on `bluetape-resilience`, `bluetape-cache-redis`, redis-py, SDK, or
  exporter packages

The focused distribution is the approved isolation mechanism for issue #24. It intentionally
replaces the issue's earlier extra-shaped wording: optionality is expressed by installing or
omitting `bluetape-observability`, not by adding a root or distribution extra.

Repository registration includes the root workspace dependency list, `tool.uv.sources`,
workspace members, `uv.lock`, package-layout policy, root README locale pair, WIP, changelog,
release/package inventories that enumerate public distributions, and CI package verification.
The root workspace dependency is development aggregation only and does not change metadata of
the published `bluetape` meta distribution.

## Testing Strategy

### API-only tests

- Import both public modules when `opentelemetry.sdk` and domain packages are unavailable.
- Construct every adapter with the API default meter and call it with valid structural event
  fixtures; calls return `None` without SDK configuration.
- Prove import does not configure or replace global trace/meter providers.
- Prove no domain or SDK module is imported as a side effect.
- Pass forged events and duck objects containing hostile strings, unsupported enum values,
  raising properties, booleans-as-integers, non-finite numbers, and integers beyond signed
  64-bit range; verify no signal emission and no escaping `Exception`.

### SDK-backed tests

- Inject a local SDK `Meter` backed by an in-memory metric reader; never call global provider
  setters in tests.
- Create a span from a local tracer provider and activate it with `use_span`; verify the exact
  span event names and allowlisted attributes.
- Verify counters, duration histograms, units, nanosecond-to-second conversion, and the absence
  of forbidden dimensions.
- Verify the meter instrumentation scope name and version are `bluetape.observability` and
  the installed `bluetape-observability` distribution version.
- Verify `inspect.signature()` exposes postponed domain annotations without runtime domain
  imports and document that raw `get_type_hints()` without explicit globals is unsupported.
- Verify every exact instrument name, type, unit, description, and construction call.
- Exercise the observer in an ordinary sync scope and inside an async coroutine; both must
  attach to the correct current span without separate adapter types.
- Construct actual `PolicyEvent`, `RedisEvent`, and `RedisCoordinationEvent` instances from the
  test-only domain dependencies and verify observer protocol compatibility.

### Failure-isolation tests

- Throw from current-span operations, counter creation/add, and histogram creation/record using
  controlled fakes; verify independent channels are still attempted and valid domain calls do
  not receive those `Exception` values.
- Throw `KeyboardInterrupt` from a controlled telemetry fake and verify it propagates.
- Make meter acquisition and each instrument-construction call raise; verify adapter construction
  fails immediately without setting globals or returning a partial instance.
- Verify no exception logging or background work appears.

### Performance acceptance

A stdlib benchmark script runs all three adapters after warmup against an empty-observer
baseline. It records three same-process runs on CPython 3.13.14 and reports median and p95
incremental latency per event.

- API-only/no-recording-span path: median increment at most `25 us`, p95 at most `75 us`.
- Local in-memory SDK path: median increment at most `150 us`, p95 at most `500 us`.
- API-only steady state: after construction and warmup, 100,000 calls followed by collection
  retain at most `64 KiB` above the baseline observer in `tracemalloc`.
- Static and runtime evidence must show zero package-owned locks, threads, tasks, queues, and
  event retention.

Timing budgets are recorded implementation evidence rather than ordinary CI assertions because
shared runners are noisy. A budget exceeded in two of three same-environment runs is a Step 4-P
blocker requiring optimization or explicit spec reapproval. Allocation and ownership checks
remain deterministic test/inspection gates.

### Packaging and integration tests

- Build all packages and inspect `bluetape-observability` wheel metadata.
- Install the wheel with API only in an isolated environment; verify imports and no SDK/domain
  package presence.
- Run focused package tests with its test dependency group so SDK-backed tests cannot silently
  skip in the dedicated CI job.
- Run full workspace tests, Ruff checks, format checks, `actionlint`, and `git diff --check`.
- Recheck the default `bluetape` wheel in isolation and prove it does not contain or depend on
  observability or OTel packages.

## Documentation Contract

- `packages/bluetape-observability/README.md` and `README.ko.md` explain purpose, direct install,
  API-only/SDK ownership, three adapters, exact metric/span-event names, cardinality/privacy
  boundary, sync/async context behavior, and unsupported propagation boundaries.
- Root `README.md` and `README.ko.md` add the focused distribution to the package inventory and
  show direct installation without adding it to the default meta install.
- Examples show resilience and Redis observer wiring and show `log_context` coexisting with an
  active span without automatic value promotion.
- README examples are explicitly split into an API-only safe-no-op path and a runnable local
  SDK-backed recording path. The latter installs `opentelemetry-sdk`, creates an
  application-owned provider/reader/exporter and injected meter, wires both Redis adapter types,
  and warns that production exporter selection and shutdown remain application-owned.
- Failure guidance distinguishes fail-fast constructor wiring errors from isolated per-event
  recording errors, states that the bridge exposes no mutable health/callback surface, and points
  operators to application-owned SDK/exporter diagnostics for delivery health.
- Migration guidance states that v1 has no observer fan-out helper, warns that assigning the
  adapter replaces an existing observer, and leaves caller-owned composition order/failure
  policy explicit.
- Package and root README locale pairs place an `English | 한국어` switch directly below the
  title and keep installation commands, examples, non-goals, logging coexistence, migration,
  rollback, and failure behavior source-equivalent.
- The logging coexistence example proves both directions are separate: logging context is not
  promoted to telemetry attributes, and active trace/span IDs do not enter stdlib log records
  without separate application logging configuration.
- `docs/package-layout.md` records the new focused distribution and dependency boundary.
- `CHANGELOG.md` records completed user-facing behavior; `WIP.md` reconciles issue #24 and the
  milestone roadmap.
- Any release inventory, publish allowlist, or release smoke-test package list that enumerates
  public distributions is updated. Publication, tag, release, and workflow dispatch remain out
  of scope.

## Failure Modes and Required Behavior

| Failure mode | Required behavior |
|---|---|
| No SDK/provider is configured | API calls remain safe no-ops; domain call behavior is unchanged. |
| No current recording span exists | Span event is skipped; metric recording is still attempted. |
| Current span or custom SDK raises `Exception` | The failing signal call is isolated; remaining metric calls are still attempted. |
| Meter acquisition or metric instrument construction fails | Adapter construction fails immediately; application wiring handles retry or fallback before installing the observer. |
| Exporter/provider work is slow | The bridge adds no worker, timeout, retry, or queue; application owns SDK performance and configuration. |
| Caller uses sensitive/high-cardinality policy names or logging context | Those values are never promoted by the fixed mapper. |
| Adapter is invoked from async code | Current coroutine context is read inline; no task is spawned or retained. |
| Work crosses an unsupported thread/process/transport boundary | No implicit propagation is promised; application must propagate explicitly. |
| `KeyboardInterrupt` or another `BaseException` occurs | It propagates and is never converted into a telemetry no-op. |
| A future domain event adds new fields | New fields are ignored until explicitly reviewed and allowlisted; existing mapping remains compatible. |
| A forged or malformed event reaches the adapter | Closed normalization drops the whole event before emission and suppresses only ordinary `Exception`. |

## Alternatives Considered

### One universal `OpenTelemetryObserver`

Rejected because resilience uses a callable while Redis uses `on_event` protocols. A universal
facade would rely on overloads/runtime dispatch, couple unrelated packages, and become the
generic hook abstraction that issue #23 explicitly avoided.

### Mapper functions only

Rejected because returning attribute dictionaries or recording commands leaves callers to
repeat OTel instrument creation, names, units, error isolation, and current-span behavior. It
does not provide the telemetry helper promised by issue #24.

### Modify existing domain packages or add OTel extras to them

Rejected because it would place OTel dependencies and lifecycle assumptions into stdlib-first
or provider-focused packages. The separate distribution keeps opt-in ownership explicit.

### Create a span per terminal event

Rejected because the observer runs after the operation outcome is known and does not own its
start time. A short post-operation span would misrepresent duration and parentage. Adding an
event to the caller's current span preserves ownership.

### Include policy names or arbitrary attributes

Rejected because the bridge cannot prove caller-controlled values are bounded or non-sensitive.
Closed allowlists are safer and keep metric cardinality reviewable.

### Add OpenTelemetry Logs or a stdlib logging bridge

Rejected for the first slice because OTel Python logs remain development and issue #23 kept
logging context separate. Documentation covers coexistence without creating a signal bridge.

## Compatibility and Migration

This is an additive distribution. Existing packages, constructors, event fields, observer
protocols, error ordering, and runtime dependencies do not change. Applications migrate by
installing the focused package and passing one adapter into an otherwise empty observer slot.
Applications with an existing observer must retain it through caller-owned explicit composition
or defer adoption; replacing the observer is not presented as a behavior-preserving migration.
Removing the adapter restores the exact prior behavior; there is no stored data, schema,
background state, or rollback migration.

Future adapters may be added only after the source package exposes a stable typed Python event
or hook and the new attributes pass privacy/cardinality review. Existing instrument and
attribute names are public compatibility contracts for the installed distribution's `0.1.x`
line. The repository milestone `0.2.0` groups issue delivery and is not the instrumentation-scope
version authority. The installed distribution metadata is authoritative for dashboards; a later
repository release may bump that version only through release-controlled metadata changes.

## Acceptance Criteria

1. `bluetape-observability` builds as a Python 3.13+ focused distribution with only
   `opentelemetry-api>=1.43,<2` in runtime metadata.
2. The three public adapter classes and explicit submodule exports match this specification.
3. Valid resilience and Redis events produce the exact span events, metrics, units, and allowed
   attributes defined here.
4. No synthetic span, global provider mutation, SDK/exporter configuration, background work,
   logging bridge, or automatic context/baggage promotion is introduced.
5. Telemetry setup failures fail adapter construction, runtime `Exception` failures are isolated
   per signal call and retried on the next event, and `BaseException` propagates.
6. API-only, local-SDK, sync, async, privacy/cardinality, hostile-input, setup/runtime failure,
   wheel-isolation, metadata, and performance checks pass with fresh evidence.
7. Existing domain packages retain their public API and behavior, and the default `bluetape`
   wheel remains core-only without observability or OTel dependencies.
8. Package/root README locale pairs, package layout, WIP, changelog, CI, and all triggered
   public-distribution inventories agree with source and packaging metadata.
9. Type A spec/plan/code reviews converge at P0=0 and P1=0, a durable lesson is committed, and
   PR/merge gates remain separate.

## Definition of Done

- Approved design spec and reviewed implementation plan are committed before implementation.
- Spec and plan review artifacts show all six independent perspectives and integration verdict
  with P0=0/P1=0.
- Implementation follows test-first evidence and the approved package/API/data boundaries.
- Focused and full validation commands pass, including package isolation and actionlint.
- Documentation and release/package inventories are synchronized in English and Korean where
  required.
- A Type A lesson records the dependency-isolation, current-span, and cardinality decisions.
- Any PR is created only under explicit authority and includes the required `## DoD Status`.
- Merge occurs only after a fresh exact-head merge-ready approval; local sync and cleanup follow
  verified merge completion.
