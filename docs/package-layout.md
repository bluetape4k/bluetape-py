# Package Layout Policy

## Goals

- Keep public packages small, Python-native, and independently useful.
- Avoid catch-all utility packages.
- Keep the default `bluetape` install thin.
- Prefer the Python standard library and focused optional dependencies before
  adding broad wrappers.
- Keep implementation details private until there is a clear public contract.

## Public Distributions

Distributions live under `packages/` and should map to focused import paths.

Current public distributions:

- `bluetape`
- `bluetape-async`
- `bluetape-cache`
- `bluetape-cache-redis`
- `bluetape-codec`
- `bluetape-collections`
- `bluetape-compression`
- `bluetape-core`
- `bluetape-id`
- `bluetape-logging`
- `bluetape-measure`
- `bluetape-money`
- `bluetape-observability`
- `bluetape-resilience`
- `bluetape-serde`
- `bluetape-testing`

Private workspace distributions:

- `bluetape-benchmark` owns `bluetape.benchmark`. It is stdlib-only and is
  built/tested with the workspace, but it is source-only and forbidden from
  every publish allowlist and meta extra. Its `Private :: Do Not Upload`
  classifier is defense in depth, not the release-selection mechanism.

The `bluetape` distribution is a meta package. It should not create a root
`bluetape/__init__.py` import surface. Focused packages own focused import paths
such as `bluetape.core`, `bluetape.logging`, and `bluetape.testing`.
The async package owns `bluetape.asyncio`, codec owns `bluetape.codec`,
collections owns `bluetape.collections`, and compression owns
`bluetape.compression`. Serde owns `bluetape.serde` and is available only from
the focused `bluetape-serde` distribution or the explicit future `serde` meta
extra; it is never part of the core-only default install. Async packages must
document cooperative ownership, cancellation, timeout, and cleanup behavior.
Compression packages must document wire formats, output bounds,
malformed-input errors, and optional-backend availability.

`bluetape-compression` keeps gzip, zlib-wrapped, and raw-DEFLATE support in the
provider-free base distribution. Its structural `Compressor` Protocol allows
application-owned implementations without inheritance. LZ4 frame, raw Snappy,
and Zstandard frame implementations live under `bluetape.compression.native`
and require the focused `lz4`, `snappy`, or `zstd` extra, or the aggregate
`native` extra. The meta distribution forwards those choices as
`compression-lz4`, `compression-snappy`, `compression-zstd`, and
`compression-native`; none may enter the default, `dev`, or `all` dependency
sets. Missing providers fail when the matching compressor is constructed, not
when the package or native namespace is imported.

All bundled decompressors enforce a non-negative logical output bound, reject
invalid or incomplete payloads, and avoid payload-bearing error messages or
logs. Application composition is explicit: serialize, then compress, then
store; read by decompressing before deserialization. Sibling language
implementations are semantic references for features and failure rules, not a
cross-language wire-compatibility promise.

`bluetape-cache` owns `bluetape.cache` and is available from the focused
distribution or the explicit `bluetape[cache]` meta extra. It is
stdlib-only and provides bounded sync and async local TTL loading caches. It is
not part of the core-only default meta install and does not add a root
`bluetape` import surface.

`bluetape-cache-redis` owns `bluetape.cache.redis`. The parent
`bluetape.cache` package extends its namespace path so the focused Redis wheel
can add the nested import without adding Redis to `bluetape-cache`. The Redis
package is available only through a direct focused install or
`bluetape[cache-redis]`; it depends on `bluetape-cache==0.1.0`, redis-py, serde,
and compression and is excluded from the default, `dev`, and `all` dependency
sets.

The milestone release must reconcile this exact cache pin in the lock and wheel
metadata, then publish and verify the `bluetape-cache` artifact before
`bluetape-cache-redis`.

The Redis surface is byte-only and keeps application serialization,
compression, key naming, and rollout policy explicit. Built-in binary and JSON
v1 envelopes enforce complete parsing and encoded-size bounds. Sync and async
providers require positive TTL writes, use atomic `SET NX PX`, and use a fixed
Lua compare-and-delete operation without a racy fallback. Factory-created
clients are owned; constructor-injected clients are borrowed. Issue #55 adds
bounded sync/async same-key load coordination with expiring Redis leases,
atomic token-checked publication, bounded polling, and explicit failure
semantics. It is not an L2 cache, fencing primitive, or distributed
invalidation system.

