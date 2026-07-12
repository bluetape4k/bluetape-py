# Issue #54 Redis Provider Substrate Design

## Summary

Issue #54 adds an opt-in `bluetape-cache-redis` distribution for the Redis
provider substrate required by #55. The package provides equivalent synchronous
and asynchronous Redis byte operations, explicit borrowed-versus-owned client
lifecycle, caller-owned payload codec contracts, selectable binary or JSON
result-envelope formats, and explicit bounded compression.

This change does not add cross-process load coordination, a durable Redis value
cache, near-cache invalidation, or a built-in application serialization policy.
Python API and packaging conventions remain authoritative. Kotlin and Go are
used to preserve feature and safety rules, not package shape or wire
compatibility.

## Problem

`bluetape-cache` is a stdlib-only local cache package. Issue #55 needs Redis
primitives and a short-lived result-envelope boundary, but adding `redis` to
`bluetape-cache` or the default `bluetape` install would violate the package
boundary. The repository also needs one place to define:

- sync/async Redis command parity;
- borrowed and owned client lifecycle;
- caller-selected serialization, trust, and schema policy;
- explicit compression identity and bounded decompression;
- versioned and size-bounded result envelopes;
- redacted provider errors and low-cardinality observability.

Without this substrate, #55 would have to mix client ownership, Redis commands,
serialization, compression, and coordination in one implementation.

## Approved Requirements

- Add the focused `bluetape-cache-redis` distribution under
  `bluetape.cache.redis`.
- Pin and lock the official `redis` package without adding it to
  `bluetape-cache`, `bluetape-core`, or the default `bluetape` install.
- Use structural Python `Protocol` contracts instead of copying Kotlin or Go
  interface shapes mechanically.
- Preserve the existing `PayloadMetadata`, `SerializedPayload`, and
  `Compressor` contracts.
- Let callers select compact binary or compact JSON/base64 envelopes.
- Treat binary as the default envelope format.
- Treat compression as explicit: no compressor means `identity`; a configured
  compressor always runs regardless of payload size.
- Record the actual algorithm in every envelope and never auto-detect or try
  multiple decompression algorithms.
- Treat caller-supplied Redis clients as borrowed. Only clients constructed by
  provider factories are owned.
- Keep sync and async operation semantics equivalent. Async cancellation is
  never swallowed, retried, or translated.
- Preserve original Redis failures as causes while redacting keys, tokens,
  payloads, connection URLs, and provider diagnostics from public text and
  observability.
- Use the ecosystem `RedisServer` wrapper for every Docker-backed test.
- Stop at the explicit PR and merge boundaries required by `bluetape-workflow`.

## Non-Goals

- Cross-process lease acquisition, polling, retry, loader execution, or result
  publication orchestration; these belong to #55.
- Durable Redis L2 value caching.
- Pub/Sub near-cache invalidation; this belongs to #56.
- Redlock, lease renewal, fencing, or external-write safety.
- Framework-specific integration.
- Built-in JSON or Fory policy selection for application values.
- Cross-language wire compatibility.
- Automatic compression thresholds, compression-ratio selection, format
  detection, or fallback decoding.
- Redis Cluster, Sentinel, client-side caching, Pub/Sub, or pipeline wrappers.

## Current Evidence

### Repository anchors

- `bluetape-cache` is stdlib-only and exports local `TTLCache` and
  `AsyncTTLCache` implementations.
- `bluetape-serde` owns frozen `PayloadMetadata` and `SerializedPayload`
  contracts plus caller-selected trust profiles.
- `bluetape-compression` owns the structural `Compressor` Protocol, stable
  algorithm identifiers, immutable implementations, and bounded
  decompression.
- `bluetape-testcontainers` owns the single-use synchronous `RedisServer`
  test boundary.
- The default `bluetape` distribution depends only on `bluetape-core`; focused
  integrations are installed through extras.
- The full approved baseline passes with 1,099 tests on CPython 3.13.14 when
  the explicit Fory and native-compression extras are installed.

### Ecosystem anchors

- Kotlin `CompressableBinarySerializer` always compresses when a compressor is
  selected. The Python design preserves that explicit all-or-none behavior but
  keeps metadata and envelope policy separate.
