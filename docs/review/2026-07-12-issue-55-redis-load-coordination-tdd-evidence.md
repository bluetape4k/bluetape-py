# Issue #55 Redis Load Coordination TDD Evidence

Baseline: `origin/develop@59bf79b`  
Verified implementation: `06c94efda6b6b7f3a958d27ab3e034b6f6f82893`

## RED/GREEN record

| Task | RED evidence | GREEN evidence |
|---|---|---|
| Contracts and packaging | New contract imports and exact dependency assertions failed before implementation. | Commit `2018e16`; contracts, envelope, and packaging tests passed. |
| Provider primitives | Recording clients rejected missing bounded snapshot/publish APIs and policy. | Commit `3e1d419`; sync/async fixed-Lua, response, policy, and no-fallback tests passed. |
| Sync coordinator | New cache-first state-machine tests failed before the coordinator existed. | Commit `395befc`; 29 sync coordinator tests and related provider tests passed. |
| Async coordinator | Async parity and cancellation tests failed before the async coordinator existed. | Commit `ff6be13`; shared-waiter, last-waiter, cleanup, and parity tests passed. |
| Real Redis and benchmark | Integration helpers and behavior were absent. | Commits `31b5dec`, `fd75af6`, and `06c94ef`; 19 serial Redis tests plus five stress repetitions passed. |
| Documentation and wheels | README marker and contract assertions failed 5 tests before docs were updated. | Commit `5dde417`; 14 packaging/README tests and isolated wheel smokes passed. |

## Fresh evidence

- `uv run pytest`: 1,398 passed.
- Focused coordination/provider/docs/packaging suite: 191 passed.
- Serial Redis coordination integration: 19 passed.
- Five repetitions of `independent or stale_owner or cancellation`: 5 passed
  per run.
- Benchmark: 64 callers, 8 coordinators, 10 cold bursts, loader count 10;
  `production_capacity_claim=false`.
- `uv run ruff check .`, `uv run ruff format --check .`,
  `uv build --all-packages`, `actionlint`, and `git diff --check`: passed.

The final async matrix includes malformed and oversized artifacts, owner-token
mismatch, loader and cleanup precedence, encode overflow, provider publication
failure, bounded attempts, invalid policy/input, cancellation, and burst
behavior. The initial focused run after `uv sync --all-packages --locked` exposed one
environment-only failure because optional native compressor dependencies were
removed. Re-running from `uv sync --all-packages --all-extras --locked` produced
209/209 passes; no product code was changed to mask that failure.
