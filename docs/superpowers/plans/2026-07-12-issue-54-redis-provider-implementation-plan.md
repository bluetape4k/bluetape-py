# Issue #54 Redis Provider Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `bluetape-cache-redis` package with bounded selectable result envelopes,
caller-owned serialization and compression policy, and equivalent synchronous/asynchronous Redis
byte providers without changing the thin default install.

**Architecture:** `bluetape.cache.redis` separates immutable public contracts, binary/JSON
envelope formats, payload/compression composition, and Redis command/lifecycle adapters. A
factory-created redis-py client is owned while a directly supplied client is borrowed. The
package is opt-in, emits only low-cardinality redacted events, and gives #55 primitives without
implementing distributed load coordination.

**Tech Stack:** CPython 3.13.14; `redis==8.0.1`; Python `Protocol`, dataclasses, `struct`, `json`,
`base64`, `threading`, and `asyncio`; `bluetape-serde==0.1.0`;
`bluetape-compression==0.1.0`; pytest, pytest-asyncio, Redis 8 Testcontainers, Ruff, uv,
actionlint, and GitHub Actions.

---

Date: 2026-07-12
Issue: [#54](https://github.com/bluetape4k/bluetape-py/issues/54)
Depends on: #57 and #59
Blocks: [#55](https://github.com/bluetape4k/bluetape-py/issues/55)
Work type: Type A - Full Feature

## Execution constraints

- Apply `bluetape-py-patterns`, `test-driven-development`, and the active
  `bluetape-workflow` gates to every task.
- Preserve Python-native structural contracts. Kotlin and Go define semantic expectations only;
  do not promise cross-language bytes or copy their package shape.
- Keep `redis`, `bluetape-cache-redis`, and all native compression providers out of default,
  `dev`, and `all` dependency sets. Add only an explicit `cache-redis` forwarding extra.
- Never auto-detect an envelope format, try a second decompressor, coerce text to bytes, retry a
  Redis command, or replace atomic Lua compare-delete with GET/DELETE.
- A configured compressor always runs. No compressor records `identity`; `identity` is never a
  custom registry entry.
- Directly supplied clients are borrowed. Only `from_url()` clients are owned and closed.
- Never swallow, wrap, or retry `asyncio.CancelledError`. The async close cleanup spans admitted
  operation draining, owned-client close, and terminal state, and is never detached.
- Wrapper errors and events exclude keys, tokens, payloads, URLs, credentials, and provider text.
  The original exception is preserved only as the trusted `__cause__` diagnostic channel.
- All Docker tests use `RedisServer`, run serially, and do not create raw containers.
- Do not add #55 coordination, loaders, leases, result polling, durable L2 caching, Pub/Sub,
  Cluster, Sentinel, Redlock, retry, or framework integration.

## Step 3-P risk prediction

| Risk | Early signal | Mitigation and proof | Rollback or rerun point |
|---|---|---|---|
| Nested package cannot coexist in editable or wheel installs | `bluetape.cache.redis` imports only after one package shadows another | namespace/import tests in workspace and isolated wheels before behavior work | revert Task 1 metadata; fix package layout before Tasks 2-7 |
| Envelope parser allocates from hostile lengths | decoder slices/base64-decodes before outer and field bounds | exact preflight, cursor checks, duplicate-key hook, exact/+1 and hostile-length spies | revert Task 2/3 parser commit and rerun format security subsets |
| Compression migration tries unintended algorithms | a decompressor spy other than the recorded ID is called | immutable unique registry and unknown/failing algorithm tests | revert Task 4 and rerun registry/token-mismatch tests |
| Close races leak a client or deadlock | operation never releases admission or observer re-enters close under a lock | deterministic barriers, concurrent close tests, observer-close tests, no lock across Redis I/O | revert Task 5/6 independently and rerun lifecycle conformance |
| Async cancellation leaves a task/client behind | pending task remains after cancelled `aclose()` | one shared shielded cleanup task, cancellation barriers, `asyncio.all_tasks()` proof | revert Task 6 and rerun only async lifecycle tests |
| Secrets escape through public diagnostics | hostile marker occurs in wrapper/event or full URL is formatted | exact stable messages, marker tests, observer schema, cause-only diagnostic rule | revert affected provider slice and rerun redaction suite |
| Redis becomes an implicit install dependency | default/dev/all metadata or base CI can import redis | dependency-isolation tests and isolated wheel installs | revert Task 1/8 metadata and lock changes |
| Lua ACL failure causes unsafe behavior | command trace contains GET followed by DELETE | fixed script and ACL-denial integration test proving no fallback | revert Task 5 and keep compare-delete unavailable |

The risk gate is mandatory because this package parses untrusted Redis bytes, owns optional network
resources, adds async cancellation behavior, and sits on the future distributed-cache hot path.

## File structure

| Path | Responsibility |
|---|---|
| `packages/bluetape-cache-redis/pyproject.toml` | Focused runtime dependencies, Python policy, test group, and build mapping. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py` | Ordered stable public export surface only. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py` | Protocols, enums, events, result envelope, stable errors, and validation. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_formats.py` | Strict binary and compact JSON envelope formats. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_envelope.py` | Payload codec, compression registry, token matching, and format composition. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_provider.py` | Shared validation plus synchronous Redis provider and lifecycle. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_async_provider.py` | Async Redis provider, loop affinity, admission, and shielded close. |
| `packages/bluetape-cache-redis/tests/_support.py` | Fake sync/async clients, barriers, observers, codecs, and hostile markers. |
| `packages/bluetape-cache-redis/tests/test_contracts.py` | Exact exports, signatures, values, immutability, and validation. |
| `packages/bluetape-cache-redis/tests/test_formats.py` | Shared semantic conformance and strict binary/JSON fixtures. |
| `packages/bluetape-cache-redis/tests/test_envelope_codec.py` | Codec/compressor composition, bounds, selection, and token outcomes. |
| `packages/bluetape-cache-redis/tests/test_sync_provider.py` | Sync command, error, observer, ownership, and race contracts. |
| `packages/bluetape-cache-redis/tests/test_async_provider.py` | Async parity, loop, cancellation, cleanup, and race contracts. |
| `packages/bluetape-cache-redis/tests/test_redis_integration.py` | Serial Redis 8 sync/async integration through `RedisServer`. |
| `packages/bluetape-cache-redis/tests/test_packaging.py` | Runtime dependency and namespace/install isolation contracts. |
| `packages/bluetape-cache-redis/benchmarks/envelope_benchmark.py` | Non-gating binary/JSON size and latency evidence. |
| `packages/bluetape-cache-redis/README.md`, `README.ko.md` | Focused install, API, lifecycle, safety, rollout, and examples. |
| `pyproject.toml`, `uv.lock`, `packages/bluetape/pyproject.toml` | Workspace registration, exact resolution, marker, and forwarding extra. |
| `.github/workflows/ci.yml` | Provider-free base proof and dedicated serial Redis-provider job. |
| `README.md`, `README.ko.md`, `packages/bluetape/README.md`, `packages/bluetape/README.ko.md` | Bilingual package status and install/usage guidance. |
| `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Durable package boundary, state, and user-visible completion record. |
| `docs/review/2026-07-12-issue-54-redis-provider-*.md` | TDD, performance/stability, verifier, and code-review evidence. |
| `docs/lessons/2026-07-12-issue-54-redis-provider.md` | Durable lesson before PR creation. |

## Acceptance traceability

| Approved requirement | Plan tasks |
|---|---|
| Focused package and Redis-free default/dev/all installs | 1, 8, 9 |
| Structural payload/format contracts and exact public API | 1, 2, 3, 4 |
| Binary default plus selectable strict JSON/base64 | 2, 3, 4 |
| Explicit identity or always-on configured compression | 4 |
| Exact algorithm selection and bounded decode | 4, 7 |
| Equivalent sync/async byte operations | 5, 6, 7 |
| Borrowed/owned lifecycle and close-race semantics | 5, 6, 7 |
| Cancellation, loop affinity, and no detached task | 6 |
| Redacted typed errors and low-cardinality events | 5, 6, 7 |
| Atomic compare-delete and script-capability failure | 5, 7 |
| RedisServer integration, packaging, CI, docs, and rollout | 7, 8, 9 |
| Full validation and 7-Tier completion gates | 10 |

## Task 1: Scaffold the focused package and lock public contracts

**Complexity:** Medium
**Depends on:** Approved spec
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache-redis/pyproject.toml`
- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py`
- Create: `packages/bluetape-cache-redis/tests/test_contracts.py`
- Create: `packages/bluetape-cache-redis/tests/test_packaging.py`
- Create: `packages/bluetape-cache-redis/README.md`
- Create: `packages/bluetape-cache-redis/README.ko.md`
- Modify: `pyproject.toml`
- Modify: `packages/bluetape/pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Write RED packaging and public-contract tests**

Add exact assertions for Python 3.13, dependencies, forwarding isolation, ordered exports,
structural protocols, frozen/slotted values, token validation, and stable enum/error values:

```python
def test_focused_distribution_has_exact_runtime_dependencies() -> None:
    project = load_pyproject(ROOT / "packages/bluetape-cache-redis/pyproject.toml")["project"]
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == [
        "bluetape-compression==0.1.0",
        "bluetape-serde==0.1.0",
        "redis==8.0.1",
    ]


def test_result_envelope_is_frozen_and_validated(metadata: PayloadMetadata) -> None:
    envelope = ResultEnvelope(
        version=1,
        owner_token="owner-42",
        metadata=metadata,
        compression_algorithm="identity",
        payload=b"value",
    )
    assert envelope.owner_token == "owner-42"
    assert not hasattr(envelope, "__dict__")
    with pytest.raises(ValueError, match="owner token"):
        replace(envelope, owner_token="")
```

Assert `PayloadCodec` and `EnvelopeFormat` are not runtime-checkable nominal bases. Assert the meta
extra is exactly `cache-redis = ["bluetape-cache-redis==0.1.0"]` and that `dev`/`all` omit it and
`redis`.

- [ ] **Step 2: Run the new tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_contracts.py \
  packages/bluetape-cache-redis/tests/test_packaging.py -q
```

Expected: collection/path failure because the package and contracts do not exist.

- [ ] **Step 3: Add metadata, workspace registration, and exact contracts**

Create the focused metadata:

```toml
[project]
name = "bluetape-cache-redis"
version = "0.1.0"
description = "Bounded Redis byte providers and result envelopes for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "bluetape-compression==0.1.0",
    "bluetape-serde==0.1.0",
    "redis==8.0.1",
]

[dependency-groups]
test = [
    "bluetape-testcontainers==0.1.0",
    "pytest>=8.4.0",
    "pytest-asyncio>=1.1.0",
]

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.cache.redis"
```

Define `PayloadCodec[T]`, `EnvelopeFormat`, `ResultEnvelope`, `RedisMode`, `RedisOperation`,
`RedisOutcome`, `RedisErrorCode`, `EnvelopeErrorCode`, `RedisEvent`, `RedisObserver`, and stable
typed errors: `RedisProviderError`, `ProviderClosedError`, `EnvelopeError`,
`EnvelopeSizeError`, `EnvelopeEncodeError`, and `EnvelopeDecodeError`. Use exact-type validation
and static messages. For example:

```python
class PayloadCodec[T](Protocol):
    def encode(self, value: T) -> SerializedPayload: ...
    def decode(self, payload: SerializedPayload) -> T: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelope:
    version: int
    owner_token: str
    metadata: PayloadMetadata
    compression_algorithm: str
    payload: bytes

    def __post_init__(self) -> None:
        _validate_envelope(self)
```

Add the package to root dependencies, uv sources, and workspace members so full workspace tests
exercise it; add only the `cache-redis` meta extra and keep meta default/dev/all unchanged. Resolve
with `uv lock`. Add initial English/Korean focused READMEs containing the package purpose, Python
3.13 policy, opt-in status, and the approved API summary. Task 9 expands that narrow scaffold with
verified examples and operational guidance.

- [ ] **Step 4: Run GREEN, namespace smoke checks, and commit**

```bash
uv sync --package bluetape-cache-redis --group test --locked
uv run pytest packages/bluetape-cache-redis/tests/test_contracts.py \
  packages/bluetape-cache-redis/tests/test_packaging.py -q
uv run python -c 'import bluetape.cache; import bluetape.cache.redis; assert bluetape.cache.redis'
```

Expected: all focused tests and both nested imports pass. Commit:

```bash
git add pyproject.toml uv.lock packages/bluetape/pyproject.toml \
  packages/bluetape-cache-redis
git commit -m "feat: establish Redis provider contracts"
```

Rollback point: revert this commit; no existing package API changes.

## Task 2: Implement the bounded binary envelope format

**Complexity:** High
**Depends on:** Task 1
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_formats.py`
- Create: `packages/bluetape-cache-redis/tests/_support.py`
- Create: `packages/bluetape-cache-redis/tests/test_formats.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`

- [ ] **Step 1: Write RED binary layout, boundary, and hostile-input tests**

Create a validated metadata fixture and assert magic/version/network-order layout, deterministic
bytes, empty payload, nullable content type, exact limit, one-over rejection, huge declared lengths,
truncation, trailing bytes, invalid ASCII/UTF-8, unknown version, and exact `ResultEnvelope` output:

```python
def test_binary_format_round_trips_exact_semantics(envelope: ResultEnvelope) -> None:
    formatter = BinaryEnvelopeFormat(max_encoded_size=4096)
    encoded = formatter.encode(envelope)
    assert encoded[:5] == b"BTRE\x01"
    assert formatter.decode(encoded) == envelope


def test_binary_format_rejects_declared_length_before_slicing() -> None:
    hostile = b"BTRE\x01" + struct.pack("!I", 0xFFFF_FFFF)
    with pytest.raises(EnvelopeDecodeError) as captured:
        BinaryEnvelopeFormat(max_encoded_size=64).decode(hostile)
    assert captured.value.code is EnvelopeErrorCode.MALFORMED_ENVELOPE
```

Use parametrized field limits and prove a custom `bytes` subclass is rejected where the contract
requires exact bytes.

- [ ] **Step 2: Run the binary subset and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_formats.py -k binary -q
```

Expected: import failure because `BinaryEnvelopeFormat` does not exist.

- [ ] **Step 3: Implement cursor-based strict binary encode/decode**

Use `struct.Struct("!I")`, preflight exact output size, and a bounded cursor helper that validates
before slicing:

```python
_U32 = struct.Struct("!I")
_MAGIC = b"BTRE"


def _take(data: bytes, cursor: int, size: int) -> tuple[bytes, int]:
    if size < 0 or size > len(data) - cursor:
        raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
    end = cursor + size
    return data[cursor:end], end
```

Encode every approved field in the exact spec order; use `0xFFFF_FFFF` only for `None` content
type. Reject unknown magic/version, illegal field lengths, invalid exact scalar types, and any
terminal offset other than `len(data)`. Validate the decoded `ResultEnvelope` again before return.

- [ ] **Step 4: Run GREEN and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_formats.py -k binary -q
uv run ruff check packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
```

Expected: binary tests and Ruff pass. Commit:

```bash
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: add bounded binary result envelopes"
```

## Task 3: Add the strict compact JSON envelope format

**Complexity:** Medium
**Depends on:** Task 2
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_formats.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/tests/test_formats.py`

- [ ] **Step 1: Write RED shared conformance and JSON strictness tests**

Parametrize both built-in formats through the same semantic suite. Add exact compact key order,
canonical base64, exact JSON scalar types, invalid UTF-8, duplicate/unknown/missing keys, trailing
JSON, empty payload, exact bound, one-over, and custom-format return validation:

```python
def test_json_format_is_compact_and_deterministic(envelope: ResultEnvelope) -> None:
    encoded = JsonEnvelopeFormat(max_encoded_size=4096).encode(envelope)
    assert b" " not in encoded and b"\n" not in encoded
    assert list(json.loads(encoded)) == [
        "version", "owner_token", "metadata", "compression", "payload"
    ]


def test_json_format_rejects_duplicate_keys(envelope: ResultEnvelope) -> None:
    encoded = JsonEnvelopeFormat().encode(envelope)
    hostile = encoded.replace(b'"version":1', b'"version":1,"version":1', 1)
    with pytest.raises(EnvelopeDecodeError):
        JsonEnvelopeFormat().decode(hostile)
```

- [ ] **Step 2: Run the JSON subset and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_formats.py -k json -q
```

Expected: import/attribute failure for `JsonEnvelopeFormat`.

- [ ] **Step 3: Implement compact JSON with strict hooks and preflight**

Use a duplicate-key rejecting hook, `base64.b64decode(..., validate=True)`, round-trip canonical
base64 comparison, exact key sets, and exact `type(...)` checks. Decode UTF-8 first and use
`JSONDecoder.raw_decode()` so the returned terminal offset must equal the exact text length;
therefore even otherwise legal trailing whitespace is rejected:

```python
def _object_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
        result[key] = value
    return result
```

Preflight fixed syntax, encoded string fields, and `4 * ((len(payload) + 2) // 3)` before building
the document. Encode with compact separators and deterministic insertion order; reject non-exact
bytes and any decoded object that cannot construct a valid exact `ResultEnvelope`.

- [ ] **Step 4: Run the complete format suite and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_formats.py -q
uv run ruff format --check packages/bluetape-cache-redis
```

Expected: the shared and format-specific suites pass. Commit:

```bash
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests/test_formats.py
git commit -m "feat: add strict JSON result envelopes"
```

## Task 4: Compose payload codecs, formats, and explicit compression

**Complexity:** High
**Depends on:** Tasks 1-3
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_envelope.py`
- Create: `packages/bluetape-cache-redis/tests/test_envelope_codec.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED composition, selection, and failure-isolation tests**

Add recording codecs/compressors and tests for binary default, identity, always-compress empty and
small inputs, metadata preservation, writer registration, explicit migration readers, duplicate
algorithm rejection, unknown algorithm, exact format output, token mismatch without decompression
or payload decode, custom format type/semantic revalidation, outer exact/+1 bounds, and ordinary
codec/compressor failure translation. Add built-in format/codec limit compatibility cases: a built-in
format bound smaller than the codec bound is rejected at construction, while an equal or larger
format bound is accepted and the codec's smaller bound remains authoritative:

```python
def test_configured_compressor_always_runs(metadata: PayloadMetadata) -> None:
    compressor = RecordingCompressor(algorithm="recording", output=b"compressed")
    codec = ResultEnvelopeCodec(
        payload_codec=StaticPayloadCodec(SerializedPayload(metadata=metadata, data=b"")),
        compressor=compressor,
    )
    encoded = codec.encode("owner-1", object())
    assert compressor.compressed_inputs == [b""]
    assert BinaryEnvelopeFormat().decode(encoded).compression_algorithm == "recording"


def test_token_mismatch_does_not_decompress_or_decode(envelope_bytes: bytes) -> None:
    compressor = RecordingCompressor(algorithm="recording")
    payload_codec = RecordingPayloadCodec()
    codec = ResultEnvelopeCodec(payload_codec=payload_codec, decompressors=(compressor,))
    assert codec.decode(envelope_bytes, expected_owner_token="other") is None
    assert compressor.decompressed_inputs == []
    assert payload_codec.decoded_payloads == []
```

Parametrize `GzipCompressor`, `ZlibCompressor`, `DeflateCompressor`, `Lz4Compressor`,
`SnappyCompressor`, and `ZstdCompressor` when their explicit extras are present; keep native cases
under `native_compression`.

- [ ] **Step 2: Run focused composition tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_envelope_codec.py \
  -m "not native_compression" -q
```

Expected: import failure because `ResultEnvelopeCodec` does not exist.

- [ ] **Step 3: Implement immutable configuration and one-algorithm decode**

Copy and validate configuration in `__post_init__`; automatically include the writer in an
immutable mapping and reject duplicate/reserved identifiers:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelopeCodec[T]:
    payload_codec: PayloadCodec[T]
    envelope_format: EnvelopeFormat = field(default_factory=BinaryEnvelopeFormat)
    compressor: Compressor | None = None
    decompressors: tuple[Compressor, ...] = ()
    max_encoded_size: int = DEFAULT_MAX_ENCODED_SIZE
    _readers: Mapping[str, Compressor] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        readers = _build_reader_registry(self.compressor, tuple(self.decompressors))
        object.__setattr__(self, "decompressors", tuple(self.decompressors))
        object.__setattr__(self, "_readers", MappingProxyType(readers))
```

`encode()` requires exact `SerializedPayload`, compresses whenever configured, creates version 1,
delegates to the selected format, then validates exact returned bytes and final size. `decode()`
checks raw size, requires an exact revalidated `ResultEnvelope`, rejects unsupported version,
returns `None` on token mismatch before decompression, selects only the recorded algorithm, creates
an exact `SerializedPayload`, and delegates once to the caller codec. Re-raise fatal
`BaseException`; translate ordinary boundary failures with stable codes and causes. When a built-in
format exposes `max_encoded_size`, require it to be at least the codec's configured limit. Custom
formats remain governed by the outer codec limit before decode and after encode.

- [ ] **Step 4: Run base and native GREEN suites and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_envelope_codec.py \
  -m "not native_compression" -q
uv sync --package bluetape-compression --extra native --group test --locked
uv run pytest packages/bluetape-cache-redis/tests/test_envelope_codec.py \
  -m native_compression -q
```

Expected: identity, stdlib, and all three native providers pass. Commit:

```bash
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: compose Redis result envelope codecs"
```

## Task 5: Implement the synchronous Redis byte provider

**Complexity:** High
**Depends on:** Task 1
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_provider.py`
- Create: `packages/bluetape-cache-redis/tests/test_sync_provider.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED command, error, observer, and lifecycle tests**

Use a recording fake client and deterministic `threading.Event` barriers. Cover exact validation,
sub-millisecond TTL ceiling, SET/PX, SET/NX/PX, missing GET, response mismatch, fixed Lua arguments,
script denial, no retry, redacted cause retention, one terminal event, observer failure/re-entry,
borrowed preservation, owned close once, close failure, post-close local failure, admitted-operation
draining, concurrent close, exact `inspect.signature()` results, ordered exports, and sync context
manager entry/exit:

```python
def test_sync_set_if_absent_uses_one_nx_px_command(client: SyncFakeRedis) -> None:
    provider = SyncRedisProvider(client)
    assert provider.set_if_absent("key", b"value", ttl=0.000_1) is True
    assert client.calls == [("set", ("key", b"value"), {"nx": True, "px": 1})]


def test_sync_delete_if_value_uses_fixed_script(client: SyncFakeRedis) -> None:
    provider = SyncRedisProvider(client)
    assert provider.delete_if_value("key", b"token") is True
    assert client.calls == [("eval", (COMPARE_AND_DELETE_SCRIPT, 1, "key", b"token"), {})]


def test_borrowed_close_never_closes_client(client: SyncFakeRedis) -> None:
    provider = SyncRedisProvider(client)
    provider.close()
    provider.close()
    assert client.close_calls == 0
```

Inject markers through key, value, URL, credentials, and provider exception text; assert absence
from wrapper `str`, `repr`, stable fields, and events while identity-checking `__cause__`.

- [ ] **Step 2: Run sync tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_sync_provider.py -q
```

Expected: import failure because `SyncRedisProvider` does not exist.

- [ ] **Step 3: Implement validation, command translation, and admission lifecycle**

Implement exact key/value/TTL validation and static Lua:

```python
COMPARE_AND_DELETE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
""".strip()


def _ttl_milliseconds(ttl: float) -> int:
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
        raise TypeError("ttl must be a real number")
    if not math.isfinite(ttl) or ttl <= 0:
        raise ValueError("ttl must be finite and positive")
    return math.ceil(ttl * 1000)
```

Use `threading.Condition` with `open`, `closing`, `closed`, and an active-operation counter. Admit
before client access, release in `finally`, and emit the terminal observer only after release. The
leader close transitions to closing and drains; concurrent callers that observed closing join the
same completion. Store the terminal close error permanently in private provider state: callers
that observed `closing` receive that shared outcome, while calls that first observe terminal
`closed` are idempotent no-ops and ignore the stored error. Never hold the condition while doing
Redis I/O or invoking observers.

`from_url()` rejects `connection_pool` and true `decode_responses`, forces false, forwards every
other option unchanged, and wraps construction failures as operation `create` without the URL.
Direct constructors reject an exposed true decode setting. Map redis connection/timeout failures
to stable codes and all other ordinary failures to provider-failure, always using static wrapper
messages and `raise wrapper from cause`.

- [ ] **Step 4: Run sync GREEN, race repetition, and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_sync_provider.py -q
for run in {1..10}; do
  uv run pytest packages/bluetape-cache-redis/tests/test_sync_provider.py \
    -k "close or concurrent or observer" -q || exit 1
done
```

Expected: all runs pass without a hang. Commit:

```bash
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: add synchronous Redis byte provider"
```

## Task 6: Implement async parity and cancellation-safe lifecycle

**Complexity:** High
**Depends on:** Task 5
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_async_provider.py`
- Create: `packages/bluetape-cache-redis/tests/test_async_provider.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED async parity, loop, race, and cancellation tests**

Reuse the sync conformance cases through async adapters and add async-only checks for direct awaits,
first-operation/close loop binding, cross-loop rejection before client access, cancellation during
a Redis command, concurrent `aclose()`, cancellation while draining, cancellation during owned
client close, close failure, no detached tasks, exact public signatures, and async context manager
entry/exit:

```python
@pytest.mark.asyncio
async def test_cancelled_aclose_finishes_owned_cleanup(
    monkeypatch: pytest.MonkeyPatch, owned_client: AsyncFakeRedis
) -> None:
    monkeypatch.setattr(redis.asyncio.Redis, "from_url", lambda *args, **kwargs: owned_client)
    provider = AsyncRedisProvider.from_url("redis://sensitive.invalid/0")
    tasks_before = set(asyncio.all_tasks())
    owned_client.block_close()
    caller = asyncio.create_task(provider.aclose())
    await owned_client.close_started.wait()
    caller.cancel()
    owned_client.release_close()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert owned_client.aclose_calls == 1
    with pytest.raises(ProviderClosedError):
        await provider.get("key")
    assert not ({task for task in asyncio.all_tasks() if not task.done()} - tasks_before)


@pytest.mark.asyncio
async def test_operation_cancellation_is_unchanged(client: AsyncFakeRedis) -> None:
    provider = AsyncRedisProvider(client)
    client.get_error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await provider.get("key")
    assert client.get_calls == 1
```

For cancelled close plus owned-client close failure, lock the deterministic rule: caller
cancellation wins and is rethrown unchanged after cleanup reaches terminal `closed`; the observer
emits that caller's single `cancelled` event with the stable cleanup error code when cleanup also
failed. Concurrent non-cancelled callers receive the shared close failure. No later call that first
observes terminal `closed` retries or re-raises the provider failure.

- [ ] **Step 2: Run async tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_async_provider.py -q
```

Expected: import failure because `AsyncRedisProvider` does not exist.

- [ ] **Step 3: Implement async commands, admission, and shielded close**

Mirror validation/result/error/event behavior while awaiting redis-py directly. Bind the running
loop before the first operation or close, lazily create loop-owned synchronization, and reject a
different loop locally. Atomically create/join exactly one close task:

```python
async def aclose(self) -> None:
    cleanup = await self._get_or_create_close_task()
    cancelled: asyncio.CancelledError | None = None
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError as error:
            if cancelled is None:
                cancelled = error
    close_error = cleanup.exception()
    if cancelled is not None:
        raise cancelled
    if close_error is not None:
        raise close_error
```

The cleanup coroutine drains admitted operations, awaits owned `client.aclose()` once, stores the
terminal result, enters closed in `finally`, wakes joiners, and clears the retained task reference
only after all callers can observe completion. No command creates a task. Observer invocation
occurs after admission release; ordinary `Exception` is isolated, fatal `BaseException` and a
deliberate observer `CancelledError` propagate. Every public close caller emits at most one terminal
event: success/failure for its shared completion, or cancelled after cleanup for a cancelled caller;
idempotent calls that first observe `closed` may emit success without touching the client.

- [ ] **Step 4: Run async GREEN and deterministic stress repetitions**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_async_provider.py -q
for run in {1..10}; do
  uv run pytest packages/bluetape-cache-redis/tests/test_async_provider.py \
    -k "cancel or close or loop" -q || exit 1
done
```

Expected: every run passes with zero pending-task warnings. Commit:

```bash
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: add asynchronous Redis byte provider"
```

## Task 7: Prove behavior against Redis 8 through the ecosystem wrapper

**Complexity:** High
**Depends on:** Tasks 2-6
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache-redis/tests/test_redis_integration.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write serial Testcontainers integration tests**

Use one explicitly owned `RedisServer` fixture and its URL. Cover sync/async set/get/delete, PX
expiry, NX, compare-delete match/mismatch, borrowed client preservation, factory-owned close,
binary/JSON round trips, outage/closed-client redaction, async connection cleanup, and script ACL
denial with no fallback:

```python
@pytest.fixture(scope="module")
def redis_server() -> Iterator[RedisServer]:
    with RedisServer() as server:
        yield server


@pytest.mark.testcontainers
def test_real_sync_compare_delete_is_atomic(redis_server: RedisServer) -> None:
    with SyncRedisProvider.from_url(redis_server.url) as provider:
        provider.set("issue:54:owner", b"owner-1", ttl=5.0)
        assert provider.delete_if_value("issue:54:owner", b"other") is False
        assert provider.get("issue:54:owner") == b"owner-1"
        assert provider.delete_if_value("issue:54:owner", b"owner-1") is True
```

Create a restricted Redis ACL user for the script-denial case, trace the client calls with a
wrapper, and assert the failure has operation `delete-if-value`, contains no credentials/key/value,
and never invokes GET or DELETE. Restore/delete the user in `finally`.

- [ ] **Step 2: Run the integration suite and diagnose RED before editing production code**

```bash
uv run pytest -m testcontainers \
  packages/bluetape-cache-redis/tests/test_redis_integration.py -q
```

Expected on first run: any mismatch with real redis-py return values, pool settings, Lua bytes, or
close behavior is recorded as RED. If Docker is unavailable, record the environmental blocker and
run this gate in CI before merge; do not substitute mocks for the required integration evidence.

- [ ] **Step 3: Make the smallest contract-preserving corrections**

Adjust only provider normalization or test setup justified by real Redis evidence. Keep strict
response tables explicit:

```python
def _require_set_success(response: object) -> None:
    if response is not True:
        raise RedisProviderError(
            operation=RedisOperation.SET,
            code=RedisErrorCode.INVALID_RESPONSE,
        )


def _deleted(response: object, *, operation: RedisOperation) -> bool:
    if type(response) is not int or response not in (0, 1):
        raise RedisProviderError(operation=operation, code=RedisErrorCode.INVALID_RESPONSE)
    return response == 1
```

Do not weaken binary response checks, ownership, redaction, atomicity, or cancellation rules to
accommodate a fixture.

- [ ] **Step 4: Run unit plus integration GREEN and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers" -q
uv run pytest -m testcontainers \
  packages/bluetape-cache-redis/tests/test_redis_integration.py -q
```

Expected: both suites pass serially. Commit:

```bash
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "test: verify Redis provider integration"
```

## Task 8: Lock dependency isolation, wheel smoke tests, and dedicated CI

**Complexity:** Medium
**Depends on:** Task 7
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-cache-redis/tests/test_packaging.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `uv.lock`

- [ ] **Step 1: Write RED isolation and metadata assertions**

Assert the focused wheel owns `bluetape.cache.redis`, exact runtime dependencies are present, root
workspace resolution is exact, meta forwarding works, and base/cache/core/default/dev/all remain
Redis-free:

```python
def test_default_and_aggregate_meta_extras_remain_redis_free() -> None:
    project = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    extras = project["optional-dependencies"]
    assert extras["cache-redis"] == ["bluetape-cache-redis==0.1.0"]
    assert all("cache-redis" not in item and "redis" not in item for item in extras["dev"])
    assert all("cache-redis" not in item and "redis" not in item for item in extras["all"])
```

- [ ] **Step 2: Run packaging RED and add the dedicated CI job**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_packaging.py -q
```

Expected: RED until every isolation/CI assertion is represented. Add a `redis-provider` job that
syncs the focused package plus its test group, runs unit tests, then runs Testcontainers serially.
Because `uv sync --all-packages` now intentionally installs the focused workspace member, remove
the in-workspace `find_spec("redis") is None` assertion from the general job. Preserve and extend
the existing isolated default-wheel check so its fresh virtual environment proves both `redis` and
`bluetape.cache.redis` are absent; keep Fory/native-provider absence checks in the general lane.

- [ ] **Step 3: Build and smoke isolated base and focused wheels**

Run exact isolated checks:

```bash
uv lock --check
uv build --all-packages
tmp_dir="$(mktemp -d)"
uv build --package bluetape-core --out-dir "$tmp_dir/base"
uv build --package bluetape --out-dir "$tmp_dir/base"
uv venv "$tmp_dir/base-venv" --python 3.13.14
uv pip install --python "$tmp_dir/base-venv/bin/python" --no-index \
  --find-links "$tmp_dir/base" bluetape==0.1.0
"$tmp_dir/base-venv/bin/python" -c \
  'import importlib.util; assert importlib.util.find_spec("redis") is None'

uv build --package bluetape-cache --out-dir "$tmp_dir/focused"
uv build --package bluetape-compression --out-dir "$tmp_dir/focused"
uv build --package bluetape-serde --out-dir "$tmp_dir/focused"
uv build --package bluetape-cache-redis --out-dir "$tmp_dir/focused"
uv venv "$tmp_dir/focused-venv" --python 3.13.14
uv pip install --python "$tmp_dir/focused-venv/bin/python" \
  --find-links "$tmp_dir/focused" bluetape-cache-redis==0.1.0
"$tmp_dir/focused-venv/bin/python" -c \
  'from bluetape.cache import TTLCache; from bluetape.cache.redis import SyncRedisProvider; assert TTLCache and SyncRedisProvider'
rm -rf "$tmp_dir"
```

Expected: base lacks redis; focused wheel coexists with `bluetape-cache` and imports both APIs.

- [ ] **Step 4: Run workflow syntax checks and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_packaging.py -q
actionlint
git diff --check
```

Expected: all commands pass. Commit:

```bash
git add pyproject.toml uv.lock .github/workflows/ci.yml \
  packages/bluetape-cache-redis/tests/test_packaging.py
git commit -m "build: isolate Redis provider packaging"
```

## Task 9: Add bilingual documentation and rollout guidance

**Complexity:** Medium
**Depends on:** Tasks 1-8
**Pattern skill:** `bluetape-maintenance`, then `bluetape-writer`

**Files:**

- Modify: `packages/bluetape-cache-redis/README.md`
- Modify: `packages/bluetape-cache-redis/README.ko.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `packages/bluetape/README.md`
- Modify: `packages/bluetape/README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write the English focused package guide from verified API**

Document focused/meta installation, binary default versus JSON selection, a complete payload-codec
example, identity and Zstd composition, sync/async provider usage, borrowed/owned lifecycle,
timeouts/cancellation, script ACL requirement, stable errors/events, trusted cause boundary,
namespace rollout/rollback, and non-goals. Use runnable code matching the public signatures:

```python
codec = ResultEnvelopeCodec(
    payload_codec=CatalogJsonCodec(),
    envelope_format=BinaryEnvelopeFormat(),
    compressor=ZstdCompressor(),
)
with SyncRedisProvider.from_url("redis://localhost:6379/0") as provider:
    provider.set("coord:catalog:42", codec.encode("owner-42", item), ttl=1.0)
```

- [ ] **Step 2: Write Korean parity and update repository/meta documentation**

Mirror every user-facing claim and code example in `README.ko.md`. Update both root README tables,
install lists, local commands, and usage sections; update both meta READMEs. Replace #54 pending
language in `WIP.md`, add the focused package boundary to `docs/package-layout.md`, and add one
`Unreleased / Added` entry to `CHANGELOG.md`. Keep PyPI publication HOLD wording intact.

- [ ] **Step 3: Verify locale and API drift mechanically**

```bash
rg -n "bluetape-cache-redis|cache-redis|BinaryEnvelopeFormat|JsonEnvelopeFormat|ZstdCompressor" \
  README.md README.ko.md packages/bluetape/README.md packages/bluetape/README.ko.md \
  packages/bluetape-cache-redis/README.md packages/bluetape-cache-redis/README.ko.md
uv run python - <<'PY'
from bluetape.cache.redis import BinaryEnvelopeFormat, JsonEnvelopeFormat
assert BinaryEnvelopeFormat().format_id == "binary-v1"
assert JsonEnvelopeFormat().format_id == "json-v1"
PY
git diff --check
```

Expected: every locale contains the same install/format/lifecycle concepts and the smoke code passes.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md README.ko.md WIP.md CHANGELOG.md docs/package-layout.md \
  packages/bluetape/README.md packages/bluetape/README.ko.md \
  packages/bluetape-cache-redis/README.md packages/bluetape-cache-redis/README.ko.md
git commit -m "docs: document Redis provider substrate"
```

## Task 10: Run performance/stability, full validation, and workflow gates

**Complexity:** High
**Depends on:** Tasks 1-9
**Pattern skill:** `bluetape-workflow`, `verification-before-completion`

**Files:**

- Create: `packages/bluetape-cache-redis/benchmarks/envelope_benchmark.py`
- Create: `docs/review/2026-07-12-issue-54-redis-provider-tdd-evidence.md`
- Create: `docs/review/2026-07-12-issue-54-redis-provider-performance-stability.md`
- Create: `docs/review/2026-07-12-issue-54-redis-provider-verifier.md`
- Create: `docs/review/2026-07-12-issue-54-redis-provider-code-review.md`
- Create: `docs/lessons/2026-07-12-issue-54-redis-provider.md`

- [ ] **Step 1: Add and run the non-gating envelope benchmark**

Benchmark empty, small, and near-limit payloads for both formats with warmup, repeated encode/decode,
raw byte size, median, and p95. Print machine-readable JSON including Python/platform/sample count;
do not add an absolute latency assertion:

```python
CASES = {"empty": b"", "small": b"x" * 1024, "near_limit": b"x" * (8 * 1024 * 1024)}
SAMPLES = {"empty": 5_000, "small": 1_000, "near_limit": 10}


def measure(formatter: EnvelopeFormat, envelope: ResultEnvelope, samples: int) -> dict[str, object]:
    encoded = formatter.encode(envelope)
    timings = []
    for _ in range(samples):
        started = perf_counter_ns()
        assert formatter.decode(formatter.encode(envelope)) == envelope
        timings.append(perf_counter_ns() - started)
    return {
        "format": formatter.format_id,
        "encoded_bytes": len(encoded),
        "median_ns": int(statistics.median(timings)),
        "p95_ns": sorted(timings)[max(0, math.ceil(samples * 0.95) - 1)],
    }
```

Run and capture raw output:

```bash
uv run python packages/bluetape-cache-redis/benchmarks/envelope_benchmark.py \
  | tee /tmp/issue-54-envelope-benchmark.json
```

Inspect that binary is smaller than JSON for byte-heavy cases, both remain within the configured
bound, and no unsupported capacity claim is made. Record environment and raw output in the
performance/stability review.

- [ ] **Step 2: Run the complete validation ladder with fresh evidence**

Run sequentially and record exit status/counts in the TDD/verifier artifacts:

```bash
uv sync --all-packages --extra fory --extra compression-native --locked
uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers" -q
uv run pytest -m native_compression packages/bluetape-cache-redis -q
uv run pytest -m testcontainers packages/bluetape-cache-redis -q
uv run ruff format --check .
uv run ruff check .
uv lock --check
uv run pytest
uv build --all-packages
actionlint
git diff --check
```

Expected: every command exits zero; pytest reports zero failures/errors; Docker/native lanes run
serially. Repeat the sync/async close-and-cancellation subsets ten times after the full suite and
record zero hangs, leaks, pending-task warnings, or flaky outcomes.

- [ ] **Step 3: Perform verifier and final 7-Tier implementation review**

Review the exact implementation diff independently through performance, stability, security,
operator/ops, developer/API, and user/caller perspectives, then integrate in the main session.
Record every finding with file/line evidence and severity. Fix every P0/P1, rerun each affected
lane, and require final `P0=0 P1=0`; fix, justify, or file every P2/P3. The verifier must reconcile
all 13 spec acceptance criteria, Type A A-01..A-11, Python PY-01..PY-07, dependency isolation,
locale parity, test evidence, and the GitHub diff.

Use this minimum review record shape:

```markdown
| Tier | P0 | P1 | P2 | P3 | Fresh evidence | Verdict |
|---|---:|---:|---:|---:|---|---|
| Performance | 0 | 0 | 0 | 0 | benchmark and bound tests | pass |
| Stability | 0 | 0 | 0 | 0 | race/cancellation repetitions | pass |
| Security | 0 | 0 | 0 | 0 | hostile envelopes and marker redaction | pass |
| Operator/Ops | 0 | 0 | 0 | 0 | CI, ACL, rollout, wheel checks | pass |
| Developer/API | 0 | 0 | 0 | 0 | signatures, exports, conformance | pass |
| User/caller | 0 | 0 | 0 | 0 | examples and locale parity | pass |
```

- [ ] **Step 4: Commit evidence and durable lesson**

Write the lesson only from verified implementation evidence: package-boundary choice, nested
namespace proof, strict parser decisions, cancellation-safe close pattern, Redis integration
surprises, and reusable commands. Commit benchmark source and evidence:

```bash
git add packages/bluetape-cache-redis/benchmarks \
  docs/review/2026-07-12-issue-54-redis-provider-tdd-evidence.md \
  docs/review/2026-07-12-issue-54-redis-provider-performance-stability.md \
  docs/review/2026-07-12-issue-54-redis-provider-verifier.md \
  docs/review/2026-07-12-issue-54-redis-provider-code-review.md \
  docs/lessons/2026-07-12-issue-54-redis-provider.md
git commit -m "docs: record Redis provider verification"
```

- [ ] **Step 5: Stop at the PR approval boundary**

Re-read the live diff and branch status, draft a PR body ending with `## DoD Status`, and report the
exact commits and fresh commands to the user. Do not push, create the PR, merge, close #54, or begin
#55 without the next explicit approval.

## Execution handoff

After this plan and its 7-Tier plan review are approved, start implementation in a fresh session so
the updated Codex runtime guidance is loaded. Two supported execution modes are available:

1. **Subagent-driven** — use `subagent-driven-development`, with a fresh role-specialized worker per
   task and two-stage review between tasks.
2. **Inline execution** — use `executing-plans`, execute task batches in this worktree, and stop at
   the documented checkpoints.

The implementation session must re-read the workspace/root `AGENTS.md`, repository `AGENTS.md`,
this plan, the approved spec, and the plan-review artifact before changing production code.
