# Issue #59 Compressor Performance and Stability Scan

- Date: 2026-07-12
- Scope: compressor production code, native providers, package metadata, tests, and CI diff from
  `origin/develop` through `e8b4100`
- Verdict: `PASS` (`P0=0`, `P1=0`, `P2=0`, `P3=0`)

## Performance inspection

| Area | Evidence | Result |
|---|---|---|
| Stdlib output bound | `_decompress()` feeds at most 64 KiB, requests `remaining + 1`, and appends only accepted output | Bounded logical output; exact and one-over tests pass |
| Gzip concatenation | Pending input is sliced and unused-data refeeding grows only to the 64 KiB cap | No unbounded refeeding; six targeted stdlib risk tests pass |
| LZ4 | `LZ4FrameDecompressor` consumes at most 64 KiB input and receives only `remaining + 1` output budget | Spy verifies every input window and budget; no one-shot full decode |
| Snappy | Declared raw output length is checked before `decompress_raw()` | Oversized spy proves decode is not called |
| Zstd | Declared frame content size is required and checked before decoder construction | Oversized spy proves decoder is not created; unknown size is rejected |
| Allocation and state | Frozen/slotted instances retain no per-call buffer or provider context; outputs are assembled once into `bytes` | Repeated calls and weak-reference cleanup pass |

Fresh risk commands:

```text
uv run --package bluetape-compression --extra native pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q \
  -k 'large_highly_compressible or bounds_input_windows or declared_oversize or exact_output_limits or do_not_retain'
=> 12 passed, 86 deselected

uv run pytest packages/bluetape-compression/tests/test_compression.py -q \
  -k 'single_output_budget or many_members_reprocesses or bounded_exponential_refeeding or largest_safe_limit'
=> 6 passed, 101 deselected
```

The 8 MiB native round-trips are stability evidence, not an absolute latency benchmark. No speed
or compression-ratio claim is made, so a benchmark chart is N/A.

## Stability inspection

- No async path, thread, lock, file, socket, subprocess, external service, or mutable shared state
  was added.
- Provider imports are lazy and focused. Configuration and provider availability fail at
  construction, so a configured instance does not fail for the first time deep in an operation.
- Malformed, truncated, trailing, concatenated, checksum-failed, and declared/actual mismatch
  inputs fail closed.
- `MemoryError` and `BaseException` subclasses are not translated. Ordinary provider failures are
  converted outside their handlers with no cause/context or caller payload logging.
- Dedicated native CI is isolated from Docker/Testcontainers and uses exact provider pins.

No performance or stability blocker remains.
