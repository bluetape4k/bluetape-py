# Issue #46 Apache Fory Adapter Design

Date: 2026-07-11
Status: Step 2-R reviewed — P0=0 P1=0
Scope: `packages/bluetape-serde`, cross-language conformance fixtures, CI and docs

## Problem

Issue #45 established strict JSON serialization and immutable payload contracts,
but `bluetape-serde` has no explicit binary adapter for authenticated internal
services. Issue #46 adds Apache Fory without widening the default installation,
letting payload bytes select their own trust/type policy, or claiming
cross-language support from a Python-only round-trip.

## Goals

1. Add Apache Fory as the explicit `bluetape-serde[fory]` optional dependency.
2. Reuse `PayloadMetadata` and `SerializedPayload` without a parallel trust model.
3. Provide a caller-selected, statically registered xlang adapter restricted to
   `TRUSTED_INTERNAL`.
4. Enforce finite byte, depth, type-metadata, and schema-version bounds with
   reference tracking disabled and a bounded runtime pool.
5. Prove one stable schema across Python, Go, Rust, and Kotlin producer bytes.
6. Return stable, payload-free typed errors for every caller-visible failure.

## Non-Goals

- No Python native mode, pickle/cloudpickle compatibility, dynamic module/class
  loading, global registry, implicit default adapter, or format auto-detection.
- No untrusted Fory decode.
- No stream/file API, encryption, compression composition, or schema migration
  engine.
- No general object-graph interoperability claim.
- No benchmark-based default recommendation.

## Design Risks and Failure Modes

1. **Provider/API drift:** exact body consumption depends on public Buffer index
   behavior. The dependency remains exact-pinned, and any upgrade must pass
   tagged-source review plus malformed/trailing-byte compatibility tests.
2. **False trust from xlang:** built-in roots remain decodable in xlang mode.
   Exact root-type checks before encode and after decode are therefore mandatory.
3. **Resource amplification:** accepted byte/metadata limits do not bound provider
   CPU or peak RSS. The first release remains authenticated internal-only and
   documents process isolation for hard limits.
4. **Cross-language drift:** different field widths, fixed-schema settings,
   or type IDs can produce plausible but incompatible bytes. Exact toolchain and
   dependency pins, canonical manifests, and bidirectional fixtures gate release.
5. **Runtime state leakage:** ordinary `Fory` reuses buffers and contexts. The
   adapter uses a frozen `ThreadSafeFory` pool and verifies cleanup/reuse after
   failures.

## Considered Designs

### A. Bluetape envelope plus numeric Fory xlang type ID — selected

Keep `PayloadMetadata` unchanged. Prefix Fory bytes with a compact fixed-width
bluetape envelope containing magic, envelope version, schema ID, schema version,
application type ID, and body length. The caller supplies the expected static
registration. The same numeric type ID is registered in Fory and repeated in the
outer envelope so mismatch rejection happens before provider decode.

This preserves Issue #45 contracts and follows the `pyfory 1.3.0` tagged source,
which supports numeric cross-language type registration. Numeric ID and name
cannot be supplied together, so the logical name remains manifest documentation
rather than a second provider lookup key.

### B. Add schema/type IDs to `PayloadMetadata` — rejected

This would widen a format-neutral public contract for one adapter and force JSON
callers to carry irrelevant fields. It also increases compatibility risk for the
already released Issue #45 API.

### C. Use only Fory registration names — rejected

This follows upstream xlang behavior but does not satisfy Issue #46's explicit
application schema/type/version gate and cannot reject a wrong registered
contract before provider decode.

## Public API

The optional module is imported explicitly:

```python
from bluetape.serde.fory import (
    ForyAdapter,
    ForyLimits,
    ForyRegistration,
)
```

The base `bluetape.serde` namespace does not import `pyfory` and does not export
an initialized default adapter.

New provider-independent error contracts are officially imported from
`bluetape.serde`, which remains importable without `pyfory`:

- `SerdeErrorCode.SCHEMA_MISMATCH = "schema_mismatch"` and
  `SchemaMismatchError(SerdeError)`;
- `SerdeErrorCode.TYPE_MISMATCH = "type_mismatch"` and
  `TypeMismatchError(SerdeError)`;
