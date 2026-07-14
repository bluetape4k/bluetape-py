# Issue #12 Resilience Policies TDD Evidence

Date: 2026-07-14 KST
Implementation evidence HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`

## Task progression

| Boundary | Commit | Fresh green evidence at the boundary |
| --- | --- | --- |
| Shared contracts and package scaffold | `37e8aa0` | 32 contract/packaging tests |
| Deterministic backoff | `757759b` | 56 relevant contract/backoff tests |
| Sync/async retry | `15ad5f6` | 71 relevant tests |
| Cooperative async timeout | `52e3181` | 24 relevant retry/timeout tests |
| Generation-safe circuit breaker | `dcd8620` | 31 circuit and surrounding policy tests |
| Bounded bulkhead | `4bc1318` | 23 bulkhead and surrounding policy tests |
| Immutable pipelines and observability | `0d53f54` | 105 package tests |
| Meta/lock/build registration | `686e472` | 11 packaging/classification tests plus focused builds |
| Bilingual docs and executable examples | `9d6efa0` | 121 package tests |
| Ownership and callable corrections | `2955071`, `979d024` | 144 package tests |
| Workspace-safe test isolation | `b21a7c6` | 144 package tests; 1,659 workspace tests collected |

The counts above are boundary results retained from the implementation run. They are
not reconstructed RED claims. Each owning task used a named test first and reran the
owning file before its task commit.

## Recorded RED/GREEN corrections

These failures were directly observed during the final integration pass:

| Contract | RED evidence | GREEN evidence |
| --- | --- | --- |
| Bilingual executable README and workspace registration | `test_readme_examples.py`: 13 failures before docs existed | 13 passed, then 121 package tests passed |
| Sync callable returning awaitable | 4 focused failures: retry exhausted, breaker/bulkhead returned coroutine, pipeline propagated the wrong terminal | 4 focused passes; one invocation, no circuit count, no permit leak |
| Completion clock callback failure | 4 sync/async half-open tests left `half_open_in_flight=1` | 4 passed with slot restored to zero |
| Cancellation during async reconciliation | 4 focused tests leaked permit/probe on one or repeated cancellation | 4 passed; cleanup completes in the caller task before cancellation escapes |
| `functools.partial` callable classification | 3 focused failures: async partial rejected, generator partial admitted | 3 passed before package-wide rerun |
| Workspace pytest collection | 10 import errors from the top-level `tests` package, later 3 basename collisions | Unique `bluetape_resilience_tests` package: 1,659 tests collected and passed |

## Deterministic controls

- `FakeClock` controls circuit deadlines and generation changes without wall-clock
  sleeps.
- `threading.Event` and bounded `join(1)` coordinate sync capacity and stale
  completions.
- `asyncio.Event`, `wait_for(..., 1)`, and explicit task cancellation coordinate
  async waiters, completion reconciliation, and repeated cancellation.
- Tests assert final `in_flight`, `waiters`, and `half_open_in_flight` snapshots and
  leave no caller-created thread or task running.

Final package command at the implementation evidence HEAD:

```text
uv run pytest packages/bluetape-resilience -q
144 passed in 0.16s
```
