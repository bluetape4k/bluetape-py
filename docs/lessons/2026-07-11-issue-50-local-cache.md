# Issue #50 Local Cache Lessons

## Context

Issue #50 introduced stdlib-only bounded synchronous and asyncio TTL loading
caches in a focused `bluetape-cache` distribution. The difficult boundary was
not basic TTL storage; it was preserving generation, waiter, cancellation, and
capacity ownership across every terminal and admission failure.

## Decisions

- Separate active/joinable flights from terminal-pending owned flights. A
  superseded or abandoned load must stop accepting waiters but continue to
  consume `max_inflight` until its loader is terminal.
- Gate publication with clear epoch, key version, active identity, and
  abandoned/superseded state. `set`, `invalidate`, and `clear` never wait for a
  loader and never permit stale publication.
- Run loader bodies outside cache locks and keep all state transitions under
  the owning lock. Use one shared store primitive for explicit writes and
  loader publication so expiry, LRU, version, eviction, and heap compaction do
  not drift.
- Treat caller cancellation and loader ownership separately. Async callers
  await a shielded shared task; the last departing waiter abandons and cancels
  the loader without awaiting its terminal cleanup.
- Make cleanup itself cancellation- and task-factory-resistant. Repeated
  cancellation can interrupt an `await` inside `finally`, and even cleanup task
  creation can fail. Both paths need deterministic regression tests and an
  exactly-once waiter transition.
- Preserve the thin install boundary. `bluetape-cache` is stdlib-only and
  available through an explicit meta extra; the default `bluetape` dependency
  remains core-only.

## Outcome and evidence

- 120 cache tests cover contracts, state, concurrency, cancellation,
  saturation, packaging, and isolated namespace behavior.
- The workspace suite increased from 737 to exactly 857 tests and passed after
  explicitly syncing all packages and extras.
- Ruff, lock validation, all-package builds, isolated no-index installs,
  actionlint, doctest, and diff checks passed.
- A committed deterministic benchmark records raw samples and passed every
  performance/stability threshold.
- Final integrated review reached `P0=0 P1=0`.

## Review misses and future guards

- Test teardown is production-grade concurrency code. Join or gather every
  owned helper before asserting survivors, so the first failure cannot prevent
  later cleanup.
- Terminal helpers must clean up even when publication itself fails. Clock and
  task-factory injection are useful deterministic ways to prove rare admission
  and cleanup paths.
- One cancellation is insufficient async evidence. Hold the cache lock and
  deliver repeated cancellations while cleanup is waiting.
- A default `uv run` may reconcile away optional workspace extras. For the
  full multi-package suite, sync all packages/extras and run pytest with
  `--no-sync` so provider tests exercise the intended environment.
- Documentation parity means behaviorally equivalent examples, not merely
  matching headings or similar prose.
- Issue #51 must reuse the generation, ownership, cancellation, redaction, and
  bounded-admission contracts here. Redis coordination must not weaken them or
  silently turn local point-in-time stats into high-cardinality telemetry.