- `SerdeErrorCode.FORY_REGISTRATION = "fory_registration"` and
  `ForyRegistrationError(SerdeError)`;
- `SerdeErrorCode.INVALID_FORY = "invalid_fory"`, allowed only by
  `MalformedPayloadError`;
- `SerdeErrorCode.FORY_ENCODE = "fory_encode"`, allowed only by
  `SerdeEncodeError`;
- `SerdeErrorCode.FORY_CONCURRENCY_LIMIT = "fory_concurrency_limit"` and
  `ForyConcurrencyError(SerdeError)`.

The optional `bluetape.serde.fory` module imports these classes for its own
implementation but does not create duplicate error types.

### `ForyRegistration[T]`

Frozen, slotted, keyword-only registration value:

- `python_type: type[T]`
- `schema_id: int` — unsigned 32-bit application schema identity
- `schema_version: int` — unsigned 16-bit positive schema version
- `type_id: int` — Fory user type identity in `1..0xFFFFFFFE`
- `logical_name: str` — bounded diagnostic/manifest name, not a provider lookup key

Construction validates exact types and bounded values. A registration is
caller configuration; it is never constructed from received bytes.
`schema_id` is `1..0xFFFFFFFF`, independently from the narrower provider type
ID. `logical_name` is 1-128 ASCII characters from `[A-Za-z0-9._-]`, with no leading,
trailing, or repeated dot. The version-controlled conformance/application
manifest owner guarantees `(schema_id, schema_version, type_id)` uniqueness.

Version 1 supports one registered root whose fields use Fory built-ins and
containers only. Nested application dataclasses/classes are unsupported because
the adapter intentionally accepts no secondary registration graph.

### `ForyLimits`

Frozen bounded configuration with conservative defaults:

- `max_input_size = 16 MiB`
- `max_output_size = 16 MiB`
- `max_depth = 64`, hard maximum 256
- `max_type_fields = 256`
- `max_type_meta_bytes = 4096`
- `max_schema_versions_per_type = 8`
- `max_average_schema_versions_per_type = 2`
- `max_concurrency = 4`, hard maximum 64
- `acquire_timeout_seconds = 5.0`, positive and at most 60 seconds
- `reference_tracking = False`

The first release requires `reference_tracking is False` and configures Fory
with `ref=False`. This disables tracking/deduplication; it does not claim that an
input graph contains zero repeated references. Cyclic or unsupported graphs fail
as sanitized encode errors.

Every integer field requires an exact `int` (not `bool`). Input/output limits
are `20..1 GiB`; depth is `1..256`; type fields are `1..65_535`; type metadata
bytes are `1..16 MiB`; schema-version counts are `1..65_535`, with the average
not exceeding the per-type maximum; concurrency is `1..64`.
`acquire_timeout_seconds` requires an exact finite `float` in `0.001..60.0`.

### `ForyAdapter[T]`

Construction receives exactly one `ForyRegistration[T]` and optional
`ForyLimits`. It creates one private `pyfory.ThreadSafeFory` pool configured with:

- `xlang=True`
- `strict=True`
- `ref=False`
- non-compatible fixed-schema mode (`compatible=False`)
- all supported finite Fory metadata/depth limits
- registration by the numeric `type_id`

Configuration and registration callbacks are frozen before first pool use and
cannot mutate afterward. A private `threading.BoundedSemaphore` caps concurrent
provider calls at `max_concurrency`, so upstream `ThreadSafeFory` can retain no
more than that many runtimes. Acquisition waits at most
`acquire_timeout_seconds`; timeout raises the stable concurrency error before
provider access. Fory resets read/write state in `finally`;
tests prove malformed input or provider failure does not poison a returned pool
instance. Callers must not mutate input objects while serialization is in progress.
Construction first creates one temporary runtime through public `pyfory.Fory`
with the exact final configuration, invokes the public registration call, and
discards the probe. Invalid provider registration therefore fails startup with
`ForyRegistrationError`, before the `ThreadSafeFory` pool is exposed. A runtime
whose later construction or registration fails is never returned to the pool;
concurrent and repeated failures remain isolated.
The adapter callback wraps only the public `fory.register(...)` call and converts
its ordinary exception to a private `_ForyRegistrationFailure` sentinel. The
operation boundary translates only that sentinel to `ForyRegistrationError`;
provider construction and encode/decode failures retain their separate mappings.

