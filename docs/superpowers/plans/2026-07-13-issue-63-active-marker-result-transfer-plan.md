# Issue #63 Active Marker Result Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove and ship a one-EVAL Redis snapshot optimization that transfers zero result bytes for active markers while preserving completed-result and failure semantics.

**Architecture:** First commit and seal a deterministic stale-result benchmark fixture while the production Lua script is unchanged. Capture a clean detached baseline, implement one conditional branch in the shared fixed script inside an isolated candidate worktree, then accept it only if paired sync/async evidence reaches zero active-result bytes with every structural guard intact. Fast-forward only the accepted candidate into the issue branch, document the measured evidence bilingually, and merge only after all required CI is green.

**Tech Stack:** Python 3.13.14, redis-py 8.0.1, Redis Lua `EVAL`, pytest/pytest-asyncio, `bluetape-testing`, Testcontainers on Colima, `bluetape-benchmark`, uv, Ruff, GitHub CLI.

---

## Authority And Execution Mode

- GitHub issue: #63, milestone `0.2.0`, assignee `debop`, label `enhancement`.
- Integration branch: `develop`.
- Accepted branch/worktree:
  `improve/issue-63-active-marker-transfer` at
  `.worktrees/issue-63-active-marker-transfer`.
- Candidate branch/worktree:
  `experiment/issue-63-active-marker-transfer/round-1-conditional-result` at
  `.omx/self-improve/worktrees/round-1-conditional-result`.
- Baseline worktree: detached fixture commit at
  `.worktrees/issue-63-benchmark-baseline`.
- Execution mode after approval: Inline, using `executing-plans` checkpoints.
- Heavyweight Testcontainers and benchmark runs are always serialized.
- `auto_push=false` and `auto_pr=false`; the already approved delivery flow is
  performed manually after local DoD passes.
- Merge strategy: GitHub rebase merge. CI success and a fresh review-thread read
  are mandatory before merge.

## File Map

### Fixture commit: sealed after baseline

- `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`
  owns the explicit stale-result workload input and its bounds.
- `packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py`
  owns stale-result setup, active/completed byte classification, and the
  deterministic two-snapshot gate.
- `packages/bluetape-cache-redis/benchmarks/_coordination_security.py`
  owns the exact report parameter/metric allowlists.
- `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`
  locks registry vectors, validation, recorder classification, and invariants.
- `packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py`
  proves the full-profile stale-result case against serial real Redis.

### Candidate files: allowed after sealing

- `packages/bluetape-cache-redis/src/bluetape/cache/redis/_provider.py`
  owns the shared fixed Lua script used by both providers.
- `packages/bluetape-cache-redis/tests/_support.py`
  owns the independent expected fixed-script text used by provider tests.
- `packages/bluetape-cache-redis/tests/test_sync_provider.py` and
  `test_async_provider.py` lock one-EVAL response parity.
- `packages/bluetape-cache-redis/tests/test_sync_coordination.py` and
  `test_async_coordination.py` lock active polling and completed reuse.
- `packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py`
  proves active omission, completed bounding, ACL, malformed, stale-owner, and
  sync/async real-Redis behavior.

### Evidence and delivery files

- `packages/bluetape-cache-redis/README.md` and `README.ko.md` document the
  active/completed snapshot contract and paired evidence.
- `docs/superpowers/research/2026-07-13-issue-63-active-marker-result-transfer-analysis.md`
  records reproducible artifacts, hashes, metrics, guards, and caveats.
- `docs/review/2026-07-13-issue-63-active-marker-result-transfer-code-review.md`
  records the final review lenses and P0/P1 convergence.
- `CHANGELOG.md` records the user-visible efficiency change.
- Ignored `.omx/self-improve/` owns recoverable runtime state only and is never
  committed.
- External raw artifacts live only under
  `/Users/debop/work/bluetape4k/.benchmark-artifacts/bluetape-py/issue-63-pair-000`.

## Task 1: Re-open workflow gates and initialize recoverable Type F state

**Files:**
- Create ignored: `.omx/self-improve/config/settings.json`
- Create ignored: `.omx/self-improve/config/goal.md`
- Create ignored: `.omx/self-improve/config/harness.md`
- Create ignored: `.omx/self-improve/state/state.json`
- Create ignored: `.omx/self-improve/tracking/baseline.json`
- Create ignored: `.omx/self-improve/tracking/raw_data.json`
- Create ignored: `.omx/self-improve/tracking/events.json`

- [ ] **Step 1: Re-read authority and instantiate every applicable checklist row**
  - **Action:** Re-read workspace/repo `AGENTS.md`, `bluetape-workflow`,
    `bluetape-self-improve`, `bluetape-py-patterns`, `executing-plans`, TDD, and
    verification guidance. Instantiate `CL-01..08`, applicable `CG-01..17`, and
    `F-01..08` before editing source. Mark only concrete scope-backed N/A rows.
  - **Evidence:** Runtime checklist records the IDs, applicability, current
    branch/worktree, clean status, issue metadata, approved spec/plan, and
    `Required checks: X/Y; N/A: N; Blocked: N` counters.
  - **Failure:** Stop before fixture mutation and repair missing authority or
    unchecked prerequisites.

