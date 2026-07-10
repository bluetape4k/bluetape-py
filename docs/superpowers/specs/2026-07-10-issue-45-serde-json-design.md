# Issue #45 Strict Serde JSON Design

Date: 2026-07-10
Status: Approved; Step 6-R reviewed contract corrections integrated
Scope: issue #45, milestone `0.2.0`, `bluetape-serde`

## Problem

`bluetape-py` has strict text codecs and bounded compression helpers, but no
payload envelope that makes a serialization format, version, trust boundary,
or rejection reason explicit. Python's standard `json` module accepts bytes in
multiple Unicode encodings, accepts `NaN` and infinities by default, keeps the
last duplicate object key, and does not impose input-size or nesting-depth
limits. The first serde package must create a small, dependency-free boundary
before optional MessagePack, CBOR, Pydantic, or Apache Fory adapters are added.

## Current Evidence

- The root `pyproject.toml` is a Python 3.13+ `uv` workspace. Every current
  focused package is a separate no-runtime-dependency distribution under
  `packages/`, and the default `bluetape` meta distribution depends only on
  `bluetape-core`.
- `bluetape-codec` exposes a small module-level API, a `ValueError`-based
  typed error, exact ordered `__all__`, and parametrized malformed-input tests.
- `bluetape-compression` demonstrates bounded byte processing, validates
  non-boolean integer limits before backend use, and keeps public errors free
  of payload content.
- Issue #10's merged research decision selects `bluetape-serde` plus a strict
  stdlib JSON adapter. It explicitly excludes a registry, auto-detection,
  pickle, streams/files, encryption, compression composition, and dynamic type
  reconstruction. Apache Fory is the separate follow-up issue #46.
- The Python JSON documentation warns that untrusted JSON can consume
  considerable CPU and memory. It also documents permissive non-finite
  constants and duplicate-key behavior; the adapter must override those
  defaults rather than inherit them.

## Goals

1. Add a dependency-free `bluetape-serde` distribution with import path
   `bluetape.serde` and an explicit `bluetape[serde]` meta extra.
2. Define immutable bytes-first payload contracts: `PayloadMetadata`,
   `SerializedPayload`, and the closed `TrustProfile` enum.
3. Add a strict JSON bytes adapter with caller-visible finite input, output,
   and structural nesting limits.
4. Require an explicit expected metadata/trust contract on every decode and
   fail closed with typed, payload-free errors on mismatch or malformed input.
5. Prove the public contract by focused pytest coverage, package/wheel smoke
   tests, and English/Korean user documentation.

## Non-Goals

- No registry, auto-detection, generic object-graph serializer, type/class
  reconstruction, `pickle`, `marshal`, YAML, or fallback adapter.
- No stream/file API, compression/encryption composition, schema migration,
  message framing, caching policy, or metrics/logging subsystem.
- No third-party JSON backend or dependency; `orjson`, MessagePack, CBOR,
  Pydantic, and Apache Fory remain separate explicitly reviewed extras.
- No claim that this API establishes a process memory ceiling. Callers own
  transport admission and the already-materialized payload buffer.

## Architecture Pre-Design

This is a security-boundary and new-public-package change, so an architecture
pre-design is required. The selected architecture has three narrow layers:

1. **Contract layer**: immutable metadata and payload values plus typed,
   payload-free errors. It contains no adapter registry or global state.
2. **Strict JSON adapter**: serializes JSON-compatible Python values to UTF-8
   bytes and decodes only a caller-supplied `SerializedPayload` after metadata,
   byte, and depth checks.
3. **Packaging/docs layer**: registers the package as optional and documents
   that its finite limits bound adapter work, not total process memory.

Data flow is intentionally one-way and explicit:

```text
Python JSON value --json_serialize(metadata, limit)--> SerializedPayload
SerializedPayload --json_deserialize(expected metadata, limits)--> Python JSON value
```

No layer selects an adapter from payload content, changes the requested target
type, or silently falls back to another decoder.

## Alternatives Considered

### A. Registry plus multiple adapters in the first package

