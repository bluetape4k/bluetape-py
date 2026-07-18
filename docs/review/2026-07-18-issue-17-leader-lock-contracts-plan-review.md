# Issue #17 Leader Election and Distributed Lock Implementation Plan Review

Date: 2026-07-18 KST
Issue: #17 - `feat: add leader election and distributed lock contracts`
Plan:
`docs/superpowers/plans/2026-07-18-issue-17-leader-lock-contracts-implementation-plan.md`
Specification:
`docs/superpowers/specs/2026-07-18-issue-17-leader-lock-contracts-design.md`

## Review Scope

Six independent read-only perspectives reviewed the committed implementation
plan against the approved specification and the Step 3-R rubric. Reviewers had
no edit, implementation, commit, push, PR, workflow-dispatch, or merge
authority. The main session integrated findings and reran every affected lens
against the live corrected artifacts until no P0/P1 remained.

| Perspective | Initial findings | Additional recheck blockers | Final result |
|---|---:|---:|---:|
| Performance | P0=0, P1=3, P2=2 | P1=1 | P0=0, P1=0 |
| Security/privacy | P0=0, P1=4, P2=4 | P1=1 | P0=0, P1=0 |
| Developer/public API | P0=0, P1=6, P2=3 | P1=1 | P0=0, P1=0 |
| Operator/Ops | P0=0, P1=2, P2=3, P3=1 | none | P0=0, P1=0 |
| Stability/fault injection | P0=0, P1=2, P2=4 | P1=4 | P0=0, P1=0 |
| User/caller | P0=0, P1=3, P2=4 | P1=1 | P0=0, P1=0 |

Final independent verdict: **P0=0 and P1=0 across all six perspectives**.
All reported P2/P3 items were integrated rather than deferred.

## Material Plan Repairs

### Exact public API and package boundary

- Corrected the core export count from 25 to the exact ordered 24-symbol list.
- Added exact sync/async protocol exit types and all four concrete Redis
  constructor signatures.
- Moved every exact built-in type guard before caller-controlled comparison or
  truthiness.
- Fixed elector snapshots to use the post-entry lease that the action receives.
- Added exact wheel, meta-extra, default-install, namespace, publish-classifier,
  and constructor-signature proofs.

### Executable TDD sequencing

Tasks 4 through 6 no longer batch behavior tests before implementation. They
prepare only fixtures and coverage inventories, then require one active-row
test, witnessed intended RED, minimum GREEN, owning-file regression, and no
later-row test authorship before the active row is GREEN. Separate rows cover
client validation, keys, records, timing, each Lua operation, uncertainty,
state transitions, worker/task lifecycle, cancellation, and failure precedence.

### Redis scripts, probes, and uncertainty

- Added an atomic read-only probe over `TYPE`, `GET`, and `PTTL`; malformed or
  no-expiry records cannot pass first context entry.
- Fixed renew/release TTL classification: missing/expired is `NOT_HELD`, while
  wrong type, malformed record, and missing expiry are corruption.
- Specified response-loss tables for acquire, renew, and release, including
  `EVALSHA`, NOSCRIPT fallback `EVAL`, reconciliation failure, and exact command
  traces.
- Response-loss reconciliation uses one fixed read-only `EVAL` over
  `TYPE`/`GET`/`PTTL`; matching ownership is recovered only with positive TTL.
  Missing or different ownership raises sanitized `LeaderBackendError`, and
  only an explicit acquire-script `CONTENDED` status is contention/`Skipped`.
- Missing uncertain-release reconciliation remains `UNKNOWN`; no path guesses
  natural expiry or issues unconditional delete.
- The uncertain-release table enumerates the one permitted same-owner repeat's
  success, `NOT_HELD`, corruption/backend failure, and second response loss,
  plus direct-versus-scoped exception types for every reconciliation result.

### Bounded sync and asyncio lifecycle

- Enumerated and stalled every supported pinned redis-py handshake shape to
  prove `H/E/P/S/A/N/R`, reconnect, and cancellation bounds.
- Replaced relative async timeout reuse with one absolute deadline, retained
  task identity, lifecycle-owner cancellation origin, one owned cancel, and
  terminal completion by `N/R + 100ms`.
- Added the same-event-loop-turn owner/owned-task cancellation race and exact
  original `CancelledError` propagation.
- Split sync worker start failure, unexpected crash, and join-deadline violation
  into separate fault-injection rows; stuck fixtures always unblock/join in
  `finally`, never race release, and enter terminal `UNKNOWN`.
- Added every state x operation, concurrent-entry, re-entry, terminal no-I/O,
  and direct process-control matrix for sync and async.

### Real Redis evidence and hang containment

