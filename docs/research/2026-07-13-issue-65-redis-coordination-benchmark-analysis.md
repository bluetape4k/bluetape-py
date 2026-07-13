# Issue #65 Redis Coordination Benchmark Evidence

This note interprets the bounded smoke evidence in
`docs/review/artifacts/issue-65-redis-coordination-benchmark.json`. It is a
repeatability and correctness artifact, not a production-capacity or SLO claim.

## Reproduction

The checked artifact was produced from a clean source tree with:

```bash
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
  --profile smoke --mode both --seed 20260712 --role snapshot \
  --output docs/review/artifacts/issue-65-redis-coordination-benchmark.json
```

The fixed smoke registry produced 12 results, 60 measured samples, 10,400
measured operations, and 12 warmups. Its safety ceilings are inherited from the
full registry: at most 24 results, 64 callers, 8 coordinators, 8 keys, a
15,728,640-byte value, and 32 MiB of aggregate payload.

## Environment

- Source Git SHA: `b989f8619a10af22f2c4725dcc2e697663709c6b`
- Python: CPython 3.13.14 on Darwin arm64
- Redis client: 8.0.1; ephemeral Redis server: 8.8.0
- Redis image digest: `sha256:2838d5524559494f6f1cd66e97e76b200d64a633a8614200620755ed395daf32`
- Policy: `redis-coordination-benchmark-v1`
- Policy digest: `7e7c46760f9c9d04c82f63972e8f7e0ab304710e725b759cb0606d1955bae8ad`
- Registry digest: `9e114b562ced345d7c7aab9295ab074173475dc192d25784811f38c37dfd3285`
- Lock digest: `a825207f86a8935492348035f65b942db501fe4fb6d3609797c3e678cdcbbd36`

## Observed Smoke Medians

| Mode | Scenario | Median ns | Correctness loaders | Correctness Redis commands |
| --- | --- | ---: | ---: | ---: |
| sync | local-only | 7,704,417 | 4 | 0 |
| sync | local-hit | 453,792 | 0 | 0 |
| sync | single-coordinator | 9,126,125 | 1 | 2 |
| sync | multi-coordinator | 17,385,333 | 1 | 17 |
| sync | completed-reuse | 1,466,250 | 0 | 10 |
| sync | unrelated-keys | 9,828,083 | 4 | 8 |
| async | local-only | 6,537,333 | 4 | 0 |
| async | local-hit | 1,006,209 | 0 | 0 |
| async | single-coordinator | 8,527,542 | 1 | 2 |
| async | multi-coordinator | 10,110,834 | 1 | 17 |
| async | completed-reuse | 1,256,000 | 0 | 10 |
| async | unrelated-keys | 6,882,959 | 4 | 8 |

Each smoke case has only five measured samples. The schema therefore records
both p95 and p99 as `null`: p95 requires at least 20 samples and p99 at least
100. The medians above describe only this captured run and must not be used as
cross-machine regression thresholds.

## Correctness Interpretation

All correctness invariants passed. The `correctness_*` fields come from a
separate instrumented phase before warmup and measurement; command recorders,
loader counters, and envelope-size probes are not installed in the timed path.
The single- and multi-coordinator cases each converged to one loader, unrelated
keys used four independent loaders, completed-result reuse invoked no waiter
loader, and local-only/local-hit issued no Redis commands. Active/completed
result bytes describe the correctness snapshot only. `process_high_water_bytes`
is sampled after measurement and is platform-local, so it is not comparable
across unlike operating systems or process models.

The artifact demonstrates bounded execution, report integrity, and the intended
coordination semantics under one ephemeral local Redis environment. It does not
establish deployment sizing, tail-latency guarantees, throughput capacity,
production topology behavior, or an SLO.