This would make future formats appear convenient, but would introduce
payload-selected behavior, configuration/default policy, and third-party
dependency decisions before the base contract has evidence. Rejected as too
broad and as a deserialization-risk multiplier.

### B. JSON convenience functions without a payload envelope

This would be small but could not make format/version/trust mismatch typed or
give #46 a stable boundary. Rejected because callers would re-invent metadata
and fallback policy around every adapter.

### C. Selected: contract envelope plus one strict stdlib JSON adapter

This follows the existing focused-package pattern, gives callers a small
Python-native surface, and establishes the security boundary that optional
adapters must preserve. It adds no runtime dependency and keeps the default
install unchanged.

## Public Contract

The package exposes exactly 21 ordered public names in the first slice:

```python
from bluetape.serde import (
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_OUTPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    MAX_SUPPORTED_NESTING_DEPTH,
    MAX_JSON_INTEGER_DIGITS,
    ContentTypeMismatchError,
    FormatMismatchError,
    InvalidMetadataError,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SerializedPayload,
    SerdeError,
    SerdeErrorCode,
    SerdeEncodeError,
    TrustProfile,
    TrustProfileMismatchError,
    UnsupportedVersionError,
    json_deserialize,
    json_serialize,
)

producer_metadata = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)
payload = json_serialize({"order_id": 42}, metadata=producer_metadata)

# Construct this from authenticated endpoint/queue policy, never from
# payload.metadata.
consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)
value = json_deserialize(payload, expected_metadata=consumer_policy)
```

The exact Python 3.13 surface is:

```python
from enum import StrEnum
from dataclasses import dataclass

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


class TrustProfile(StrEnum):
    UNTRUSTED = "untrusted"
    TRUSTED_INTERNAL = "trusted_internal"


@dataclass(frozen=True, slots=True, kw_only=True)
class PayloadMetadata:
    format: str
    version: int
    content_type: str | None
    trust_profile: TrustProfile


@dataclass(frozen=True, slots=True, kw_only=True)
class SerializedPayload:
    metadata: PayloadMetadata
    data: bytes


def json_serialize(
    value: JsonValue,
    *,
    metadata: PayloadMetadata,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> SerializedPayload: ...


def json_deserialize(
    payload: SerializedPayload,
    *,
    expected_metadata: PayloadMetadata,
    max_input_size: int = DEFAULT_MAX_INPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> JsonValue: ...
```

All configuration parameters are keyword-only. `json_serialize` requires
exact `PayloadMetadata`; `json_deserialize` requires exact
`SerializedPayload` and `PayloadMetadata`. Wrong runtime argument types raise
`TypeError` before value traversal, encoder iteration, metadata comparison, or
payload inspection. Both dataclasses have no field defaults; field order is
part of introspection only because construction is keyword-only.

`PayloadMetadata` and `SerializedPayload` are frozen, slotted dataclasses.
`SerializedPayload.data` accepts exact `bytes` only; it does not retain or
implicitly snapshot mutable `bytearray`/`memoryview` input. A wrong runtime
type raises `TypeError`. `b""` is valid payload data and never represents a
null payload. Empty JSON bytes are therefore reported as a typed malformed JSON
payload, not converted to `None`.

`PayloadMetadata` contains:

- `format`: exact `str`, validated lowercase ASCII identifier; the JSON adapter
  accepts exactly `"json"`.
- `version`: positive, non-boolean exact `int` schema/version identifier.
- `content_type`: exact `str` or `None` in the generic envelope. The JSON
  adapter requires exactly `"application/json"`; callers should not use
  `None` for JSON.
- `trust_profile`: exact `TrustProfile` enum value that records the payload's
  approved decode boundary.

Wrong metadata runtime types raise `TypeError`; correctly typed but invalid
values raise `InvalidMetadataError`. This preserves Python's caller-error
convention while keeping semantic metadata failures stable.

