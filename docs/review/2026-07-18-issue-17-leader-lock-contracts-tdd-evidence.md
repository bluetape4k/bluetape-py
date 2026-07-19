# Issue #17 leader lock contracts TDD evidence

Date: 2026-07-19 KST
Issue: #17, milestone `0.2.0`
Pre-evidence implementation head: `2f6cf37657ea86ee148e87ac023d91eb9a7e51e4`
Approved base: `48b1dbc291a3a00606654f3c1c46bffbeed1361e`

This ledger records witnessed RED/GREEN work before the evidence commit. It
does not claim that the later immutable-head verifier has passed.

## Approved inputs

- Design SHA-256:
  `7b83444388305a2dd2a705042778c73538495b2030e2c306cb2356ba5f4c6e65`
- Design review SHA-256:
  `169b65f8db94beadf5f2bbfc93809f6a0b406a3365a31198a1a114339cb6fb4e`
- Implementation plan SHA-256:
  `00b6e1266180a0fa7d9440a10db285cfb4c24501cdb10cdbacc2a47ec1107ee5`
- Plan review SHA-256:
  `09a56ec9b4eb2b9d42d0334409506704d5ade8ab39b2807dc9ab9f9e8c7c3d5f`

## Captured RED to GREEN transitions

| Task | Witnessed RED | GREEN convergence | Commits |
|---|---|---|---|
| 1. Separate distributions and sanitized errors | Metadata, namespace, exact exports, and fixed-message error selectors failed because both distributions and their public errors were absent | Registration, formatting, fixed messages, copy/pickle and redaction contracts passed | `87bb03d`, `5b913a4`, `67cc679` |
| 2. Options and lease values | Validation selectors failed on missing options/lease types, identity/fencing ambiguity, and unusable derived renewal intervals | Frozen/slotted values, exact built-in validation, caller-value preservation, separate operator identity and fencing capability passed | `26db9fc`, `648b705`, `a006b1d` |
| 3. Results and protocols | Result/protocol selectors failed on missing precise outcomes and accepted spoofed boundary values | Exact result unions, sync/async generic protocols, redacted representations, and strict instance validation passed | `24a5640`, `6d7ee2f` |
| 4. Redis substrate | Ordered 4A-4N selectors failed one behavior family at a time: key/record validation, Lua fallback, client shape, timing, retries, mapping keys, RESP2 AUTH and RESP3 handshake bounds | Fixed scripts, hashed key identity, hostile record rejection, zero retry, exact client/pool validation, bounded command stages, and one-shot reconciliation passed | `596a864` through `33bc453` |
| 5. Sync lock | Ordered sync selectors failed before manual state, scoped entry proof, renewal worker, late failure, terminal-state and lock/I/O separation behavior existed | Manual/scoped lifecycle, one non-daemon worker per held auto-renew lease, owned cleanup, fail-closed terminal states, and no I/O under local state guards passed | `f5e7f25` through `9fd7807` |
| 6. Async lock | Ordered async and cancellation matrices failed on missing parity, detached-task boundaries, repeated cancellation, process-control precedence, worker-start cleanup and retained UNKNOWN failures | Async 69, sync+async 199, full Redis 627; the 21-case lifecycle repair set passed 20 repetitions and the final independent closure gate reported P0=0/P1=0/P2=0 | `909ca9e` through `5c639eb` |
| 7. Electors | `24` expected failures covered missing sync/async electors and result/failure-precedence matrices | `28` initial passes, then `44` after callback-suppression and concrete lifecycle-matrix hardening; full Redis reached `666 passed` | `95cfc4b`, `d352317` |
| 8. Real Redis | Integration selectors failed on absent real-server fixtures, contention/fencing proofs, ACL shape coverage, loss cleanup and exact resource baselines | Final gate: 48 ACL cases and 73 sync/async Redis cases passed; 16 contenders across 10 generations proved one winner, strictly increasing fences, exact commandstats and leak freedom | `e28c819` through `cb5b7aa` |
| 9. Packaging, CI and bilingual docs | `14 collected`: `5 passed`, `9 failed` for missing README scenarios, examples, status and operational guidance | Dedicated serial `leader-redis` CI job, isolated wheel/meta/default contracts, 13 stable bilingual scenarios and executable examples passed; workspace collection collision was repaired | `d586506`, `6b64639`, `810f67d`, `9db6804` |
| 10. Review corrections | Five lifecycle/timing regressions produced four intended failures and one bounded-retry pass; effective-TTL sync/async regressions produced `2 failed`; composite/manual README runtime regressions produced `2 failed`; final caller signature/lifecycle guidance produced `4 failed` | Lifecycle corrections: `5 passed`, lock suites `204 passed`; effective TTL and minimal ACL: adapter `753 passed`; composite/manual docs: core `113 passed`; caller-facing API/docs: `4 passed`, then core+adapter `867 passed` | `9bd104c`, `077f083`, `91e8ee4`, `8c9fc98`, `c285752`, `8167fa9`, `1451f7f`, `79da572`, `2f6cf37` |

Only observed missing-surface or wrong-behavior failures are called RED. Review
findings were first reproduced as focused regressions where executable behavior
was involved; documentation-only operator gaps were repaired with existing
bilingual README contract tests.

## Pre-evidence validation convergence

- `uv run pytest packages/bluetape-leader-redis/tests -q`: `753 passed`.
- `uv run pytest packages/bluetape-leader/tests -q`: `113 passed`.
- Final combined core and adapter replay after the keyword-only constructor and
  lifecycle examples: `867 passed`.
- First clean full-workspace replay: `3245 passed, 1 failed`; the sole failure
  was existing cache-redis benchmark infrastructure startup
  `BTBENCH_REDIS_FAILED`.
- Immediate isolated rerun of that exact benchmark test on the clean same head:
  `1 passed` in 2.08 seconds.
- Focused Ruff lint, Ruff format checks, `actionlint`, all-package builds, lock
  checks and `git diff --check` passed during their owning tasks.
- Coverage aggregation is N/A: this repository has no coverage plugin or
  report-combination contract to extend.
- Nightly Redis execution is N/A: no scheduled workflow exists; the dedicated
  `leader-redis` job is required on every configured push and pull request and
  rejects zero tests, failures, errors, or skips from its JUnit evidence.

Fresh canonical replay at the final evidence head remains the verifier gate.
