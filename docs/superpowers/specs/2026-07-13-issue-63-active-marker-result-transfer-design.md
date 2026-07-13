# Issue #63 Active Marker Result Transfer Design

Date: 2026-07-13
Issue: #63
Work type: Type F - Self Improve
Target branch: `develop`

## Problem

Redis load coordination observes the lease marker and the bounded result prefix
through one fixed Lua script. The current script reads and returns both values
for every snapshot. When the marker is `active:<owner>`, coordinators discard
the result because only a `completed:<owner>` marker may authorize result reuse.
An expired or hostile stale result can therefore be transferred on every active
poll even though it cannot affect the coordinator outcome.

The transfer is already bounded by the encoded-result ceiling, poll ceiling,
and wall deadline. This issue is an efficiency improvement, not a correction of
an unbounded read or an atomicity defect.

## Approved Outcome

Change the shared fixed snapshot script so an observed active marker returns no
result bytes. The operation remains one `EVAL`, the marker and result-state
decision remains atomic inside Redis, and the six-field provider response stays
compatible with the existing parser.

The change is accepted only when a sealed before/after benchmark proves that a
large stale result is transferred during repeated active polling on the
baseline and that the candidate reduces those bytes to zero. Correctness,
single-round-trip behavior, sync/async parity, completed-result reuse, and
failure semantics remain hard gates.

## Goals

- Avoid result-key reads and result-byte transfer when the bounded marker prefix
  begins with `active:`.
- Preserve one atomic snapshot operation and one Redis round trip.
- Preserve bounded result reads for completed, missing, and malformed non-active
  markers.
- Keep the public provider signature, immutable snapshot type, and six-field Lua
  response shape unchanged.
- Prove the same behavior through sync and async providers and coordinators.
- Produce comparable external baseline, candidate, and comparison artifacts.

## Non-Goals

- A second `GET`, client-side retry, or non-atomic fallback.
- Redis L2 caching, lease renewal, fencing, or near-cache invalidation.
- Relaxing marker, owner-token, envelope, result-size, attempt, poll, or deadline
  bounds.
- Production capacity, latency, throughput, or SLO claims.
- A new public API, dependency, distribution, or Redis data migration.

## Current Evidence

- `COORDINATION_SNAPSHOT_SCRIPT` always runs `EXISTS`, `STRLEN`, and `GETRANGE`
  for both the marker key and result key.
- `_coordination_snapshot()` already accepts an absent result triple and maps it
  to `result=None` and `result_oversized=False`.
- Both providers use the same script and parser, so one fixed-script change can
  preserve sync/async parity.
- Both coordinators inspect the result only after parsing a completed marker.
- The issue #65 benchmark already records Redis command counts and result-byte
  metrics, supports paired clean-worktree execution, and rejects incomparable
  reports.
- The current benchmark recorder classifies every returned result as completed;
  fixture preparation must first classify bytes by marker state and make active
  polling deterministic before a valid baseline can be captured.
- After restarting the session-owned Colima runtime and removing its stale test
  container, the untouched base passes the full suite: `1496 passed`.

## Alternatives

### A. Read the marker first and fetch the result with a second command

Rejected. It adds a Redis round trip and permits the marker to change between
the two observations, violating the issue's atomic snapshot requirement.

### B. Add separate active and completed snapshot APIs or scripts

Rejected. The caller cannot safely choose a path before observing the marker,
and two contracts would add branching and drift without reducing one-call
atomic work.

### C. Return every bounded result and discard active bytes in Python

Rejected. This is the current behavior and retains the avoidable network and
client allocation cost that #63 targets.

### D. Branch inside the existing fixed Lua script

Selected. The script reads the bounded marker first. If its prefix is
`active:`, it returns an absent-result sentinel without touching the result key;
otherwise it performs the existing bounded result snapshot. The decision and
all returned state are produced by one script invocation.

## Fixed-Script Contract

The script continues to return exactly:

```text
marker_exists, marker_length, marker_value,
result_exists, result_length, result_value
```

The result sentinel for an active marker is exactly `0, 0, ""`. Redis-py maps
the empty bulk value to `b""`, and the existing parser maps the triple to an
absent, non-oversized result.

The branch is based on the bounded marker bytes already returned to the caller:

```lua
local marker_exists = redis.call('exists', KEYS[1])
local marker_length = redis.call('strlen', KEYS[1])
local marker_value = redis.call('getrange', KEYS[1], 0, ARGV[1] - 1)
if string.sub(marker_value, 1, 7) == 'active:' then
  return {marker_exists, marker_length, marker_value, 0, 0, ''}
end
local result_exists = redis.call('exists', KEYS[2])
local result_length = redis.call('strlen', KEYS[2])
local result_value = redis.call('getrange', KEYS[2], 0, ARGV[2] - 1)
return {marker_exists, marker_length, marker_value, result_exists, result_length, result_value}
```

The implementation uses this logic as the exact fixed script. No caller-owned
script, dynamic command construction, or fallback is introduced.