`json_deserialize` requires `expected_metadata`; it matches format, version,
content type, and trust profile exactly before parsing. The expected value is
caller policy supplied from an authenticated configuration, endpoint, queue,
cache namespace, or equivalent external boundary. It must never be copied or
inferred from the untrusted payload or its metadata. Payload metadata is only a
claim to validate, not proof of trust, and cannot raise its own trust level. A
mismatch raises the specific error instead of returning `None`, attempting
another format, or performing cache eviction/rebuild behavior.

The stable error tree is `SerdeError(ValueError)` with typed subclasses:
`InvalidMetadataError`, `FormatMismatchError`,
`ContentTypeMismatchError`, `UnsupportedVersionError`,
`TrustProfileMismatchError`, `PayloadLimitError`, `SerdeEncodeError`, and
`MalformedPayloadError`. Metadata construction rejects wrong field types,
boolean versions, and invalid trust-profile objects with `TypeError`; zero
versions and blank or non-lowercase format identifiers raise
`InvalidMetadataError`. Public messages and exception chaining must not expose
raw payload bytes, decoded snippets, or caller secrets. Stdlib `TypeError`,
`ValueError`, and `RecursionError` from unsupported,
circular, or excessively nested encode values become `SerdeEncodeError` with a
fixed reason category; no broad `Exception` catch is allowed. Translation must
record the public replacement inside the `except` block and raise it only after
leaving that block. The resulting public error must have both `__cause__ is
None` and `__context__ is None`; `raise ... from None` inside the handler is
insufficient because it retains payload-bearing exceptions in `__context__`.
Public adapter errors cross a narrow cloning boundary as type/code only. The
caller `payload`/`value` and derived data, text, traversal, encoder, chunk, and
output-buffer locals are cleared before a fresh public error is raised; no
`_json.py` helper traceback frame may retain traversal state.
`MemoryError`, `KeyboardInterrupt`, and `SystemExit` remain native.

Every `SerdeError` exposes a stable `code: SerdeErrorCode` rather than requiring
message parsing. `SerdeErrorCode` is a `StrEnum` with these 17 first-slice values:
`invalid_metadata`, `format_mismatch`, `content_type_mismatch`,
`unsupported_version`, `trust_profile_mismatch`, `input_limit`,
`output_limit`, `nesting_limit`, `integer_digit_limit`, `invalid_utf8`, `duplicate_key`,
`decode_non_finite_number`, `invalid_json`, `unsupported_value`,
`circular_reference`, `encode_non_finite_number`, and `encode_recursion`.
Messages and concrete classes are fixed by this matrix:

| Concrete class | Allowed code | Exact message |
| --- | --- | --- |
| `InvalidMetadataError` | `invalid_metadata` | `invalid payload metadata` |
| `FormatMismatchError` | `format_mismatch` | `payload format does not match expected format` |
| `ContentTypeMismatchError` | `content_type_mismatch` | `payload content type does not match expected content type` |
| `UnsupportedVersionError` | `unsupported_version` | `payload version is unsupported` |
| `TrustProfileMismatchError` | `trust_profile_mismatch` | `payload trust profile does not match caller policy` |
| `PayloadLimitError` | `input_limit` | `serialized payload exceeds max_input_size` |
| `PayloadLimitError` | `output_limit` | `serialized output exceeds max_output_size` |
| `PayloadLimitError` | `nesting_limit` | `JSON nesting exceeds max_nesting_depth` |
| `PayloadLimitError` | `integer_digit_limit` | `JSON integer exceeds MAX_JSON_INTEGER_DIGITS` |
| `MalformedPayloadError` | `invalid_utf8` | `payload is not valid UTF-8` |
| `MalformedPayloadError` | `duplicate_key` | `JSON object contains a duplicate key` |
| `MalformedPayloadError` | `decode_non_finite_number` | `JSON payload contains a non-finite number` |
| `MalformedPayloadError` | `invalid_json` | `payload is not valid JSON` |
| `SerdeEncodeError` | `unsupported_value` | `value is not JSON-serializable` |
| `SerdeEncodeError` | `circular_reference` | `value contains a circular reference` |
| `SerdeEncodeError` | `encode_non_finite_number` | `value contains a non-finite number` |
| `SerdeEncodeError` | `encode_recursion` | `value nesting exceeds encoder recursion support` |