- Replaced ambiguous 16x10 contention with a prewarmed, barrier-started,
  `wait_time=0` generation: the winner holds until all 15 losers return.
- Uses caller-owned `INFO commandstats`, not MONITOR, so command arguments and
  owner tokens are never observed or logged.
- Adds readiness deadlines, concrete long-action timing, stale-owner takeover,
  ACL, counter rollback, downstream high-watermark, and resource-baseline proof.
- Every real scenario has an outer deadline and unconditional resource cleanup.
- Hang-sensitive sync scenarios run in a spawned child process. The parent
  requires one fixed secret-free `ChildResult`, zero exit code, expected public
  outcome, exact action/fencing relation, lease cleanup, zero resource deltas,
  and usable borrowed client; abnormal exit or timeout is fatal after cleanup.

### Security, operations, CI, and documentation

- Real backend-conversion tests scan args, cause, context, notes, representation,
  and formatted traceback; raw Redis canaries never survive into public errors.
- Owner entropy is one private `token_urlsafe(24)` value per public acquisition
  call, retained only for its retries/reconciliation and absent from public
  state.
- Hostname, TLS, URL-derived/custom pools, callbacks, providers, subclasses,
  proxies, and wrong client families fail before DNS, callback, connect, or I/O.
- ACL tests cover adapter commands, conditional witnessed handshake commands,
  key-prefix restriction, and negative `SCRIPT LOAD`/unrelated-command proofs.
- Adds a dedicated required `leader-redis` job to the existing `ci.yml`; unit
  and serial Testcontainers tests must collect nonzero cases with zero skips.
- Records nightly and coverage aggregation as evidence-backed `N/A` because the
  repository has neither contract, while full Redis integration runs on every
  PR/push.
- EN/KO scenario parity now covers precise-None ambiguity, manual versus scoped
  lifecycle, async cancellation, identity roles, atomic fencing, non-diagnostic
  backend errors, topology, safe signals, ACLs, ordered migration/restore,
  lease loss, rollback, operator actions, and deployment checks.

## Step 3-R Required Checks

| Check | Evidence in corrected plan | Result |
|---|---|---|
| Every spec/DoD item maps to a task | Spec coverage table plus final DoD | PASS |
| Implementable ordering | Tasks 1-10 and explicit dependencies | PASS |
| No later-task dependency | Package/core -> Redis substrate -> lifecycle -> integration -> docs/CI -> review | PASS |
| Complete test paths | Success, failure, edge, contention, coroutine, lifecycle, fault, backend capability | PASS |
| Concrete verification | Focused selectors, owning files, full commands, JUnit no-skip proof | PASS |
| Bilingual public docs | Stable EN/KO scenario IDs and semantic parity | PASS |
| Contributor/release artifacts | README pairs, WIP, CHANGELOG, release preflight, CI | PASS |
| Publish/settings/CI registration | Workspace/meta/classifier/lock plus dedicated CI job | PASS |
| Cancellation boundaries | Absolute deadlines, retained tasks, exact cancellation identity | PASS |
| Performance/stability | Timing stalls, quantitative contention, subprocess hang isolation, cleanup baselines | PASS |
| Duplication decision | Shared core contracts/scripts; sync/async lifecycle remains intentionally separate | PASS |
| Resource ownership | Borrowed clients, child tasks/threads, fixtures, ACL users, executors all closed by owner | PASS |
| Migration/rollback | Stop-the-world identity and high-watermark sequence plus safe rollback | PASS |
| Baseline honesty | Known unrelated Redis benchmark startup failure remains separately reported | PASS |

## Specification Clarifications Discovered During Planning

Step 3-R exposed five safety details that the public design intent required but
the approved prose did not make executable:

1. non-auto-renew context entry uses an atomic probe script, not a value-only
   GET, so a canonical record without expiry fails closed;
2. pending async Redis operations are cancelled at their `N/R` envelope and
   must become terminal by `N/R + 100ms`; and
3. acquire/release response-loss reconciliation atomically validates
   `TYPE`/`GET`/positive `PTTL` in one fixed read-only `EVAL`, then performs the
   private owner comparison in Python;
4. an absent or different-owner record after acquire response loss is a backend
   failure, not contention; only the acquire script proves `CONTENDED`; and
5. `LeaderBackendError` remains deliberately non-diagnostic, so condition-
   specific recovery relies on caller-owned Redis evidence rather than unsafe
   raw causes or guessed public fields.

These corrections change no distribution, dependency, public symbol,
constructor, or topology boundary. They narrow unsafe interpretations and are
reflected in the specification and plan.

## Gate Result

The implementation plan is internally converged at P0=0/P1=0 and is ready for
the implementation execution gate. No production package code, workflow edit,
push, PR, merge, release, publication, issue closure, or cleanup was performed
during planning.