- Go `cache/rediscoord` uses a caller-owned codec, a versioned owner-token
  result envelope, encoded-size bounds, non-error token mismatch, redacted
  provider errors, and namespace-based rollout. Python preserves these rules
  without copying its JSON-only wire format or coordination implementation.

### Upstream evidence

- PyPI reports `redis==8.0.1` as the current stable release supporting Python
  3.13: <https://pypi.org/project/redis/>.
- Official redis-py guidance recommends sharing a client for an application
  lifetime and closing it at shutdown. Async clients use `aclose()` and
  cancellation disconnects the affected connection to avoid protocol
  misalignment:
  <https://redis.io/docs/latest/develop/clients/redis-py/async/>.
- Official Redis guidance documents connection-pool ownership and explicit
  close behavior:
  <https://redis.io/docs/latest/develop/clients/redis-py/connect/>.

## Alternatives

### A. Layered structural contracts — selected

Separate payload codec, envelope format, envelope composition, and Redis byte
provider responsibilities. This gives #55 small testable components, preserves
caller policy, and keeps sync/async parity reviewable.

### B. Integrated Redis value provider — rejected

One provider could serialize, compress, envelope, and issue Redis commands.
This is convenient for a narrow call site but couples Redis lifecycle to value
policy and makes #55, tests, and custom codecs harder to compose.

### C. Free functions only — rejected

Free functions minimize initial types but scatter lifecycle, configuration,
error, and observability rules across callers. Sync and async behavior can
drift.

### D. Binary envelope only — rejected

Binary minimizes payload size, but operators sometimes need a directly
inspectable representation. Both formats can share the same semantic
conformance suite without runtime dependencies.

### E. JSON/base64 envelope only — rejected

JSON is inspectable and resembles the Go implementation, but base64 expands
binary payloads and conflicts with the stated Redis payload-size objective.

### F. MessagePack or CBOR envelope — rejected

These formats are compact but add a runtime provider solely for envelope
encoding. The stdlib binary format already meets the size goal.

## Package Boundary

### Distribution and namespace

```text
packages/bluetape-cache-redis/
  pyproject.toml
  README.md
  README.ko.md
  src/bluetape/cache/redis/
    __init__.py
    _contracts.py
    _envelope.py
    _formats.py
    _provider.py
  tests/
```

The exact internal file split may be refined in the implementation plan, but
the public namespace and responsibility boundaries are fixed by this spec.

### Dependencies

`bluetape-cache-redis` has exact workspace dependencies on:

- `redis==8.0.1`;
- `bluetape-serde==0.1.0`;
- `bluetape-compression==0.1.0`.

The base compression distribution is stdlib-only. LZ4, Snappy, and Zstandard
remain available only through the existing focused compression extras.

The `bluetape` meta distribution adds only `cache-redis` as a forwarding extra.
Redis and native compression providers are excluded from default, `dev`, and
`all` dependency sets. A caller composes extras explicitly, for example:

```bash
pip install "bluetape[cache-redis,compression-zstd]"
```

No root `bluetape/__init__.py` is created.

## Public Contracts

### PayloadCodec

```python
class PayloadCodec[T](Protocol):
    def encode(self, value: T) -> SerializedPayload:
        """Encode a value with caller-owned metadata and policy."""
        ...

    def decode(self, payload: SerializedPayload) -> T:
        """Decode a metadata-bearing payload under caller policy."""
        ...
```

The Redis package does not provide a default codec. Callers adapt strict JSON,
Apache Fory, or another policy explicitly. The codec remains responsible for
schema, type, content type, trust profile, input bounds, output bounds, and
registration.

### ResultEnvelope

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelope:
    version: int
    owner_token: str
    metadata: PayloadMetadata
    compression_algorithm: str
    payload: bytes
