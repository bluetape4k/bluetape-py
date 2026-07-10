# Issue #9 Codec and Compression Design

## Context

Issue #9 requests focused Python-native codec and compression packages without
making the default `bluetape` distribution heavier. The repository currently
has focused stdlib-first packages and no codec/compression distribution.

Python's `base64.b64decode(..., validate=True)` rejects non-alphabet input,
whereas its default decoder discards it. `gzip.decompress()` and
`zlib.decompress()` materialize their output, so public decompression helpers
must enforce a logical returned-payload bound while producing data
incrementally. This bound is not a process-memory ceiling: callers already own
the compressed input and a bytes-returning API necessarily retains its result.

## Decision

Create two independent stdlib-only distributions:

| Distribution | Import path | First public surface |
|---|---|---|
| `bluetape-codec` | `bluetape.codec` | strict URL-safe Base64 and hexadecimal helpers |
| `bluetape-compression` | `bluetape.compression` | bounded gzip, zlib, and raw-deflate byte helpers |

Both are optional `bluetape` extras. The default `bluetape` dependency remains
only `bluetape-core`.

`bluetape-compression` supports Python implementations with the optional
stdlib `zlib` module enabled. It imports neither `zlib` nor `gzip` at package
import time: each public compression helper resolves its backend lazily, so
`import bluetape.compression` remains available on a zlib-free build. A missing
backend raises a fixed, payload-free `CompressionError` with suppressed context;
the package README documents this platform requirement.

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

- URL-safe Base64 uses exactly `[A-Za-z0-9_-]`; unpadded form is the default.
- Unpadded decode rejects `=`, rejects a length congruent to one modulo four,
  adds only the required internal padding, validates the alphabet, and accepts
  only a value equal to the unpadded encoder's canonical result.
- Padded decode requires canonical four-character grouping with `=` only at the
  end, validates the alphabet, and accepts only a value equal to the padded
  encoder's canonical result. It does not silently discard malformed characters
  or accept non-zero unused pad bits.
- Hex encode emits lowercase ASCII. Hex decode accepts ASCII upper/lowercase
  digits only and rejects prefixes, whitespace, separators, odd length, and
  non-ASCII input with `CodecError`.
- Type mismatches keep native `TypeError`. A malformed value discovered by a
  stdlib decoder becomes `CodecError` chained from that decoder exception;
  locally detected ASCII, padding, length, or canonical-form violations raise
  `CodecError` without a cause.

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
- Invalid `level` types or values retain the matching native stdlib `TypeError`
  or `ValueError`; this package does not translate them.
- Decompression uses source chunks of at most 64 KiB and one operation-wide
  remaining-output counter. Every `decompress()` call receives
  `max_length=remaining + 1`; the implementation drains `unconsumed_tail` and
  empty-input pending output only through further bounded `decompress()` calls.
  The state machine first re-feeds `unconsumed_tail`; when a gzip member leaves
  `unused_data`, it first probes a minimum-size gzip member and then advances
  the tail through exponentially growing memory-view slices capped at 64 KiB
  for the next member. This prevents repeated large-tail reprocessing without
  one-call-per-byte amplification. When an empty-input probe yields no output,
  no tail, and no
  `eof`, it feeds the next source chunk when one remains, otherwise raises
  `CompressionError` for truncation and never retries that no-progress state.
  It never calls `Decompress.flush()`, because its length argument is not a hard
  output cap. The implementation raises `DecompressionLimitError` before
  appending an over-limit result and avoids proportional preallocation. No
  public helper calls an unbounded one-shot decompressor.
- `max_output_size` is a non-boolean integer from zero through
  `sys.maxsize - 1`; a zero limit permits only an empty decompressed payload.
  Larger values raise `ValueError` before they can overflow the `remaining + 1`
  C API argument.
- Invalid `max_output_size` type or negative value keeps native `TypeError` or
  `ValueError`. Invalid, truncated, and trailing payloads raise a fixed,
  payload-free `CompressionError` with exception context suppressed, whether
  found locally or through `zlib.error`. Output over the limit raises a fixed,
  cause-free `DecompressionLimitError` immediately, before later terminal
  validation; no terminal decode failure returns a partial result.
- Every decompressor member must reach `eof`. Gzip accepts concatenated valid
  members only when all `unused_data` advances to another complete gzip member.
  It uses `wbits=16 + zlib.MAX_WBITS`, creates a fresh decompressor for each
  member, advances one monotonic input cursor while handing the unread suffix to
  the next member exactly once, and shares the same remaining-output counter
  across every member. A member ending at a chunk boundary does not imply end of
  source: gzip starts another member whenever unread source bytes remain, while
  zlib and raw deflate reject both `unused_data` and all unread source bytes.
  A partial subsequent member, arbitrary garbage, or terminal zero padding is
  rejected as `CompressionError`.
- `zlib_*` emits and consumes zlib-wrapped streams; `deflate_*` emits and
  consumes raw RFC 1951 DEFLATE streams. No helper auto-detects formats.
- The input is already a caller-owned in-memory buffer, so v1 deliberately does
  not add a `max_input_size` parameter or claim a process-memory ceiling. The
  implementation processes a byte view in fixed chunks without an additional
  full input copy; streaming/file APIs remain a separate future scope.
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

Each package README must document its import path, strict canonical decode and
`padded` behavior, all exception classes, output-limit semantics/default,
trailing-data rules, wire-format distinction, unsupported streaming/native
backends, the compression package's zlib-enabled-platform requirement, and
source-workspace versus future registry installation. The release guide remains
unchanged: no tag or PyPI publication is part of this issue; rollback is a
`develop` revert followed by metadata and thin-default wheel verification.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Permissive Base64 accepts attacker-controlled junk. | Enforce ASCII and stdlib strict validation; test malformed alphabet, padding, and length. |
| Small compressed input expands beyond the returned-payload limit. | Use source chunks of at most 64 KiB, linear gzip-tail handling, `remaining + 1` output caps, bounded `decompress()` draining without `flush()`, and a bomb test. |
| Format confusion accepts trailing bytes. | Require `eof` per member; accept only complete concatenated gzip members and reject trailing zlib/raw-deflate data. |
| New packages leak into the thin default install. | Inspect built meta-wheel metadata and run isolated wheel smoke tests. |
| A Python build omits optional `zlib`. | Lazy-load compression backends; keep package importable and raise a fixed `CompressionError` only when a helper is called. |
| Sibling APIs encourage over-broad parity. | Limit v1 to stdlib formats and record the rejected registry/native-backend options. |

## Acceptance Criteria

1. All ten public codec/compression functions preserve empty payloads; four
   codec functions and each matching compression/decompression pair round-trip
   representative bytes.
2. Codec tests cover malformed URL-safe Base64 and strict hex inputs.
3. Compression tests cover invalid/truncated payloads, trailing bytes, valid
   gzip multi-member payloads in one input chunk and across a 64 KiB boundary,
   partial-second-member and member-plus-garbage rejection, many-small-member
   linear cursor handling, zlib/raw stream-plus-garbage at the 64 KiB boundary,
   zero/boundary/`sys.maxsize - 1` limits, bounded `unconsumed_tail` and
   pending-output draining, no-progress truncated-input termination, invalid
   compression levels, sanitized payload-free public errors, lazy backend
   absence with an import-and-call smoke test, and a bounded expansion fixture
   with no partial result.
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
