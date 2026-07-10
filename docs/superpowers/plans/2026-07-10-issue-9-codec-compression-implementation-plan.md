# Issue #9 Codec and Compression Implementation Plan

> **For implementation:** follow test-driven development. Add each failing
> contract test before its smallest supporting implementation, then run its
> focused suite before proceeding.

**Goal:** Deliver focused, stdlib-only `bluetape-codec` and
`bluetape-compression` distributions without adding either package to the
default `bluetape` install.

**Architecture:** Each distribution owns one focused namespace module. Codec
uses strict ASCII validation plus stdlib decoding and a re-encode canonicality
check. Compression lazy-loads `zlib`, wraps gzip/zlib/raw-DEFLATE wire formats,
and performs bounded incremental decompression with a single output budget per
invocation. The meta distribution gates both focused distributions behind
extras only.

**Tech stack:** Python 3.13+, `base64`, `binascii`, lazy `importlib` + `zlib`,
`uv`, `uv_build`, pytest, Ruff.

## File Structure

| Path | Responsibility |
|---|---|
| `packages/bluetape-codec/pyproject.toml` | `bluetape-codec` metadata and `bluetape.codec` mapping. |
| `packages/bluetape-codec/src/bluetape/codec/__init__.py` | Strict Base64url/hex public API and `CodecError`. |
| `packages/bluetape-codec/tests/test_codec.py` | Success, type, malformed, padding, and canonicality tests. |
| `packages/bluetape-codec/README.md` | Focused codec usage and error contract. |
| `packages/bluetape-compression/pyproject.toml` | `bluetape-compression` metadata and `bluetape.compression` mapping. |
| `packages/bluetape-compression/src/bluetape/compression/__init__.py` | Lazy backend, bounded decompression, compression API, and errors. |
| `packages/bluetape-compression/tests/test_compression.py` | Wire-format, malformed, limit, member, availability, and resource tests. |
| `pyproject.toml`, `uv.lock` | Workspace registration and lock state. |
| `packages/bluetape/pyproject.toml`, `packages/bluetape/README.md` | Extras and meta-package install contract. |
| `README.md`, `README.ko.md`, `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Root/documentation lifecycle records. |
| `docs/lessons/2026-07-10-issue-9-codec-compression.md` | Durable safe-decompression lesson. |

## Task 1: Register two thin focused distributions

**Files:** create both package directories, metadata, empty modules, tests, and
READMEs; modify root `pyproject.toml`, `packages/bluetape/pyproject.toml`, and
`uv.lock`.

1. Create two `uv_build` packages with Python `>=3.13`, no runtime
   dependencies, and module names `bluetape.codec` / `bluetape.compression`.
   Start their `__init__.py` files with module docstrings and empty `__all__`.
2. Add both focused distributions to root workspace dependencies, workspace
   sources, and members. Add `codec` and `compression` extras to the meta
   package and include both in its `dev` and `all` extras. Keep
   `packages/bluetape/pyproject.toml` default `dependencies` exactly
   `bluetape-core==0.1.0`.
3. Run `uv lock && uv sync --all-packages && uv lock --check`.
4. Prove the placeholders import with:

   ```bash
   uv run python -c "import bluetape.codec, bluetape.compression"
   ```

5. Commit the boundary with a Lore commit headed `build: register codec compression packages`.

## Task 2: Specify codec behavior with failing tests

**Files:** modify `packages/bluetape-codec/tests/test_codec.py`.

1. Add an export test requiring exactly `CodecError`, `base64url_encode`,
   `base64url_decode`, `hex_encode`, and `hex_decode`; assert
   `issubclass(CodecError, ValueError)`.
2. Add Base64url tests for bytes, bytearray, and memoryview round trips;
   empty bytes; default unpadded output; explicit padded output; and every
   valid remainder shape.
3. Add parametrized invalid-input tests that reject standard Base64 alphabet,
   whitespace, non-ASCII text, misplaced/extra padding, padding in unpadded
   mode, length modulo four equal to one, and non-canonical unused pad bits.
   Assert `CodecError` and ensure public messages do not echo the value.
4. Add hex tests for lowercase output, case-insensitive valid decode, empty
   payload, and rejection of whitespace, prefixes, separators, odd length,
   invalid digits, and non-ASCII text.
5. Add tests that text API type mismatches remain native `TypeError`, and
   bytes-like encoder buffer failures remain native rather than becoming
   `CodecError`.
6. Run `uv run pytest packages/bluetape-codec/tests/test_codec.py -q`; it must
   fail until Task 3 supplies the implementation.

## Task 3: Implement the strict codec API

**Files:** modify `packages/bluetape-codec/src/bluetape/codec/__init__.py`.

1. Define `CodecError(ValueError)` and export the four public helpers plus the
   error in ordered `__all__`.
2. Encode with `base64.urlsafe_b64encode`, decode ASCII text only, and use
   `base64.b64decode(..., altchars=b"-_", validate=True)` after only the
   internally required padding is introduced. Reject malformed form before the
   stdlib call; compare the decoded payload re-encoded with the selected
   `padded` mode to the original input, which rejects non-canonical pad bits.
3. Encode hex with `bytes(data).hex()` only after the buffer protocol has been
   accepted; decode only validated ASCII hexadecimal text. Preserve native
   `TypeError` for wrong API types, but translate malformed encoded values to
   `CodecError` (chaining only a safe stdlib decode exception where applicable).
4. Run the Task 2 suite and:

   ```bash
   uv run ruff check packages/bluetape-codec
   uv run ruff format --check packages/bluetape-codec
   ```

5. Commit with a Lore commit headed `feat: add strict codec helpers`.

## Task 4: Specify bounded compression behavior with failing tests

**Files:** modify `packages/bluetape-compression/tests/test_compression.py`.

1. Require exactly `DEFAULT_MAX_OUTPUT_SIZE`, `CompressionError`,
   `DecompressionLimitError`, and the six compression/decompression helpers in
   `__all__`. Assert `issubclass(CompressionError, ValueError)` and
   `issubclass(DecompressionLimitError, CompressionError)`. Verify empty and
   representative binary round trips for gzip, zlib, and raw DEFLATE, including
   cross-format rejection.
2. Test native level validation, bytes-like input support, wrong type behavior,
   and `max_output_size` validation: reject booleans/non-integers/negative
   values, accept zero only for an empty payload, accept `sys.maxsize - 1`, and
   reject larger values before a zlib C-API overflow.
3. Add expansion fixtures whose compressed input is small but whose decoded
   result is at, below, and one byte above the logical output limit. Assert an
   over-limit call raises only `DecompressionLimitError` and yields no partial
   return value; assert its `__cause__ is None`.
4. Add malformed/truncated tests for all three formats, zlib/raw trailing-byte
   rejection, and a zlib/raw payload that ends exactly on a 64 KiB input
   boundary followed by garbage. Every locally detected and `zlib.error`
   failure must assert a fixed payload-free `CompressionError` message,
   `__cause__ is None`, and `__suppress_context__ is True`; a translated
   `zlib.error` may remain as suppressed internal context.
5. Construct concatenated gzip members: accept complete members, reject a
   partial second member, member-plus-garbage, terminal zero bytes, and many
   small members. Include a first complete member ending exactly at the 64 KiB
   source-chunk boundary with its next member starting in the next chunk. Add
   two-member limit cases proving that the single remaining budget is shared:
   a combined payload at the limit succeeds, while the second member exceeding
   it raises `DecompressionLimitError` with no partial return. Instrument the
   many-small-member fixture with a private test seam or observable counter to
   prove monotonically consumed source bytes and an O(n) upper bound on input
   bytes presented to decompressors; never accept a test that only times the
   fixture.
6. Add a truncated fixture exercising the source-exhausted empty-input probe;
   assert it raises `CompressionError` rather than looping. Add a fixture that
   forces `unconsumed_tail`/pending-output draining under a small limit.
7. Patch the module-local lazy backend resolver to emulate a missing `zlib`;
   assert `import bluetape.compression` works and every compression helper
   raises a fixed, payload-free `CompressionError` with suppressed context.
8. Run `uv run pytest packages/bluetape-compression/tests/test_compression.py -q`;
   it must fail until Task 5 supplies the behavior.

## Task 5: Implement safe lazy compression helpers

**Files:** modify `packages/bluetape-compression/src/bluetape/compression/__init__.py`.

1. Keep package import independent of `zlib`/`gzip`; use a private lazy resolver
   around `importlib.import_module("zlib")`. A missing backend raises a fixed,
   cause-suppressed `CompressionError`; do not expose original module-path or
   payload text.
2. Define the public error hierarchy and `DEFAULT_MAX_OUTPUT_SIZE = 64 * 1024 *
   1024`. Validate a non-boolean output limit in `0..sys.maxsize - 1` before
   consuming/decompressing input; keep normal compression-level exceptions
   native.
3. Implement compression through the resolved zlib backend with explicit
   `wbits`: gzip (`16 + MAX_WBITS`), zlib wrapper (`MAX_WBITS`), raw DEFLATE
   (`-MAX_WBITS`). Do not auto-detect decode formats.
4. Implement one shared private bounded decode routine. Treat source as a
   byte-view and feed source chunks of at most 64 KiB; when a gzip member leaves
   `unused_data`, first probe a minimum-size gzip member, then advance that tail
   through exponentially growing memory-view slices capped at 64 KiB. This keeps
   many small members from reprocessing a growing suffix or incurring one call
   per byte. Keep a list of emitted chunks and one operation-wide remaining-
   output counter. Each call must use
   `decompress(input, remaining + 1)`: if it returns more than remaining, raise
   `DecompressionLimitError` before appending.
5. Drive decompressor state deterministically: re-feed `unconsumed_tail` first;
   otherwise feed the next source chunk; use empty input only to drain pending
   output. If an empty probe yields no output/tail/eof, feed source when
   available, otherwise raise a fixed `CompressionError` without retrying. Do
   not call `Decompress.flush()` anywhere.
6. Require `eof` per member. Reject any `unused_data` or unread source for
   zlib/raw DEFLATE. For gzip, create a new member decompressor and process its
   unused suffix exactly once before new source bytes; track a monotonic source
   cursor and never concatenate/re-scan already supplied source. Preserve the
   one remaining counter across members. Reject partial successors and terminal
   garbage/zero padding. Translate locally discovered decode failures and
   `zlib.error` to fixed, context-suppressed `CompressionError`; never return
   accumulated chunks on failure.
7. Run the Task 4 suite and:

   ```bash
   uv run ruff check packages/bluetape-compression
   uv run ruff format --check packages/bluetape-compression
   ```

8. Commit with a Lore commit headed `feat: add bounded compression helpers`.

## Task 6: Publish the source-workspace contract

**Files:** complete both package READMEs; modify `packages/bluetape/README.md`,
`README.md`, `README.ko.md`, `docs/package-layout.md`, `WIP.md`, and
`CHANGELOG.md`.

1. Document source-workspace availability and PyPI hold, direct/future-extra
   install commands, imports, import-backed examples, strict canonical Base64
   `padded` behavior, hex casing, all public error classes, default/output
   limit, and zlib-enabled platform requirement.
2. Explain gzip multi-member acceptance, zlib/raw trailing-byte rejection, wire
   format distinction, no streaming/file APIs, no native backends, and why the
   output limit is not a process-memory guarantee.
3. Add both distributions to English/Korean root tables, install sections,
   usage examples, and package-documentation links; update the meta README
   extras and keep its default-install statement core-only.
4. Mark #9 source-workspace implementation in WIP, add both public package
   records to the layout policy, and add concise `Unreleased / Added` changelog
   entries. Write the lesson with the `flush()` non-bound insight, test evidence,
   and a directive for future streaming work.
5. Run `git diff --check` and execute each README code example with `uv run
   python` or a focused pytest smoke test. Commit with a Lore `docs:` intent.

## Task 7: Release-quality verification and evidence

1. Run, in order:

   ```bash
   uv lock --check
   uv sync --all-packages --locked
   uv run pytest packages/bluetape-codec/tests/test_codec.py packages/bluetape-compression/tests/test_compression.py
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv build --all-packages
   git diff develop...HEAD --check
   ```

2. Inspect the built `bluetape` wheel metadata: default requirements must be
   exactly `bluetape-core`; codec/compression must appear only with their own
   extras, and both must be present in `dev`/`all` extra markers.
3. In fresh virtual environments install each focused wheel and import/run a
   representative codec/compression round trip. Separately install the meta
   wheel and assert that neither focused distribution is installed by default.
4. Add a concise implementation-review artifact with the exact commands and
   P0/P1 result. If any command fails, fix only the evidenced defect and rerun
   the affected tests plus this matrix.

## Plan Self-Review

| Spec/DoD item | Plan task |
|---|---|
| Two focused optional distributions and thin default | 1, 6, 7 |
| Strict canonical Base64url and hex | 2, 3, 6 |
| Gzip/zlib/raw formats and typed errors | 4, 5, 6 |
| Bounded no-flush decompression and limit semantics | 4, 5, 7 |
| Gzip members/trailing/truncation/resource boundaries | 4, 5 |
| Optional-zlib import/call behavior | 4, 5, 6, 7 |
| README locale parity, WIP, changelog, lesson | 6 |
| Lock, lint, tests, build, metadata, isolated wheels | 1, 7 |

No CI workflow edit is planned: existing CI already runs `uv sync
--all-packages`, the full suite, Ruff, and `uv build --all-packages`; Task 7
proves both new packages participate in that generic coverage.