```

`ResultEnvelope` is public so custom `EnvelopeFormat` implementations can be
written without depending on internal state. Construction validates exact
types. Empty `payload` is valid; a missing payload field is not.

Owner tokens are exact strings whose ASCII encoding is 1 through 128 bytes.
Allowed characters are ASCII letters, digits, `.`, `_`, `~`, and `-`. Tokens
are opaque and never formatted into errors or events.

Compression identifiers follow the stable `Compressor.algorithm` values.
`identity` is reserved by this package and cannot be registered as a custom
compressor.

### EnvelopeFormat

```python
class EnvelopeFormat(Protocol):
    @property
    def format_id(self) -> str:
        """Return the stable configuration identifier."""
        ...

    def encode(self, envelope: ResultEnvelope) -> bytes:
        """Encode one validated semantic envelope."""
        ...

    def decode(self, data: bytes) -> ResultEnvelope:
        """Decode one complete envelope without fallback."""
        ...
```

The two built-in frozen implementations are `BinaryEnvelopeFormat` with
`format_id == "binary-v1"` and `JsonEnvelopeFormat` with
`format_id == "json-v1"`. Neither implementation auto-detects the other
format. Custom formats must pass the same semantic conformance suite.

### ResultEnvelopeCodec

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelopeCodec[T]:
    payload_codec: PayloadCodec[T]
    envelope_format: EnvelopeFormat = BinaryEnvelopeFormat()
    compressor: Compressor | None = None
    decompressors: tuple[Compressor, ...] = ()
    max_encoded_size: int = DEFAULT_MAX_ENCODED_SIZE

    def encode(self, owner_token: str, value: T) -> bytes: ...
    def decode(self, data: bytes, *, expected_owner_token: str) -> T | None: ...
```

`DEFAULT_MAX_ENCODED_SIZE` is 16 MiB, matching the current strict JSON payload
scale. Configuration is copied and validated during construction so later
caller mutation cannot alter behavior.

The writer compressor is automatically present in the read registry.
`decompressors` permits explicit readers for short migrations. Algorithm names
must be unique, `identity` is forbidden, and each envelope selects exactly one
registered decompressor. The implementation never tries another algorithm
after a failure.

`decode()` returns `None` when the envelope is well formed but its owner token
does not equal `expected_owner_token`. This is a normal stale-result outcome,
not an error. Malformed token fields remain errors.

### Redis providers

```python
class SyncRedisProvider:
    def __init__(self, client: redis.Redis, *, observer: RedisObserver | None = None): ...
    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        observer: RedisObserver | None = None,
        **redis_options: object,
    ) -> Self: ...

    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes, *, ttl: float) -> None: ...
    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def delete_if_value(self, key: str, expected_value: bytes) -> bool: ...
    def close(self) -> None: ...


class AsyncRedisProvider:
    # Equivalent constructor, factory, command, and result semantics.
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, *, ttl: float) -> None: ...
    async def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool: ...
    async def delete(self, key: str) -> bool: ...
    async def delete_if_value(self, key: str, expected_value: bytes) -> bool: ...
    async def aclose(self) -> None: ...
```

The final public signatures and export order are locked by contract tests.
Providers also support matching sync and async context-manager protocols.

`from_url()` mirrors redis-py's keyword configuration only where the provider
can preserve the binary contract. It rejects `connection_pool`, rejects an
explicit true `decode_responses`, and always constructs with
`decode_responses=False`. URL validation or client-construction failures are
wrapped as a redacted `create` operation without formatting the URL. A borrowed
client whose pool exposes `decode_responses=True` is rejected at provider
construction; structurally compatible clients that do not expose that setting
remain subject to strict response-type checks on every command.

All other `redis_options` are forwarded unchanged to the matching redis-py
`from_url()` factory and remain redis-py configuration. Signature and forwarding
tests lock this contract. No option may silently override provider ownership,
binary responses, observer state, or close semantics.

### Representative composition

```python
from bluetape.cache.redis import (
    BinaryEnvelopeFormat,
    ResultEnvelopeCodec,
    SyncRedisProvider,
)
from bluetape.compression.native import ZstdCompressor

payloads = CatalogJsonCodec()  # caller-owned PayloadCodec[CatalogItem]
envelopes = ResultEnvelopeCodec(
    payload_codec=payloads,
    envelope_format=BinaryEnvelopeFormat(),
    compressor=ZstdCompressor(),
)

with SyncRedisProvider.from_url("redis://localhost:6379/0") as provider:
    encoded = envelopes.encode("owner-token-42", catalog_item)
    provider.set("coord:catalog:42", encoded, ttl=1.0)
    stored = provider.get("coord:catalog:42")
    restored = (
        None
        if stored is None
        else envelopes.decode(stored, expected_owner_token="owner-token-42")
    )
```