### State Matrix

| Observed marker prefix | Result-key commands | Returned result triple | Coordinator behavior |
|---|---:|---|---|
| Valid `active:<owner>` | 0 | absent sentinel | Polls without inspecting a result |
| Malformed or oversized `active:` prefix | 0 | absent sentinel | Preserves invalid-artifact failure from marker validation |
| Valid `completed:<owner>` | Existing bounded read | Existing bounded triple | Requires a present, bounded, matching envelope |
| Missing marker | Existing bounded read | Existing bounded triple | Preserves retry/acquire behavior |
| Malformed non-active marker | Existing bounded read | Existing bounded triple | Preserves invalid-artifact failure |

The optimization deliberately keys off `active:` rather than duplicating the
full owner-token parser in Lua. Python remains the authority for exact marker
validation. A malformed active-prefixed marker therefore still fails with the
same stable coordination error; it merely avoids transferring a result that
cannot change that failure.

## Atomicity, Round Trips, And ACL

- The client still sends one `EVAL` and receives one six-element response.
- Marker observation and the decision to omit or snapshot the result occur in
  one Redis script execution, so no client-visible race is introduced.
- Active snapshots intentionally do not require result-key access. Completed
  and non-active paths retain the same result-key commands and bounded sizes.
- Denied `EVAL`, denied marker commands, connection failures, timeouts, and
  malformed Redis responses keep the existing provider error mapping.
- Completed-result command/ACL denial still fails rather than falling back.
- The documented production ACL continues to allow the fixed script and its
  marker/result key prefix; the optimization does not broaden permissions.

## Provider And Coordinator Compatibility

`SyncRedisProvider.coordination_snapshot()` and
`AsyncRedisProvider.coordination_snapshot()` keep their current signatures and
return `RedisCoordinationSnapshot`. For active markers the existing optional
`result` field becomes `None`, which already represents an absent result.
`result_oversized` remains `False` because no result is observed.

The coordinators already parse the marker before using the result. Active
markers continue polling. Completed markers still require a non-oversized,
present result whose envelope owner matches the completion token. Marker
oversize, malformed markers, stale-owner results, attempts, polls, deadlines,
lease loss, cleanup, cancellation, and observer behavior remain unchanged.

## Benchmark Fixture Preparation

Benchmark preparation is committed before the production optimization. That
commit becomes the baseline SHA and is shared unchanged by the candidate.

### Explicit Case Input

Add `stale_result_bytes` to `ScenarioCase` and set it explicitly to zero in
ordinary registry cases. Set it to `65_536` only for the full-profile
`multi-coordinator/high-medium-short` case. Validation requires the value to be
an exact non-negative integer within the encoded-result ceiling and requires at
least two callers and two coordinators when it is non-zero.

The field is included in the canonical registry, report parameters, security
allowlist, stable-vector tests, and comparison identity. This makes the fixture
visible and prevents silent baseline/candidate drift.

Before every correctness, warmup, and measured repetition of that case, the
runner writes a deterministic 65,536-byte stale result at the derived result
key. Fixture setup occurs before the ready/release clock and is excluded from
command metrics. Each phase/repetition already has a distinct namespace, so
the setup cannot leak between samples.

### Deterministic Multiple Polls

The correctness loader for the stale-result case remains bounded but does not
complete until the recorder has observed at least two active snapshots. Sync
uses a condition/event; async uses an event owned by the running loop. Both
paths have a short explicit timeout below the coordinator wall deadline and
fail with a fixed benchmark category if the gate is not reached.

The repository already provides the Awaitility-style
`bluetape.testing.eventually()` and `eventually_async()` helpers. Fixture tests
use those helpers when asserting externally visible convergence. The benchmark
runner itself uses direct condition/event signalling instead of polling so its
own wait loop cannot inflate Redis poll counts or perturb the workload being
measured. No new retry/testing dependency is added.

The recorder tracks:

- `active_snapshot_count` when the marker begins with `active:`;
- active result bytes only when such a snapshot also returned result bytes;
- completed result bytes only when the marker begins with `completed:`.

Add `correctness_active_snapshot_count` to the report metric allowlist and add
the `multiple_active_snapshots` invariant to the selected case. This proves the
baseline and candidate exercised repeated active polling even when the
candidate correctly returns zero result bytes.

Measured runs keep the registry loader delay and stale-result setup but do not
use the correctness gate or recorder. Their timing remains secondary,
environment-qualified evidence.

## Sealed Evaluation Contract

The self-improvement state lives under ignored `.omx/self-improve/`; benchmark
artifacts live outside all Git worktrees. After the fixture preparation commit:

- record the baseline SHA and SHA-256 digests for the benchmark registry,
  scenarios, security policy, benchmark tests, and shared benchmark package;
- validate the sealed paths before every candidate evaluation;
- reject any candidate that changes a sealed path after baseline capture;
- if a fixture defect requires a sealed change, invalidate the baseline,
  recommit the fixture, and capture a new pair from the new SHA.

