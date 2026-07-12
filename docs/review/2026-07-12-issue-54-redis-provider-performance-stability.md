# Issue #54 Redis Provider Performance and Stability

Date: 2026-07-12 KST

## Non-Gating Envelope Snapshot

Command:

```bash
uv run python packages/bluetape-cache-redis/benchmarks/envelope_benchmark.py \
  | tee /tmp/issue-54-envelope-benchmark.json
```

Environment: Python 3.13.14, macOS 26.5.1, arm64. The benchmark performs a
short warmup, then measures encode plus decode. It makes no absolute latency,
throughput, production-capacity, or cross-machine ranking claim.

| Case | Format | Encoded bytes | Samples | Median ns | p95 ns |
|---|---|---:|---:|---:|---:|
| empty | binary-v1 | 94 | 5,000 | 4,500 | 4,791 |
| empty | json-v1 | 195 | 5,000 | 5,959 | 6,583 |
| small, 1 KiB | binary-v1 | 1,118 | 1,000 | 4,833 | 5,083 |
| small, 1 KiB | json-v1 | 1,563 | 1,000 | 8,667 | 9,167 |
| near-limit, 8 MiB | binary-v1 | 8,388,702 | 10 | 603,562 | 616,041 |
| near-limit, 8 MiB | json-v1 | 11,185,007 | 10 | 23,473,166 | 25,121,584 |

Binary is smaller than JSON for the byte-heavy cases. Both encoded near-limit
results remain below the configured 16 MiB outer bound. The raw output was
captured at `/tmp/issue-54-envelope-benchmark.json`; that temporary path is
evidence location, not a tracked release artifact.

## Stability Evidence

The sync close subset ran 10 consecutive times: 6 passed per run, 60 total.
The async close/cancel/loop subset ran 10 consecutive times: 9 passed per run,
90 total. There were zero hangs, pending-task warnings, leaked-task warnings,
or flaky failures.

Redis integration ran serially through the ecosystem `RedisServer`: 8 passed.
Coverage includes TTL expiry, `SET NX PX`, fixed Lua compare-delete, borrowed
sync/async lifecycle, binary/JSON round trips, script ACL denial without an
unsafe fallback, and redacted connection failures.

## Scan Result

| Priority | File:Line | Lens | Finding | Disposition |
|---|---|---|---|---|
| none | `_formats.py:125`, `_formats.py:269` | performance | Binary and JSON predict/enforce the outer bound before large output construction. | PASS |
| none | `_async_provider.py:230-302` | performance | Async commands await redis-py directly; no executor or blocking sync client appears in async paths. | PASS |
| none | `_provider.py:326`, `_async_provider.py:304` | stability | Admission drains before owned close; no lifecycle lock spans Redis command I/O. | PASS |
| none | `_async_provider.py:328-386` | stability | Exactly one transient cleanup task is shielded, joined, and cleared. | PASS |

