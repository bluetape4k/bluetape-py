# Issue #59 Compressor Contracts TDD 근거

날짜: 2026-07-12
범위: `bluetape-compression` structural 및 native compressor contract

## RED/GREEN 기록

| Slice | RED 근거 | GREEN 근거 | Commit |
|---|---|---|---|
| Structural protocol 및 stdlib object | `Compressor`를 import할 수 없어 `test_compression.py` collection 실패 | `uv run pytest packages/bluetape-compression/tests/test_compression.py -q` — 107 passed | `b98941c` |
| Native provider boundary | `bluetape.compression.native`와 `_support`가 없어 `test_native_imports.py` 12개 실패 | Focused suite 13 passed; combined stdlib/import suite 120 passed; `uv lock --check` 통과 | `e47ff25` |
| LZ4 frame provider | `Lz4Compressor`를 import할 수 없어 native provider suite collection 실패 | LZ4 subset 26 passed | `c539a10` |
| Raw Snappy provider | `SnappyCompressor`를 import할 수 없어 native provider suite collection 실패 | Snappy subset 20 passed, 26 deselected | `b8281f0` |
| Zstd frame provider | `ZstdCompressor`를 import할 수 없어 native provider suite collection 실패 | Slice boundary의 aggregate native suite 75 passed | `8e8d6b7` |
| Cross-provider conformance | Aggregate run에서 stale import-test assumption 두 개 노출: collection order가 native namespace를 load하고 final `native.__all__`가 더 이상 empty가 아님 | Fresh-subprocess base/import suite 120 passed; final native conformance suite 98 passed | Task 6 conformance commit |

## Task 6에서 추가한 contract 근거

- Exact ordered root 및 native export
- Inheritance 없이 사용하는 structural custom compressor
- 6 implementation의 empty/bare-empty/repeatability/no-logging matrix
- LZ4 64 KiB input window 및 remaining-output budget instrumentation
- Snappy/Zstd declared/actual size mismatch 거부
- Absolute timing threshold 없이 native 8 MiB highly compressible round-trip
- Ordinary Python traceback cleanup 후 caller memoryview release

Provider version은 `lz4==4.4.5`, `cramjam==2.11.0`,
`zstandard==0.25.0`으로 lock했다. Provider-dependent command는 명시적인
focused 또는 aggregate extra를 선택했으며 base import는 package 설치에 의존하지 않는다.
