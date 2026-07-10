# Issue #10 Python Serialization Strategy

## Decision

`bluetape-serde` begins as a dependency-free contract package with a strict
JSON adapter built on the Python standard library. It does not ship a generic
object serializer, a registry, or an unsafe Python-object adapter in its first
implementation slice.

The package remains an explicit `bluetape[serde]` extra; the default
`bluetape` installation remains `bluetape-core` only.

## Baseline And Trust Boundary

| Use case | Initial decision | Reason |
| --- | --- | --- |
| Portable text payloads | Strict stdlib JSON | Zero third-party runtime dependency and clear text boundary. |
| Untrusted input | Explicit `UNTRUSTED` profile | Enforce finite byte and nesting-depth limits, reject non-finite constants and duplicate keys, prohibit type/class reconstruction, and return typed failures. |
| Trusted internal payloads | Explicit `TRUSTED_INTERNAL` profile | It may raise, but never disable, explicit finite byte and nesting-depth limits; it never enables a hidden fallback or implicit unsafe codec. |
| Python object graphs | Out of scope | `pickle` can execute arbitrary code during unpickling and is not a cross-language format. |

Python's `json` documentation warns that malicious input can consume substantial
CPU and memory, and notes that the module does not impose its own input-size or
nesting limits. The future adapter must therefore accept bytes only after a
caller-visible size and nesting-depth gates. Its bytes contract is UTF-8 only,
which makes the byte-size gate and a string/escape-aware structural depth
preflight deterministic before `json.loads()`. It then configures strict JSON
semantics rather than accept the standard library's permissive non-finite
constants and duplicate keys. Tests must cover invalid UTF-8, the depth
boundary, over-depth input, brackets in strings, and escaped characters.
[Python json documentation](https://docs.python.org/3/library/json.html)

`pickle` is not a fallback codec. Python documents that unpickling untrusted or
tampered data can execute arbitrary code. A future explicitly named unsafe
adapter, if ever accepted, must be a separate opt-in package, require
`TRUSTED_INTERNAL`, and be excluded from all untrusted decode paths.
[Python pickle documentation](https://docs.python.org/3/library/pickle.html)

## Proposed Contract Vocabulary

The first implementation issue should define these public concepts before any
optional backend adapters:

- `PayloadMetadata`: format identifier, schema/version identifier, and optional
  content type. Metadata describes the payload and must not expose payload bytes
  in `repr` or errors.
- `SerializedPayload`: immutable metadata plus `bytes`; empty bytes remain data,
  not an implicit null convention.
- `TrustProfile`: `UNTRUSTED` and `TRUSTED_INTERNAL`, selected by the caller for
  every decode operation.
- `SerdeError` with typed decode subtypes: format mismatch, unsupported version,
  trust-profile violation, payload-limit violation, and malformed payload.

Version or format mismatch must raise a typed error. It must not decode as
`None`, silently choose another codec, or trigger cache eviction/rebuild policy.
Those operational actions belong to callers.

## Optional Adapter Decision

| Candidate | Decision | Boundary |
| --- | --- | --- |
| `orjson` | Defer as `orjson` extra | Performance-oriented JSON backend; preserve the standard contract, including error and strictness semantics. |
| `msgpack` | Follow-up `msgpack` extra | Portable binary format. Pass explicit `max_buffer_size` and retain `strict_map_key=True` for untrusted decode. |
| `pydantic` | Follow-up `pydantic` extra | Model-to-JSON integration only; Pydantic remains the model owner and is not a replacement serde core. |
| `cbor2` | Follow-up `cbor` extra | Useful compact tagged binary format, but its project says it has not been tested against malicious input. |
| Apache Fory / `pyfory` | Committed `fory` extra | A dedicated optional adapter follows the base contract and must prove Python/Go/Rust/Kotlin schema conformance before it is released. |

`orjson` supports common Python application types and produces bytes, making it
a performance implementation candidate rather than the contract owner.
[orjson project documentation](https://github.com/ijl/orjson)

`msgpack-python` provides an efficient binary interchange format and documents
`max_buffer_size` plus `strict_map_key=True` as defenses for unreliable input.
[msgpack-python documentation](https://github.com/msgpack/msgpack-python)

Pydantic serializes its models to JSON through `model_dump_json()` and raises a
serialization error for unsupported values; its model lifecycle stays outside
`bluetape-serde`. [Pydantic serialization documentation](https://pydantic.dev/docs/validation/latest/concepts/serialization/)

`cbor2` supports CBOR tags and shared references, but explicitly says it has
not been tested against malicious input. It therefore cannot define the
untrusted baseline. [cbor2 project page](https://pypi.org/project/cbor2/)

Apache Fory documents Python support and cross-language schema registration.
It is a committed dedicated optional adapter, not a transparent fallback for
JSON or MessagePack. Its implementation must prove an explicit schema/type-id
fixture suite before release. Its first release is `TRUSTED_INTERNAL` only. An
untrusted Fory decode path needs a separate approved threat model and security
gate covering fixed allowlisted schema/type-ids, no dynamic type/class loading,
finite payload/depth/reference limits, and malformed/adversarial fixtures.
[Apache Fory overview](https://fory.apache.org/docs/introduction/overview/)

## Cross-Language Compatibility

- Interoperability is semantic, not byte-for-byte: matching format identifier,
  schema/version, field semantics, and conformance fixtures are required.
- JSON and MessagePack may carry portable payloads only when the application
  defines canonical field names, number range, datetime, bytes, map-key, and
  duplicate-key policies.
- Fory compatibility is limited to an explicit cross-language schema mode; it
  must not be inferred from a Python-native object graph.
- Python `pickle`, Pydantic-internal representation, and library-specific
  defaults are never cross-language contracts.

This preserves the sibling Go/Rust/Kotlin lesson: payload metadata and trust
profile are caller-visible, while unsafe type reconstruction and cache policy do
not leak into generic decode APIs.

## Non-Goals

- No serializer registry, auto-detection, stream/file API, encryption,
  compression composition, or schema migration engine.
- No `pickle`, `marshal`, YAML, protobuf, or Avro adapter in the first
  implementation issue. Fory remains a separate explicit extra after the base
  contract; it is not a fallback for any other format.
- No claim that JSON parsing alone provides a process-memory ceiling; callers
  own transport and input-size admission.

## Follow-Up Work

1. [#45](https://github.com/bluetape4k/bluetape-py/issues/45): add
   `bluetape-serde` payload contracts and strict stdlib JSON adapter.
2. Add optional MessagePack, CBOR, and Pydantic adapter packages only after the
   base contract is verified.
3. [#46](https://github.com/bluetape4k/bluetape-py/issues/46): add the
   committed Apache Fory adapter as a `fory` extra with Python, Go, Rust, and
   Kotlin schema/type-id conformance fixtures as a release gate. Initial decode
   support is `TRUSTED_INTERNAL` only.

## Retrieval Notes

- Retrieved on 2026-07-10 from the linked official Python/project
  documentation and local `bluetape-go`, `bluetape-rs`, and `bluetape4k`
  sources.
- No external images were required.