Operations:

```python
adapter.serialize(value, *, metadata) -> SerializedPayload
adapter.deserialize(payload, *, expected_metadata) -> T
```

The optional module exports immutable `FORY_FORMAT`, `FORY_VERSION`, and
`FORY_CONTENT_TYPE` constants to reduce spelling errors. It does not export a
default `PayloadMetadata`, trust policy, registration, or adapter.

`metadata` and `expected_metadata` must be exact `PayloadMetadata` values:

| field | required value |
| --- | --- |
| `format` | `"apache-fory-xlang"` |
| `version` | `1` |
| `content_type` | `"application/x-apache-fory"` |
| `trust_profile` | `TrustProfile.TRUSTED_INTERNAL` |

The expected metadata comes from authenticated and authorized caller
configuration. The decoder never copies expected policy from
`payload.metadata`.

External authenticated routing selects an adapter first: for example, a fixed
topic, queue, cache namespace, or RPC method maps to one configured adapter and
schema version. Only then does that adapter compare received IDs with expected
IDs. Callers must never inspect payload IDs to choose an adapter.

A complete caller lifecycle keeps routing and expected policy independent from
received bytes:

```python
from dataclasses import dataclass

import pyfory

from bluetape.serde import (
    ForyConcurrencyError,
    PayloadMetadata,
    SerdeError,
    SerializedPayload,
    TrustProfile,
)
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyRegistration,
)


@dataclass(frozen=True, slots=True)
class ConformanceRecord:
    record_id: pyfory.Int64
    name: str
    active: bool
    scores: list[pyfory.Int32]


producer_metadata = PayloadMetadata(
    format=FORY_FORMAT,
    version=FORY_VERSION,
    content_type=FORY_CONTENT_TYPE,
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
registration = ForyRegistration(
    python_type=ConformanceRecord,
    schema_id=0x42544659,
    schema_version=1,
    type_id=1001,
    logical_name="io.bluetape.serde.ConformanceRecord",
)
adapter = ForyAdapter(registration=registration)
value = ConformanceRecord(7, "blue", True, [1, 2, 3])

# Producer configuration owns metadata; it is not derived from the value.
produced = adapter.serialize(value, metadata=producer_metadata)
wire_metadata, wire_bytes = produced.metadata, produced.data

# An authenticated route selects this adapter and its independently configured
# expected metadata before reconstructing the received transport value.
consumer_policy = PayloadMetadata(
    format=FORY_FORMAT,
    version=FORY_VERSION,
    content_type=FORY_CONTENT_TYPE,
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
received = SerializedPayload(metadata=wire_metadata, data=wire_bytes)
try:
    decoded = adapter.deserialize(received, expected_metadata=consumer_policy)
except ForyConcurrencyError:
    # Retry only this same route/codec with application-bounded backoff.
    raise
except SerdeError:
    # Reject/quarantine; never probe another codec.
    raise
```

The producer and consumer policies are separately constructed application-owned
immutable `PayloadMetadata` values. The optional module intentionally does not
provide either as a default. Public documentation must show route selection
before payload reconstruction and must not show payload-ID dispatch.

## Wire Envelope

All integer fields use unsigned big-endian encoding:

| field | size | value |
| --- | ---: | --- |
| magic | 4 bytes | ASCII `BTFY` |
| envelope version | 1 byte | `1` |
| flags | 1 byte | `0`; unknown bits rejected |
| schema ID | 4 bytes | registration value |
| schema version | 2 bytes | registration value |
| type ID | 4 bytes | registration value |
| body length | 4 bytes | exact remaining Fory byte count |

The fixed header is 20 bytes. Decoder validation order is metadata, total input
limit, fixed header, magic/version/flags, caller-expected registration IDs,
body length, then Fory decode. There is no registry lookup keyed only by
received IDs.

The outer `type_id` must equal the caller registration and the same numeric ID
is registered inside every language's Fory runtime. The stable logical name is
manifest-only. Encode requires `type(value) is python_type`; decode requires
`type(result) is python_type`, so built-in roots and subclasses cannot pass as
the registered result.

