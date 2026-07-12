# Issue #59 Compressor Contracts TDD Evidence

Date: 2026-07-12
Scope: `bluetape-compression` structural and native compressor contracts

## RED/GREEN record

| Slice | RED evidence | GREEN evidence | Commit |
|---|---|---|---|
| Structural protocol and stdlib objects | `test_compression.py` collection failed because `Compressor` was not importable. | `uv run pytest packages/bluetape-compression/tests/test_compression.py -q` — 107 passed. | `b98941c` |
| Native provider boundary | `test_native_imports.py` — 12 failures because `bluetape.compression.native` and `_support` did not exist. | Focused suite — 13 passed; combined stdlib/import suite — 120 passed; `uv lock --check` passed. | `e47ff25` |
| LZ4 frame provider | Native provider suite collection failed because `Lz4Compressor` was not importable. | LZ4 subset — 26 passed. | `c539a10` |
| Raw Snappy provider | Native provider suite collection failed because `SnappyCompressor` was not importable. | Snappy subset — 20 passed, 26 deselected. | `b8281f0` |
| Zstd frame provider | Native provider suite collection failed because `ZstdCompressor` was not importable. | Aggregate native suite at the slice boundary — 75 passed. | `8e8d6b7` |
| Cross-provider conformance | Aggregate run exposed two stale import-test assumptions: collection order loaded the native namespace and final `native.__all__` was no longer empty. | Fresh-subprocess base/import suite — 120 passed; final native conformance suite — 98 passed. | Task 6 conformance commit |

## Contract evidence added in Task 6

- Exact ordered root and native exports.
- Structural custom compressor without inheritance.
- Six-implementation empty/bare-empty/repeatability and no-logging matrix.
- LZ4 64 KiB input windows and remaining-output budget instrumentation.
- Snappy and Zstd declared/actual size mismatch rejection.
- Native 8 MiB highly compressible round-trips without an absolute timing threshold.
- Caller memoryview release after ordinary Python traceback cleanup.

Provider versions are locked as `lz4==4.4.5`, `cramjam==2.11.0`, and
`zstandard==0.25.0`. Provider-dependent commands selected an explicit focused or aggregate extra;
base imports never relied on those packages being installed.