- [ ] **Step 2: Confirm there is no active or legacy self-improve run**
  - **Action:** Inspect `.omx/self-improve/state/state.json`, legacy
    `agent-settings.json`/`iteration_state.json`, registered worktrees, current
    diff, and `.omx/self-improve/STOP`. Migrate only if the skill's exact legacy
    condition is present; never overwrite an active state file.
  - **Evidence:** `git status --short --branch`, `git worktree list --porcelain`,
    state-file inventory, and stop-file result are read and recorded.
  - **Failure:** Recover the last valid checkpoint or stop as blocked; do not
    create a candidate over ambiguous state.

- [ ] **Step 3: Materialize concrete ignored configuration atomically**
  - **Action:** Use `apply_patch` to create missing config/state/tracking files
    from the self-improve templates. Configure: metric
    `correctness_active_result_bytes_sum`, direction `lower_is_better`, target
    `0`, minimum improvement `1.0`, baseline repetitions `1`, max iterations
    `2`, plateau threshold `0.0`, plateau window `1`, regression threshold
    `0.0`, circuit breaker `2`, base `develop`, winner branch
    `improve/issue-63-active-marker-transfer`, and user stop file
    `.omx/self-improve/STOP`. Keep `auto_push` and `auto_pr` false.
  - **Evidence:** Every JSON file passes `jq empty`; `goal.md` contains the
    approved scope/metric/hypothesis; `harness.md` contains the exact pair-000
    commands from Tasks 4 and 7; state is atomically written through
    `state.json.tmp`, parsed, renamed, and records approval/trust confirmation.
  - **Failure:** Leave `F-02` unchecked and repair state integrity before any
    candidate work.

## Task 2: Lock the explicit stale-result workload with failing unit tests

**Files:**
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`
- Test target: `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`
- Test target: `packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py`
- Test target: `packages/bluetape-cache-redis/benchmarks/_coordination_security.py`

- [ ] **Step 1: Write matrix and allowlist tests first**
  - **Action:** Extend the benchmark tests to require:
    `stale_result_bytes == 0` for all smoke cases; exactly `65_536` for full
    `multi-coordinator/high-medium-short`; zero for the other full cases;
    smoke registry digest
    `fac8eae63c0d6dbeff96cc99827ca1c3d893b53203eb22be1289f85324bfe5e3`;
    full registry digest
    `2cc0e4b8700f3678aa51e004acfd966a4fdd363a9b5435459188b039849e5566`;
    unchanged matrix totals; rejection of bool, negative, over-limit, or
    single-coordinator stale fixtures; and exact new parameter/metric fields.
  - **Evidence:** The test code names `stale_result_bytes` and
    `correctness_active_snapshot_count` explicitly and preserves the existing
    seed vector because seed derivation uses stable scenario/case identity.
  - **Failure:** Repair tests that permit implicit defaults, an unbounded stale
    value, or a fixture that cannot produce waiters.

- [ ] **Step 2: Write recorder and invariant tests first**
  - **Action:** Construct `RedisCoordinationSnapshot` values for two active
    results (`3` and `5` bytes), one active absent result, one completed result
    (`7` bytes), and one missing marker. Require command count `5`, active
    snapshot count `3`, active bytes `8`, completed bytes `7`, and no
    misclassification. Require the stale multi-coordinator invariant to fail at
    count `1` and pass at count `2`. Use
    `bluetape.testing.eventually()`/`eventually_async()` only to observe an
    externally signalled gate; do not add assertion polling to benchmark code.
  - **Evidence:** Tests cover success, absent input, malformed/non-matching
    marker prefix, exact boundary `2`, and preservation of caller-owned
    snapshot values.
  - **Failure:** Keep fixture implementation blocked until active and completed
    bytes are independently observable.

- [ ] **Step 3: Run RED**
  - **Action:** Run:
    `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`.
  - **Evidence:** The command fails specifically because the new case field,
    active snapshot count, classification, allowlist, and invariant do not yet
    exist.
  - **Failure:** If tests pass or fail for collection/environment reasons, fix
    the test setup before implementation.

## Task 3: Implement, verify, and commit the sealed benchmark fixture

**Files:**
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py`
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_security.py`
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py`

- [ ] **Step 1: Add exact bounded matrix input**
  - **Action:** Add `MAX_STALE_RESULT_BYTES = 16_777_216` and the exact-int
    `stale_result_bytes` field to `ScenarioCase`. Include it in non-negative
    validation. In `validate_profile`, reject values above the ceiling and
    reject a non-zero fixture unless `callers >= 2`, `coordinators >= 2`, and
    `scenario_id == "multi-coordinator"`. Set all existing cases explicitly to
    zero except full `multi-coordinator/high-medium-short`, which is `65_536`.
  - **Evidence:** Registry digest tests match both fixed SHA-256 vectors and
    result/sample/operation/warmup totals stay unchanged.
  - **Failure:** Do not continue if the workload identity is implicit or totals
    drift.