The async form uses the same codec and format objects with
`AsyncRedisProvider`, `async with`, awaited commands, and `await aclose()` when
not using a context manager.

## Envelope Encoding

### Composition order

Encoding is deterministic:

```text
value
  -> payload_codec.encode(value)
  -> SerializedPayload(metadata, data)
  -> selected compressor.compress(data), or identity
  -> ResultEnvelope(version, owner token, metadata, algorithm, payload)
  -> selected EnvelopeFormat.encode(envelope)
  -> enforce encoded envelope bound
  -> Redis bytes
```

Decoding runs in reverse:

```text
Redis bytes
  -> enforce encoded envelope bound
  -> selected EnvelopeFormat.decode(bytes)
  -> validate version, token field, metadata, algorithm, complete input
  -> token match? no => None
  -> selected bounded decompressor, or identity
  -> SerializedPayload(original metadata, logical data)
  -> payload_codec.decode(payload)
```

Compression does not alter metadata, schema, type, content type, or trust
profile. A configured compressor always runs, including for empty or small
payloads. No size threshold or compression-ratio branch is hidden in the
contract.

### BinaryEnvelopeFormat

The binary format uses this network-byte-order layout:

```text
magic "BTRE"                  4 bytes
envelope version              unsigned 8-bit
owner token length            unsigned 32-bit
owner token                   ASCII bytes
serde format length           unsigned 32-bit
serde format                  ASCII bytes
serde version                 unsigned 32-bit
content type length           unsigned 32-bit; 0xffffffff means None
content type                  UTF-8 bytes when present
trust profile length          unsigned 32-bit
trust profile                 ASCII bytes
compression algorithm length  unsigned 32-bit
compression algorithm         ASCII bytes
payload length                unsigned 32-bit
payload                       exact bytes
```

The maximum encoded size is below the unsigned 32-bit sentinel, so no legal
payload conflicts with the nullable content-type marker. The decoder checks the
outer bound, every declared length, field limits, exact terminal offset, and
integer validity before slicing or allocating derived values. Trailing bytes
are rejected.

Before materializing built-in binary output, the encoder computes the exact
header and field length and rejects a guaranteed oversize envelope. It still
performs a final exact bound check on the returned bytes. Custom formats receive
the validated semantic envelope but remain caller-owned code; the outer codec
always checks their returned exact `bytes` value and final encoded size. On
decode, the outer codec requires an exact `ResultEnvelope` return value and
revalidates every semantic field before token comparison, decompression, or
payload codec access.

Content type is limited to 1,024 UTF-8 bytes when present. Compression
algorithm identifiers are 1 through 64 allowed ASCII identifier characters.
Existing `PayloadMetadata` validation remains authoritative for its other
fields.

### JsonEnvelopeFormat

The JSON format uses compact UTF-8 JSON with these exact keys:

```json
{
  "version": 1,
  "owner_token": "opaque-token",
  "metadata": {
    "format": "json",
    "version": 1,
    "content_type": "application/json",
    "trust_profile": "untrusted"
  },
  "compression": "zstd-frame",
  "payload": "base64"
}
```

Actual output uses compact separators and deterministic key order. The decoder
rejects duplicate keys, unknown keys, missing keys, invalid UTF-8, invalid or
non-canonical base64, non-exact JSON scalar types, and trailing JSON input. It
checks the encoded-size bound before JSON parsing. JSON payload expansion is a
documented caller tradeoff.

The built-in JSON encoder preflights fixed syntax, encoded string fields, and
the exact base64 length before materializing the complete document, then checks
the returned byte length again. The preflight prevents predictable envelope
overhead from crossing the configured bound; codec and compressor output limits
remain independently responsible for their own intermediate allocations.

## Redis Command Semantics

- Keys are exact non-blank strings without surrounding whitespace or control
  characters. #55 owns namespace and key derivation.
- Values and expected values are exact immutable `bytes`.
- TTL values use seconds like the existing cache API. They must be finite and
  positive, reject `bool`, and convert to Redis milliseconds by rounding up.
  A positive sub-millisecond TTL therefore becomes 1 ms.
