# Issue #50 Local Cache Code Review

Date: 2026-07-11
Scope: `origin/develop...feat/issue-50-local-cache`
Gate: Type A Step 6-R pre-PR review

## Review convergence

The implementation was reviewed incrementally after every planned task. The
following P1 findings were reproduced and repaired before this final pass:

- finite positive TTL values large enough to overflow float nanosecond
  conversion;
- non-callable clocks accepted until first state access;
- thread teardown that stopped joining after the first failed assertion;
- sync publication exceptions that stranded waiters and flight capacity;
- async task-factory rejection that leaked admitted flights;
- repeated caller cancellation that interrupted waiter release;
- release-task factory rejection that leaked a coroutine and overrode caller
  cancellation;
- root examples that were shorter than the package contract examples.

Every repair has deterministic regression coverage. The final branch review is
against the current integrated diff and raw benchmark/package evidence.

| Lens | P0 | P1 | Final evidence |
|---|---:|---:|---|
| Performance | 0 | 0 | Deterministic raw JSON passes hit-cost, contention, expiry-scaling, and rebuild-proxy thresholds; no blocking loader body runs under a cache lock. |
| Stability | 0 | 0 | Finite lifecycle tests cover sync threads, loop binding, cancellation, repeated cancellation, task-factory/publication failure, supersession, saturation, and terminal cleanup. |
| Security | 0 | 0 | No logging/callback surface formats keys, values, loaders, flights, or errors. Unsanitized `KeyError(key)` and loader exceptions are explicitly caller-owned/redaction-required surfaces. |
| Operator/Ops | 0 | 0 | Immutable lifetime counters and point-in-time gauges are documented; default install remains core-only; no hidden thread, scheduler, listener, or external backend exists. |
| Developer/API | 0 | 0 | Exact exports, keyword-only constructors, sync/async concept parity, native hash errors, `None` identity, focused distribution, lockfile, wheel metadata, and doctest examples agree. |
| User/Caller | 0 | 0 | English/Korean root docs and package docs cover install state, TTL/loading/mutation/cancellation behavior, limits, monitoring, secret redaction, and Redis issue #51. |

## Main-session integration review

- State ownership is centralized in `_CacheState`; sync and async wrappers own
  their respective locks and flight lifecycles.
- Version, epoch, and active-flight identity gates prevent stale loader
  publication after `set`, `invalidate`, `clear`, cancellation, or supersession.
- Versioned expiry nodes and post-write rebuilding keep heap metadata bounded;
  unused key versions are removed when no entry or owned flight remains.
- Loader bodies run outside cache locks. Same-key callers coalesce; different
  keys can progress independently. Hard admission counts owned terminal-pending
  flights rather than only joinable active flights.
- The meta package adds only an explicit `cache` extra; default installation
  remains `bluetape-core` only, with no root `bluetape/__init__.py` surface.
- The benchmark and review documents use tables instead of a chart because the
  acceptance signals have different units and thresholds; a combined visual
  would obscure rather than clarify the result.

## Residual P2/P3 decisions

- Timing and RSS observations are machine-local regression evidence, not a
  portable SLA.
- Redis, cross-process invalidation, background expiry, byte-size accounting,
  callbacks/listeners, and framework adapters remain outside issue #50.
- A cancellation-resistant async loader continues to own its admission slot
  until terminal; callers must provide cooperative cancellation and deadlines.

Final gate: **P0=0 P1=0**.

