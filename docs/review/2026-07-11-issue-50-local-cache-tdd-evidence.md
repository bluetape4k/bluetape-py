# Issue #50 Local Cache TDD Evidence

Date: 2026-07-11
Baseline: 737 workspace tests before `bluetape-cache`
Current result: 857 workspace tests, including 120 cache tests

## Behavior-first sequence

| Slice | RED evidence | GREEN evidence |
|---|---|---|
| Package and constructors | Missing distribution, exports, validation, and exact signature contracts failed. | Constructor/export/typing/package contracts pass, including huge finite TTL conversion and non-callable clocks. |
| TTL/LRU state | 25 state cases failed before public state methods and `_CacheState` existed. | Exact-tick expiry, rollback clamp, MRU movement, live-LRU eviction, heap compaction, counters, invalidation, and loop ownership pass. |
| Sync loading | 12 loading cases failed before `get_or_load` and flight ownership. | Same-key coalescing, different-key progress, recursion, failure identity, supersession, hard limits, and exact gauges pass. |
| Async loading | 10 loading cases failed before async flight ownership and generation gates. | Coalescing, inherited recursion rejection, mutation generations, task admission rollback, and publication failure cleanup pass. |
| Async cancellation | Cancellation/abandonment/saturation cases failed before shielded caller ownership. | Surviving waiters, last-waiter abandonment, cancellation-resistant loaders, self-cancellation, saturation recovery, and task cleanup pass. |
| Repeated cancellation | A second cancel interrupted waiter cleanup and left a phantom active flight. | Lock-contention probes preserve multiple cancellation deliveries while completing waiter release exactly once. |
| Cleanup task admission | A rejecting loop task factory leaked the release coroutine and overrode caller cancellation. | The unsubmitted coroutine closes, inline fallback cleanup converges, and caller cancellation/value semantics remain intact. |
| Packaging | Missing `cache` extra raised `KeyError`. | Metadata tests, all-package build, default-install isolation, and explicit-extra import pass. |

## Deterministic lifecycle proof

- Sync and async test files passed ten consecutive pre-benchmark iterations:
  `64 passed` per iteration.
- The final cache suite passed `120 tests` with finite thread/task/event
  boundaries and no pending-task warning.
- The final workspace run used an explicit all-package/all-extra sync followed
  by `uv run --no-sync pytest -q`; result: `857 passed in 8.41s`.
- The default `uv run pytest -q` path was not accepted as evidence after it
  pruned the Apache Fory extra and failed collection. Reinstalling every package
  extra and using `--no-sync` proved the current workspace instead of hiding
  the environment mismatch.

## Fresh validation ladder

```text
uv run --no-sync ruff format --check .     38 files already formatted
uv run --no-sync ruff check .              All checks passed
uv run pytest packages/bluetape-cache/tests -q   120 passed
uv sync --all-packages --all-extras --locked
uv run --no-sync pytest -q                 857 passed
uv lock --check                            resolved 20 packages
uv build --all-packages                    10 distributions built
isolated no-index base/cache-extra smoke   PASS
actionlint                                 PASS
git diff --check                           PASS
```

The new collected-test delta is exactly `857 - 737 = 120`, matching the cache
package suite.