`bluetape-serde` is stdlib-only for its strict JSON v1 contract. Its root public
surface is imported from `bluetape.serde` and is fixed at 25 ordered exports
plus 23 stable `SerdeErrorCode` values. JSON integers are limited to 640 decimal
digits on encode and decode. The Apache Fory adapter lives in the
provider-dependent `bluetape.serde.fory` module and is available only through
the CPython 3.13 `bluetape-serde[fory]` or forwarding `bluetape[fory]` extra.
It must not leak into the base, `serde`, `dev`, or `all` dependency sets or
become an implicit decoder fallback.

`bluetape-resilience` owns `bluetape.resilience` and is available from the
focused distribution or explicit `bluetape[resilience]` meta extra. It is
stdlib-only and provides separate sync/async retry, circuit breaker, and
bulkhead policy families, cooperative async timeout, and immutable fluent
pipelines. It is not part of the core-only default install. The package must not
add a synchronous timeout, hidden worker, detached task, reset scheduler,
global registry, or package-owned logger. Policy instances retain their own
state or capacity, and pipelines share that state only by retaining the caller's
explicit instance.

`bluetape-observability` owns `bluetape.observability` and is available only
through its directly installed focused distribution. It depends on
`opentelemetry-api` at runtime and keeps resilience, Redis, the OpenTelemetry
SDK, providers, exporters, and shutdown lifecycle caller-owned. It is not part
of the default meta install or any meta extra.

Applications own Fory route identity as a fixed
`(schema_id, schema_version, type_id)` tuple mapped to one exact registered root
type. Schema changes require a new tuple and versioned route, reader-first
deployment, explicit compatibility review, and drain evidence before retiring
the old reader. Fory is trusted-internal only; hard CPU/RSS containment belongs
to a separate constrained process rather than byte limits alone.

`bluetape-id`, `bluetape-measure`, and `bluetape-money` are independent
stdlib-only value distributions and explicit `id`, `measure`, `money`, or
aggregate `values` meta extras. None enters the core-only default install.
Identifiers persist as canonical strings while monotonic generator state is
process-local and resets across restart, fork, upgrade, or rollback. Measures
persist as the exact versionless `amount`/`unit` primitive schema; applications
own custom immutable unit definitions and supply them during deserialization.
Money persists as the exact versionless `amount`/`currency` schema and uses a
committed current ISO 4217 snapshot; applications own historical currency
policy and every exchange-rate source, freshness rule, cache, and lifecycle.

KSUID waits for a concrete compatibility consumer. Snowflake IDs, compound or
affine measurements, locale money, and provider-backed FX each require a
separate source-backed design issue before implementation.

## Future Packages

Create a new distribution only when it has:

- a clear domain boundary;
- package README documentation;
- tests for success, failure, and boundary behavior;
- explicit dependency and extras impact;
- root README and WIP visibility when it affects user-facing scope.

Avoid adding optional integrations to the default `bluetape` dependency list.
Use extras or direct focused distribution installs for heavier capabilities.

## Internal Code

Use package-local private modules for implementation details that are not public
API. Good candidates:

- shared validation internals;
- serializer/compressor implementation details;
- fixture helpers not intended for users;
- compatibility shims while public APIs are still settling.

If users must import it, it belongs in a public package with docs and tests.

## Package Documentation

Every public package should have package documentation before it is considered
release-ready:

- package purpose;
- primary API examples;
- sync/async ownership rules when relevant;
- exception and error semantics;
- dependency and optional-extra notes;
- compatibility notes for sibling bluetape4k, bluetape-go, or bluetape-rs
  behavior when applicable.

## Examples

Prefer examples that solve real backend problems:

- validation at API boundaries;
- request/task log context;
- eventual consistency waits in tests;
- cache loading and invalidation;
- resilience policy wrapping;
- Testcontainers-backed integration fixtures;
- SQL transaction and outbox handoff patterns.