- `get()` returns exact bytes or `None`. A decoded string or another provider
  result type is a binary-contract failure; callers must not use
  `decode_responses=True`.
- `set()` uses one expiring write and succeeds only on the provider's exact
  success response.
- `set_if_absent()` uses `SET key value NX PX ttl` and returns whether the write
  occurred.
- `delete()` returns whether a key was deleted.
- `delete_if_value()` uses a fixed internal Lua compare-and-delete script and
  returns whether the expected bytes matched and the key was deleted. Script
  text is static; keys and values are arguments, not interpolated source.
- `delete_if_value()` requires Redis script execution (`EVAL`/`EVALSHA`). A
  server or ACL that forbids scripts yields a redacted provider failure; the
  provider does not replace the atomic operation with an unsafe GET/DELETE
  sequence.
- Providers do not retry commands. Retry policy belongs to the caller or #55.
- Providers do not retain keys or payload values after an operation completes.

Sync and async providers share conformance cases for validation, command
arguments, result normalization, errors, lifecycle, and observability.

## Client Ownership and Lifecycle

### Borrowed clients

A client passed directly to a provider constructor is borrowed. `close()` or
`aclose()` marks the provider closed but never closes the Redis client or its
pool. This prevents one adapter from invalidating a shared application client.

### Owned clients

`from_url()` constructs and owns one redis-py client. Closing the provider
closes that client exactly once. A close failure is surfaced as a redacted
provider error; the provider remains closed and a later close does not retry or
double-close the client.

### Common lifecycle

- Close is idempotent.
- Every operation after close raises `ProviderClosedError` before touching the
  client.
- Lifecycle state is `open`, `closing`, or `closed`. Close atomically enters
  `closing`, rejects new operations, waits for operations admitted while open,
  then closes an owned client and enters `closed`. No lifecycle lock is held
  across Redis I/O.
- Concurrent close callers share the same close completion and never invoke the
  owned client close method more than once.
- Context-manager exit closes the provider according to its ownership mode.
- The async provider never swallows or wraps `asyncio.CancelledError`.
- If cancellation interrupts an in-flight Redis call, provider state remains
  usable unless the provider itself was closed; redis-py owns connection-level
  recovery.
- The async provider binds to the first running event loop that performs an
  operation or close. Later use from another loop fails locally before client
  access.
- Async close atomically creates or joins one transient cleanup task that spans
  draining admitted operations, closing the owned client, and entering the
  terminal state. Cancellation cannot strand a half-closed provider. If a
  caller is cancelled, cleanup is shielded and awaited to completion before
  that caller's original `CancelledError` is rethrown. The task is never
  detached or retained after close.
- Provider construction has no eager network side effect. First-command
  connection behavior remains redis-py behavior.

## Error Contract

### Stable codes

`RedisOperation` identifies `create`, `get`, `set`, `set-if-absent`, `delete`,
`delete-if-value`, and `close`.

`RedisErrorCode` includes:

- `closed`;
- `invalid-input`;
- `connection`;
- `timeout`;
- `provider-failure`;
- `invalid-response`.

`EnvelopeErrorCode` includes:

- `invalid-input`;
- `encoded-size-limit`;
- `malformed-envelope`;
- `unsupported-version`;
- `unsupported-format`;
- `unknown-algorithm`;
- `compression-failure`;
- `payload-codec-failure`.

The implementation may use focused subclasses such as
`ProviderClosedError`, `EnvelopeSizeError`, `EnvelopeEncodeError`, and
`EnvelopeDecodeError`, while the stable code remains the machine-readable
contract.

### Cause and redaction

Redis failures are raised as `RedisProviderError` with the original redis-py
exception as `__cause__`. Envelope boundary failures preserve codec or
compressor errors as causes when safe. The wrapper's `str`, `repr`, stable
fields, event data, and documentation examples never include raw keys, tokens,
payloads, connection URLs, credentials, or provider diagnostics.

The preserved `__cause__` is an explicit trusted diagnostic channel and can
contain text produced by redis-py or caller code. Python renders chained causes
in full tracebacks, so applications must not expose complete exception chains
to untrusted users. Observers never receive the cause. Redaction tests prove
that injected sensitive markers are absent from the wrapper and events while
the original exception object remains available as `__cause__`.

