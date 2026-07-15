# Issue #23 Python Observability and OpenTelemetry Boundaries

Issue: [#23](https://github.com/bluetape4k/bluetape-py/issues/23)
Milestone: `0.2.0`
Date: 2026-07-15

## Decision

Keep `bluetape-logging`, `bluetape-resilience`, `bluetape-cache`, and provider
packages free of OpenTelemetry dependencies. Their package-local event and
context contracts remain the source of truth.

If issue #24 proceeds, use a separate opt-in `bluetape-observability`
distribution as the canonical bridge boundary. Its production dependency is
limited to `opentelemetry-api`; domain-specific bridge modules must not pull
Redis or another provider package into the base install. A future
`bluetape[observability]` meta extra may forward that distribution, but an
extra on `bluetape-logging` is rejected because logging does not own tracing or
metrics.

Applications own `opentelemetry-sdk`, providers, processors and readers,
sampling, exporters, endpoints, credentials, resource detection, propagator
selection, and shutdown. Bluetape packages and bridges must not install or
replace global providers, create exporters, perform telemetry network I/O, or
own exporter queues and background workers.

OpenTelemetry Logs remain a Development signal in the reviewed Python status.
The first bridge slice must therefore avoid a stable public Logs API promise;
stdlib logging examples can remain application-owned until the signal and the
repository's concrete use cases mature.

This research decision does not authorize implementation. Issue #24 must still
define its exact package metadata, bridge API, optional dependency groups,
tests, and release impact before code is added.

## Current Repository Contracts

| Surface | Current contract | Decision |
| --- | --- | --- |
| `bluetape.logging` | Stdlib `logging`, one private `ContextVar`, caller-provided context fields, and redaction helpers. | Keep stdlib-only. Do not turn the logging context into an OpenTelemetry context or baggage store. |
| `PolicyEvent` | Immutable typed resilience event delivered inline through a callable observer. Observer failure propagates after policy cleanup. | Keep package-local and preserve its failure semantics. A bridge must not replace or widen the event. |
| `RedisEvent` | Immutable, low-cardinality terminal provider event delivered through `RedisObserver`. Observer failure never changes the provider result. | Keep package-local and preserve failure isolation. |
| `RedisCoordinationEvent` | Immutable, redacted coordination event with bounded counters and `cleanup_failed`. | Keep package-local; map only allowlisted fields to telemetry. |
| `bluetape.cache` | No stable public telemetry event contract. | Do not invent one in a generic bridge. Add package-local events only when a concrete cache requirement proves the fields and lifecycle. |
| Leader election and AWS adapters | No stable Python package-local event contract exists. | Defer generic hooks. Future packages may define typed, redacted events only after concrete lifecycle and field requirements exist; AWS SDK instrumentation remains application-owned. |
| Web middleware | No stable repository middleware contract exists. | Defer a generic hook. Framework adapters own request lifecycle and carrier injection/extraction; a future package-local event must be justified independently. |

The observer shapes and failure rules intentionally differ. A universal event
union, global observer registry, or shared async dispatcher would erase those
domain contracts and introduce lifecycle behavior that the owning packages do
not currently have.

## Minimum Bridge Contract For Issue #24

1. Depend on `opentelemetry-api` only in production. SDK packages are allowed
   only in tests and examples that prove application integration.
2. Obtain named and versioned tracers or meters through the API. Permit explicit
   provider injection for tests and application composition; never set globals.
3. Adapt existing package-local events without changing their classes,
   observer signatures, ordering, synchrony, cleanup, or failure behavior.
4. Use a fixed allowlist of typed enum, boolean, and bounded numeric fields.
   Exclude raw keys, values, arguments, results, exception text, URLs,
   credentials, request/user/account/session identifiers, and arbitrary logging
   context. Caller-controlled names are metric attributes only when the caller
   explicitly guarantees bounded cardinality.
5. Keep bridge instrumentation failure from changing the protected domain
   operation. Arbitrary caller observers retain each package's current failure
   semantics, but the bridge adapter must contain its own OpenTelemetry/API
   errors before returning through that observer boundary. Do not add
   package-owned queues, retries, exporters, or detached tasks as an isolation
   mechanism.
6. Keep trace context, baggage, and logging context distinct. Promotion of
   baggage or logging fields into span, metric, or log attributes is explicit
   and allowlisted, never automatic.
7. Do not define transport propagation. Framework and application adapters own
   carrier injection and extraction at HTTP, messaging, job, and RPC boundaries.

## Python 3.13 Context Compatibility

- `asyncio.Task` copies the current `contextvars.Context` when the task is
  created. Task-local changes do not mutate another task's context. Explicit
  task contexts remain caller-owned.
- `asyncio.to_thread()` propagates the current context into its worker thread.
- Raw threads and `loop.run_in_executor()` do not provide an equivalent
  propagation guarantee. When propagation is required, capture
  `copy_context()` and submit a distinct `ctx.run(...)` per concurrent call.
- `copy_context()` is O(1), but one `Context` cannot be entered concurrently or
  recursively. Reusing the same captured object across concurrent submissions
  is invalid.
- Callbacks, detached/background work, and transport boundaries must document
  whether they capture, clear, or reconstruct context. Cancellation cleanup
  must reset any package-owned `ContextVar` token.

`bluetape.logging` should continue to use `contextvars` for local logging
fields. Active OpenTelemetry context is a separate execution-scoped contract;
it is not a replacement dictionary for arbitrary log fields.

## Metric And Sensitive-Data Policy

OpenTelemetry's SDK cardinality limit is an overflow guard, not a design
target. Bridge metrics use fixed attribute keys and low-cardinality values.
The existing typed event enums and booleans are suitable candidates; raw
identifiers and caller payloads are not.

Baggage can propagate beyond the process and has no built-in integrity
guarantee. Credentials, access tokens, Redis keys, exception text, health or
financial data, and other sensitive values must not be placed in baggage or
copied automatically into telemetry attributes. Applications may clear baggage
before an untrusted boundary.

## Required Verification For A Future Bridge

- API-only smoke tests with no SDK configured; instrumentation must remain a
  valid no-op.
- Explicit injected-provider tests without global provider mutation.
- Attribute allowlist, cardinality, redaction, and hostile-marker tests.
- Sync and async event mapping parity without changing existing observer
  ordering or failure semantics.
- Python 3.13 tests for normal task creation, explicit task context,
  `asyncio.to_thread()`, raw threads, `run_in_executor()` with explicit
  `copy_context()`, cancellation, and context cleanup.
- Packaging tests proving that the default `bluetape`, `bluetape-logging`,
  `bluetape-resilience`, cache, Redis, `dev`, and `all` installs do not gain
  OpenTelemetry dependencies unless the approved package policy explicitly
  changes.
- A version recheck before any Logs-facing API because the reviewed signal is
  not stable.

## Rejected Alternatives

| Alternative | Reason for rejection |
| --- | --- |
| `bluetape-logging[otel]` as the canonical integration | Couples traces and metrics to logging ownership and encourages treating logging context as telemetry context. |
| Add OpenTelemetry dependencies to domain packages | Breaks stdlib/provider isolation and makes generic domain behavior depend on a telemetry stack. |
| Own the SDK, exporters, collector endpoints, or shutdown | These are application and operator lifecycle decisions. |
| Universal event or observer facade | Existing packages have different event fields and observer-failure contracts. |
| Automatic logging-context or baggage promotion | Creates cardinality, privacy, and trust-boundary risks. |
| Stable OTel Logs bridge in the first slice | The reviewed Python signal remains Development. |

## Non-Goals

- Vendor backend or collector selection.
- Exporter retry, batching, buffering, or shutdown management.
- Automatic instrumentation or monkey-patching.
- Framework middleware, HTTP/message carrier propagation, or cross-process
  baggage policy.
- Replacing existing package event contracts.
- Adding a generic logging facade or package-owned global logger state.

## Sources

Official Python sources:

- [Python 3.13 `asyncio` tasks and `to_thread`](https://docs.python.org/3.13/library/asyncio-task.html)
- [Python 3.13 `contextvars`](https://docs.python.org/3.13/library/contextvars.html)
- [Python 3.13 `run_in_executor`](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.run_in_executor)
- [PEP 567 thread-offloading guidance](https://peps.python.org/pep-0567/#offloading-execution-to-other-threads)

Official OpenTelemetry sources:

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

Repository and sibling evidence:

- `packages/bluetape-logging/src/bluetape/logging/__init__.py`
- `packages/bluetape-resilience/src/bluetape/resilience/_core.py`
- `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py`
- [`bluetape-go` issue #275 observability scope](https://github.com/bluetape4k/bluetape-go/blob/develop/docs/research/2026-06-26-issue-275-observability-scope.md)
- [`bluetape-go` issue #422 OTel bridge guidance](https://github.com/bluetape4k/bluetape-go/blob/develop/docs/research/2026-07-09-issue-422-otel-bridge-guidance.md)
- [`bluetape-go` issue #21 observability hook spec](https://github.com/bluetape4k/bluetape-go/blob/develop/docs/superpowers/specs/2026-06-03-issue-21-observability-hooks-spec.md)

## Version And Retrieval Notes

- Retrieved on 2026-07-15 against Python 3.13.14 documentation.
- The reviewed OpenTelemetry specification rendered version `1.59.0`; the
  official Python repository listed release
  [`1.43.0` / `0.64b0`](https://github.com/open-telemetry/opentelemetry-python/releases/tag/v1.43.0)
  dated 2026-06-24 as latest.
- OpenTelemetry version and signal maturity must be refreshed before issue #24
  implementation. No external images were required.