The baseline worktree is detached at the fixture commit. The candidate remains
on `improve/issue-63-active-marker-transfer`. Both must be clean and use the
same lockfile, Python 3.13.14 environment, Colima/Redis image, runner ID, seed,
profile, mode order, and pair identity.

## Metrics And Stop Conditions

### Primary Metric

For the full-profile paired reports, sum
`correctness_active_result_bytes` across the selected sync and async case.
Lower is better.

- Required baseline: greater than zero.
- Target candidate: exactly zero.
- Minimum improvement: 100%.
- Repetitions for the correctness metric: one deterministic correctness phase
  per mode is sufficient; timing samples do not determine acceptance.

### Correctness Guards

- Baseline and candidate each report at least two active snapshots per mode for
  the stale-result case.
- Registry, dependency lock, policy, environment, runner, seed, case, and mode
  comparison gates are equal and `comparable=true`.
- `correctness_redis_commands` is equal per scenario/mode, proving no added
  client round trip.
- Completed-result bytes remain greater than zero for completed reuse and match
  the existing completed-result invariants.
- Every benchmark invariant is true.
- Targeted mocked and real Redis tests, then the full repository validation,
  pass.

Latency medians and p95 values are recorded but have no regression threshold.
They may be discussed only as observations for this bounded machine and
workload.

### Iteration Budget

- Maximum candidate rounds: 2.
- Stop immediately on the first candidate that reaches zero and passes every
  guard.
- Reject a candidate on non-comparable artifacts, sealed-input drift, a failed
  correctness gate, or a primary metric above zero.
- If round 1 fails for an implementation defect, round 2 may change only
  candidate-allowed files and must use a new pair index/order.
- If no candidate succeeds by round 2, stop without merge and report the
  blocking evidence.

## Test Strategy

### Fixture Tests Before Baseline

- Exact registry membership, totals, new field validation, canonical digest,
  report allowlist, and seed vectors.
- Recorder classification for active, completed, absent, malformed, and
  result-less snapshots.
- Awaitility-style test assertions reuse `bluetape.testing.eventually()` and
  `eventually_async()`; the benchmark runtime contains no assertion polling.
- Sync/async correctness gates prove at least two active snapshots with the
  seeded 65,536-byte stale result.
- Fixture setup is outside timing and command metrics and uses distinct derived
  namespaces.
- Testcontainers-backed smoke for both modes remains serial.

### Candidate Tests

- Exact sync/async `EVAL` invocation remains one call with two keys and two
  bounds.
- Active fixed-script response yields the original marker plus
  `result=None/result_oversized=False`, even when a large stale result exists.
- Completed fixed-script response still returns bounded bytes and oversized
  status.
- Missing and malformed non-active markers preserve existing bounded responses.
- Malformed and oversized active-prefixed markers preserve invalid-artifact
  coordinator failures.
- Stale-owner completed envelopes, deadlines, poll exhaustion, lease loss,
  denied script ACL, cleanup, and async cancellation retain existing behavior.
- Sync and async provider/coordinator behavior remains equivalent.

## Documentation And Evidence

- Update `packages/bluetape-cache-redis/README.md` and `README.ko.md` together to
  state that active snapshots omit result bytes while completed snapshots keep
  bounded result enforcement.
- Update the paired benchmark section with the actual external artifact paths,
  commands, and a compact baseline/candidate correctness table.
- Add a research analysis under `docs/superpowers/research/` with environment,
  SHAs, hashes, primary metric, guards, timing observations, and limitations.
- Update `CHANGELOG.md` with the active-marker transfer optimization.
- Do not check in raw external full-profile artifacts if they contain bulky
  samples; record their SHA-256 digests and the reproducible command instead.

No diagram or chart is required because the acceptance result is a small exact
correctness table, not a trend or capacity study.

## Rollout And Rollback

The wire marker and result formats do not change. Mixed old/new participants
remain compatible: old participants may still receive unused active result
bytes, while new participants omit them; all continue to read completed results
and publish the same artifacts.

Rollback restores the previous fixed script. No key migration or data cleanup
is required. Existing TTL bounds retire all coordination artifacts normally.

## Definition Of Done

- The fixture-preparation commit is sealed and its untouched production script
  produces a baseline with active result bytes greater than zero.
- The candidate produces exactly zero active result bytes with repeated active
  snapshots in both modes.
- One atomic EVAL, six response fields, completed-result reuse, sync/async
  parity, bounds, and stable failure behavior are preserved.
- Targeted unit/integration tests and serial real Redis tests pass.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv build --all-packages`, isolated import/metadata smoke, `actionlint`, and
  `git diff --check` pass.
- Workflow review and live PR review converge at P0=0 and P1=0.
- Required GitHub CI succeeds before merge.
- The PR is merged with GitHub rebase merge.
- Local `develop` is synchronized and the issue worktree plus merged local and
  remote feature branches are removed.