Fatal `BaseException` subclasses propagate unchanged. Async cancellation is
observed as cancellation and rethrown unchanged.

## Observability

```python
class RedisObserver(Protocol):
    def on_event(self, event: RedisEvent) -> None:
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisEvent:
    mode: RedisMode
    operation: RedisOperation
    outcome: RedisOutcome
    error_code: RedisErrorCode | None
    elapsed_ns: int
```

Enum values are stable and low-cardinality. Elapsed time is a measurement, not
a label. Events contain no namespace, key, token, URL, connection details,
payload data, or payload size. The provider emits at most one terminal event
per attempted operation. Observer failures derived from `Exception` are
isolated and do not change the Redis result, exception, or cancellation
outcome; the provider does not log them or install global observer state. Fatal
`BaseException` subclasses, including a deliberately raised `CancelledError`,
propagate unchanged. The active-operation slot is released before invoking the
terminal observer so an observer cannot deadlock by closing the provider.

## Concurrency and Async Rules

- Providers add no global client, pool, lock, registry, task, or executor and
  no persistent background task. The only permitted transient task is the
  shielded async-close cleanup described above.
- Thread/task safety follows the supplied redis-py client. The provider stores
  only immutable configuration plus its local closed state.
- Close-versus-operation races use an admission counter and lifecycle gate: an
  operation admitted before close finishes and releases its slot in `finally`,
  while operations admitted after the `closing` transition fail locally. The
  implementation plan must select and test the smallest sync and async
  primitives that provide this rule without holding a lock across Redis I/O.
- Async command methods await redis-py directly. They do not use `asyncio.run`,
  create background tasks, or translate blocking calls through an executor.
- Cancellation and caller timeout ownership remain with the caller.

## Security Boundaries

- Redis transport security, authentication, ACL, TLS, credential rotation, and
  endpoint policy remain caller-owned redis-py configuration.
- Script execution is a declared server/ACL capability for atomic
  compare-and-delete. Absence is a hard capability error, not a reason to use a
  racy fallback.
- Serialization is not encryption. Redis operators can see envelope metadata
  and encoded payload bytes.
- `TrustProfile` is preserved exactly; compression and envelope encoding do
  not upgrade untrusted input to trusted input.
- Custom codecs, compressors, envelope formats, observers, and clients execute
  caller code. The package validates their returned public contract values but
  does not sandbox them.
- Lua source is constant and never interpolates caller-controlled key or value
  data.
- Decoders enforce the outer encoded bound before JSON parsing, binary field
  processing, decompression, or payload codec invocation.
- Unknown versions, formats, algorithms, and fields fail closed.

## Failure Modes

### 1. Encoded envelope exceeds the bound

Encoding rejects the complete result before Redis publication. Decoding checks
the raw Redis byte length before parsing or allocating derived payloads and
raises the stable size-limit error.

### 2. Compressed payload expands beyond its logical bound

The selected `Compressor` enforces its own `max_output_size` and raises a
bounded decompression error. The envelope codec returns no partial value and
does not try another algorithm.

### 3. Stale owner result

A valid envelope whose owner token differs from the expected token returns
`None`. It is not decoded through the application codec and is not treated as a
provider outage.

### 4. Malformed, truncated, duplicate, or trailing envelope input

The selected format rejects the input as a stable malformed-envelope error.
The implementation does not auto-detect another format.

### 5. Unknown compression algorithm

The decoder rejects before decompression. It does not import providers
dynamically, select a default, or try registered compressors in sequence.

### 6. Borrowed shared client is closed elsewhere

The next operation surfaces a redacted `RedisProviderError` retaining the
redis-py cause. Closing the borrowed provider never attempts to repair or close
the shared client.

### 7. Owned client close fails

Close reports a redacted close error and marks the provider closed. Subsequent
close calls are idempotent and do not invoke the client again.

### 8. Async close caller is cancelled

The provider completes the already-started owned-client cleanup exactly once,
enters `closed`, and then rethrows the caller's cancellation. It does not leave
a detached cleanup task.

### 9. Async operation is cancelled

The provider emits a cancellation event without sensitive values and rethrows
`CancelledError` unchanged. It does not retry or wrap the cancellation.

