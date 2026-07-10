# Issue #9 Codec and Compression Design

## Context

Issue #9 requests focused Python-native codec and compression packages without
making the default `bluetape` distribution heavier. The repository currently
has focused stdlib-first packages and no codec/compression distribution.

Python's `base64.b64decode(..., validate=True)` rejects non-alphabet input,
whereas its default decoder discards it. `gzip.decompress()` and
`zlib.decompress()` materialize their output, so public decompression helpers
must enforce an output bound while producing data incrementally.

## Decision

Create two independent stdlib-only distributions:

| Distribution | Import path | First public surface |
|---|---|---|
| `bluetape-codec` | `bluetape.codec` | strict URL-safe Base64 and hexadecimal helpers |
| `bluetape-compression` | `bluetape.compression` | bounded gzip, zlib, and raw-deflate byte helpers |

Both are optional `bluetape` extras. The default `bluetape` dependency remains
only `bluetape-core`.

## Public API

### Codec

```python
class CodecError(ValueError):
    """Raised when encoded text is malformed or non-canonical."""


def base64url_encode(data: bytes | bytearray | memoryview, *, padded: bool = False) -> str: ...
def base64url_decode(value: str, *, padded: bool = False) -> bytes: ...
def hex_encode(data: bytes | bytearray | memoryview) -> str: ...
def hex_decode(value: str) -> bytes: ...
```

- URL-safe Base64 uses `-` and `_`; unpadded form is the default.
- Unpadded decode rejects `=`, rejects a length congruent to one modulo four,
  adds only the required internal padding, and validates the alphabet.
- Padded decode requires canonical four-character grouping and validates the
  alphabet. It does not silently discard malformed characters.
- Hex encode emits lowercase ASCII. Hex decode accepts ASCII upper/lowercase
  digits only and rejects prefixes, whitespace, separators, odd length, and
  non-ASCII input with `CodecError`.
- Type mismatches keep native `TypeError`; malformed encoded input is translated
  to `CodecError` with its original stdlib exception as the cause.

### Compression

```python
DEFAULT_MAX_OUTPUT_SIZE = 64 * 1024 * 1024

class CompressionError(ValueError):
    """Raised when compressed data cannot be decoded safely."""


class DecompressionLimitError(CompressionError):
    """Raised when decompressed output would exceed the caller limit."""


def gzip_compress(data: bytes | bytearray | memoryview, *, level: int = 9) -> bytes: ...
def gzip_decompress(data: bytes | bytearray | memoryview, *, max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE) -> bytes: ...
def zlib_compress(data: bytes | bytearray | memoryview, *, level: int = -1) -> bytes: ...
def zlib_decompress(data: bytes | bytearray | memoryview, *, max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE) -> bytes: ...
def deflate_compress(data: bytes | bytearray | memoryview, *, level: int = -1) -> bytes: ...
def deflate_decompress(data: bytes | bytearray | memoryview, *, max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE) -> bytes: ...
```

- Compression delegates valid levels to the matching stdlib primitive.
- Decompression processes chunks with a `zlib.decompressobj` and limits every
  produced chunk before appending it; no public helper calls an unbounded
  one-shot decompressor.
- `max_output_size` is a non-boolean integer greater than or equal to zero.
  A zero limit permits only an empty decompressed payload.
- Invalid/truncated payloads and unexpected trailing bytes raise
  `CompressionError`; output over the limit raises `DecompressionLimitError`.
- Gzip supports concatenated valid members. Zlib and raw deflate reject trailing
  bytes so callers do not accidentally accept an ambiguous wire payload.
- `MemoryError`, `KeyboardInterrupt`, and `SystemExit` are never translated.

## Explicit Non-Goals

- No generic compressor registry, global default compressor, stream reader or
  writer API, file/path API, serialization metadata, checksums, encryption, or
  Base58/Base62 surface in this issue.
- No `zstd`, `lz4`, or `snappy` dependency or optional extra. Those native or
  third-party backends need a separate dependency/security/maintenance decision.
- No compatibility promise with Go/Rust beyond the selected URL-safe Base64,
  lowercase hex, gzip, zlib, and raw-deflate wire formats.

## Packaging and Documentation

Add both projects to the `uv` workspace, root dependency/source maps, and
`bluetape` optional extras (`codec`, `compression`, `dev`, and `all`). Keep the
root default dependency unchanged. Add English package READMEs, update English
and Korean root README tables/install/usage sections, package-layout policy,
WIP, CHANGELOG, module guidance, and a lesson.

Until PyPI ownership and trusted publishing are confirmed, docs describe
source-workspace use as available and registry commands as intended future
install shape.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Permissive Base64 accepts attacker-controlled junk. | Enforce ASCII and stdlib strict validation; test malformed alphabet, padding, and length. |
| Small compressed input expands beyond memory budget. | Chunked decompression with a caller-visible 64 MiB default output limit and bomb test. |
| Format confusion accepts trailing bytes. | Preserve gzip multi-member semantics; reject trailing zlib/raw-deflate data. |
| New packages leak into the thin default install. | Inspect built meta-wheel metadata and run isolated wheel smoke tests. |
| Sibling APIs encourage over-broad parity. | Limit v1 to stdlib formats and record the rejected registry/native-backend options. |

## Acceptance Criteria

1. All six public codec/compression functions round-trip bytes and preserve
   empty payloads.
2. Codec tests cover malformed URL-safe Base64 and strict hex inputs.
3. Compression tests cover invalid/truncated payloads, trailing bytes, valid
   gzip multi-member payloads, zero/boundary limits, and a bounded expansion
   fixture.
4. Built wheel metadata proves both packages are optional and the default meta
   distribution remains core-only.
5. README snippets import from built packages or are exercised with a smoke
   command; existing root README locales stay aligned.
6. Full verification and 7-tier reviews close with `P0 = 0` and `P1 = 0`.

## Definition of Done

- The two distributions, tests, docs, extras, lockfile, and durable records are
  committed on an isolated feature branch.
- Targeted tests, the workspace suite, Ruff, lock check, all-package build,
  built-wheel metadata checks, and isolated wheel imports pass.
- PR review and CI pass before the merge handoff.
