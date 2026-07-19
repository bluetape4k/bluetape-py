# Issue #17 leader lock verifier map

Date: 2026-07-19 KST
Pre-evidence implementation head: `2f6cf37657ea86ee148e87ac023d91eb9a7e51e4`

Status: **READY FOR EXACT-HEAD VERIFICATION**. This file maps the approved
criteria but does not pre-claim the independent verifier verdict.

## Acceptance criterion map

| Criterion | Source evidence | Executable evidence | Pre-head status |
|---|---|---|---|
| Backend-neutral core supports varied repositories | `bluetape.leader` protocols, values, results and errors contain no Redis imports | exact exports/signatures, stdlib-only import and focused-wheel tests | Mapped |
| Redis is a separate opt-in adapter | separate distribution metadata and namespace package | focused/meta/default isolated wheel and metadata tests | Mapped |
| Exact sync/async API parity | lock, lease and elector protocols plus four Redis exports | exact signature/export and paired behavior matrices | Mapped |
| Ownership is secure and value-safe | 192-bit owner tokens, fixed Lua, bound arguments, hashed logical keys, fixed public errors | hostile records, redaction scans, spoof rejection and uncertain-operation reconciliation | Mapped |
| Fencing is monotonic and downstream-enforced | Redis counter scripts and `FencedLeaderLease` | 16-by-10 contention, strict generations, atomic stale-write rejection, overflow fail-close | Mapped |
| Timing and retries are bounded | measured client timing, zero-retry validation, effective millisecond TTL gate | stalled-stage timing, retry-count, sync/async pre-I/O boundary and derived-interval tests | Mapped |
| Lifecycle cleanup is owned | sync thread state machine and async structured tasks | repeated cancellation/process-control matrices, thread/task baselines, borrowed-client usability | Mapped |
| Minimal ACL matches documentation | exact command/key allowlist, no `SCRIPT LOAD` or unconditional `CLIENT SETINFO` | 48 protocol/auth/db/client-name ACL combinations and negative command/key checks | Mapped |
| Topology and migration fail closed | single-primary contract, ordered stop-the-world migration, loss/rollback runbooks | documentation scenario tests and real loss/takeover/corruption integration tests | Mapped |
| Counter exhaustion cannot reuse ordering | signed integer ceiling and compound epoch guidance | sync/async overflow integration plus bilingual deployment checklist assertions | Mapped |
| CI cannot silently skip Redis evidence | dedicated serialized `leader-redis` job | actionlint and JUnit nonempty/zero-failure/error/skip assertion | Mapped |
| User guidance is executable and bilingual | EN/KO core and adapter READMEs with 13 stable scenario IDs | identical snippets, runtime manual-failure tests and cross-document status tests | Mapped |
| Review and lesson gates are durable | TDD, performance/stability, code-review and lesson artifacts | six lenses converged to P0=0/P1=0; independent verifier remains final gate | Pending exact-head replay |

## Final verifier requirements

- Candidate SHA equals `git rev-parse HEAD` before and after all commands.
- Worktree is clean.
- `uv sync --all-packages --all-extras --python 3.13.14 --locked` succeeds.
- `uv run pytest`, Ruff lint, Ruff format check, all-package build,
  `actionlint`, lock check and `git diff --check` pass.
- The prior full-suite Redis startup flake is not hidden; rerun evidence and the
  final canonical outcome are recorded explicitly.
- All six independent lenses report P0=0 and P1=0 at the corrected surface.
- No PR, merge, release, publication or cleanup claim is folded into local
  verification.

PR creation, CI review, merge and release remain separate workflow gates.