### 10. Observer raises

The provider isolates ordinary `Exception` failures, preserves the Redis
operation outcome, and performs no logging or global fallback. Fatal
`BaseException` subclasses propagate unchanged.

### 11. Client returns decoded text or an incompatible response

The provider raises `invalid-response` rather than guessing an encoding or
coercing a value. Documentation requires `decode_responses=False`.

## Test Design

### Contract and format tests

- exact public exports, signatures, Protocol method shapes, enum values, and
  frozen/slotted dataclasses;
- strict exact-type and boundary validation;
- shared binary/JSON semantic conformance;
- custom envelope format conformance and failure isolation;
- deterministic binary layout and compact JSON key order;
- duplicate, unknown, missing, truncated, trailing, invalid UTF-8, and invalid
  base64 cases;
- empty payload, exact encoded limit, and one-byte-over rejection;
- token match and non-match without application decode on non-match;
- metadata preservation across identity and compression paths;
- algorithm registry uniqueness and explicit selection;
- gzip, zlib, DEFLATE, LZ4, Snappy, and Zstandard composition;
- proof that input bounds run before parsing, decompression, or codec access.

### Provider unit and conformance tests

- identical sync/async command arguments and normalized results;
- success, nil/missing, invalid input, response mismatch, and provider failure;
- exact TTL conversion including sub-millisecond ceiling;
- fixed Lua source with key/value arguments;
- borrowed client preservation and owned client close exactly once;
- idempotent close, close failure, operation-after-close, and
  close-versus-operation admission;
- concurrent close, first-loop binding, cross-loop rejection, cancellation
  during async close, and absence of detached cleanup tasks;
- cause retention and redaction of key, token, payload, URL, credentials, and
  provider text;
- one terminal low-cardinality event per attempted operation;
- observer failure isolation;
- async timeout and cancellation without wrapping, retry, task, or resource
  leaks.

### Redis integration tests

All Docker-backed tests use one explicitly owned `RedisServer` fixture and run
serially:

- sync and async real-client get/set/delete parity;
- expiring writes and `NX` behavior;
- atomic compare-and-delete match and mismatch;
- borrowed and owned real-client lifecycle;
- binary and JSON envelope storage round trips;
- Redis outage and closed-client error redaction;
- connection cleanup after async operations.
- script-capability denial fails atomically without GET/DELETE fallback;
- factory option forwarding, forbidden ownership/binary overrides, and
  redacted factory failure.

### Packaging and CI tests

- base `bluetape-cache`, `bluetape-core`, and default `bluetape` wheels have no
  Redis or focused-provider dependency;
- the focused wheel declares exact Redis, serde, and base-compression
  dependencies;
- `bluetape[cache-redis]` forwards only the focused package;
- native compression remains absent unless its explicit extra is selected;
- isolated focused wheel imports sync and async APIs and runs Redis smoke tests;
- `uv lock --check`, all-package build, namespace coexistence, and metadata
  checks pass;
- a dedicated Redis-provider CI job installs only intended extras and runs
  Testcontainers tests serially;
- the existing provider-free CI assertion remains true.

## Validation Ladder

1. TDD RED/GREEN slices for contracts, formats, envelope composition, sync
   provider, async provider, and lifecycle.
2. Targeted non-Docker package tests.
3. Sequential `RedisServer` integration tests.
4. `uv run ruff format --check .` and `uv run ruff check .`.
5. `uv lock --check` and explicit dependency-isolation assertions.
6. Full pytest with intended Fory and native-compression extras.
7. `uv build --all-packages` and isolated wheel/import/metadata smoke checks.
8. `actionlint` and `git diff --check`.
9. Performance/stability scan and final 7-Tier review with `P0=0 P1=0`.
10. GitHub CI, live review/thread reread, and workflow DoD gates.

Testcontainers and native-provider checks are serialized across worktrees and
review lanes.

The performance scan includes a reproducible non-gating microbenchmark for
binary versus JSON envelope encoded size and encode/decode latency over empty,
small, and near-limit payloads. Results document environment and raw output;
they do not claim production capacity or replace correctness bounds.

## Documentation