`SerdeError(*, code: SerdeErrorCode)` owns the immutable `code` attribute and
fixed message lookup; callers may catch it but the adapter raises only concrete
subclasses. Fixed-code concrete errors have a zero-argument constructor.
`PayloadLimitError`, `MalformedPayloadError`, and `SerdeEncodeError` accept one
keyword-only `code`; a code outside that subclass's matrix rows raises
`ValueError`. No constructor accepts payload bytes, decoded text, arbitrary
message text, or a source exception. Tests assert every allowed mapping, reject
every cross-class combination, and verify the fixed message, `__cause__ is
None`, `__context__ is None`, and marker non-disclosure.

The JSON adapter implements exactly `format="json"`,
`content_type="application/json"`, and `version=1`. Encode rejects any other
format/content type with its mismatch error and any other version with
`UnsupportedVersionError`. Decode first validates that expected metadata names
this supported adapter/version, then compares actual payload metadata in the
deterministic order format, content type, version, trust profile. Matching
expected and actual metadata at an unsupported version never permits parsing.

## Trust And Strict JSON Semantics

The first adapter supports exactly two profiles:

| Profile | Decode boundary |
| --- | --- |
| `UNTRUSTED` | UTF-8 only; finite input/depth limits; string/escape-aware structural preflight; reject duplicate keys, non-finite constants, malformed JSON, and all implicit type reconstruction. |
| `TRUSTED_INTERNAL` | The same finite input/depth limits and no dynamic type reconstruction, registry lookup, or fallback. It is an explicit compatibility vocabulary for later trusted-only adapters, not permission to disable bounds. |

Both profiles use strict JSON syntax: `allow_nan=False` for encode,
`parse_constant` rejection for decode, and duplicate-key detection with
`object_pairs_hook`. Keeping these canonical JSON rules shared prevents a
trusted producer from emitting a value that an untrusted consumer interprets
differently.

`UNTRUSTED` is the default policy recommendation. `TRUSTED_INTERNAL` may be
chosen only for an authenticated and authorized closed deployment boundary; an
internal network location or payload claim alone is insufficient. The two
profiles intentionally have identical JSON parsing rules. Their distinction is
preserved for explicit caller policy and for later trusted-only adapters such
as Fory.

The decode sequence is fixed:

1. Validate payload/metadata runtime types and non-boolean integer byte/depth
   limits without inspecting payload content.
2. Validate supported expected format/content/version, then compare actual
   metadata in the order format, content type, version, trust profile.
3. Reject input over `max_input_size` before UTF-8 decode.
4. Decode bytes with explicit UTF-8 only; invalid UTF-8 becomes
   `MalformedPayloadError`.
5. Scan structural `{`, `}`, `[`, and `]` in one forward state-machine pass
   while respecting quoted strings and escaped quotes/backslashes; use no
   regex, slicing, recursion, or backtracking, keep only constant scanner state,
   and fail immediately when open-container depth is greater than
   `max_nesting_depth`.
6. Parse with strict constant, integer, and duplicate-key hooks. The integer
   hook rejects more than `MAX_JSON_INTEGER_DIGITS` decimal digits before
   calling `int()`, so behavior is independent of CPython's process-global
   integer-string digit setting. Translate
   `json.JSONDecodeError`, strict hook failures, and `RecursionError` to fixed,
   payload-free `MalformedPayloadError` only after leaving the handler so no
   payload-bearing context is retained; decode `RecursionError` uses the
   `invalid_json` code. No broad `Exception` catch is allowed.

Before encoder iteration, encode runs an iterative enter/leave-stack preflight
over exact JSON-native builtins only: `None`, `bool`, `int`, finite `float`,
`str`, `list`, and `dict` with exact `str` keys. It rejects tuples, subclasses,
custom objects, non-string keys, non-finite numbers, cycles, and container depth
over the configured limit. An active-container identity set distinguishes
cycles from repeated shared references. This prevents key coercion such as
`{1: "a", "1": "b"}` from producing duplicate wire keys and prevents hidden
user-defined conversion hooks. Exact integers whose absolute value has more
than `MAX_JSON_INTEGER_DIGITS` decimal digits are rejected by arithmetic
comparison without decimal string conversion.

