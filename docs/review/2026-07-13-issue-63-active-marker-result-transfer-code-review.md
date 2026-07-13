# Issue #63 Active-Marker Result Transfer Pre-PR Code Review

Review base: `349ef1417a16d7394bc261b685b489caf4a6bf83`  
Final code benchmark checkpoint: `984c49ad7b701f9e1c17a3176c4ea8fd8f2a1252`  
Verified documentation checkpoint: `cda8b80f21f039f8bc8bd6fee1225cac817af72c`

## Findings and convergence

| Priority | Lens | Finding | Resolution |
|---|---|---|---|
| P1 | Developer/API | The first Lua branch recognized `active:` only from the caller-bounded marker value. With `max_marker_size < 7`, it returned the stale result prefix. | Added a minimum seven-byte internal marker probe while still returning only the caller-bound prefix. Sync and async real Redis tests reproduce the six-byte boundary and pass after the fix. |
| P1 | Performance/stability | The first acceptance rule required raw command equality even though concurrent active polling changes snapshot counts between identical runs. | A same-SHA baseline rerun proved the variance. The approved rule now subtracts recorded active snapshots for `multi-coordinator` only; all other scenarios retain raw parity, and provider tests lock one `EVAL` per snapshot. |
| P2 | Performance | A single baseline-first pair showed slower candidate medians. | Documented as observational only. The accepted claim is the measured 100% removal of ignored active result bytes, not latency or capacity improvement. |

Final unresolved findings: P0=0, P1=0, P2=0, P3=0.

## Six-perspective result

| Lens | P0 | P1 | Evidence | Verdict |
|---|---:|---:|---|---|
| Performance | 0 | 0 | Active result bytes `3,407,872 -> 0`; stable command shape; no extra round trip | PASS |
| Stability | 0 | 0 | Deterministic active-snapshot and unrelated-key overlap gates; 1,515 full tests | PASS |
| Security | 0 | 0 | Fixed Lua only; existing keys, TTLs, redaction, binary bounds, and `EVAL` ACL remain unchanged | PASS |
| Operator/Ops | 0 | 0 | No deployment/configuration change; Colima resources cleaned; all-package build and actionlint pass | PASS |
| Developer/API | 0 | 0 | No signature or exported-type change; six-byte marker boundary and completed-result behavior locked | PASS |
| User/caller | 0 | 0 | Active snapshots expose `result=None`; completed and missing markers preserve bounded result reuse | PASS |

## Benchmark evidence

- Pair `issue-63-pair-000`, full sync/async, seed `20260713`, same Colima runner.
- Generic comparison: comparable, no reasons, distinct clean source SHAs.
- Baseline/candidate active result bytes: `3,407,872 / 0`.
- Candidate sync/async active snapshots: `25 / 24`, each above the required two.
- Snapshot-normalized command parity and raw parity for all other scenarios: passed.
- Four completed-reuse result-byte guards and every scenario invariant: passed.
- Final candidate/comparison SHA-256: `c57f3a2d34a68845854c37835eee07443d3762c3c8b4f93340b02296db74d39b` / `8e287e32e8cd793b59b4b0cc547724d7990476ff63138cd3a77b04c7a4f81861`.

## Verification

- `uv sync --all-packages --all-extras --python 3.13.14 --locked`: passed.
- `uv run pytest`: 1,515 passed, including all real Redis and benchmark integration tests.
- Boundary RED/GREEN: sync and async six-byte active marker tests failed with 64 stale bytes before the fix and passed with no result afterward.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 91 files already formatted.
- `uv build --all-packages`: all 13 workspace distributions built.
- `actionlint`, `git diff --check`, and sealed-file validation: passed.
- Docker containers after verification: none.

The Inline pre-PR gate is converged at P0=0 and P1=0. GitHub checks and fresh
review-thread state must still pass before rebase merge.
