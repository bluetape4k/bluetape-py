# Issue #17 leader lock verifier map

Date: 2026-07-19 KST
Pre-evidence implementation head: `2f6cf37657ea86ee148e87ac023d91eb9a7e51e4`

Status: **PASS** at independently verified candidate head
`56752afd3578541c8a86d2be7e41e53703381cc4`.

Final severity count: **P0=0, P1=0, P2=0, P3=0**. The verifier started and
finished at the same clean head with no blocker.

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
| Review and lesson gates are durable | TDD, performance/stability, code-review and lesson artifacts | six lenses converged to P0=0/P1=0; independent verifier passed with P0-P3 all zero | Passed |

## Independent verifier evidence

- `uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked`
  passed.
- The independent public API and packaging set passed `130` tests.
- The canonical suite passed `3249` tests with one unrelated testcontainers
  deprecation warning.
- The first canonical attempt exposed one transient existing cache-redis Redis
  container startup failure. Its isolated rerun passed, the affected package
  had no feature-branch diff, and the complete canonical rerun passed all
  `3249` tests.
- `uv run ruff check .`, `uv run ruff format --check .`, `actionlint`,
  `uv lock --check`, and `git diff --check` passed.
- `uv build --all-packages` produced all `21` wheels and all `21` source
  distributions; the verifier checked archive integrity.
- All `62` feature commits passed `git interpret-trailers --parse`, with zero
  literal backslash-n sequences and zero missing mandatory Lore trailers.
- All `33` commit references and `10` task ranges in the four SHA-bound review
  artifacts are reachable and match the rewritten commit subjects and order.
- The approved design, spec-review, plan and plan-review hashes still match the
  TDD ledger.

This verdict covers the implementation and pre-verdict evidence tree at the
candidate head above. The commit that records this verdict is an evidence-only
administrative delta and receives a final clean-head, trailer and diff refresh
after commit.

PR creation, CI review, merge and release remain separate workflow gates.