Encode uses a compact `json.JSONEncoder(...).iterencode()` stream with
`allow_nan=False`. It UTF-8 encodes each emitted text chunk, compares it with
the remaining byte budget, and stops consuming encoder output as soon as the
next chunk would exceed `max_output_size`. Accepted chunks extend one
`bytearray` immediately, and the completed buffer is converted to `bytes`
exactly once. A single stdlib encoder
chunk may still be larger than the remaining budget, and the caller already
owns the source object graph; the limit bounds accepted aggregate adapter
output, not peak process memory.

Defaults are explicit constants: 16 MiB for input and output, depth 100, and
`MAX_JSON_INTEGER_DIGITS == 640` for every exact JSON integer.
The JSON default is deliberately lower than compression's 64 MiB returned-byte
default because decoding JSON creates a Python object tree with substantially
more overhead than the UTF-8 payload.
Byte limits must be non-boolean integers in `0..sys.maxsize - 1`.
`max_nesting_depth` must be a non-boolean integer in
`0..MAX_SUPPORTED_NESTING_DEPTH`, where the hard maximum is 256. Wrong types
raise `TypeError`; negative, overflowing, or over-depth configuration raises
`ValueError`, all before payload inspection. Zero bytes are permitted by the
envelope but not by JSON grammar; a depth limit of zero allows scalar JSON but
rejects arrays/objects. The hard depth maximum keeps parsing below ordinary
CPython recursion limits; `RecursionError` is still translated if a host lowers
its runtime recursion limit.

## Rollout, Recovery, And Follow-Up Contracts

This package does not migrate application schemas or storage. For a queue,
cache, or durable store, deploy readers that understand JSON version 1 before
enabling version-1 writers. Keep prior wire formats in a separate versioned
namespace/topic or explicit application path during the rollback window. A
rollback stops new-version writes first and retains the previous reader/writer
path until version-1 data is drained, expired, evicted, or migrated by the
application. `UnsupportedVersionError` is a hard reject; applications may
explicitly invoke a separately configured older reader and then migrate the
decoded value, but this package never retries versions or falls back itself.

Issue #46 must reuse `PayloadMetadata`, `SerializedPayload`, trust policy,
finite limits, and payload-free error codes. Its Fory adapter belongs in a
separate `fory` extra, begins as `TRUSTED_INTERNAL` only, requires explicit
schema/type identifiers, prohibits payload-selected dynamic type loading, and
must pass Python/Go/Rust/Kotlin conformance fixtures before release.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Stdlib JSON accepts attacker-controlled duplicate keys or non-finite values. | Configure duplicate-key and constant rejection in every decode path and test both profiles. |
| Brackets inside quoted or escaped strings falsely consume depth budget. | Implement a byte/character scanner that tracks quote and escape state; test bracket and backslash fixtures. |
| A large encode result allocates before the output limit check. | Consume `JSONEncoder.iterencode()` incrementally, account UTF-8 bytes per chunk, stop before final assembly, and test that later encoder chunks are not consumed after the limit fails. |
| High chunk counts retain one allocation per encoder chunk. | Extend one bounded `bytearray`, convert once, and use a prebuilt high-chunk-count `tracemalloc` regression with a stable small output multiple. |
| Raw input appears in exceptions or tracebacks. | Clone only public error type/code across a narrow boundary, clear caller and derived locals before raising a fresh error, and assert no `_json.py` helper frame or source identity remains. |
| Integer acceptance varies with `sys.set_int_max_str_digits`. | Enforce the fixed 640-digit contract before encode string conversion and through a decode `parse_int` hook before `int()`. |
| The optional package leaks into default installation. | Inspect built wheel metadata and create an isolated meta-wheel smoke test proving only core is installed by default. |
| Future Fory work bypasses this boundary. | Keep Fory out of this package and retain #46's explicit trusted-only and conformance gates. |

