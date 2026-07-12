# Issue #55 Performance and Stability Scan

Scope: `59bf79b..06c94ef`, focused on the sync/async coordinator, provider Lua
primitives, result envelopes, real Redis tests, and benchmark.

## Scan

| Area | Evidence | Verdict |
|---|---|---|
| Polling and retries | Finite `max_attempts`, `max_polls`, exponential capped jitter, one deadline, and provider policy requiring zero retry. | PASS |
| Deadline command guards | Sync/async recheck immediately before acquire and each snapshot; deterministic tests prevent post-deadline starts. | PASS |
| Redis round trips | One `SET NX PX` acquisition; one bounded atomic snapshot per poll; one atomic publish; cleanup only on owned failure. | PASS |
| Artifact memory | Marker and result prefixes are bounded before parsing/decoding; envelope size is bounded. | PASS |
| Sync blocking | Blocking behavior is explicit in the sync API; acquired user loaders are not falsely interruptible. | PASS |
| Async cancellation | Individual waiters preserve the cache-owned flight; last-waiter cancellation performs one shielded cleanup and leaves no in-flight load. | PASS |
| Ownership | Coordinators borrow cache/provider/codec/observer. Provider owned/borrowed close behavior is unchanged and tested. | PASS |
| Backend failure | Connection, timeout, ACL denial, malformed response, stale owner, expiry, and cleanup failure remain explicit and redacted. | PASS |
| Contention proof | 64 callers across 8 independent coordinators collapse to one loader in sync and async real Redis tests. | PASS |
| Benchmark claims | JSON contains workload/platform metadata and explicitly disclaims production capacity. | PASS |
| Connection-pool admission | Blocking connection pools are rejected because pool-acquisition wait is outside socket timeout bounds. | PASS |

No P0/P1 finding was identified in the main-session scan. The benchmark is a
regression smoke, not a service sizing result.

One P2 optimization is deferred: an active-marker snapshot still transfers a
bounded result prefix that the coordinator ignores. The approved contract
requires one atomic marker/result snapshot, every response and poll budget is
bounded, and changing the Lua result shape would amend that contract. Revisit
this before high-volume production sizing rather than changing it during
review.

## Point-in-time benchmark evidence

Command:

```bash
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py
```

Environment: Python 3.13.14, macOS 26.5.1 arm64. Raw result from the current
review iteration:

```json
{"commands_per_caller":0.3125,"contended_cold_burst_median_ns":4368437,"loader_count":10,"local_hit_median_ns":1125,"metadata":{"callers":64,"cold_repetitions":10,"coordinators":8,"local_repetitions":1000,"options":{"lease_ttl":2.0,"max_attempts":3,"max_poll_interval":0.01,"max_polls":100,"namespace":"benchmark:test:value-v1","poll_interval":0.001,"redis_io_timeout":0.4,"result_ttl":2.0,"wait_timeout":2.0},"payload_bytes":5,"platform":"macOS-26.5.1-arm64-arm-64bit-Mach-O","production_capacity_claim":false,"python":"3.13.14"},"redis_commands":200}
```
