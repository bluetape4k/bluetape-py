# Issue #54 Redis Provider Pre-PR Code Review

Review base: `eb272ac58a2fd0b8445de334b84ee8d557d9d3e7`  
Mode: Inline execution; six perspective passes and integration were performed
locally as requested, without delegated agents.

## Findings and Convergence

| Priority | Lens | Evidence | Resolution |
|---|---|---|---|
| P1 | Developer/API | Full workspace pytest reported an import-file mismatch between Redis and serde `test_contracts.py`. | Renamed the Redis module; 211 focused regression tests and 1,237 full tests pass in `6ed10b1`. |
| P2 | Operator/Ops | The planned isolated smoke installed only the provider but imported `TTLCache`, contradicting the spec's exact three runtime dependencies. | Kept the approved dependency boundary and explicitly installed both focused wheels for coexistence proof. |

Final unresolved findings: P0=0, P1=0, P2=0, P3=0.

## Six Perspective Results

| Tier | P0 | P1 | P2 | P3 | Fresh evidence | Verdict |
|---|---:|---:|---:|---:|---|---|
| Performance | 0 | 0 | 0 | 0 | bounded parsers, non-gating benchmark, direct async awaits | PASS |
| Stability | 0 | 0 | 0 | 0 | lifecycle/cancellation tests, 10x repetitions, Redis 8 lane | PASS |
| Security | 0 | 0 | 0 | 0 | fixed Lua source, argument binding, hostile envelopes, ACL and marker redaction | PASS |
| Operator/Ops | 0 | 0 | 0 | 0 | low-cardinality events, rollout/rollback docs, CI, lock/build/wheels | PASS |
| Developer/API | 0 | 0 | 0 | 0 | 22 ordered exports, exact signatures, sync/async parity, full suite | PASS |
| User/caller | 0 | 0 | 0 | 0 | runnable focused examples, explicit non-goals, English/Korean parity | PASS |

## Integrated Review Notes

- Performance: formats bound raw/derived allocation and never add a Redis
  round trip; binary is the compact default. No benchmark threshold gates CI.
- Stability: sync/async providers release admission before observer code;
  factory-owned clients close once, borrowed clients stay open, and async close
  has one joined transient task.
- Security: no caller data is interpolated into Lua; there is no GET/DELETE
  fallback, decoder auto-detection, dynamic compressor selection, or logging of
  keys/tokens/payloads/URLs. Preserved causes are documented as trusted only.
- Operator/Ops: errors/events are stable and low-cardinality; ACL requirement,
  versioned namespace rollout, TTL-aware retirement, and no-`KEYS` guidance are
  explicit.
- Developer/API: the new distribution owns `bluetape.cache.redis` and uses a
  namespace extension without putting Redis in local cache/core/default/dev/all.
- User/caller: identity versus explicit compression, binary versus JSON,
  deadline ownership, owned/borrowed clients, and #55 non-goals are visible in
  both locales.

The workflow scan found the literal `KEYS[1]` only inside the fixed Lua script;
it is a Lua key argument reference, not the unbounded Redis `KEYS` command.