Fory's root out-of-band flag is prohibited. The public provider decoder does not
reject trailing root bytes, so the adapter wraps each body in a public
`pyfory.Buffer`, calls public `deserialize(buffer)`, and checks that the final
reader index equals body length. This must pass against the actual 1.3.0 Cython
wheel path. A provider upgrade cannot move the pin until trailing-byte and public
Buffer compatibility tests pass.

The outer schema ID/version are caller contract assertions, not a cryptographic
fingerprint of the Fory body. They reject an unexpected outer contract before
decode, while provider parsing and exact result-type checks reject foreign body
shapes. Authentication/integrity remain transport responsibilities.

## Error Contract

Extend `SerdeErrorCode` and existing restricted error classes without exposing
payload bytes, provider messages, class reprs, or field values:

| failure | class/code | fixed message / recovery |
| --- | --- | --- |
| wrong magic or malformed length/header/body | `MalformedPayloadError.INVALID_FORY` | `payload is not valid Fory`; reject/quarantine |
| outer envelope version unsupported | `UnsupportedVersionError` | retain Issue #45 message; deploy the matching reader |
| schema ID or schema version mismatch | `SchemaMismatchError.SCHEMA_MISMATCH` | `Fory schema does not match caller registration`; surface route/configuration drift |
| application type ID mismatch | `TypeMismatchError.TYPE_MISMATCH` | `Fory type does not match caller registration`; surface route/configuration drift |
| provider registration failure | `ForyRegistrationError.FORY_REGISTRATION` | `Fory registration failed`; fix deployment configuration |
| provider encode failure | `SerdeEncodeError.FORY_ENCODE` | `value cannot be encoded as registered Fory type`; reject value |
| provider decode failure | `MalformedPayloadError.INVALID_FORY` | `payload is not valid Fory`; reject/quarantine |
| total input/output bound | `PayloadLimitError.INPUT_LIMIT` / `.OUTPUT_LIMIT` | retain Issue #45 messages; reject/quarantine |
| provider depth/type metadata/schema-history rejection during decode | `MalformedPayloadError.INVALID_FORY` | `payload is not valid Fory`; reject/quarantine |
| adapter concurrency acquisition timeout | `ForyConcurrencyError.FORY_CONCURRENCY_LIMIT` | `Fory adapter concurrency limit reached`; retry with bounded backoff on the same route/codec |
| non-trusted or mismatched trust policy | `TrustProfileMismatchError` | retain Issue #45 message; reject route/policy mismatch |

`SchemaMismatchError`, `TypeMismatchError`, `ForyRegistrationError`, and
`ForyConcurrencyError` are sealed-behavior `SerdeError` subclasses. Generic
fallback or retry with another codec is forbidden.

Tagged `pyfory 1.3.0` exposes these decode limits through generic provider
`ValueError` paths rather than dedicated public exception types. The adapter
therefore does not guess from provider messages: every provider parse or limit
failure during decode maps to `INVALID_FORY`. Provider failures during encode
map to `FORY_ENCODE`; only outer byte limits retain `INPUT_LIMIT` or
`OUTPUT_LIMIT`.

Caller type/configuration mistakes remain native `TypeError` or `ValueError`.
Provider exceptions are never chained into public errors. The handler records
only an error specification, releases value/payload/body/partial-result/provider
exception locals, and raises a fresh typed error outside the handler so
`__cause__`, `__context__`, traceback locals, and provider messages are absent.
`MemoryError`, `KeyboardInterrupt`, and `SystemExit` are never translated.

## Security Model

1. A successful decode requires an authenticated and authorized closed producer
   boundary established outside the payload.
2. `TRUSTED_INTERNAL` does not bypass any resource or registration check.
3. `strict=True` limits registered application classes, while exact root-type
   checks additionally reject Fory built-in roots and subclasses.
4. `xlang=True` excludes Python-native functions, reduction hooks, local
   classes, and pickle-style reconstruction; xlang mode alone is not treated as
   a security boundary.
