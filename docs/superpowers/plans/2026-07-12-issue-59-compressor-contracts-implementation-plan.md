# Issue #59 Composable Compressor Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one Python-native structural compressor contract, immutable stdlib and native
implementations, bounded decompression, and opt-in LZ4/Snappy/Zstd installation paths without
changing the thin default install.

**Architecture:** `bluetape.compression` keeps the existing function API and adds a stdlib-only
`Compressor` protocol plus three frozen object adapters. `bluetape.compression.native` exposes
three provider-backed classes whose modules are importable without providers, while construction
loads exactly one focused provider. All implementations share stable errors and logical output
bounds; no registry, auto-detection, serializer decorator, or Redis envelope is introduced.

**Tech Stack:** CPython 3.13.14; Python 3.13 `Protocol`, frozen/slotted dataclasses, `zlib`, and
`importlib`; `lz4==4.4.5`, `cramjam==2.11.0`, `zstandard==0.25.0`; pytest, Ruff, uv, and actionlint.

---

Date: 2026-07-12
Issue: [#59](https://github.com/bluetape4k/bluetape-py/issues/59)
Blocks: [#54](https://github.com/bluetape4k/bluetape-py/issues/54)
Work type: Type A - Full Feature

## Execution constraints

- Apply `bluetape-py-patterns` and strict RED/GREEN TDD to every public behavior.
- Preserve every existing function signature, export, gzip concatenation rule, and wire format.
- Keep `bluetape-compression` base metadata stdlib-only. Native dependencies appear only in
  `lz4`, `snappy`, `zstd`, and `native` extras and the four forwarding meta extras.
- Keep native class-name imports provider-free. Validate configuration first, then require the
  focused provider when constructing a native instance.
- Never translate `MemoryError`, `KeyboardInterrupt`, `SystemExit`, or `GeneratorExit`. Translate
  ordinary provider failures outside the active handler so public errors have no provider cause or
  context, and never log library failures.
- Do not introduce a compressor registry, mutable singleton, payload auto-detection, streaming
  public API, file/path API, serializer decorator, Redis envelope, or wire compatibility claim.
- Run native-provider commands sequentially. The implementations are synchronous and own no
  thread, task, file, socket, or external service lifecycle.
- No diagram is required; the approved spec assigns the public shape to API tables and a linear
  composition example.

## Step 3-P risk prediction

| Risk | Early signal | Mitigation and proof | Rollback or rerun point |
|---|---|---|---|
| Optional providers leak into base/default/dev/all installs | base metadata or `find_spec()` exposes lz4/cramjam/zstandard | focused extras, provider-free import tests, wheel metadata inspection, isolated base/meta installs | revert Task 2/7 metadata and lock changes; rerun base isolation before provider work |
| Decompression allocates beyond the caller bound | provider decode runs after an oversized declaration or returns `limit + 1` bytes | LZ4 incremental budget, Snappy/Zstd declared-size preflight, exact/+1 tests, provider spies | revert the affected Task 3/4/5 decoder and rerun its full failure/boundary subset |
| Provider diagnostics or payload references escape | marker appears in error text/cause/context/logs or survives after traceback cleanup | fresh stable errors outside handlers, no logging, hostile provider tests, reference-release checks | revert Task 6 error path and rerun all failure-isolation tests |
| Provider upgrade silently changes strictness | Snappy accepts trailing bytes, Zstd accepts unknown size/trailing frames, or API signature changes | exact pins, source/signature anchors, strict trailing fixtures, lock check | reject the lock update; keep pinned versions until a parser or reviewed migration exists |
| Native CI proves aggregate success but not focused extras | one selected extra imports every provider or unselected construction succeeds | isolated `lz4`, `snappy`, `zstd`, `native`, base, and forwarding-meta smoke environments | revert Task 7 CI/metadata, retain unit behavior, repair focused isolation before PR |
| Hot-path copies or loops regress | repeated input refeeding, output grows beyond one bounded assembly, or large fixture hangs | call-count/input-budget tests and non-flaky 8 MiB stress round-trips without absolute timing claims | return to provider task, inspect allocation/call evidence, rerun Step 4-P |

Risk gate is required because this change adds three native dependencies and processes potentially
hostile compressed bytes on a serialization/cache hot path.

## File structure

| Path | Responsibility |
|---|---|
| `packages/bluetape-compression/src/bluetape/compression/__init__.py` | Existing functions, shared validation, `Compressor`, and stdlib object implementations. |
| `packages/bluetape-compression/src/bluetape/compression/native/__init__.py` | Provider-free exports for the three native classes. |
| `packages/bluetape-compression/src/bluetape/compression/native/_support.py` | Focused provider loading and fresh public-error translation. |
| `packages/bluetape-compression/src/bluetape/compression/native/_lz4.py` | Complete LZ4 frame compression and bounded incremental decode. |
| `packages/bluetape-compression/src/bluetape/compression/native/_snappy.py` | Raw Snappy block compression and declared-size preflight decode. |
| `packages/bluetape-compression/src/bluetape/compression/native/_zstd.py` | Checksummed Zstd frame compression and declared-size/strict-extra decode. |
| `packages/bluetape-compression/tests/test_compression.py` | Existing function compatibility plus stdlib object/protocol tests. |
| `packages/bluetape-compression/tests/test_native_imports.py` | Provider-free imports, missing-extra classification, and metadata isolation. |
| `packages/bluetape-compression/tests/test_native_compressors.py` | Native conformance, malformed/boundary/security/stress tests under explicit extras. |
| `packages/bluetape-compression/pyproject.toml`, `uv.lock` | Exact focused and aggregate native dependency resolution. |
| `packages/bluetape/pyproject.toml` | Exact forwarding extras without changing default/dev/all dependencies. |
| `.github/workflows/ci.yml`, `pyproject.toml` | Provider-free base proof and dedicated `native_compression` CI marker/job. |
| `packages/bluetape-compression/README.md`, `README.ko.md` | Focused package API, extras, errors, limits, and Kotlin/Python semantic notes. |
| `packages/bluetape/README.md`, `README.md`, `README.ko.md` | Meta extras, install examples, package status, and caller examples. |
| `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Durable dependency policy, issue state, and completed user-facing change. |
| `docs/review/2026-07-12-issue-59-compressor-contracts-*.md` | TDD, verifier, performance/stability, and code-review evidence. |
| `docs/lessons/2026-07-12-issue-59-compressor-contracts.md` | Durable lesson committed before PR creation. |

## Acceptance traceability

| Approved requirement | Plan tasks |
|---|---|
| Structural `Compressor` and six immutable implementations | 1, 3, 4, 5, 6 |
| Existing function and wire compatibility | 1, 6, 9 |
| Empty, malformed, trailing, exact-bound, and one-over behavior | 1, 3, 4, 5, 6 |
| Bounded LZ4/Snappy/Zstd materialization | 3, 4, 5, 6 |
| Stable provider-free imports and focused missing-extra errors | 2, 3, 4, 5, 7 |
| Base/default/dev/all dependency isolation and focused/aggregate extras | 2, 7, 9 |
| Redacted, non-logging, non-retaining public failures | 2, 6 |
| English/Korean docs, semantic parity, Redis/serde composition boundary | 8 |
| Full validation, packaging, CI, 7-Tier review, lessons, PR DoD | 7, 9, 10 |

## Task 1: Add the structural contract and stdlib object adapters

**Complexity:** Medium
**Depends on:** Approved spec
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-compression/tests/test_compression.py`
- Modify: `packages/bluetape-compression/src/bluetape/compression/__init__.py`

- [ ] **Step 1: Write failing protocol, configuration, and object-conformance tests**

Add imports for `FrozenInstanceError`, `Compressor`, `GzipCompressor`, `ZlibCompressor`, and
`DeflateCompressor`. Add parametrized tests equivalent to:

```python
@pytest.mark.parametrize(
    ("factory", "algorithm", "default_level"),
    [
        (GzipCompressor, "gzip", 9),
        (ZlibCompressor, "zlib", -1),
        (DeflateCompressor, "deflate", -1),
    ],
)
def test_stdlib_compressors_are_frozen_structural_implementations(
    factory, algorithm: str, default_level: int
) -> None:
    compressor: Compressor = factory(max_output_size=8)
    assert compressor.algorithm == algorithm
    assert compressor.level == default_level
    assert compressor.max_output_size == 8
    assert compressor.decompress(compressor.compress(memoryview(b"bluetape"))) == b"bluetape"
    assert not hasattr(compressor, "__dict__")
    with pytest.raises(FrozenInstanceError):
        compressor.max_output_size = 9  # type: ignore[misc]
```

Parametrize `bytes`, `bytearray`, `memoryview`, empty data, unsupported input, `bool`, level
`-2/10`, output limit `-1/sys.maxsize`, exact bound, and one-byte-over behavior. Assert the ordered
`__all__` adds the four new public names while preserving all existing names.

- [ ] **Step 2: Run the focused tests and record RED**

Run:

```bash
uv run pytest packages/bluetape-compression/tests/test_compression.py -q
```

Expected: collection fails because `Compressor` and the object implementations do not exist.

- [ ] **Step 3: Implement common validation, protocol, and frozen adapters**

Add exact-type validators and the structural contract:

```python
class Compressor(Protocol):
    @property
    def algorithm(self) -> str: ...

    @property
    def max_output_size(self) -> int: ...

    def compress(self, data: bytes | bytearray | memoryview) -> bytes: ...
    def decompress(self, data: bytes | bytearray | memoryview) -> bytes: ...


def _validate_level(level: int, *, minimum: int, maximum: int) -> None:
    if isinstance(level, bool) or not isinstance(level, int):
        raise TypeError("level must be an integer")
    if not minimum <= level <= maximum:
        raise ValueError("level is outside the supported range")
```

Implement each adapter as `@dataclass(frozen=True, slots=True)`, validate `level` and
`max_output_size` in `__post_init__`, expose `algorithm` with a property, delegate `compress()` to
the matching existing function, and delegate `decompress()` with the stored output bound. Do not
mark the protocol runtime-checkable or change existing function validation/wire behavior.
Extract the current `_decompress()` output-limit checks into `_validate_max_output_size()` so
constructors and functions share one rule. Add a private bytes-like validator used by object/native
methods before provider resolution:

```python
def _as_bytes(data: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    return bytes(data)
```

The existing public functions may keep passing caller buffers directly to zlib; only the new object
methods require this stable pre-provider validation boundary.

- [ ] **Step 4: Run GREEN and commit the stdlib slice**

Run the focused test and expect all cases to pass. Commit:

```bash
git add packages/bluetape-compression/src/bluetape/compression/__init__.py \
  packages/bluetape-compression/tests/test_compression.py
git commit -m "feat: add structural compressor contracts"
```

Rollback point: revert this commit; the original function-only API remains intact.

## Task 2: Establish focused provider loading and dependency metadata

**Complexity:** Medium
**Depends on:** Task 1
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-compression/src/bluetape/compression/native/__init__.py`
- Create: `packages/bluetape-compression/src/bluetape/compression/native/_support.py`
- Create: `packages/bluetape-compression/tests/test_native_imports.py`
- Modify: `packages/bluetape-compression/pyproject.toml`
- Modify: `packages/bluetape/pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Write failing base-import and provider-loader tests**

Test that `import bluetape.compression` never imports `bluetape.compression.native`; importing the
native namespace does not resolve `lz4`, `cramjam`, or `zstandard`; a direct missing provider gains
only focused installation guidance; transitive `ModuleNotFoundError`, `ImportError`, `OSError`, and
`MemoryError` preserve their original type and message.

```python
def test_native_namespace_does_not_eagerly_load_providers() -> None:
    module = importlib.import_module("bluetape.compression.native")
    assert module is not None
    assert not {"lz4", "cramjam", "zstandard"} & sys.modules.keys()
```

- [ ] **Step 2: Run loader tests and record RED**

```bash
uv run pytest packages/bluetape-compression/tests/test_native_imports.py -q
```

Expected: import failure because the native namespace/support module does not exist.

- [ ] **Step 3: Add exact extras and resolve the lock**

Add focused and aggregate extras to `bluetape-compression`:

```toml
[project.optional-dependencies]
lz4 = ["lz4==4.4.5"]
snappy = ["cramjam==2.11.0"]
zstd = ["zstandard==0.25.0"]
native = ["lz4==4.4.5", "cramjam==2.11.0", "zstandard==0.25.0"]
```

Add forwarding meta extras `compression-lz4`, `compression-snappy`, `compression-zstd`, and
`compression-native`; leave base dependencies and the existing `dev`/`all` arrays byte-for-byte
free of native providers. Run:

```toml
compression-lz4 = ["bluetape-compression[lz4]==0.1.0"]
compression-snappy = ["bluetape-compression[snappy]==0.1.0"]
compression-zstd = ["bluetape-compression[zstd]==0.1.0"]
compression-native = ["bluetape-compression[native]==0.1.0"]
```

```bash
uv lock
uv lock --check
```

- [ ] **Step 4: Implement provider loading and fresh error translation**

Implement `_support.py` around `importlib.import_module()` so only a direct missing top-level
provider is translated. Raise focused guidance after leaving the `except` block. Add a generic
provider-call helper that rethrows `MemoryError` and translates ordinary `Exception` after leaving
its handler; never catch `BaseException` and never log.

```python
def load_provider(module_name: str, *, install: str):
    missing = False
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name.split(".", 1)[0]:
            raise
        missing = True
    if missing:
        raise ModuleNotFoundError(install, name=module_name.split(".", 1)[0]) from None
    raise AssertionError("unreachable")
```

Keep `native.__all__` empty until provider classes are added in Tasks 3-5.

- [ ] **Step 5: Run GREEN and commit metadata/support**

```bash
uv run pytest packages/bluetape-compression/tests/test_native_imports.py -q
uv lock --check
git add packages/bluetape-compression packages/bluetape/pyproject.toml uv.lock
git commit -m "build: isolate native compression providers"
```

Rollback point: revert metadata/support and regenerate `uv.lock`; Task 1 remains stdlib-only.

## Task 3: Implement complete LZ4 frames with bounded incremental decode

**Complexity:** High
**Depends on:** Task 2
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-compression/src/bluetape/compression/native/_lz4.py`
- Modify: `packages/bluetape-compression/src/bluetape/compression/native/__init__.py`
- Create: `packages/bluetape-compression/tests/test_native_compressors.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing LZ4 contract tests**

Register the `native_compression` pytest marker, then mark provider tests with it. Cover
frozen/slotted configuration,
`algorithm == "lz4-frame"`, levels `0..16`, bytes-like and empty round-trips, stored content size,
content checksum, malformed/truncated/trailing data, exact/+1 output limits, and an injected decoder
that records every `max_length` and input window.

- [ ] **Step 2: Run the LZ4 subset and record RED**

```bash
uv run --package bluetape-compression --extra lz4 pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q -k lz4
```

Expected: import failure for `Lz4Compressor`.

- [ ] **Step 3: Implement LZ4 compression and bounded terminal validation**

Create a frozen/slotted class with default `compression_level=0`. Compression calls
`lz4.frame.compress(..., store_size=True, content_checksum=True, return_bytearray=False)`.
Decompression uses `LZ4FrameDecompressor`, feeds at most 64 KiB input windows, passes
`remaining + 1` as `max_length`, feeds `b""` while `needs_input` is false, and returns only when
`eof` is true and both `unused_data` and unread source are empty. Map over-limit output separately
from malformed/provider failure.

- [ ] **Step 4: Run GREEN and commit LZ4**

```bash
uv run --package bluetape-compression --extra lz4 pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q -k lz4
git add packages/bluetape-compression
git commit -m "feat: add bounded LZ4 frame compressor"
```

## Task 4: Implement raw Snappy with declared-size preflight

**Complexity:** High
**Depends on:** Task 2 and the shared native test file from Task 3
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-compression/src/bluetape/compression/native/_snappy.py`
- Modify: `packages/bluetape-compression/src/bluetape/compression/native/__init__.py`
- Modify: `packages/bluetape-compression/tests/test_native_compressors.py`

- [ ] **Step 1: Write failing Snappy contract tests**

Cover `algorithm == "snappy-raw"`, immutable output bound, bytes-like/empty round-trips, invalid
length prefix, truncation, tested trailing bytes, exact/+1 bounds, declaration/actual mismatch, and
a spy proving `decompress_raw()` is never called when `decompress_raw_len()` exceeds the limit.

- [ ] **Step 2: Run the Snappy subset and record RED**

```bash
uv run --package bluetape-compression --extra snappy pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q -k snappy
```

Expected: import failure for `SnappyCompressor`.

- [ ] **Step 3: Implement raw Snappy preflight and strict decode**

Use `cramjam.snappy.compress_raw()` and return exact `bytes`. On decode, read the declared size
first, reject it before provider decode when it exceeds the bound, call `decompress_raw()` only for
an allowed declaration, convert its buffer to bytes, and require exact declared/actual equality.
Use the shared provider-error boundary for malformed, truncated, and trailing input.

- [ ] **Step 4: Run GREEN and commit Snappy**

```bash
uv run --package bluetape-compression --extra snappy pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q -k snappy
git add packages/bluetape-compression
git commit -m "feat: add bounded raw Snappy compressor"
```

Provider-upgrade hold: if the pinned decoder accepts any committed trailing fixture, do not weaken
the contract or approve the upgrade without a separately reviewed parser.

## Task 5: Implement checksummed Zstd frames with strict size preflight

**Complexity:** High
**Depends on:** Task 2 and the shared native test file
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-compression/src/bluetape/compression/native/_zstd.py`
- Modify: `packages/bluetape-compression/src/bluetape/compression/native/__init__.py`
- Modify: `packages/bluetape-compression/tests/test_native_compressors.py`

- [ ] **Step 1: Write failing Zstd contract tests**

Cover `algorithm == "zstd-frame"`, levels `1..22`, bytes-like/empty round-trips, content-size and
checksum frame parameters, unknown/error content size, truncation, trailing bytes, concatenated
frames, exact/+1 limits, declaration/actual mismatch, and a spy proving no decompressor is created
for an oversized declared size.

- [ ] **Step 2: Run the Zstd subset and record RED**

```bash
uv run --package bluetape-compression --extra zstd pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q -k zstd
```

Expected: import failure for `ZstdCompressor`.

- [ ] **Step 3: Implement content-size/checksum frames and strict extra rejection**

Compression uses:

```python
provider.ZstdCompressor(
    level=self.level,
    write_content_size=True,
    write_checksum=True,
).compress(source)
```

Decode calls `frame_content_size()` first. Reject `CONTENTSIZE_UNKNOWN`/`CONTENTSIZE_ERROR` as
`CompressionError`, reject a declaration above the bound as `DecompressionLimitError`, then call
`ZstdDecompressor().decompress(source, max_output_size=declared,
allow_extra_data=False)` and require `len(decoded) == declared`. Do not claim that provider
`max_output_size` is a hard cap for frames with content size; the validated declaration is the
pre-decode allocation boundary.

- [ ] **Step 4: Run GREEN and commit Zstd**

```bash
uv run --package bluetape-compression --extra zstd pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q -k zstd
git add packages/bluetape-compression
git commit -m "feat: add bounded Zstd frame compressor"
```

## Task 6: Converge common conformance and failure isolation

**Complexity:** High
**Depends on:** Tasks 1, 3, 4, and 5
**Pattern skill:** `bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-compression/tests/test_compression.py`
- Modify: `packages/bluetape-compression/tests/test_native_imports.py`
- Modify: `packages/bluetape-compression/tests/test_native_compressors.py`
- Modify: affected implementation files only when a failing contract requires it
- Create: `docs/review/2026-07-12-issue-59-compressor-contracts-tdd-evidence.md`

- [ ] **Step 1: Add one six-implementation conformance matrix**

For all six compressors, verify exact `bytes` output, bytes-like input, empty framed round-trip,
bare-empty decode rejection, deterministic repeated calls, exact/+1 limit behavior, malformed and
truncated input, no mutable `__dict__`, and stable algorithm identifiers. Add a structural custom
compressor that satisfies `Compressor` without inheritance. Assert the native namespace has exactly
the ordered exports `Lz4Compressor`, `SnappyCompressor`, and `ZstdCompressor`, while the root
compression namespace exports only the protocol and stdlib implementations in addition to its
pre-existing function/error surface.

- [ ] **Step 2: Add hostile failure and stability tests**

Monkeypatch provider operations to raise marker-bearing ordinary exceptions and each fatal class.
Assert ordinary failures expose no marker in message/attributes/`__cause__`/`__context__`, emit no
log records, and retain no extra caller wrapper after `traceback.clear_frames()` and traceback
release. Assert fatal failures propagate unchanged. Run an 8 MiB highly compressible round-trip per
native provider plus repeated empty/small calls; use call/allocation evidence, not an absolute time
threshold.

- [ ] **Step 3: Run aggregate native and stdlib suites**

```bash
uv run pytest packages/bluetape-compression/tests/test_compression.py \
  packages/bluetape-compression/tests/test_native_imports.py -q
uv run --package bluetape-compression --extra native pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q
```

Expected: all tests pass; no provider test is silently skipped in the aggregate-extra run.

- [ ] **Step 4: Record RED/GREEN evidence and commit**

Record each task's failing symbol/behavior, exact RED command, GREEN command, result counts, and
the provider versions. Commit tests, any minimal fixes, and the evidence:

```bash
git add packages/bluetape-compression docs/review/2026-07-12-issue-59-compressor-contracts-tdd-evidence.md
git commit -m "test: prove compressor conformance and failure isolation"
```

## Task 7: Prove packaging isolation and add dedicated native CI

**Complexity:** High
**Depends on:** Task 6
**Pattern skill:** `bluetape-py-patterns`
**Triggered hazard:** workflow YAML and optional dependency metadata

**Files:**

- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `packages/bluetape-compression/tests/test_native_imports.py`
- Modify: packaging metadata only if isolation tests expose a defect

- [ ] **Step 1: Verify the marker and add metadata assertions**

Verify `native_compression` is registered in the root pytest marker list. Assert base wheel
requirements omit all providers; focused extras each contain one exact pin; aggregate contains all
three; forwarding meta extras target the exact focused extra; and meta `dev`/`all` remain
provider-free.

- [ ] **Step 2: Extend base CI and add a native job**

In the existing base job, after provider-free sync assert `find_spec()` is `None` for `lz4`,
`cramjam`, and `zstandard`, and exclude the explicit native marker from its full pytest command.
Add one `compression-native` job that pins Python 3.13.14, runs
`uv sync --package bluetape-compression --extra native --locked`, executes only the marked package
tests, and builds all packages. Do not combine it with Docker/Testcontainers work.

- [ ] **Step 3: Run focused isolated wheel/install smoke checks**

Build `bluetape-core`, `bluetape-compression`, and `bluetape` wheels into a temporary directory.
Create separate venvs for base, `lz4`, `snappy`, `zstd`, `native`, and
`bluetape[compression-native]`. In each focused environment, import all native class names,
construct the selected class(es), and assert constructing every uninstalled class raises only its
focused `ModuleNotFoundError`. In the base meta environment, assert no provider spec exists and no
root `bluetape/__init__.py` appears.

Run one checked script equivalent to:

```bash
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
uv build --package bluetape-core --out-dir "$tmp_dir/dist"
uv build --package bluetape-compression --out-dir "$tmp_dir/dist"
uv build --package bluetape --out-dir "$tmp_dir/dist"
uv venv "$tmp_dir/base" --python 3.13.14
uv pip install --python "$tmp_dir/base/bin/python" --no-index \
  --find-links "$tmp_dir/dist" "bluetape==0.1.0"
"$tmp_dir/base/bin/python" - <<'PY'
import importlib.util

assert importlib.util.find_spec("lz4") is None
assert importlib.util.find_spec("cramjam") is None
assert importlib.util.find_spec("zstandard") is None
assert importlib.util.find_spec("bluetape").origin is None
PY
for extra in lz4 snappy zstd native; do
  uv venv "$tmp_dir/$extra" --python 3.13.14
  uv pip install --python "$tmp_dir/$extra/bin/python" \
    --find-links "$tmp_dir/dist" "bluetape-compression[$extra]==0.1.0"
  "$tmp_dir/$extra/bin/python" - "$extra" <<'PY'
import importlib.util
import sys

from bluetape.compression.native import Lz4Compressor, SnappyCompressor, ZstdCompressor

selected = sys.argv[1]
cases = {
    "lz4": ("lz4", Lz4Compressor),
    "snappy": ("cramjam", SnappyCompressor),
    "zstd": ("zstandard", ZstdCompressor),
}
for name, (module_name, compressor_type) in cases.items():
    installed = selected == "native" or selected == name
    assert (importlib.util.find_spec(module_name) is not None) is installed
    if installed:
        compressor_type()
    else:
        try:
            compressor_type()
        except ModuleNotFoundError as error:
            assert name in str(error).lower()
        else:
            raise AssertionError(f"{name} provider unexpectedly available")
PY
done
uv venv "$tmp_dir/meta" --python 3.13.14
uv pip install --python "$tmp_dir/meta/bin/python" --find-links "$tmp_dir/dist" \
  "bluetape[compression-native]==0.1.0"
"$tmp_dir/meta/bin/python" - <<'PY'
from bluetape.compression.native import Lz4Compressor, SnappyCompressor, ZstdCompressor

assert Lz4Compressor() and SnappyCompressor() and ZstdCompressor()
PY
```

- [ ] **Step 4: Validate workflow and packaging, then commit**

```bash
uv lock --check
uv build --all-packages
actionlint
git diff --check
git add pyproject.toml .github/workflows/ci.yml packages/bluetape-compression/tests \
  packages/bluetape-compression/pyproject.toml packages/bluetape/pyproject.toml uv.lock
git commit -m "ci: verify native compression extras in isolation"
```

Rollback point: remove the native CI job and forwarding extras together, regenerate the lock, and
retain the stdlib contract while provider delivery is repaired.

## Task 8: Publish bilingual API and dependency guidance

**Complexity:** Medium
**Depends on:** Tasks 6 and 7
**Pattern skill:** `bluetape-py-patterns`; use `bluetape-writer` for Korean prose

**Files:**

- Modify: `packages/bluetape-compression/README.md`
- Create: `packages/bluetape-compression/README.ko.md`
- Modify: `packages/bluetape/README.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update the focused package documentation in English and Korean**

Add reciprocal language links, the `Compressor` protocol and six implementations, exact algorithm
IDs, constructor ranges/defaults, focused/aggregate install commands, empty-input semantics,
bounded decode and error tables, missing-extra timing, and a custom structural implementation
example. Explain that Python `Protocol` provides Kotlin-interface-like composition semantics but
does not promise shared wire bytes.

- [ ] **Step 2: Update root/meta documentation and durable policy**

Keep `README.md` and `README.ko.md` source-equivalent. Add all forwarding extras, an immutable
compressor example, and the serde/compress/Redis order while keeping #54 explicitly pending. Update
the meta README extra table, package-layout optional-provider policy, WIP issue #59/#54 dependency
state, and the Unreleased changelog entry. Remove the old package README statement that LZ4,
Snappy, Zstd, and checksums are unsupported.

- [ ] **Step 3: Validate documentation claims and commit**

```bash
rg -n "Compressor|Lz4Compressor|SnappyCompressor|ZstdCompressor|compression-native" \
  README.md README.ko.md packages/bluetape/README.md packages/bluetape-compression/README*.md \
  docs/package-layout.md WIP.md CHANGELOG.md
git diff --check
git add README.md README.ko.md packages/bluetape/README.md packages/bluetape-compression/README*.md \
  docs/package-layout.md WIP.md CHANGELOG.md
git commit -m "docs: document composable compression providers"
```

Expected: every public source name and extra appears in both root locales and the package docs;
no Redis provider is claimed as implemented.

## Task 9: Run full verification and 7-Tier pre-PR convergence

**Complexity:** High
**Depends on:** Tasks 1-8
**Required skills/references:** `verification-before-completion`, Step 5 verifier checklist,
performance/stability scan, and Step 6-R code review

**Files:**

- Create: `docs/review/2026-07-12-issue-59-compressor-contracts-verifier.md`
- Create: `docs/review/2026-07-12-issue-59-compressor-contracts-performance-stability.md`
- Create: `docs/review/2026-07-12-issue-59-compressor-contracts-code-review.md`
- Modify: implementation/tests/docs only to repair verified findings

- [ ] **Step 1: Run targeted and full validation from a clean dependency state**

```bash
uv sync --all-packages --extra fory --extra compression-native --python 3.13.14 --locked
uv run ruff format --check .
uv run ruff check .
uv run --package bluetape-compression --extra native pytest packages/bluetape-compression -q
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest -m "not testcontainers"
uv build --all-packages
actionlint
git diff --check
```

Expected: every command succeeds with provider extras preserved; record exact test counts and build
artifacts rather than relying on prior output.

- [ ] **Step 2: Verify exact spec/plan acceptance and repository hazards**

Map every acceptance row to source, tests, docs, and command evidence. Recheck namespace-package
layout, base/default/dev/all metadata, focused extras, lock pins, CI marker/job selection, README
locale parity, changelog/WIP state, and unchanged existing function fixtures. Outcome must be PASS;
`NEEDS FIX` returns to the owning task, and `NEEDS REVIEW SCOPE` reopens spec/plan approval.

- [ ] **Step 3: Run Step 4-P performance/stability review**

Review all compressor and CI changes for repeated copies, unbounded buffering, input refeeding,
provider state retention, mutable shared state, and flaky stress evidence. Record exact files and
commands. Fix P0/P1 and rerun the affected provider tests before continuing.

- [ ] **Step 4: Run the seven pre-PR review lanes**

Review the final diff through Performance, Stability, Security, Operator/Ops, Developer/API, and
User/Caller lenses, then perform main-session integration. Normalize findings to P0/P1/P2/P3,
apply in-scope fixes, rerun affected tests and lanes, and close only at `P0=0 P1=0`. Record P2/P3
as fixed or explicitly deferred/filed with rationale.

- [ ] **Step 5: Commit verification/review evidence**

```bash
git add docs/review packages/bluetape-compression packages/bluetape pyproject.toml uv.lock \
  .github/workflows/ci.yml README.md README.ko.md docs/package-layout.md WIP.md CHANGELOG.md
git commit -m "test: verify compressor delivery gates"
```

## Task 10: Commit lessons and prepare the issue-scoped PR

**Complexity:** Medium
**Depends on:** Task 9 with `P0=0 P1=0`
**External boundary:** PR creation is allowed only under the active approved workflow; merge is not

**Files:**

- Create: `docs/lessons/2026-07-12-issue-59-compressor-contracts.md`
- Modify: PR body/metadata only after the lesson commit

- [ ] **Step 1: Write and commit the durable lesson**

Record context, Python `Protocol` decision, provider-specific bounded-decode differences, the Zstd
`max_output_size` discovery, optional dependency isolation, actual RED/GREEN and review misses, and
the future provider-upgrade guard.

```bash
git add docs/lessons/2026-07-12-issue-59-compressor-contracts.md
git commit -m "docs: record compressor provider lessons"
```

- [ ] **Step 2: Recheck the final branch and issue metadata**

Confirm the branch is based on current `origin/develop`, the diff contains only #59 scope, issue
#59 still has milestone `0.2.0`, label `enhancement`, and assignee `debop`, and no P0/P1 or
unchecked required gate remains.

- [ ] **Step 3: Create and verify the PR without merging**

Use an English title and body describing why/what before validation. End the body with the final
Markdown heading `## DoD Status`. Verify live assignee, milestone, labels, base `develop`, body,
reviews, and checks with `gh pr view`; rerun the seven review lanes against the live PR diff and
wait for required CI conclusions.

- [ ] **Step 4: Report the explicit merge boundary**

Render all workflow and Python checklist rows with reconciled counts, commands, commits, changed
files, P0/P1 status, CI/review state, and residual risks. Stop at `PENDING - PR ready for explicit
merge decision`. Do not merge #59 and do not resume #54 until the user explicitly approves merge,
the prerequisite is merged, and the #54 worktree is rebased on current `origin/develop`.

## Plan completion checks

- [ ] Every approved spec acceptance criterion maps to a task and fresh command.
- [ ] No implementation task consumes a file, provider, marker, or artifact created later.
- [ ] Every public behavior has success, invalid, empty, boundary, and caller-value-preservation
  coverage; async/cancellation/resource lifecycle are N/A because all implementations are pure,
  synchronous, call-scoped byte transforms with no owned resource.
- [ ] Workflow YAML, packaging, localized docs, changelog, WIP, rollback, and lessons are assigned.
- [ ] Final implementation and live-PR reviews each use six independent lenses plus main integration
  and close at `P0=0 P1=0`.