- [ ] **Step 2: Implement marker-aware recorder and deterministic release gate**
  - **Action:** Extend `CorrectnessMetrics` with `active_snapshot_count`. Extend
    `_Recorder` with a target, `threading.Event`, loop-bound `asyncio.Event`,
    bounded sync/async wait methods, and marker-state classification. An active
    prefix increments count and active bytes; a completed prefix increments
    completed bytes. Signal at target `2`. Extend `_SyncLoader` and
    `_AsyncLoader` with an optional pre-return gate callback, then preserve the
    configured delay.
  - **Evidence:** Recorder tests prove exact counts and the gate has a fixed
    timeout/category rather than an unbounded wait.
  - **Failure:** Stop on polling-based gate code, cross-loop event use, or any
    result classification that ignores marker state.

- [ ] **Step 3: Seed the derived result key outside timing and metrics**
  - **Action:** Import the existing private `_coordination_keys` helper. For
    non-zero `stale_result_bytes`, hash the benchmark namespace exactly as the
    coordinator does, derive the `key-0` result key, and call the first provider's
    ordinary `set(..., ttl=options.result_ttl)` before ready/release. Use
    `b"s" * case.stale_result_bytes`. Apply the setup to correctness, warmup,
    and measurement repetitions in both modes; only correctness uses the
    two-snapshot gate.
  - **Evidence:** Unit tests prove setup precedes the measurement clock and the
    recorder's command count excludes the setup `SET`. Namespace tests prove
    phase/repetition isolation.
  - **Failure:** Stop if setup is timed, counted, uses a raw duplicated key
    formula, or can leak between repetitions.

- [ ] **Step 4: Emit and validate the new exact fields**
  - **Action:** Add `stale_result_bytes` to `_parameters`; add
    `correctness_active_snapshot_count` to both mode metric mappings and the
    security `METRICS` allowlist; pass `stale_result_bytes` into
    `invariants_for`; and add `multiple_active_snapshots` only when the fixture
    is non-zero.
  - **Evidence:** Unit suite passes with every report invariant true and no
    extra result rows.
  - **Failure:** Reject unknown report fields or an invariant that makes ordinary
    smoke cases depend on the new fixture.

- [ ] **Step 5: Add serial real-Redis fixture proof**
  - **Action:** Add a Testcontainers test that runs the clean CLI with
    `--profile full --mode both --scenario multi-coordinator --seed 20260713`
    and verifies the selected high-medium result in both modes has
    `stale_result_bytes == 65_536`, active snapshot count at least `2`, and the
    `multiple_active_snapshots` invariant. Do not assert active-result bytes are
    non-zero because the same sealed test must pass the accepted candidate.
  - **Evidence:** The test is marked `testcontainers`, uses one subprocess at a
    time, parses the report, and checks both modes.
  - **Failure:** Fix lifecycle or fixture determinism before sealing.

- [ ] **Step 6: Run GREEN unit gates and commit the fixture**
  - **Action:** Run the benchmark unit suite, Ruff on the benchmark/test paths,
    formatting check, and `git diff --check`, then commit only fixture paths as
    `test: add active transfer benchmark fixture`.
  - **Evidence:** Unit commands exit `0`; `git show --stat --oneline HEAD` lists
    only the five fixture files; worktree is clean.
  - **Failure:** Repair and rerun; do not create a baseline from dirty or
    partially passing fixture code.

- [ ] **Step 7: Run clean serial integration proof**
  - **Action:** From the clean fixture commit run:
    `uv run pytest -m testcontainers packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py -vv`.
  - **Evidence:** Both smoke and focused full stale-result tests pass with zero
    leaked Redis container. Record the fixture commit SHA.
  - **Failure:** Add a separate repair commit, rerun unit/integration gates, and
    treat the repair commit as the new fixture SHA.

## Task 4: Seal the fixture and capture the untouched baseline

**Files:**
- Update ignored: `.omx/self-improve/config/*`
- Update ignored: `.omx/self-improve/state/state.json`
- Create external: `issue-63-pair-000-baseline.json`

- [ ] **Step 1: Pin trusted SHA and sealed paths**
  - **Action:** Set `trusted_base_revision`, `baseline_commit`, and
    `last_valid_checkpoint` to the exact 40-character fixture commit SHA using
    `apply_patch`. Seal these repository-relative paths:
    `packages/bluetape-cache-redis/benchmarks/`, both coordination benchmark
    test files, and `packages/bluetape-benchmark/`. Record SHA-256 digests for
    each sealed tracked file in `tracking/baseline.json`.
  - **Evidence:** `jq empty` passes; symbolic branch names are absent from trusted
    revision fields; digest inventory and `git ls-tree` resolve at the pinned
    commit.
  - **Failure:** Stop before baseline if any sealed input is ignored, untracked,
    mutable, or pinned to a symbolic ref.

- [ ] **Step 2: Validate the accepted branch against its own trusted base**
  - **Action:** Run the skill's `validate-sealed.sh` with `--repo` set to the
    accepted worktree, `--settings` set to its absolute settings file, and
    `--base` set to the fixture SHA.
  - **Evidence:** Exact output: `OK: sealed files unchanged.`
  - **Failure:** Repair contamination or create a new fixture commit and
    invalidate prior state.

