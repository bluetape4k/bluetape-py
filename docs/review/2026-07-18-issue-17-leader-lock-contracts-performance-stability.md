# Issue #17 leader lock performance and stability evidence

Date: 2026-07-19 KST
Implementation evidence head: `f93e4e057cac6cd0994f6a2a6b3438921a515e4d`

## Bounded timing model

The adapter measures finite client-stage bounds before lock construction. For
auto-renew, let `N` be the measured worst-case renewal command bound, `I` the
renew interval, and `L_ms` the exact whole-millisecond lease sent to Redis. The
accepted contract is strictly:

```text
N < I
N + I < L_ms / 1000
```

Both sync and async acquisition validate this before Redis I/O. A derived
`lease / 3` interval is copied rather than mutating caller options and is
floored to Redis milliseconds. The review boundary
`lease=1.000999s, I=0.9605s, N=0.04s` is rejected because Redis owns only a
`1.000s` TTL even though the original Python duration is longer.

Stalled-stage integration tests bind command completion to the observed bound
plus a 100 ms scheduling allowance. Async cancellation of a stalled command is
required to become terminal within 100 ms. No indefinite retry, health-check
loop, scheduler, detached task, sync timeout worker, or global registry exists.

## Contention and command cost

Real Redis contention runs `16` independent contenders for `10` generations in
both sync and async modes. Each generation must produce exactly one elected
action and one strictly increasing fencing token. The commandstats proof fixes
the expected adapter trace per mode to:

- `EVALSHA`: `10 * (16 + 2) = 180` calls;
- fallback `EVAL`: `0` calls on the warmed path;
- `GET`: `180 + 9 = 189` calls, including downstream verification;
- no stale contender may complete the atomic downstream fenced write.

This deterministic command-count proof is preferred over a machine-specific
throughput microbenchmark. The contract is about bounded dispatch, one winner,
strict fencing, and no hidden retries, not a portable operations-per-second
claim.

## Resource ownership

- Sync auto-renew owns at most one named non-daemon renewal thread per held
  lease. The 16-handle integration proof reaches exactly baseline plus 16 and
  returns to the original baseline after release.
- Async lifecycle and cancellation tests snapshot the current event-loop task
  baseline, cancel/await owned tasks, and require exact restoration.
- Borrowed Redis clients remain caller-owned and usable after lock/elector
  completion. Test fixtures close them only after terminal cleanup.
- Process-control exceptions retain exact identity. If a real sync thread has
  started, cleanup signals, joins and owner-checks release before rethrowing the
  original control object.
- Ordinary backend failures cross the public boundary only as fixed sanitized
  package errors.

## Stability replay

- Adapter suite after final timing/ACL correction: `753 passed`.
- Sync/async lock correction suite: `204 passed`.
- Task 6 adversarial lifecycle subset: `21` cases repeated `20` times before
  closure; async `69`, sync+async `199`, full Redis `627` at that checkpoint.
- Real integration final Task 8 gate: `48` ACL cases and `73` sync/async Redis
  cases passed with P0=0/P1=0/P2=0.
- Full workspace replay collected `3246` tests and ended `3245 passed, 1 failed`
  only because the pre-existing cache-redis benchmark could not start Redis.
  The exact failed test immediately passed alone (`1 passed` in 2.08s), so the
  event is classified as external test-service startup flake, not leader logic.

Coverage aggregation and nightly scheduling are N/A for the same reasons
recorded in the TDD ledger. Final exact-head replay remains mandatory.
