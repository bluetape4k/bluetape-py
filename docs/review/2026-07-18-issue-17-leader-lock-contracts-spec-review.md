# Issue #17 Leader Election and Distributed Lock Specification Review

Date: 2026-07-18 KST
Issue: #17 - `feat: add leader election and distributed lock contracts`
Artifact:
`docs/superpowers/specs/2026-07-18-issue-17-leader-lock-contracts-design.md`

## Review Scope

Six independent read-only perspectives reviewed the committed design before
implementation planning. Reviewers had no edit, commit, GitHub mutation,
build, or test authority. The main session normalized findings, repaired the
specification, and reran every affected lens until P0/P1 convergence.

| Perspective | Role surface | Initial result | Final result |
|---|---|---:|---:|
| Performance | `code-reviewer` | P0=0, P1=4 | P0=0, P1=0 |
| Stability/reliability | `verifier` | P0=0, P1=6 | P0=0, P1=0 |
| Security/privacy | `code-reviewer` | P0=0, P1=5 | P0=0, P1=0 |
| Operator/Ops | `verifier` | P0=0, P1=3 | P0=0, P1=0 |
| Developer/public API | `code-reviewer` | P0=0, P1=6 | P0=0, P1=0 |
| User/caller | `writer` | P0=0, P1=4 | P0=0, P1=0 |

Final independent verdict: **P0=0, P1=0 across all six perspectives**.
Final performance, security, Ops, developer/API, and user reruns also reported
P2=0 and P3=0. Stability's final rerun reported no remaining lower-severity
finding.

## Material Repairs

### Backend-neutral core and typed fencing capability

The initial draft leaked Redis millisecond resolution into core options and
typed generic results as base `LeaderLease`, hiding Redis fencing from static
type checkers. The repaired contract:

- validates only backend-neutral `timedelta` relationships in core;
- applies millisecond conversion at the Redis adapter boundary;
- carries `LeaseT` through results, lock handles, distributed locks, sync
  electors, and async electors;
- fixes concrete Redis types to `FencedLeaderLease`;
- keeps physical `node_id`, audit identity, secret owner token, and integer
  fencing token semantically separate.

### Bounded Redis execution and lifecycle ownership

The initial timeout rule omitted script fallback, reconciliation, pool waits,
retries, DNS, health checks, callbacks, and cold reconnect handshakes. The
repaired contract defines exact supported redis-py client configuration and
rejects unprovable execution paths:

- exact pinned sync/async client types only;
- zero command retries, zero health-check interval, finite pool/connect/socket
  timeouts, no dynamic credential providers or command callbacks;
- numeric IP or Unix-domain endpoints only;
- TLS rejected in the first slice because redis-py does not expose a hard
  whole-handshake deadline;
- `H` handshake round trips, `E` connection, `P` primitive command, `S` script,
  `A` acquire, `N` renew, and `R` release envelopes;
- fixed 40-60ms contention jitter, no post-deadline dispatch, and quantified
  command ceilings;
- non-daemon sync renew workers and retained async tasks that are stopped,
  cancelled once at deadline, and awaited to terminal state before return.

### Ownership, uncertainty, and terminal state

The repaired Redis record and scripts now:

- distinguish valid positive-TTL contention from wrong type, malformed value,
  missing TTL, and counter corruption;
- recover a response-lost acquire by strict record parsing plus constant-time
  owner-token comparison, then recover the server-issued fencing token;
- never redispatch an uncertain acquire script;
- classify release as delete, minimum-TTL application, not-held, or corruption;
- repeat an uncertain same-owner release at most once and fail closed if proof
  remains unavailable;
- preserve fencing integers as canonical decimal strings across the Lua
  floating-point precision boundary.

The active handle state machine now includes `ACQUIRED`, `ENTERED`, `LOST`,
`RELEASED`, and `UNKNOWN`. First context entry proves current ownership before
caller code runs. Terminal uncertainty never reports false success and permits
no new I/O beyond the operation's single owned reconciliation.

### Failure and cancellation semantics

The initial draft did not resolve action failure combined with lease loss or
cleanup failure, and it overstated what `asyncio.shield` guarantees. The
repaired specification provides:

- a complete action × renewal × release × cancellation outcome table;
- a separate manual context-manager precedence table;
- redacted `LeaderExecutionError` for action plus lifecycle failure;
- sanitized `LeaderBackendError` raised `from None` with no raw redis-py cause
  retained in renewal or composite lifecycle values;