- Add English and Korean package READMEs with install, architecture, sync and
  async examples, ownership, codec, envelope-format, compression, security,
  observability, rollout, and rollback guidance.
- Update root `README.md` and `README.ko.md` package tables and install examples
  together.
- Update `packages/bluetape/README.md` and `README.ko.md` with the forwarding
  extra while preserving the core-only default.
- Update `docs/package-layout.md`, `WIP.md`, and `CHANGELOG.md`.
- Document that binary is compact, JSON/base64 is inspectable, and neither is
  cross-language compatible.
- Document explicit namespace configuration and forbid format/codec/compressor
  fallback.
- No diagram is required for #54: the layers and one linear encode/decode flow
  are clearer as tables and text. #55 may add a coordination sequence diagram.

## Rollout and Rollback

Processes sharing a #55 namespace must use the same envelope format, payload
codec policy, writer compressor, decompressor registry, encoded-size bound,
and logical decompression limits.

Use a configuration-bearing namespace such as:

```text
catalog:binary-v1:json-v1:zstd-v1
```

Deploy readers before writers only when the reader registry explicitly
contains the upcoming algorithm. Each envelope still selects one exact
algorithm; no trial decoding occurs. For a format, codec, trust, or incompatible
schema change, use a new namespace and switch readers and writers together.

Rollback returns to the previous namespace and configuration. Retain the old
namespace for at least the future #55 lock TTL plus result TTL and a safety
margin. Cleanup relies on natural TTL expiry or bounded TTL-aware `SCAN MATCH`;
never use `KEYS`.

## Compatibility

The change is additive. Existing cache, serde, compression, testing, and meta
imports keep their behavior. The default meta install remains core-only.

The package promises semantic compatibility for the documented v1 fields and
rules inside Python. Built-in binary and JSON bytes are format-specific. No
Kotlin, Go, Rust, or Apache Fory cross-language wire compatibility is promised.

## Acceptance Criteria

1. `bluetape-cache-redis` is a focused Python 3.13+ distribution and the only
   new package that depends on `redis==8.0.1`.
2. Default, core, base-cache, `dev`, and `all` installs remain Redis-free; the
   explicit `cache-redis` extra resolves correctly.
3. Payload codec and envelope format are structural contracts; binary and JSON
   implementations pass one semantic conformance suite.
4. Result envelopes validate version, owner token, payload presence, metadata,
   format, algorithm, complete input, and the configured 16 MiB encoded bound.
5. A token mismatch returns `None` without payload codec invocation.
6. Identity and all six current compressors compose explicitly; a configured
   writer always compresses, and decode selects exactly one recorded algorithm.
7. Sync and async providers have equivalent get/set/NX/delete/compare-delete
   semantics and strict binary response handling.
8. Caller-supplied clients remain open; factory-owned clients close exactly
   once; close is idempotent and post-close operations fail locally.
9. Async command cancellation propagates unchanged with no retry, persistent
   background task, or resource leak; cancellation during owned async close
   completes cleanup before rethrowing.
10. Provider errors retain their Redis cause while wrapper text, stable fields,
    and events redact keys, tokens, payloads, URLs, credentials, and provider
    text; documentation identifies chained tracebacks as a trusted diagnostic
    channel.
11. All real Redis tests use `RedisServer` and pass sequentially for sync and
    async clients.
12. README locale pairs, package guidance, WIP, CHANGELOG, layout docs,
    packaging metadata, lock state, CI, and isolated wheel checks agree with
    source.
13. Spec, plan, implementation, performance/stability, verifier, pre-PR, and
    post-PR reviews converge at `P0=0 P1=0` before their dependent gates.

## Definition of Done

- Type A checklist A-01 through A-11 and Python checklist PY-01 through PY-07
  are reconciled with fresh evidence.
- Every acceptance criterion maps to an implementation-plan task and a fresh
  validation command.
- Targeted, integration, full-suite, lint, format, lock, build, isolated-wheel,
  workflow, and diff checks pass.
- Latest 7-Tier integrated review reports `P0=0 P1=0`; every P2/P3 is fixed,
  deferred with rationale, or filed.
- PR metadata and final `## DoD Status` are verified live, CI is green, and
  reviews/threads are reread after CI.
- Merge remains behind a separate explicit user decision.
