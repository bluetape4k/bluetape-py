# Issue #59 Compressor 성능 및 안정성 scan

- 날짜: 2026-07-12
- 범위: `origin/develop`부터 `e8b4100`까지 compressor production code, native provider, package metadata, test, CI diff
- 판정: `PASS` (`P0=0`, `P1=0`, `P2=0`, `P3=0`)

## Performance inspection

| 영역 | 근거 | 결과 |
|---|---|---|
| Stdlib output bound | `_decompress()`가 최대 64 KiB를 feed하고 `remaining + 1`을 요청하며 accepted output만 append | Bounded logical output; exact와 one-over test 통과 |
| Gzip concatenation | Pending input을 slice하고 unused-data refeed가 64 KiB cap까지만 증가 | Unbounded refeed 없음; targeted stdlib risk test 6개 통과 |
| LZ4 | `LZ4FrameDecompressor`가 최대 64 KiB input을 소비하고 `remaining + 1` output budget만 받음 | Spy가 모든 input window와 budget을 검증; one-shot full decode 없음 |
| Snappy | Declared raw output length를 `decompress_raw()` 전에 검사 | Oversized spy가 decode가 호출되지 않음을 증명 |
| Zstd | Declared frame content size를 요구하고 decoder construction 전에 검사 | Oversized spy가 decoder가 생성되지 않음을 증명; unknown size 거부 |
| Allocation 및 state | Frozen/slotted instance가 per-call buffer나 provider context를 보존하지 않고 output을 한 번 `bytes`로 조립 | Repeated call과 weak-reference cleanup 통과 |

새 위험 명령:

```text
uv run --package bluetape-compression --extra native pytest \
  packages/bluetape-compression/tests/test_native_compressors.py -q \
  -k 'large_highly_compressible or bounds_input_windows or declared_oversize or exact_output_limits or do_not_retain'
=> 12 passed, 86 deselected

uv run pytest packages/bluetape-compression/tests/test_compression.py -q \
  -k 'single_output_budget or many_members_reprocesses or bounded_exponential_refeeding or largest_safe_limit'
=> 6 passed, 101 deselected
```

8 MiB native round-trip은 stability evidence이며 absolute latency benchmark가
아니다. Speed나 compression-ratio claim을 하지 않으므로 benchmark chart는 N/A다.

## Stability inspection

- Async path, thread, lock, file, socket, subprocess, external service, mutable
  shared state를 추가하지 않았다.
- Provider import는 lazy하고 focused하다. Configuration과 provider availability는
  construction에서 실패하므로 configured instance가 operation 중 처음 실패하지 않는다.
- Malformed, truncated, trailing, concatenated, checksum-failed, declared/actual
  mismatch input은 fail closed한다.
- `MemoryError`와 `BaseException` subclass는 translate하지 않는다. Ordinary
  provider failure는 handler 밖에서 cause/context나 caller payload logging 없이
  변환한다.
- Dedicated native CI는 Docker/Testcontainers와 격리되고 exact provider pin을 사용한다.

Performance와 stability blocker는 남아 있지 않다.