- retained, bounded, re-awaited async renew and cleanup tasks;
- original cancellation/process-control propagation only after owned cleanup
  reaches a terminal state;
- explicit acknowledgement that elector actions receive a snapshot, cannot be
  force-stopped on lease loss, and must use atomic downstream fencing.

### Security and operational honesty

The repaired design bounds names and prefixes, fixes one script execution path,
defines minimum ACL commands, redacts all capability and connection material,
and requires downstream high-watermark comparison plus business write in one
atomic operation. Fencing monotonicity is conditioned on an authoritative
counter that has not been deleted, decreased, or restored from an older
snapshot.

Coordination identity migration is stop-the-world rather than rolling. The
operator contract covers standalone-primary topology, restore/high-watermark
safety, safe signals, lease-loss response, and first-slice TLS/network limits.

### Executable caller guidance

The design now includes normative sync and async manual-lock examples with an
explicit contention guard, precise elector-result handling, cancellation
behavior, atomic fencing requirements, delayed-entry ownership proof, and
English/Korean README coverage. An undefined preflight API was removed from
scope in favor of caller-owned deployment tooling.

## Main-Session Integration Checks

| Check | Evidence | Result |
|---|---|---|
| Issue boundary | Live issue #17 remains open in milestone `0.2.0`; single Redis proof and backend-neutral contracts only | PASS |
| Sibling structure | `bluetape4k-leader` core/backend split and lifecycle types are explicitly mapped without mechanical porting | PASS |
| Package boundary | stdlib-only `bluetape-leader`; focused `bluetape-leader-redis`; no cache/serde/compression dependency | PASS |
| Public typing | `LeaseT` capability reaches results, handles, electors, and concrete Redis fencing APIs | PASS |
| Atomicity | acquire, renew, release, corruption, fencing, uncertainty, and NOSCRIPT behavior are specified | PASS |
| Lifecycle | sync worker, async task, entry proof, cancellation, release, and terminal uncertainty are bounded | PASS |
| Security | secret owner values, raw Redis errors, names, keys, clients, prefixes, credentials, and tracebacks are redacted | PASS |
| Operations | topology, timing envelopes, ACL, migration, rollback, restore, and fencing caveats are explicit | PASS |
| Testability | deterministic fake seams, quantitative contention/resource gates, Testcontainers cases, docs, and packaging are specified | PASS |
| Baseline honesty | pre-existing full-suite Redis benchmark failure is isolated and not claimed as an Issue #17 regression | PASS |
| Placeholders | no unresolved implementation choice, TODO, FIXME, or open design decision | PASS |
| Diff hygiene | `git diff --check` | PASS |

## Remaining Non-Blocking Risks

- The first adapter is intentionally single-primary and does not provide
  failover-safe consensus or Redlock.
- TLS is excluded from the first slice to keep reconnect and worker shutdown
  strictly bounded; protected networking or Unix-domain sockets are required.
- Synchronous auto-renew costs one non-daemon thread per active renewed lease.
- A stale action can continue after lease loss; downstream atomic fencing is
  mandatory for side-effect safety.
- Fence safety still depends on Redis counter persistence and downstream
  high-watermark preservation across backup, restore, and migration.
- The pre-existing full-suite Redis benchmark startup failure remains a known
  baseline exception outside this design change.

## Post-Approval Step 3-R Clarifications

Implementation-plan review preserved the approved package/API boundary and
made five safety rules executable:

- non-auto-renew entry uses an atomic `TYPE`/`GET`/`PTTL` probe script so a
  no-expiry record cannot authorize the context body;
- an in-flight async Redis operation is cancelled once at `N/R` and must reach
  terminal state by `N/R + 100ms`, proven against the pinned redis-py path; and
- response-loss reconciliation atomically validates type, value, and positive
  expiry in one fixed read-only `EVAL`, then compares the private owner in
  Python;
- missing or different-owner acquire reconciliation raises sanitized
  `LeaderBackendError`; only an explicit acquire-script `CONTENDED` status is
  normal contention; and
- `LeaderBackendError` remains deliberately non-diagnostic, with suspected
  condition recovery delegated to caller-owned Redis evidence.

The six-lens implementation-plan review and reruns converged at P0=0/P1=0.
Detailed evidence is recorded in
`docs/review/2026-07-18-issue-17-leader-lock-contracts-plan-review.md`.

## Original Specification Gate Result

The written specification is internally converged and ready for user review.
Implementation planning and production-code edits remain blocked until the
user approves the revised committed specification.
