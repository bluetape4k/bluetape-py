# Step 3-R Plan Review - Issue #7 Collections

Date: 2026-07-10 KST
Scope:

- `docs/superpowers/specs/2026-07-10-issue-7-collections-design.md`
- `docs/superpowers/plans/2026-07-10-issue-7-collections-plan.md`

## Initial Independent Lane Results

| Lane | P0 | P1 | P2 | P3 | Gate |
|---|---:|---:|---:|---:|---|
| Performance | 0 | 1 | 1 | 0 | FAIL |
| Stability | 0 | 0 | 2 | 0 | FAIL |
| Security | 0 | 0 | 0 | 0 | PASS |
| Operator | 0 | 0 | 4 | 2 | PASS |
| Developer/API | 0 | 1 | 3 | 1 | FAIL |
| Performance rerun | 0 | 0 | 0 | 0 | PASS |
| Developer/API rerun | 0 | 0 | 0 | 1 | PASS |
| User/caller | 0 | 2 | 2 | 0 | FAIL |
| User/caller rerun | 0 | 0 | 0 | 0 | PASS |

## Required Plan Edits Applied

- Added a single-pass/no-full-input-pre-materialization invariant.
- Added a stdlib stress/allocation smoke requirement.
- Moved `uv sync --all-packages` before import/build smoke checks and added
  lockfile verification.
- Added isolated built-wheel import and default-meta smoke checks.
- Made `bluetape` optional-extra wiring explicit for `collections`, `dev`,
  `all`, and `[tool.uv.sources]`.
- Fixed new package metadata requirements to match focused package conventions.
- Added precise failure-contract tests for invalid size, callable arguments,
  unhashable distinct values/keys, and exception propagation.
- Added Python 3.13 typing/signature conventions.
- Recorded publish hold, release non-goals, CI mergeability checks, and
  rollback notes.
- Added install wording constraints so README files do not imply current PyPI
  availability while publishing remains on HOLD.
- Added package README requirements explaining `map_or_raise` /
  `filter_or_raise`, unsupported capabilities, and sibling compatibility notes.

## Integration Status

P0/P1 after applied edits and reruns: 0.

Step 3-R plan gate: PASS

## Follow-Up Verification Obligations

- Run the stdlib `timeit`/`tracemalloc` stress/allocation smoke and preserve
  size, elapsed time, peak memory, and pass/fail evidence.
- Verify README files do not imply current PyPI availability while publishing
  remains on HOLD.
- Verify `map_or_raise` / `filter_or_raise` docs explain eager container
  returns, no exception wrapping, and native Python alternatives.
- Verify package metadata keeps the default `bluetape` dependency list at
  `["bluetape-core==0.1.0"]`.
