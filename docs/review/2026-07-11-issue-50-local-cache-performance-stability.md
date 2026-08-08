# Issue #50 Local Cache 성능 및 안정성 근거

## 범위

이 근거는 issue #50에서 추가한 stdlib-only `TTLCache`와 `AsyncTTLCache`를
다룬다. Product gate가 아닌 product telemetry다. 아래 acceptance threshold는
구현 path의 병리를 감지하지만 public performance guarantee는 아니다.

## 환경 및 명령

- Python: 3.13.14
- Platform: macOS 26.5.1, arm64, 10 logical CPUs
- Benchmarked source SHA: `e7a4c3d16cb68a5def84b3b2ddfce95dc5a662be`
- Raw evidence: `docs/review/artifacts/issue-50-local-cache-benchmark.json`
- Raw evidence SHA-256: `8d36c98adf995b3d6ec654aa1f5424a08c015ee1e4ec93917279d92aa85814d1`

```bash
uv run python packages/bluetape-cache/benchmarks/cache_benchmark.py \
  --capacity 10000 --operations 100000 --warmups 3 --repetitions 7 \
  --output docs/review/artifacts/issue-50-local-cache-benchmark.json
```

Timing은 `tracemalloc` 없이 실행했다. Allocation measurement는 별도 in-process
phase에서 실행했다. 각 RSS scenario는 fresh subprocess에서 실행했으며 기록된
값은 retained memory가 아니라 normalized process high-water다.

## Acceptance 결과

| Signal | 관찰 | Threshold | 결과 |
|---|---:|---:|---|
| Same-key loader invocation | 8 caller에 1 | exactly 1 | PASS |
| Different-key loader overlap | 2 loader가 barrier에서 만남 | overlap required | PASS |
| Cache-hit / `OrderedDict` median cost | 10.82x | <= 25x | PASS |
| Distinct/hot throughput | 1.03x | >= 0.5x | PASS |
| Distinct/hot p95 latency | 1.00x | <= 2.5x | PASS |
| Expiry-heavy 10k/1k median ns/op | 1.05x | <= 2.5x | PASS |
| Expiry-heavy 10k/1k batch p99 | 1.02x | <= 15x | PASS |
| Expiry-heavy 10k/1k batch max | 1.22x | <= 15x | PASS |
| Rebuild-trigger proxy 10k/1k max | 6.50x | <= 15x | PASS |
| Counted heap rebuild | 각 capacity에서 1 | every shrink counted | PASS |

Fixed-worker scenario는 worker 8개와 worker당 20,000 operation, 90% get / 10%
set mix를 사용했다. Hot-key throughput은 2.19M operations/second,
distinct-key throughput은 2.26M operations/second였다. 이 실행에서 두
distribution의 p95 operation latency는 708 ns였다.

## Lifecycle 및 boundedness

- Timing 전에 10회 연속 sync/async correctness run이 통과했다. 반복마다
  64 tests이며 join timeout, pending task, warning은 없었다.
- Same-key sync 및 async observation은 각각 8 caller에 대해 하나의 loader만
  호출했다.
- Different sync key는 loader body에 concurrent하게 진입했다.
- Constant-clock overwrite probe는 capacity 1,000과 10,000에서 threshold를
  넘는 heap rebuild를 각각 한 번 관찰했다. 최종 heap length는 각각 1,999와
  19,999로 `2 * max_size` bound인 2,000과 20,000보다 작았다.
- 별도 allocation phase는 10,000 cache-hit operation에서 traced peak 520
  byte를 기록했다. Fresh-process RSS high-water는 hit scenario에서
  35,323,904 byte, overwrite에서 39,124,992 byte였다.

## 주의 사항

- 한 개발자 machine의 `perf_counter_ns` timing은 ratio-based regression
  detection에는 유용하지만 machine 간 비교에는 적합하지 않다.
- Heap rebuild duration은 externally timed triggering operation이며 주변 `set`
  작업을 포함하는 upper-bound proxy다.
- macOS는 `ru_maxrss`를 byte로, Linux는 KiB로 보고한다. Harness는 Linux 값을
  1024배해 정규화한다.
- 이 internal review는 단위와 threshold가 다른 다섯 개 independent ratio
  gate를 가지므로 chart를 넣지 않았다. Compact threshold table이 덜 오해를
  일으키는 비교 surface다. Public README performance claim은 이 측정에 의존하지 않는다.

## 판정

Performance 또는 stability threshold를 위반하지 않았다. Production repair도
trigger되지 않았다.

`P0=0 P1=0`
