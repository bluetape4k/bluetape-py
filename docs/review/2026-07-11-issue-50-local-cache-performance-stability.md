# Issue #50 Local Cache Performance and Stability Evidence

## Scope

This evidence covers the stdlib-only `TTLCache` and `AsyncTTLCache` introduced
for issue #50. It is non-gating product telemetry: the acceptance thresholds
below detect implementation pathologies, but they are not public performance
guarantees.

## Environment and command

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

Timing ran without `tracemalloc`. Allocation measurement ran in a separate
in-process phase. Each RSS scenario ran in a fresh subprocess; the recorded
value is normalized process high-water, not retained memory.

## Acceptance results

| Signal | Observed | Threshold | Result |
|---|---:|---:|---|
| Same-key loader invocations | 1 for 8 callers | exactly 1 | PASS |
| Different-key loader overlap | 2 loaders met at barrier | overlap required | PASS |
| Cache-hit / `OrderedDict` median cost | 10.82x | <= 25x | PASS |
| Distinct/hot throughput | 1.03x | >= 0.5x | PASS |
| Distinct/hot p95 latency | 1.00x | <= 2.5x | PASS |
| Expiry-heavy 10k/1k median ns/op | 1.05x | <= 2.5x | PASS |
| Expiry-heavy 10k/1k batch p99 | 1.02x | <= 15x | PASS |
| Expiry-heavy 10k/1k batch max | 1.22x | <= 15x | PASS |
| Rebuild-trigger proxy 10k/1k max | 6.50x | <= 15x | PASS |
| Counted heap rebuilds | 1 at each capacity | every shrink counted | PASS |

The fixed-worker scenarios used eight workers and 20,000 operations per worker
with a 90% get / 10% set mix. Hot-key throughput was 2.19M operations/second;
distinct-key throughput was 2.26M operations/second. Both distributions had a
708 ns p95 operation latency in this run.

## Lifecycle and boundedness

- Ten consecutive sync/async correctness runs passed before timing: 64 tests
  per iteration, with no join timeout, pending task, or warning.
- Same-key sync and async observations each invoked one loader for eight callers.
- Different sync keys entered their loader bodies concurrently.
- Constant-clock overwrite probes observed one threshold-crossing heap rebuild
  at capacities 1,000 and 10,000. Final heap lengths were 1,999 and 19,999,
  respectively, below the `2 * max_size` bounds of 2,000 and 20,000.
- The separate allocation phase recorded a 520-byte traced peak for 10,000
  cache-hit operations. Fresh-process RSS high-water was 35,323,904 bytes for
  the hit scenario and 39,124,992 bytes for overwrite.

## Caveats

- `perf_counter_ns` timing on one developer machine is useful for ratio-based
  regression detection, not cross-machine comparison.
- The heap rebuild duration is the externally timed triggering operation, an
  upper-bound proxy that includes the surrounding `set` work.
- macOS reports `ru_maxrss` in bytes; Linux reports KiB. The harness normalizes
  Linux values by multiplying by 1024.
- A chart is not included because this internal review has five independent
  ratio gates with different units and thresholds; the compact threshold table
  is the less misleading comparison surface. No public README performance claim
  depends on these measurements.

## Verdict

No performance or stability threshold was breached. No production repair was
triggered.

`P0=0 P1=0`