- [ ] **Step 3: Create and prepare the detached baseline worktree**
  - **Action:** Add
    `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/issue-63-benchmark-baseline`
    detached at the fixture SHA. Run
    `uv sync --all-packages --all-extras --python 3.13.14 --locked` there and
    confirm `git status --short` is empty.
  - **Evidence:** Worktree list shows the exact detached SHA; Python is 3.13.14;
    `pyfory`, `cramjam`, `lz4`, and `zstandard` import successfully.
  - **Failure:** Stop on environment or clean-tree mismatch.

- [ ] **Step 4: Capture pair-000 baseline serially**
  - **Action:** Create the external artifact directory, assert the baseline path
    does not exist, then from the baseline worktree run:

    ```bash
    uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
      --profile full --mode both --seed 20260713 --role baseline \
      --runner-id runner-colima-a --pair-id issue-63-pair-000 --pair-index 0 \
      --candidate-order baseline-first \
      --output /Users/debop/work/bluetape4k/.benchmark-artifacts/bluetape-py/issue-63-pair-000/issue-63-pair-000-baseline.json
    ```

  - **Evidence:** Report loads through `read_report`; source is clean; role,
    pair, SHA, profile, mode order, environment, registry, policy, and lock
    fields are exact; selected sync and async active-result byte sums are each
    positive and active snapshot counts are at least two.
  - **Failure:** Do not create a candidate until a fresh valid baseline exists;
    environment failure is reported as environment failure, never improvement.

- [ ] **Step 5: Hash and checkpoint the baseline atomically**
  - **Action:** Record `shasum -a 256` of the baseline artifact, its primary
    total, per-mode active counts/bytes, Redis image/version, and environment in
    ignored tracking/state files through temp-parse-rename. Mark F-01..F-04
    evidence current.
  - **Evidence:** `tracking/baseline.json`, raw/event logs, and state agree on
    SHA, artifact digest, score, and next step `candidate_round_1`.
  - **Failure:** Preserve raw output and recover the prior state before candidate
    work.

## Task 5: Create the isolated candidate and establish RED script tests

**Files:**
- Modify in candidate: `packages/bluetape-cache-redis/tests/_support.py`
- Modify in candidate: `packages/bluetape-cache-redis/tests/test_sync_provider.py`
- Modify in candidate: `packages/bluetape-cache-redis/tests/test_async_provider.py`
- Modify in candidate: `packages/bluetape-cache-redis/tests/test_sync_coordination.py`
- Modify in candidate: `packages/bluetape-cache-redis/tests/test_async_coordination.py`
- Modify in candidate: `packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py`

- [ ] **Step 1: Create one hypothesis branch/worktree from the trusted SHA**
  - **Action:** Create
    `experiment/issue-63-active-marker-transfer/round-1-conditional-result` and
    its `.omx/self-improve/worktrees/round-1-conditional-result` worktree from
    the exact fixture SHA. Record the hypothesis: branch inside the shared fixed
    script after the bounded marker read; return an absent result sentinel for
    `active:` and otherwise preserve existing bounded result commands.
  - **Evidence:** Candidate branch base equals fixture SHA, accepted branch is
    unchanged, candidate status is clean, and allowed files exclude every
    sealed path.
  - **Failure:** Remove the contaminated candidate and recreate it from the
    trusted SHA.

- [ ] **Step 2: Change the independent expected script and provider cases**
  - **Action:** In `_support.py`, set the expected script to the approved exact
    Lua text with `string.sub(marker_value, 1, 7) == 'active:'` and
    `{marker_exists, marker_length, marker_value, 0, 0, ''}`. In both provider
    suites require an active response to map to `result=None` and a completed
    response to retain bounded bytes/oversize status. Keep exact one-`eval`, two
    keys, and two bounds assertions.
  - **Evidence:** The expected test constant is independent from production and
    both mode tests cover active and completed responses.
  - **Failure:** Do not import the production script into the expected fixture
    or weaken exact call assertions.

- [ ] **Step 3: Add coordinator and real-Redis regression cases**
  - **Action:** Change the sync active-then-completed fake snapshot result from
    `b"ignored"` to `None`; add the equivalent async active-then-completed test.
    Add serial real-Redis sync/async tests that write an active marker plus a
    65,536-byte stale result and require no returned result, then change the
    marker to completed and require the existing bounded prefix/oversize result.
    Keep stale-owner publish and denied-EVAL ACL assertions.
  - **Evidence:** Tests cover active valid, active oversized/malformed marker
    failure, completed valid/oversized result, stale owner, deadline/poll, and
    ACL behavior without changing public signatures.
  - **Failure:** Add missing failure-path coverage before production mutation.

- [ ] **Step 4: Run RED**
  - **Action:** Run the exact sync/async provider tests and the new real snapshot
    tests serially.
  - **Evidence:** Provider tests fail because production still sends the old
    fixed script; real Redis tests fail because active snapshots still return
    stale result bytes. Existing completed and failure tests remain meaningful.
  - **Failure:** If RED is caused by Docker/environment or test mistakes, repair
    it before changing production.