5. `ref=False` disables reference tracking; it is not a reference-count bound.
6. The envelope is not authentication, integrity protection, or encryption.
7. Logs and errors contain only safe identifiers, configured limits, operation,
   and byte counts; never payload bytes or decoded values.
8. Accepted byte and metadata limits reduce resource exhaustion but do not
   form a hard CPU/RSS sandbox. A hard boundary requires a separately limited
   process.

## Cross-Language Conformance

Use one `ConformanceRecord` with exact field order, non-null fields, and
deliberately portable field widths:

- `record_id: Int64`
- `name: String`
- `active: Bool`
- `scores: List[Int32]`

The Python fixture declaration is a frozen, slotted dataclass with fields in
that order and annotations `pyfory.Int64`, `str`, `bool`, and
`list[pyfory.Int32]`. Equivalent producer declarations are Go
`int64/string/bool/[]int32`, Rust `i64/String/bool/Vec<i32>`, and Kotlin
`Long/String/Boolean/List<Int>`. No field is nullable or optional.

Stable contract values:

- schema ID: `0x42544659`
- schema version: `1`
- application type ID: `1001`
- Fory numeric type ID: `1001`
- logical manifest name: `io.bluetape.serde.ConformanceRecord`
- compatible mode: disabled; all peers use the exact declared schema
- reference tracking: disabled

Repository fixtures contain one producer output each for Python, Go, Rust, and
Kotlin plus a canonical JSON manifest with runtime/library version, SHA-256, and
expected semantic value. Locale is `C.UTF-8`, timezone is `UTC`, JSON keys are
sorted, and the shared schema source is committed once. Producer source,
language lock/checksum files, and deterministic regeneration commands live
beside the fixtures.

| producer | toolchain | Fory dependency | authoritative pin |
| --- | --- | --- | --- |
| Python | CPython 3.13.14 | `pyfory==1.3.0` | `.python-version` and `uv.lock` |
| Go | Go 1.26.5 | `github.com/apache/fory/go/fory v1.3.0` | conformance `go.mod`/`go.sum` |
| Rust | Rust 1.96.1 | `fory = 1.3.0` | `rust-toolchain.toml` and `Cargo.lock` |
| Kotlin | Eclipse Temurin 21.0.11+10, Gradle 9.6.0 | `org.apache.fory:fory-kotlin:1.3.0` | toolchain config, wrapper/checksums, version catalog/Gradle lock |

The committed Gradle wrapper pins distribution SHA-256
`bbaeb2fef8710818cf0e261201dab964c572f92b942812df0c3620d62a529a01`
and wrapper JAR SHA-256
`497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7`.
Each producer job installs these exact versions rather than using ambient
runtimes, prints them into its artifact manifest fragment, and fails before
regeneration if any observed version differs.

Required proof:

1. Python decodes all four producer bytes to the same value.
2. Python-generated bytes are decoded by Go, Rust, and Kotlin consumers.
3. Each producer can regenerate its committed fixture without drift under the
   pinned toolchain/dependency version.
   It must generate twice in separate fresh processes into temporary output,
   compare those outputs, and never overwrite canonical fixtures during verify.
4. Wrong schema/type/version fixtures fail before Fory object reconstruction.
5. Valid root plus trailing bytes and out-of-band root flags are rejected.
6. Same outer IDs with a foreign body cannot bypass provider/exact-type checks.

If an upstream runtime cannot implement the shared contract, the feature is not
declared cross-language complete; the precise blocker is recorded and Issue #46
remains open.

One adapter accepts exactly one envelope schema version. A field/type change
requires a new registration and externally versioned route; old/new readers run
in parallel during migration. Provider schema-history limits remain configured
as finite defense-in-depth but are not an evolution mechanism in fixed-schema
mode.

## Packaging and Compatibility

- Add `fory = ["pyfory==1.3.0"]` to `bluetape-serde` optional dependencies.
- Add `bluetape[fory] = ["bluetape-serde[fory]==0.1.0"]` as the exact
  forwarding metadata without changing default `bluetape` dependencies.
- Lock `pyfory` and verify wheel installation on CPython 3.13.
- Current `pyfory 1.3.0` has no CPython 3.14 wheel or source distribution.
  Core/JSON remain Python 3.13+, while the Fory extra is CPython 3.13 only.