## Packaging And Documentation

Create `packages/bluetape-serde` as a `uv_build` distribution with no runtime
dependencies and module name `bluetape.serde`. Register it in the root
workspace and sources, then add `serde` plus `dev`/`all` extras in the thin
meta package without changing its default dependency.

Update the package README, root `README.md` and `README.ko.md`, package layout,
WIP, and CHANGELOG. Documentation must show only import-backed public usage,
construct expected metadata from authenticated caller policy rather than
received metadata, show fixed-code handling for mismatch/limit/malformed
failures, state that defaults are finite logical adapter limits, and identify
Fory as the separate follow-up. No diagram is needed because the existing
workspace diagram does not change and this feature adds no architectural visual
relationship.

## Acceptance Criteria

1. `bluetape-serde` imports as `bluetape.serde`, has no runtime dependency,
   and is installed only by `bluetape[serde]`, `bluetape[dev]`, or
   `bluetape[all]`; default `bluetape` remains core-only.
2. Metadata, payload, trust, and all documented typed errors are immutable or
   closed as designed; empty `bytes` remains data rather than an implicit null.
3. JSON output is UTF-8 and rejects non-finite values. Decode validates exact
   metadata/trust before parsing and has no fallback/type reconstruction path.
   Expected metadata comes only from an authenticated caller-owned policy;
   payload metadata cannot select or elevate its trust profile.
4. Decode rejects invalid UTF-8, malformed JSON, duplicate keys, non-finite
   constants, input over the limit, and depth over the limit with typed,
   payload-free errors. Public errors retain neither cause nor context and
   expose the documented stable `SerdeErrorCode`.
5. Structural preflight is one forward state-machine pass with no regex,
   slicing, recursion, or backtracking. It correctly ignores brackets in
   strings and escaped quotes/backslashes, including odd/even backslash runs
   before quotes (`\\\"`, `\\\\\"`) and mixed string content such as
   `"{[]}"`; depth-boundary and near-input-limit adversarial fixtures prove
   linear work and constant extra state.
6. Encode rejects result bytes over the output limit while consuming
   `iterencode()` output, uses one incremental `bytearray`, and does not consume later chunks after failure;
   unsupported and circular values become fixed, payload-free
   `SerdeEncodeError`; configured depth excess becomes `PayloadLimitError` with
   `nesting_limit`, while an unexpected encoder `RecursionError` becomes
   `SerdeEncodeError` with `encode_recursion`. Both encode/decode reject invalid
   limit argument shapes before consuming data. Encode also rejects non-string
   object keys, key-coercion collisions, cycles, non-native value types, and
   container depth over the configured bound. The error class/code/message
   matrix is exhaustively tested. Integers at 640 decimal digits succeed and
   641-digit integers fail identically on encode and decode regardless of the
   available CPython global integer-string digit setting.
7. Deployment docs specify reader-first rollout, versioned coexistence,
   rollback write-stop/order, and hard-reject version recovery. The #46 handoff
   preserves the envelope, trust, finite-limit, no-dynamic-type-loading, and
   cross-language conformance gates.
8. Focused tests, complete workspace tests, Ruff, lock verification, all-wheel
   build, built-wheel metadata inspection, README smoke tests, and `git diff
   --check` pass. Wheel proof includes no `Requires-Dist` in
   `bluetape-serde`, successful isolated `bluetape[serde]` import, core-only
   default meta install, and correct `serde` membership in `dev`/`all` markers.
9. Spec, plan, implementation, and PR review convergence each end at
   `P0 = 0` and `P1 = 0` before the next workflow stage.

## Definition Of Done

- The feature branch contains the new optional package, tests, docs, lockfile,
  spec, plan, review evidence, and lesson with Lore-protocol commits.
- The public API contains no unsafe deserialization, no hidden fallback, no
  global registry, and no default-install dependency expansion.
- The final PR closes #45, ends with `## DoD Status`, passes CI, and is handed
  to the user for explicit merge approval.