## Task 6: Implement the minimal shared Lua branch and make candidate GREEN

**Files:**
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_provider.py`
- Test: all candidate files from Task 5

- [ ] **Step 1: Replace only the fixed snapshot script**
  - **Action:** Use this exact production constant; do not change provider
    signatures, parser, snapshot dataclass, coordinator loops, or async provider:

    ```python
    COORDINATION_SNAPSHOT_SCRIPT = """
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
    """.strip()
    ```

  - **Evidence:** Diff shows one production mechanism; async continues importing
    the shared constant and parser behavior is unchanged.
  - **Failure:** Revert any extra command, fallback, public API, or duplicated
    async script.

- [ ] **Step 2: Run targeted GREEN tests**
  - **Action:** Run provider and coordinator suites for both modes, then serial
    real Redis coordination integration. Run Ruff/format checks on changed
    Python files and `git diff --check`.
  - **Evidence:** All commands exit `0`; active returns absent result; completed
    returns bounded result; malformed/oversized/stale-owner/deadline/ACL cases
    retain stable errors; no container leaks.
  - **Failure:** Repair with a new failing test first; do not benchmark a failed
    candidate.

- [ ] **Step 3: Validate sealed inputs before commit**
  - **Action:** Run `validate-sealed.sh` against the candidate repo with the
    accepted worktree's absolute settings and fixture SHA.
  - **Evidence:** Exact output: `OK: sealed files unchanged.` Candidate diff
    contains only allowed production/test files.
  - **Failure:** Reject and recreate the candidate if any sealed path changed.

- [ ] **Step 4: Commit and reverify clean candidate**
  - **Action:** Commit as `perf: skip active marker result transfer`, then rerun
    targeted provider/coordinator tests and serial real Redis integration from
    the clean candidate commit.
  - **Evidence:** Candidate status is clean, commit parent is fixture SHA, tests
    pass, and state records the candidate SHA and approach family.
  - **Failure:** Add an explicit repair commit and refresh candidate SHA/tests;
    never rewrite baseline or sealed fixture history.

## Task 7: Capture candidate, compare pair-000, and apply exact acceptance

**Files:**
- Create external: `issue-63-pair-000-candidate.json`
- Create external: `issue-63-pair-000-comparison.json`
- Update ignored tracking/state files

- [ ] **Step 1: Capture candidate serially on the same runner**
  - **Action:** From the clean candidate worktree, after the baseline run and no
    concurrent Testcontainers activity, run:

    ```bash
    uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
      --profile full --mode both --seed 20260713 --role candidate \
      --runner-id runner-colima-a --pair-id issue-63-pair-000 --pair-index 0 \
      --candidate-order baseline-first \
      --output /Users/debop/work/bluetape4k/.benchmark-artifacts/bluetape-py/issue-63-pair-000/issue-63-pair-000-candidate.json
    ```

  - **Evidence:** Candidate report loads, candidate SHA differs from baseline,
    paired environment/registry/lock/policy fields match, and source is clean.
  - **Failure:** Reject incomparable or environment-failed output; do not patch
    metrics or reuse stale artifacts.

- [ ] **Step 2: Generate the generic comparison artifact**
  - **Action:** Run:

    ```bash
    uv run python -m bluetape.benchmark.compare \
      --baseline /Users/debop/work/bluetape4k/.benchmark-artifacts/bluetape-py/issue-63-pair-000/issue-63-pair-000-baseline.json \
      --candidate /Users/debop/work/bluetape4k/.benchmark-artifacts/bluetape-py/issue-63-pair-000/issue-63-pair-000-candidate.json \
      --output /Users/debop/work/bluetape4k/.benchmark-artifacts/bluetape-py/issue-63-pair-000/issue-63-pair-000-comparison.json
    ```

  - **Evidence:** Exit `0`, `comparable=true`, empty reasons, opposite roles,
    distinct Git SHAs, and timing deltas present only as observations.
  - **Failure:** Stop and recapture the pair under a matching environment.

- [ ] **Step 3: Apply the benchmark-specific correctness acceptance script**
  - **Action:** Run this exact read-only validator:

    ```bash
    uv run python - <<'PY'
    import json
    from pathlib import Path

    from bluetape.benchmark import compare_reports, read_report

    root = Path(
        "/Users/debop/work/bluetape4k/.benchmark-artifacts/"
        "bluetape-py/issue-63-pair-000"
    )
    baseline = read_report(root / "issue-63-pair-000-baseline.json")
    candidate = read_report(root / "issue-63-pair-000-candidate.json")
    comparison = compare_reports(baseline, candidate)
    assert comparison.comparable and comparison.reasons == ()

    def index(report):
        return {
            (item.mode, item.scenario_id, dict(item.parameters)["case_id"]): item
            for item in report.scenarios
        }

    before = index(baseline)
    after = index(candidate)
    assert before.keys() == after.keys()
    target_keys = (
        ("sync", "multi-coordinator", "high-medium-short"),
        ("async", "multi-coordinator", "high-medium-short"),
    )
    baseline_active = sum(
        dict(before[key].metrics)["correctness_active_result_bytes"]
        for key in target_keys
    )
    candidate_active = sum(
        dict(after[key].metrics)["correctness_active_result_bytes"]
        for key in target_keys
    )
    assert baseline_active > 0
    assert candidate_active == 0
    assert (baseline_active - candidate_active) / baseline_active == 1.0
    active_snapshots = {
        key[0]: {
            "baseline": dict(before[key].metrics)["correctness_active_snapshot_count"],
            "candidate": dict(after[key].metrics)["correctness_active_snapshot_count"],
        }
        for key in target_keys
    }
    assert all(
        count >= 2
        for values in active_snapshots.values()
        for count in values.values()
    )

    def stable_command_count(item):
        metrics = dict(item.metrics)
        commands = metrics["correctness_redis_commands"]
        if item.scenario_id == "multi-coordinator":
            return commands - metrics["correctness_active_snapshot_count"]
        return commands

    assert all(
        stable_command_count(before[key]) == stable_command_count(after[key])
        for key in before
    )
    completed_keys = tuple(key for key in before if key[1] == "completed-reuse")
    assert len(completed_keys) == 4
    assert all(
        dict(before[key].metrics)["correctness_completed_result_bytes"] > 0
        and dict(after[key].metrics)["correctness_completed_result_bytes"] > 0
        for key in completed_keys
    )
    assert all(
        all(value for _, value in item.invariants)
        for report in (baseline, candidate)
        for item in report.scenarios
    )
    print(
        json.dumps(
            {
                "active_snapshots": active_snapshots,
                "baseline_active_result_bytes": baseline_active,
                "candidate_active_result_bytes": candidate_active,
                "command_parity": True,
                "comparable": True,
                "completed_result_guard": True,
                "improvement": 1.0,
            },
            sort_keys=True,
        )
    )
    PY
    ```

  - **Evidence:** The script exits `0` and the printed summary contains primary
    baseline/final/delta, per-mode counts, command parity, completed-result
    guard, and `comparable: true` without raw keys, endpoints, or payloads.
    `multi-coordinator` command parity excludes active-snapshot polling because
    a same-SHA diagnostic rerun proved that concurrent scheduling changes the
    raw polling count; all other scenarios retain raw command-count parity.
  - **Failure:** Reject the candidate when any assertion fails. A latency win
    cannot override a correctness failure.

- [ ] **Step 4: Hash and checkpoint all raw evidence**
  - **Action:** Record SHA-256 for baseline, candidate, and comparison artifacts;
    append the exact command/results to raw/event history; atomically update
    iteration 1 state, best score `0`, accepted winner SHA, decision `accepted`,
    and stop reason `target_reached`.
  - **Evidence:** `jq empty` passes and state/raw/event/digest records reconcile.
  - **Failure:** Preserve raw artifacts and recover the last valid state before
    integration.

- [ ] **Step 5: Use round 2 only for a bounded failed round 1**
  - **Action:** If round 1 is rejected for an implementation defect and a
    measurable correction remains, create
    `experiment/issue-63-active-marker-transfer/round-2-conditional-result-corrected`
    fresh from the fixture SHA. Use pair index `1`, pair ID
    `issue-63-pair-001`, `candidate-first`, and run candidate before baseline.
    Reapply every test, sealed, comparability, and acceptance gate.
  - **Evidence:** State records round-1 rejection family/evidence and round-2
    distinction. No round-2 branch exists when round 1 reaches target.
  - **Failure:** Stop after two rounds, circuit breaker `2`, user STOP, or no
    distinct measurable correction.

## Task 8: Integrate only the accepted winner and retire temporary worktrees

**Files:**
- Update ignored: `.omx/self-improve/state/*`
- No source edits

- [ ] **Step 1: Revalidate winner and accepted branch**
  - **Action:** Confirm accepted branch still equals fixture SHA, candidate
    winner equals recorded SHA, both statuses are clean, sealed validation still
    passes, and target/guards remain accepted.
  - **Evidence:** Fresh SHAs, clean statuses, sealed output, and state decision.
  - **Failure:** Do not integrate drifted or unrecorded code.

- [ ] **Step 2: Fast-forward the accepted branch to the winner**
  - **Action:** In the accepted worktree run a local `git merge --ff-only` of the
    accepted candidate branch. Do not create a merge commit.
  - **Evidence:** Accepted HEAD equals winner SHA and history contains the fixture
    and performance commits in order.
  - **Failure:** Stop on non-fast-forward history and inspect rather than force.

- [ ] **Step 3: Remove only proven temporary candidate/baseline worktrees**
  - **Action:** After hashes/state are durable, remove the candidate and detached
    baseline worktrees, delete the merged local experiment branch, and prune
    worktree metadata. Keep the accepted issue worktree until PR merge.
  - **Evidence:** `git worktree list` contains neither temporary path; experiment
    branch is absent; accepted branch is clean.
  - **Failure:** Preserve a worktree whose evidence or ownership is uncertain.

## Task 9: Record durable benchmark analysis and bilingual contract docs

**Files:**
- Modify: `packages/bluetape-cache-redis/README.md`
- Modify: `packages/bluetape-cache-redis/README.ko.md`
- Create: `docs/superpowers/research/2026-07-13-issue-63-active-marker-result-transfer-analysis.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Generate exact evidence rows from validated reports**
  - **Action:** Run a read-only Python formatter over the two reports to print a
    Markdown table with mode, baseline active bytes, candidate active bytes,
    active snapshot count, Redis command parity, completed-result guard, and
    primary reduction. Also print environment, SHAs, artifact hashes, timing
    medians/p95, and comparison caveats.
  - **Evidence:** Generated values match the accepted JSON summary and raw
    artifacts; no value is copied from memory or hand-calculated.
  - **Failure:** Stop documentation on any mismatch and revalidate artifacts.

- [ ] **Step 2: Update aligned English and Korean package contracts**
  - **Action:** State in both READMEs that one fixed EVAL first observes the
    bounded marker; active-prefixed snapshots return an absent result without
    reading the result key; completed/non-active paths keep bounded result and
    oversize enforcement. Add the generated compact evidence table and exact
    reproduction command, identify Python/Colima/Redis/runner context, and state
    that latency is observational and not a capacity/SLO claim.
  - **Evidence:** English/Korean sections have identical commands, identifiers,
    numbers, caveats, and table rows; Korean prose is engineer-to-engineer and
    not literal translationese.
  - **Failure:** Repair locale drift or unsupported claims before commit.

- [ ] **Step 3: Write the durable analysis and changelog**
  - **Action:** Create the research document with objective, fixture SHA,
    candidate SHA, sealed hashes, exact commands, artifact hashes, primary
    baseline/final/delta, structural guards, timing observations, limits,
    accept decision, and rollback. Add an English changelog bullet linking #63.
  - **Evidence:** Every numerical claim is traceable to a hashed external
    artifact and states what it does not prove.
  - **Failure:** Remove or qualify ungrounded performance language.

- [ ] **Step 4: Verify and commit documentation**
  - **Action:** Run focused README/example checks if present, locale diff review,
    Ruff only if Python docs tests change, and `git diff --check`. Commit as
    `docs: record active transfer benchmark evidence`.
  - **Evidence:** Docs are aligned, accepted worktree is clean, and commit lists
    only analysis/README/changelog files.
  - **Failure:** Repair before full verification.

## Task 10: Run full validation and record P0/P1 review evidence

**Files:**
- Create: `docs/review/2026-07-13-issue-63-active-marker-result-transfer-code-review.md`
- Modify only files required by reproduced review failures

- [ ] **Step 1: Run focused unit and serial Redis suites**
  - **Action:** Run benchmark, provider, coordinator, README/example tests, then
    Testcontainers benchmark and coordination integration files sequentially.
  - **Evidence:** Fresh pass counts, command order, and zero leaked containers are
    recorded.
  - **Failure:** Use systematic debugging; a retry-only pass is insufficient.

- [ ] **Step 2: Run the complete repository command set**
  - **Action:** Run sequentially:

    ```bash
    uv sync --all-packages --all-extras --python 3.13.14 --locked
    uv run pytest
    uv run ruff check .
    uv run ruff format --check .
    uv build --all-packages
    actionlint
    git diff --check
    ```

  - **Evidence:** Every command exits `0`; record exact pytest count and build
    package count.
  - **Failure:** Reproduce and repair the smallest failing contract, commit, and
    rerun affected targeted plus every downstream full gate.

- [ ] **Step 3: Run isolated cache-redis wheel/import metadata smoke**
  - **Action:** Run:

    ```bash
    tmp_dir="$(mktemp -d)"
    uv build --all-packages --out-dir "$tmp_dir/dist"
    uv venv "$tmp_dir/venv" --python 3.13.14
    uv pip install --python "$tmp_dir/venv/bin/python" redis==8.0.1
    uv pip install --python "$tmp_dir/venv/bin/python" \
      --no-index --find-links "$tmp_dir/dist" bluetape-cache-redis==0.1.0
    "$tmp_dir/venv/bin/python" - <<'PY'
    from importlib.metadata import requires

    from bluetape.cache.redis import AsyncRedisProvider, SyncRedisProvider

    requirements = requires("bluetape-cache-redis") or []
    assert AsyncRedisProvider and SyncRedisProvider
    assert "redis==8.0.1" in requirements
    assert "bluetape-cache==0.1.0" in requirements
    assert "bluetape-compression==0.1.0" in requirements
    assert "bluetape-serde==0.1.0" in requirements
    PY
    ```

  - **Evidence:** Clean venv installation/import exits `0` and uses built local
    bluetape wheels.
  - **Failure:** Block PR until packaging/import metadata is repaired.

- [ ] **Step 4: Perform six read-only review lenses and repair blockers**
  - **Action:** Review the complete `origin/develop...HEAD` diff for performance
    and benchmark integrity, stability/concurrency, security/ACL/redaction,
    operator/rollback, developer/API, and user/caller/locale behavior. Record
    finding severity, file/line, evidence, repair, and rerun. Resolve every P0
    and P1; do not dispatch untyped reviewers.
  - **Evidence:** Review document reports exact head SHA and final `P0=0 P1=0`,
    with each lens and verification evidence.
  - **Failure:** Return each blocker to TDD, rerun affected and full gates, and
    refresh the review against the new exact head.

- [ ] **Step 5: Commit review evidence and prove final cleanliness**
  - **Action:** Commit the review document as
    `docs: record active transfer review evidence`, then rerun `git diff --check`,
    status, and `git log --oneline origin/develop..HEAD`.
  - **Evidence:** Clean worktree, intentional commit series, P0/P1=0, accepted
    state target reached, and Type F `Required checks: X/Y; N/A: N; Blocked: 0`.
  - **Failure:** Do not push with incomplete checklist or dirty state.

## Task 11: Open PR, require green CI, rebase merge, sync, and clean up

**Files:**
- No source edits unless live CI/review exposes a reproduced defect

- [ ] **Step 1: Refresh issue metadata and push the accepted branch**
  - **Action:** Re-read issue #63 live, verify assignee/milestone/label, push
    `improve/issue-63-active-marker-transfer`, and create a PR to `develop` with
    title `perf: avoid active marker result transfer`. Mirror issue metadata.
  - **Evidence:** Live PR reports base/head, assignee `debop`, milestone `0.2.0`,
    relevant label, and `Closes #63`.
  - **Failure:** Repair metadata before CI/merge progression.

- [ ] **Step 2: End the PR body with exact DoD status**
  - **Action:** Include problem, one-EVAL mechanism, sealed benchmark
    baseline/final/delta, command/complete-result/error guards, full validation,
    P0/P1 evidence, artifact hashes, and limitations. Make the final heading
    exactly `## DoD Status` and report checklist counts.
  - **Evidence:** `gh pr view` confirms the live body and final heading.
  - **Failure:** Update the body before merge readiness.

- [ ] **Step 3: Watch every required CI check to success**
  - **Action:** Use `gh pr checks --watch` or `ci-status --watch`. If a check
    fails, inspect logs, reproduce locally, add a failing test, repair, rerun
    targeted/full gates, commit/push, and watch the replacement run.
  - **Evidence:** Every required check is successful; none is pending,
    cancelled, failed, or unexpectedly skipped.
  - **Failure:** CI failure blocks merge; never bypass protection.

- [ ] **Step 4: Refresh live review and irreversible holds**
  - **Action:** After CI is green, re-read PR reviews, inline threads, mergeable
    state, exact head SHA, issue closure link, and `CL-01..08`/`CG-09..11`
    holds. Confirm no newer user comment reopens the gate.
  - **Evidence:** Unresolved actionable threads `0`, P0/P1 `0`, mergeable state,
    green checks, and explicit approved rebase-merge authority.
  - **Failure:** Address feedback and rerun all affected evidence.

- [ ] **Step 5: Rebase merge only the green PR**
  - **Action:** Run `gh pr merge --rebase --delete-branch` for the verified PR.
  - **Evidence:** PR state is `MERGED`, merge commit/base SHA is live, and issue
    #63 is closed.
  - **Failure:** Stop on any merge-state drift; do not switch merge strategies.

- [ ] **Step 6: Synchronize and remove obsolete local state**
  - **Action:** Fetch/prune in the real checkout, fast-forward local `develop` to
    `origin/develop`, verify equality, remove the merged issue worktree, delete
    the merged local accepted branch and any remaining proven issue experiment
    branches/worktrees, prune worktrees, and verify the remote feature branch is
    absent. Preserve external benchmark evidence and ignored Type F state until
    final reporting, then remove only if no recovery need remains.
  - **Evidence:** Local and remote develop SHAs match; `worktree-list`, branch
    list, remote refs, and clean status show no unnecessary #63 worktree/branch.
  - **Failure:** Report pending cleanup rather than deleting uncertain user work.

## Spec Coverage Review

- Atomic one-EVAL active branch and unchanged six-field parser: Tasks 5-6.
- Completed/non-active bounded result behavior: Tasks 5-7 and 10.
- Malformed, oversized, stale-owner, deadline, ACL, cleanup, and cancellation
  preservation: Tasks 5-6 and 10.
- Deterministic large stale result with multiple polls in both modes: Tasks 2-4.
- Sealed baseline/candidate comparability and exact 100% target: Tasks 4 and 7.
- Maximum two rounds, circuit breaker, stop file, and recoverable state: Tasks 1,
  7, and 8.
- Public signature and dependency stability: Tasks 6 and 10.
- Bilingual documentation, evidence caveats, changelog, and rollback: Task 9.
- P0/P1=0, complete local verification, green CI, fresh live review, rebase
  merge, local sync, and branch/worktree cleanup: Tasks 10-11.

No source file is modified by this planning commit. Implementation begins only
after explicit approval of this plan, the pair-000 benchmark commands, and the
repeated execution of repository code under the bounded Type F loop.