- Direct `import bluetape.serde` succeeds without `pyfory`. Only
  `ModuleNotFoundError` with `error.name == "pyfory"` becomes a fixed,
  unchained installation error. Transitive/ABI/provider initialization failures
  propagate unchanged and are never mislabeled as a missing extra.
- Public troubleshooting tells operators to verify CPython 3.13.14 and the
  `pyfory==1.3.0` wheel/ABI rather than repeatedly reinstalling the extra when a
  transitive import or provider initialization error propagates.
- Wheel smoke tests prove CPython 3.14 can install the base distribution while
  the current Fory extra fails dependency resolution explicitly rather than
  producing a partially installed adapter.

Install matrix:

| install | contents |
| --- | --- |
| `bluetape-serde` / `bluetape[serde]` | contracts and JSON only |
| `bluetape-serde[fory]` / `bluetape[fory]` | contracts, JSON, and Fory on CPython 3.13 |
| `bluetape[dev]` / `bluetape[all]` | excludes native/binary provider extras including Fory |

Source-workspace installation uses
`uv sync --package bluetape-serde --extra fory --python 3.13`; a built local
wheel uses
`python3.13 -m pip install "./dist/bluetape_serde-0.1.0-py3-none-any.whl[fory]"`;
future PyPI uses `python3.13 -m pip install "bluetape-serde[fory]==0.1.0"`.
Importing
the optional module without the extra raises a fresh `ModuleNotFoundError` with
fixed message `Install bluetape-serde[fory] with CPython 3.13 to use Apache Fory.`

## Resource and Allocation Semantics

- `max_input_size` and `max_output_size` include the complete 20-byte envelope.
- Metadata, length, flags, and registration checks are O(1) and precede decode.
- Every provider limit maps one-to-one to a same-named supported upstream
  constructor argument.
- The adapter semaphore bounds simultaneous provider calls and permanently
  retained `ThreadSafeFory` runtimes. Concurrency timeout is measured before
  provider work and never expands the pool.
- Encode checks exact root type before provider work and logical output size
  immediately after provider serialization. Envelope assembly uses at most one
  additional bounded body-sized allocation.
- Decode passes a provider buffer view where supported, avoids another body
  copy, and performs no second generic Python graph traversal.
- Output and metadata limits are acceptance limits, not peak process-memory
  ceilings. Provider encode materializes its body before length is known;
  `MemoryError` remains native.
- Non-flaky `tracemalloc` smoke tests compare small/large scaling and oversized
  output behavior. Timing evidence uses ratios/observations, never absolute CI
  latency gates.

## Documentation and CI

Update package/root English and Korean README files, `CHANGELOG.md`, WIP status,
and package layout documentation. Keep inexpensive committed-fixture checksum
and Python decode checks in the normal CPython 3.13 job. Add path-gated cached
producer jobs for Python, Go, Rust, and Kotlin that run in parallel for this
feature PR, future serde/fixture/lock/workflow changes, and `develop`. Each job
has an explicit timeout and uploads its regenerated fixture/manifest fragment,
so a failing language is identifiable. A final conformance job verifies the
downloaded artifacts against committed fixtures and the canonical manifest only
after every producer succeeds. These jobs:

- install the explicit extra;
- run Fory unit, boundary, malformed-input, and conformance tests;
- regenerate/verify their own language fixture under exact pins;
- build the focused distribution and verify wheel install/import behavior;
- prove the default installation does not contain `pyfory`.

The final job downloads all four commit-SHA/producer-named artifacts, recomputes
SHA-256, compares them byte-for-byte with committed fixtures, and validates the
canonical manifest. Python decodes the downloaded Go/Rust/Kotlin bytes; each
Go/Rust/Kotlin consumer decodes the downloaded Python bytes. Editing only the
committed manifest cannot make the gate pass. Workflow permissions are
`contents: read`; PR concurrency cancels superseded runs. The implementation
plan must pin per-job timeout, lockfile-derived cache key, and short artifact
retention before workflow editing.

## Rollout, Rollback, and Observability

Rollout order is fixed:

1. Verify the authenticated/authorized producer allowlist.
2. Deploy readers on a separate versioned Fory route.
3. Enable a canary writer for that route.
4. Observe attempts, successes, failures grouped by stable error code, and
   latency before expanding writers.

Before canary activation, the deploying application records its caller-owned
observation window, error-rate/latency thresholds, and automatic write-stop
condition. These values are deployment-specific rather than library defaults.

Rollback stops Fory writes, switches producers to the previous codec's separate
route, and keeps Fory readers until queue/cache TTL drain completes. The same
queue, topic, route, or keyspace must not mix codecs. Automatic fallback and
payload-selected routing are forbidden.

The library emits no logs or metrics by default. Callers may aggregate only
`operation`, stable `SerdeErrorCode`, total envelope byte count, success/failure,
latency, and a caller-owned low-cardinality `route_id` fixed before payload
receipt. Payload/body/value, provider text, traceback locals, class repr,
schema/type IDs, schema logical name, payload-derived identifiers, and arbitrary
high-cardinality identifiers are forbidden as logs or metric labels. A caller
that omits `route_id` must isolate each versioned route into a separate metric
and log stream so canary and rollback decisions remain attributable.

## Testing Strategy

- Registration value validation, provider registration failure, and mismatch cases.
- Exact metadata/trust enforcement before decode.
- Envelope boundary, truncation, overflow, flag, and length mismatch cases.
- Input/output bounds, provider depth/type metadata/schema version enforcement, and the
  `reference_tracking=False` invariant.
- Sanitized provider encode/decode failure mapping, exception isolation, and
  successful runtime reuse after failure.
- Concurrent encode/decode marker isolation across the `ThreadSafeFory` pool.
- Concurrency saturation, bounded wait, stable timeout error, and retained pool
  size at or below `max_concurrency` after a contention spike. The test injects
  a counting fake through the public `ThreadSafeFory(fory_factory=...)` seam and
  never inspects the provider's private `_pool`.
- Exact root type, built-in root, subclass, trailing-byte, and out-of-band cases.
- No default import or hidden fallback.
- Four-language fixture exchange and deterministic regeneration.
- Wheel install with and without the `fory` extra.
- `timeit`/`tracemalloc` smoke evidence for construction, pool reuse,
  small/large scaling, and encoded size without hard timing gates.
- A bounded subprocess records RSS high-water observations for small/large
  payloads and after a concurrency spike, covering native allocations that
  `tracemalloc` cannot see; observations remain diagnostic rather than flaky
  absolute CI gates.
- Fatal `MemoryError`, `KeyboardInterrupt`, and `SystemExit` paths emit no
  library log and are not wrapped or retried.

Tests are written first for every public contract and failure family.

## Definition of Done

- [ ] Optional `pyfory` dependency is locked and isolated behind the `fory` extra.
- [ ] `PayloadMetadata` and `SerializedPayload` are reused unchanged.
- [ ] Caller-owned `TRUSTED_INTERNAL` policy is enforced.
- [ ] Static registration, bounded provider concurrency, and all finite limits are enforced.
- [ ] Exact root type, exact body consumption, and exception isolation are enforced.
- [ ] Typed payload-free failures cover every acceptance case.
- [ ] Python/Go/Rust/Kotlin bidirectional fixture verification passes.
- [ ] Default installation remains core-only and imports without `pyfory`.
- [ ] README locale set, CHANGELOG, package docs, research, review, and lesson
      artifacts are current.
- [ ] Ruff, all pytest suites, package builds, wheel smoke tests, fixture checks,
      and CI pass.
- [ ] Step 6-R and Step 7-R converge at P0 = 0 and P1 = 0.

## Sources

- `docs/superpowers/research/2026-07-11-issue-46-apache-fory-research.md`
- <https://github.com/bluetape4k/bluetape-py/issues/46>
- <https://fory.apache.org/docs/guide/python/configuration/>
- <https://fory.apache.org/docs/guide/python/type_registration/>
- <https://fory.apache.org/docs/guide/xlang/serialization/>
- <https://pypi.org/project/pyfory/>
- <https://github.com/apache/fory/blob/v1.3.0/python/pyfory/_fory.py>
- <https://github.com/apache/fory/blob/v1.3.0/python/pyfory/registry.py>
