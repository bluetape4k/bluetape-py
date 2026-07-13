# Redis Coordination Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-publishable, stdlib-only benchmark package and a reproducible sync/async Redis coordination benchmark matrix for issue #65.

**Architecture:** `bluetape.benchmark` owns immutable timing, report, atomic JSON, and comparison contracts. Redis-specific profile, policy, scenario, lifecycle, security, and CLI code remains under `packages/bluetape-cache-redis/benchmarks/`; correctness runs are instrumented, while warmup and measured runs use unwrapped preconnected providers. The checked artifact uses the bounded smoke registry, and the full registry supplies paired evidence for #63 without introducing latency thresholds into CI.

**Tech Stack:** Python 3.13, stdlib dataclasses/JSON/hashlib/tempfile/multiprocessing/asyncio, uv workspace/build backend, redis-py 8.0.1, Testcontainers, pytest/pytest-asyncio, Ruff, GitHub Actions.

---

## File Map

- `packages/bluetape-benchmark/`: private package containing `_contracts.py`, `_timing.py`, `_json.py`, `_comparison.py`, `compare.py`, exact exports, tests, and bilingual READMEs.
- `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`: exact profiles, canonical digests, report assembly.
- `packages/bluetape-cache-redis/benchmarks/_coordination_security.py`: bytes codec, allowlists, diagnostics, Git preflight.
- `packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py`: correctness/warmup/measurement scenario execution.
- `packages/bluetape-cache-redis/benchmarks/_coordination_runtime.py`: Redis ownership, spawn containment, async convergence, signals.
- `packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py`: thin run CLI.
- `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`: pure registry/policy/CLI/security tests.
- `packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py`: serial real-Redis smoke and cleanup proof.
- `docs/review/artifacts/issue-65-redis-coordination-benchmark.json`: checked smoke artifact.
- `docs/research/2026-07-13-issue-65-redis-coordination-benchmark-analysis.md`: result interpretation.
- Root/package/release READMEs and `CHANGELOG.md`: package, operator, and publication boundaries.

### Task 1: Scaffold the private workspace package and publication guard

**Files:**
- Create: `packages/bluetape-benchmark/pyproject.toml`
- Create: `packages/bluetape-benchmark/src/bluetape/benchmark/__init__.py`
- Create: `packages/bluetape-benchmark/tests/test_packaging.py`
- Modify: `pyproject.toml`
- Modify: `packages/bluetape-cache-redis/pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Write failing packaging tests**

```python
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_benchmark_distribution_is_private_and_stdlib_only() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-benchmark/pyproject.toml")
    assert metadata["project"]["dependencies"] == []
    assert metadata["project"]["classifiers"] == ["Private :: Do Not Upload"]
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.benchmark"


def test_workspace_builds_but_meta_never_installs_benchmark() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")
    assert root["tool"]["uv"]["sources"]["bluetape-benchmark"] == {"workspace": True}
    assert "packages/bluetape-benchmark" in root["tool"]["uv"]["workspace"]["members"]
    assert all("benchmark" not in item for item in root["project"]["dependencies"])
    meta = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    assert all("benchmark" not in item for item in meta["dependencies"])
    assert all("benchmark" not in item for values in meta["optional-dependencies"].values() for item in values)
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_packaging.py -q`

Expected: FAIL because the package metadata and workspace registration are absent.

- [ ] **Step 3: Add exact private metadata and workspace edges**

```toml
[project]
name = "bluetape-benchmark"
version = "0.1.0"
description = "Internal benchmark contracts and artifact helpers for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []
classifiers = ["Private :: Do Not Upload"]

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.benchmark"
```

Add `bluetape-benchmark = { workspace = true }` and `packages/bluetape-benchmark` only to root sources/members. Add `bluetape-benchmark==0.1.0` only to cache-redis `test`. Do not add a root dependency or meta extra.

- [ ] **Step 4: Add the namespace, lock, sync, verify, and commit**

```python
"""Internal benchmark contracts for source-workspace tooling."""

__all__: list[str] = []
```

Run: `uv lock && uv sync --all-packages --all-extras && uv run pytest packages/bluetape-benchmark/tests/test_packaging.py packages/bluetape-cache-redis/tests/test_packaging.py -q`

Expected: PASS.

```bash
git add pyproject.toml uv.lock packages/bluetape-benchmark packages/bluetape-cache-redis/pyproject.toml
git commit -m "build: add private benchmark workspace package"
```

### Task 2: Implement immutable contracts and timing summaries

**Files:**
- Create: `packages/bluetape-benchmark/src/bluetape/benchmark/_contracts.py`
- Create: `packages/bluetape-benchmark/src/bluetape/benchmark/_timing.py`
- Create: `packages/bluetape-benchmark/tests/test_contracts.py`
- Create: `packages/bluetape-benchmark/tests/test_timing.py`
- Modify: `packages/bluetape-benchmark/src/bluetape/benchmark/__init__.py`

- [ ] **Step 1: Write exact-type, immutability, invariant, and percentile tests**

```python
def test_report_copies_and_sorts_caller_fields() -> None:
    values = {"payload_bytes": 1024, "case_id": "small"}
    result = scenario(parameters=values)
    values["payload_bytes"] = 0
    assert result.parameters == (("case_id", "small"), ("payload_bytes", 1024))


def test_summary_uses_honest_tail_gates() -> None:
    smoke = summarize_timings([1, 2, 3, 4, 5], operations_per_sample=8)
    assert smoke.p95_ns is None and smoke.p99_ns is None
    full = summarize_timings(range(1, 21), operations_per_sample=1)
    assert full.p95_ns == 19 and full.p99_ns is None
    assert summarize_timings(range(1, 101)).p99_ns == 99


def test_snapshot_rejects_pair_fields_and_failed_invariant() -> None:
    with pytest.raises(ValueError):
        BenchmarkRunIdentity(mode_order=("sync",), role="snapshot", pair_id="pair-000")
    with pytest.raises(ValueError):
        scenario(invariants={"loader_count": False})
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_contracts.py packages/bluetape-benchmark/tests/test_timing.py -q`

Expected: collection FAIL because the models/functions are not exported.

- [ ] **Step 3: Implement frozen/slotted contracts and validators**

```python
type BenchmarkScalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkRunIdentity:
    mode_order: tuple[str, ...]
    role: str = "snapshot"
    runner_id: str | None = None
    pair_id: str | None = None
    pair_index: int | None = None
    candidate_order: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkScenarioResult:
    scenario_id: str
    mode: str
    parameters: tuple[tuple[str, BenchmarkScalar], ...]
    timing: TimingSummary
    metrics: tuple[tuple[str, BenchmarkScalar], ...]
    invariants: tuple[tuple[str, bool], ...]
```

Implement all approved `TimingSummary`, `BenchmarkEnvironment`, `BenchmarkReport`, `BenchmarkDelta`, and `BenchmarkComparison` fields. Normalize mappings to sorted immutable tuples; reject duplicate names, bool-as-int, non-finite floats, failed invariants, duplicate `(mode, scenario_id, case_id)`, malformed SHA-256, incomplete pairing, invalid parity/order, and capacity claims.

- [ ] **Step 4: Implement nearest-rank and summary**

```python
def nearest_rank(samples: Sequence[int], percentile: float) -> int:
    values = _validated_samples(samples)
    if type(percentile) not in (int, float) or isinstance(percentile, bool):
        raise TypeError("percentile must be an exact number")
    if not math.isfinite(percentile) or not 0 < percentile <= 100:
        raise ValueError("percentile must be in (0, 100]")
    ordered = sorted(values)
    return ordered[math.ceil(float(percentile) / 100 * len(ordered)) - 1]


def summarize_timings(samples_ns: Sequence[int], *, operations_per_sample: int = 1) -> TimingSummary:
    values = _validated_samples(samples_ns)
    total = sum(values)
    if type(operations_per_sample) is not int or operations_per_sample <= 0 or total <= 0:
        raise ValueError("positive exact operations and duration are required")
    return TimingSummary(
        operations_per_sample=operations_per_sample, raw_samples_ns=values,
        min_ns=min(values), median_ns=nearest_rank(values, 50),
        p95_ns=nearest_rank(values, 95) if len(values) >= 20 else None,
        p99_ns=nearest_rank(values, 99) if len(values) >= 100 else None,
        max_ns=max(values),
        throughput_ops_per_sec=operations_per_sample * len(values) * 1_000_000_000 / total,
    )
```

- [ ] **Step 5: Export, verify GREEN, and commit**

Export only the documented models plus `nearest_rank` and `summarize_timings`.

Run: `uv run pytest packages/bluetape-benchmark/tests/test_contracts.py packages/bluetape-benchmark/tests/test_timing.py -q`

Expected: PASS.

```bash
git add packages/bluetape-benchmark
git commit -m "feat: add benchmark contracts and timing"
```

### Task 3: Implement strict schema-v1 JSON and secure atomic writes

**Files:**
- Create: `packages/bluetape-benchmark/src/bluetape/benchmark/_json.py`
- Create: `packages/bluetape-benchmark/tests/test_json.py`
- Modify: `packages/bluetape-benchmark/src/bluetape/benchmark/__init__.py`

- [ ] **Step 1: Write round-trip, symlink, preservation, and concurrency tests**

```python
def test_report_round_trip_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    write_report(path, report())
    first = path.read_bytes()
    assert read_report(path) == report()
    write_report(path, report())
    assert path.read_bytes() == first


def test_writer_rejects_symlink_and_preserves_real_target(tmp_path: Path) -> None:
    real = tmp_path / "real.json"; real.write_text("previous")
    link = tmp_path / "report.json"; link.symlink_to(real)
    with pytest.raises(ValueError):
        write_report(link, report())
    assert real.read_text() == "previous"


def test_concurrent_writers_leave_one_complete_report(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda value: write_report(path, value), (report("a"), report("b"))))
    assert read_report(path) in {report("a"), report("b")}


def test_design_document_json_example_is_a_valid_filtered_smoke_report() -> None:
    raw = extract_json_fence(DESIGN_SPEC)
    report = report_from_json(raw)
    assert report.profile == "smoke"
    assert report.run.mode_order == ("sync",)
    assert len(report.scenarios[0].timing.raw_samples_ns) == 5
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_json.py -q`

Expected: collection FAIL for missing I/O functions.

- [ ] **Step 3: Implement canonical encoding and strict reconstruction**

```python
def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def read_report(path: Path) -> BenchmarkReport:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if type(raw) is not dict or set(raw) != REPORT_KEYS or raw["schema_version"] != 1:
        raise ValueError("unsupported benchmark report schema")
    return _report_from_mapping(raw)
```

Use exact key sets at every level, reconstruct tuples explicitly, reject JSON booleans in integer fields, and rerun model validation.

- [ ] **Step 4: Implement exclusive same-directory atomic replacement**

```python
def _atomic_write(path: Path, payload: bytes) -> None:
    _validate_safe_destination(path)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory_when_supported(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
```

Reject symlink/non-directory ancestors and symlink/non-regular targets. Preserve last-complete-writer-wins and clean only the owned temp path.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_json.py -q`

Expected: PASS including deterministic bytes, `0600`, concurrent writers, replacement, failure cleanup, and path safety.

```bash
git add packages/bluetape-benchmark
git commit -m "feat: add atomic benchmark report IO"
```

### Task 4: Add fail-closed paired comparison API and CLI

**Files:**
- Create: `packages/bluetape-benchmark/src/bluetape/benchmark/_comparison.py`
- Create: `packages/bluetape-benchmark/src/bluetape/benchmark/compare.py`
- Create: `packages/bluetape-benchmark/tests/test_comparison.py`
- Modify: `packages/bluetape-benchmark/src/bluetape/benchmark/_json.py`
- Modify: `packages/bluetape-benchmark/src/bluetape/benchmark/__init__.py`

- [ ] **Step 1: Write comparable, gate-rejection, and exit tests**

```python
def test_comparison_emits_median_and_available_p95_deltas() -> None:
    result = compare_reports(paired_report("baseline", 100), paired_report("candidate", 110))
    assert result.comparable is True and result.reasons == ()
    assert result.deltas[0].absolute_delta_ns == 10
    assert result.deltas[0].relative_delta_percent == 10.0


@pytest.mark.parametrize("field", ["seed", "profile_registry_digest", "dependency_lock_digest", "git_sha"])
def test_comparison_rejects_each_required_gate(field: str) -> None:
    baseline, candidate = mismatched_pair(field)
    result = compare_reports(baseline, candidate)
    assert result.comparable is False and result.deltas == ()
    assert result.reasons == (EXPECTED_REASON[field],)


def test_cli_returns_four_without_deltas_for_non_comparable_pair(tmp_path: Path) -> None:
    completed = run_compare_cli(tmp_path, mismatched_pair("seed"))
    assert completed.returncode == 4
    assert json.loads(completed.stdout)["deltas"] == []
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_comparison.py -q`

Expected: collection FAIL for missing comparator symbols.

- [ ] **Step 3: Implement artifact-sourced gates and ordered deltas**

```python
def compare_reports(baseline: BenchmarkReport, candidate: BenchmarkReport) -> BenchmarkComparison:
    reasons = tuple(sorted(_comparison_reasons(baseline, candidate)))
    if reasons:
        return BenchmarkComparison(
            schema_version=1, comparable=False, reasons=reasons,
            baseline_git_sha=baseline.environment.git_sha,
            candidate_git_sha=candidate.environment.git_sha, deltas=(),
        )
    deltas = tuple(
        _delta(base, cand, statistic)
        for base, cand in zip(baseline.scenarios, candidate.scenarios, strict=True)
        for statistic in ("median_ns", "p95_ns")
        if getattr(base.timing, statistic) is not None
    )
    return BenchmarkComparison(
        schema_version=1, comparable=True, reasons=(),
        baseline_git_sha=baseline.environment.git_sha,
        candidate_git_sha=candidate.environment.git_sha, deltas=deltas,
    )
```

Gate schema/profile/registry/cases/seed/mode order/runner/pair/index/parity/Python/platform/CPU/lock/dependencies/Redis version/image/config/policy/source clean state. Require opposite roles and different Git SHAs. Fixed reason codes never contain values.

- [ ] **Step 4: Implement module CLI and atomic comparison output**

```python
def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        comparison = compare_reports(read_report(arguments.baseline), read_report(arguments.candidate))
        write_comparison(arguments.output, comparison)
    except (OSError, TypeError, ValueError):
        return 2
    return 0 if comparison.comparable else 4
```

Support `--output -` as JSON-only stdout. A parse/write failure preserves an existing file.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest packages/bluetape-benchmark/tests -q`

Expected: PASS.

```bash
git add packages/bluetape-benchmark
git commit -m "feat: add benchmark artifact comparison"
```

### Task 5: Define the exact Redis registry, policy, codec, and report vocabulary

**Files:**
- Create: `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`
- Create: `packages/bluetape-cache-redis/benchmarks/_coordination_security.py`
- Create: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`

- [ ] **Step 1: Write exact smoke/full registry totals**

```python
def test_smoke_registry_is_exact() -> None:
    assert [(case.scenario_id, case.case_id, case.repetitions) for case in SMOKE.cases] == [
        ("local-only", "moderate-small-short", 5),
        ("local-hit", "steady-small", 5),
        ("single-coordinator", "moderate-small-short", 5),
        ("multi-coordinator", "moderate-small-short", 5),
        ("completed-reuse", "moderate-small-immediate", 5),
        ("unrelated-keys", "moderate-small-short", 5),
    ]
    assert matrix_totals(SMOKE, ("sync", "async")) == MatrixTotals(12, 60, 10_400, 12)


def test_full_registry_has_fixed_safety_totals() -> None:
    assert matrix_totals(FULL, ("sync", "async")) == MatrixTotals(24, 412, 409_944, 72)
```

- [ ] **Step 2: Write policy, codec, digest, and allowlist tests**

```python
def test_fixed_policy_matches_provider_discovery() -> None:
    client = make_sync_client("redis://localhost:6379/0")
    assert SyncRedisProvider(client).command_policy == RedisCommandPolicy(
        connect_timeout=0.1, socket_timeout=0.1
    )
    assert load_options("safe:namespace") == RedisLoadOptions(
        namespace="safe:namespace", lease_ttl=2.0, result_ttl=2.0,
        poll_interval=0.001, max_poll_interval=0.01, wait_timeout=2.0,
        max_attempts=3, max_polls=100, redis_io_timeout=0.4,
    )


def test_bytes_codec_rejects_trusted_or_oversized_payload() -> None:
    codec = BenchmarkBytesCodec()
    with pytest.raises(ValueError):
        codec.decode(payload(trust_profile=TrustProfile.TRUSTED_INTERNAL))
    with pytest.raises(ValueError):
        codec.decode(payload(data=b"x" * (MAX_PAYLOAD_BYTES + 1)))
```

- [ ] **Step 3: Verify RED**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: collection FAIL for missing registry/security modules.

- [ ] **Step 4: Implement frozen registry and canonical seeds**

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ScenarioCase:
    scenario_id: str; case_id: str; callers: int; coordinators: int; keys: int
    payload_bytes: int; loader_delay_seconds: float; operations_per_sample: int
    warmups: int; repetitions: int


def derived_seed(root_seed: int, profile: str, mode: str, case: ScenarioCase, phase: str, repetition: int) -> int:
    value = [root_seed, profile, mode, case.scenario_id, case.case_id, phase, repetition]
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")
```

Instantiate the exact six smoke and six full-addition rows from the design. Validate 24 results, 64 callers, eight coordinators/keys, 15,728,640 payload bytes, 32 MiB aggregate bytes, 120/900-second ceilings before Redis startup. Compute registry SHA-256 from canonical compact UTF-8 JSON and lock SHA-256 from exact `uv.lock` bytes.

- [ ] **Step 5: Implement fixed clients/options/codec and vocabulary**

```python
CLIENT_OPTIONS = {
    "decode_responses": False, "socket_connect_timeout": 0.1,
    "socket_timeout": 0.1, "retry_on_timeout": False,
    "retry_on_error": (), "retry": None, "max_connections": 128,
}
PARAMETERS = frozenset({"case_id", "callers", "coordinators", "keys", "payload_bytes", "loader_delay_seconds", "warmups", "repetitions"})
METRICS = frozenset({"correctness_loader_count", "correctness_redis_commands", "correctness_active_result_bytes", "correctness_completed_result_bytes", "correctness_overlap_observed", "process_high_water_bytes"})
```

`BenchmarkBytesCodec` accepts only `raw-bytes`, version 1, `application/octet-stream`, `TrustProfile.UNTRUSTED`, and the payload bound; decode returns `payload.data`. Compose `BinaryEnvelopeFormat`/`ResultEnvelopeCodec` at 16,777,216 bytes with no compression/readers. Serialize fixed policy ID/digest.

- [ ] **Step 6: Verify GREEN and commit**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: PASS without Docker.

```bash
git add packages/bluetape-cache-redis/benchmarks packages/bluetape-cache-redis/tests/test_coordination_benchmark.py
git commit -m "feat: define redis benchmark matrix contracts"
```

### Task 6: Implement correctness and uninstrumented scenario phases

**Files:**
- Create: `packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py`
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`

- [ ] **Step 1: Write all-scenario phase and parity tests**

```python
@pytest.mark.parametrize("scenario_id", SCENARIO_ORDER)
def test_sync_correctness_precedes_uninstrumented_measurement(scenario_id: str) -> None:
    trace = run_sync_scenario(fake_context(scenario_id))
    assert trace.phases == ("correctness", "warmup", "measurement")
    assert trace.correctness_provider.recording is True
    assert all(not provider.recording for provider in trace.measured_providers)
    assert trace.verification_started_ns >= trace.measurement_stopped_ns


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", SCENARIO_ORDER)
async def test_async_has_sync_result_field_parity(scenario_id: str) -> None:
    sync = run_sync_scenario(fake_context(scenario_id))
    result = await run_async_scenario(fake_async_context(scenario_id))
    assert sync.parameters == result.parameters
    assert sync.metrics.keys() == result.metrics.keys()
    assert sync.invariants.keys() == result.invariants.keys()
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: FAIL for missing scenario runners.

- [ ] **Step 3: Implement two-phase gate and exact timing window**

```python
def measure_sync(workers: Sequence[Thread], gate: CallerGate, operations: int) -> int:
    for worker in workers: worker.start()
    gate.wait_until_all_ready(timeout=5.0)
    started = perf_counter_ns(); gate.release_all()
    for worker in workers: worker.join(timeout=gate.join_timeout)
    stopped = perf_counter_ns()
    if any(worker.is_alive() for worker in workers): raise BenchmarkLiveWorker
    verify_worker_results()
    return stopped - started
```

Create async tasks and await readiness before timing; stop immediately after convergence and verify afterward. Correctness uses recording providers/counting loaders. Warmup/measurement share fresh preconnected unwrapped providers and loaders without counters, locks, observers, tracemalloc, or recorder code.

After latency measurement and teardown, optionally read `resource.getrusage` into nullable `process_high_water_bytes`; normalize platform units in one tested function. Never enable the probe or `tracemalloc` inside the measured phase, and never compare the value across different platforms.

- [ ] **Step 4: Implement all six semantics and failures**

Dispatch fixed IDs: independent local caches/zero Redis; seeded local hit; one coordinator; round-robin multi coordinator; pre-seeded matching completed envelope; fixed unrelated keys with overlap. Use unique phase/repetition namespaces. Test barrier, loader, mismatch, timeout, Redis/provider/codec, cleanup, and non-overlap failures; never accept a failed timing.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: PASS.

```bash
git add packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py packages/bluetape-cache-redis/tests/test_coordination_benchmark.py
git commit -m "feat: add redis benchmark scenario phases"
```

### Task 7: Add bounded sync child and async cancellation lifecycle

**Files:**
- Create: `packages/bluetape-cache-redis/benchmarks/_coordination_runtime.py`
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`

- [ ] **Step 1: Write spawn containment and repeated-cancellation tests**

```python
def test_sync_timeout_terminates_spawned_child() -> None:
    result = run_sync_case_in_child(non_converging_case())
    assert result.category == "live-worker"
    assert result.events == ("abort", "terminate", "kill", "join")
    assert multiprocessing.active_children() == []


@pytest.mark.asyncio
async def test_repeated_cancellation_reuses_one_shielded_cleanup() -> None:
    runtime = async_runtime(block_at="provider-close")
    task = asyncio.create_task(runtime.run()); task.cancel(); task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert runtime.cleanup_task_creations == 1
    assert runtime.pending_owned_tasks == ()
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: FAIL for missing runtime.

- [ ] **Step 3: Implement spawn-only child protocol**

```python
@dataclass(frozen=True, slots=True)
class ChildConfig:
    redis_url: str; profile: str; mode: str; case_id: str; seed: int


def run_sync_case_in_child(config: ChildConfig) -> ChildResult:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_child_main, args=(child, config))
    process.start(); child.close()
    try: return _await_child(parent, process, config)
    finally: parent.close()
```

Pass only immutable case data and private connection config, close unused IPC, and never pass/inherit provider/client/Docker/server objects. On deadline: abort, cleanup 10s, terminate 5s, kill/join 5s. Close providers then child clients; close parent server after convergence.

- [ ] **Step 4: Implement exact async convergence**

Retain first `CancelledError`; stop admission/release; cancel unfinished owned tasks once; create one cleanup task using `gather(..., return_exceptions=True)`; shield it; close providers then clients then Redis; repeated cancellation awaits the same task; re-raise first cancellation. Cleanup categories never replace it.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: PASS with zero live processes/threads/tasks across injected failures.

```bash
git add packages/bluetape-cache-redis/benchmarks/_coordination_runtime.py packages/bluetape-cache-redis/tests/test_coordination_benchmark.py
git commit -m "feat: bound redis benchmark lifecycle"
```

### Task 8: Build the run CLI, source preflight, signals, and diagnostics

**Files:**
- Replace: `packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py`
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_security.py`
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`

- [ ] **Step 1: Write parsing, dirty-source, secret, and signal tests**

```python
def test_seed_is_required_and_pair_flags_are_all_or_none() -> None:
    assert cli("--profile", "smoke", "--output", "-").returncode == 2
    result = cli("--profile", "full", "--output", external_path(), "--seed", "1", "--role", "baseline")
    assert result.returncode == 2


@pytest.mark.parametrize("dirty_kind", ["staged", "unstaged", "untracked"])
def test_checked_or_paired_run_refuses_dirty_source(dirty_repo: Path, dirty_kind: str) -> None:
    make_dirty(dirty_repo, dirty_kind)
    result = cli_in(dirty_repo, checked_snapshot_args())
    assert result.returncode == 2
    assert diagnostic(result).category == "source-dirty"


def test_sentinel_secret_is_absent_from_every_surface(tmp_path: Path) -> None:
    result = cli_with_injected_failure("SECRET_SENTINEL", tmp_path)
    surfaces = result.stdout + result.stderr + " ".join(path.name for path in tmp_path.iterdir())
    assert "SECRET_SENTINEL" not in surfaces


def test_external_artifact_does_not_dirty_the_other_pair_worktree(pair_worktrees: PairWorktrees) -> None:
    baseline = cli_in(pair_worktrees.baseline, pair_args("baseline", pair_worktrees.artifacts))
    candidate = cli_in(pair_worktrees.candidate, pair_args("candidate", pair_worktrees.artifacts))
    assert baseline.returncode == candidate.returncode == 0
    assert git_status(pair_worktrees.baseline) == git_status(pair_worktrees.candidate) == ""
```

- [ ] **Step 2: Verify RED against the old script**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: FAIL because the old script lacks the contract.

- [ ] **Step 3: Implement strict arguments and preflight**

```python
def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--profile", choices=("smoke", "full"), required=True)
    result.add_argument("--mode", choices=("sync", "async", "both"), default="both")
    result.add_argument("--scenario", action="append", default=[])
    result.add_argument("--output", required=True); result.add_argument("--seed", type=exact_int, required=True)
    result.add_argument("--role", choices=("snapshot", "baseline", "candidate"), default="snapshot")
    result.add_argument("--runner-id"); result.add_argument("--pair-id")
    result.add_argument("--pair-index", type=exact_int)
    result.add_argument("--candidate-order", choices=("baseline-first", "candidate-first"))
    return result
```

Compute Git SHA/dirty state, exact lock digest, registry digest, dependency versions, and allowed Redis extensions internally. Reject duplicate/unknown filters, empty/over-ceiling matrices, incomplete pair flags, paired output inside either worktree, dirty checked/paired source, and unsafe output before Redis starts.

- [ ] **Step 4: Implement stable diagnostics and signals**

Emit one sorted compact JSON line after `bluetape-benchmark-error ` with exactly `code/category/mode/scenario_id/case_id/phase/repetition`. Use fixed categories and exit codes 2/3/4/5/6/130/143. First SIGINT/SIGTERM invokes bounded convergence and preserves output; second signal exits conventionally. Never emit exception text.

Inject the first signal during Redis startup, sync child wait, async wait, cleanup, and pre-replace write; assert exact diagnostic/category/exit, previous-output preservation, and zero live child/container/task. Inject a second signal during cleanup and assert immediate 130/143 escalation is never reported as success.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: PASS for filters, stdout, source, exact diagnostics, signals, and sentinel scans.

```bash
git add packages/bluetape-cache-redis/benchmarks packages/bluetape-cache-redis/tests/test_coordination_benchmark.py
git commit -m "feat: add redis benchmark CLI contract"
```

### Task 9: Prove real Redis sync/async smoke execution and cleanup

**Files:**
- Create: `packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py`
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_runtime.py`
- Modify: `packages/bluetape-cache-redis/benchmarks/_coordination_scenarios.py`
- Modify: `.github/workflows/ci.yml` only if the serial Redis job does not collect the file.

- [ ] **Step 1: Write serial Testcontainers smoke tests**

```python
@pytest.mark.testcontainers
def test_real_redis_smoke_emits_twelve_valid_results(tmp_path: Path) -> None:
    output = tmp_path / "smoke.json"
    completed = invoke_benchmark("--profile", "smoke", "--mode", "both", "--seed", "20260712", "--output", str(output))
    assert completed.returncode == 0
    report = read_report(output)
    assert len(report.scenarios) == 12
    assert all(len(item.timing.raw_samples_ns) == 5 for item in report.scenarios)
    assert all(item.timing.p95_ns is None for item in report.scenarios)


@pytest.mark.testcontainers
def test_failure_preserves_output_and_leaks_no_child(tmp_path: Path) -> None:
    output = tmp_path / "report.json"; output.write_text("previous")
    completed = invoke_injected_timeout(output)
    assert completed.returncode == 3 and output.read_text() == "previous"
    assert multiprocessing.active_children() == []
```

- [ ] **Step 2: Verify RED with real Redis**

Run: `uv run pytest -m testcontainers packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py -x -vv`

Expected: FAIL at the first incomplete real lifecycle/scenario edge.

- [ ] **Step 3: Complete minimal real wiring**

Own one parent `RedisServer`; sync children receive only URL/config and construct standard clients; async constructs async clients in runtime. Execute sequential cases, sync before async. Use SHA-256 namespaces for profile/mode/scenario/case/phase/repetition/seed. Close provider, client, then server.

- [ ] **Step 4: Verify serial and pure suites**

Run: `uv run pytest -m testcontainers packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py -vv`

Expected: PASS.

Run: `uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers and not native_compression" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/bluetape-cache-redis/benchmarks packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py .github/workflows/ci.yml
git commit -m "test: verify redis benchmark integration"
```

### Task 10: Check in bounded evidence and analysis

**Files:**
- Create: `docs/review/artifacts/issue-65-redis-coordination-benchmark.json`
- Create: `docs/research/2026-07-13-issue-65-redis-coordination-benchmark-analysis.md`
- Modify: `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`

- [ ] **Step 1: Write the checked artifact contract test**

```python
def test_checked_issue_65_artifact_is_clean_smoke_report() -> None:
    report = read_report(ROOT / "docs/review/artifacts/issue-65-redis-coordination-benchmark.json")
    assert report.schema_version == 1 and report.profile == "smoke"
    assert report.environment.source_dirty is False
    assert report.run == BenchmarkRunIdentity(mode_order=("sync", "async"))
    assert len(report.scenarios) == 12
    assert report.production_capacity_claim is False
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py::test_checked_issue_65_artifact_is_clean_smoke_report -q`

Expected: FAIL with file not found.

- [ ] **Step 3: Commit implementation, require clean tree, and generate**

Run: `git status --short`

Expected: no output.

```bash
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
  --profile smoke --mode both --seed 20260712 --role snapshot \
  --output docs/review/artifacts/issue-65-redis-coordination-benchmark.json
```

Expected: exit 0 and 12 valid schema-v1 results.

- [ ] **Step 4: Write bounded analysis**

Record command, Git SHA, Python/Redis/image/policy/lock/registry environment, medians, correctness metrics, ceilings, p95/p99 null explanation, and untimed `correctness_*` meaning. Explicitly reject production-capacity/SLO interpretation.

- [ ] **Step 5: Verify and commit evidence**

Run: `uv run pytest packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: PASS.

```bash
git add docs/review/artifacts/issue-65-redis-coordination-benchmark.json docs/research/2026-07-13-issue-65-redis-coordination-benchmark-analysis.md packages/bluetape-cache-redis/tests/test_coordination_benchmark.py
git commit -m "docs: record redis coordination benchmark evidence"
```

### Task 11: Document package, operator, comparison, and release boundaries

**Files:**
- Create: `packages/bluetape-benchmark/README.md`
- Create: `packages/bluetape-benchmark/README.ko.md`
- Modify: `README.md`, `README.ko.md`, `CHANGELOG.md`
- Modify: `packages/bluetape-cache-redis/README.md`, `packages/bluetape-cache-redis/README.ko.md`
- Modify: `docs/package-layout.md`, `docs/release.md`, `docs/release/pypi-preflight.md`, `docs/release/release-guide.md`
- Modify: `packages/bluetape-benchmark/tests/test_packaging.py`
- Modify: `packages/bluetape-cache-redis/tests/test_readme_examples.py`

- [ ] **Step 1: Write failing documentation/release tests**

```python
def test_benchmark_is_never_in_publish_allowlist() -> None:
    workspace = workspace_distribution_names()
    private = {"bluetape-benchmark"}
    assert workspace == documented_publishable() | private
    assert "bluetape-benchmark" not in documented_publishable()


@pytest.mark.parametrize("readme", [ENGLISH, KOREAN])
def test_readme_has_operator_contract(readme: Path) -> None:
    text = readme.read_text()
    for value in ("--profile smoke", "--profile full", "120", "900", "Docker", "correctness_", "source_dirty", "baseline-first", "exit 130", "bluetape.benchmark.compare"):
        assert value in text
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_packaging.py packages/bluetape-cache-redis/tests/test_readme_examples.py -q`

Expected: FAIL on missing package/release/operator documentation.

- [ ] **Step 3: Write aligned English/Korean and root/package docs**

Document the benchmark package as stdlib-only, source-only, built/tested, and forbidden to publish; do not add install/meta-extra guidance. Document smoke/full commands, Docker prerequisites, 120/900-second ceilings, payload/concurrency limits, exits/output preservation/signals, untimed correctness metrics, dirty-source rules, and external-artifact two-worktree #63 sequence.

- [ ] **Step 4: Make release selection fail closed and update changelog**

Explicitly classify every workspace distribution as publishable or private. Unknown members block preflight. State that `Private :: Do Not Upload` is PyPI-only defense in depth. Add issue #65 behavior to `CHANGELOG.md`.

- [ ] **Step 5: Verify and commit docs**

Run: `uv run pytest packages/bluetape-benchmark/tests/test_packaging.py packages/bluetape-cache-redis/tests/test_readme_examples.py -q`

Expected: PASS.

```bash
git add README.md README.ko.md CHANGELOG.md docs packages/bluetape-benchmark/README.md packages/bluetape-benchmark/README.ko.md packages/bluetape-benchmark/tests/test_packaging.py packages/bluetape-cache-redis/README.md packages/bluetape-cache-redis/README.ko.md packages/bluetape-cache-redis/tests/test_readme_examples.py
git commit -m "docs: document benchmark and release boundaries"
```

### Task 12: Run full verification and Type A review gates

**Files:**
- Modify only files required by concrete verification/review failures.

- [ ] **Step 1: Run targeted suites**

Run: `uv run pytest packages/bluetape-benchmark packages/bluetape-cache-redis/tests/test_coordination_benchmark.py -q`

Expected: PASS.

- [ ] **Step 2: Run serial real Redis**

Run: `uv run pytest -m testcontainers packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py -vv`

Expected: PASS and zero leaked resources.

- [ ] **Step 3: Run repository gates**

```bash
uv sync --all-packages --all-extras --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 4: Run isolated build/import smoke**

```bash
tmp_dir="$(mktemp -d)"
uv build --package bluetape-benchmark --out-dir "$tmp_dir/dist"
uv venv "$tmp_dir/venv" --python 3.13.14
uv pip install --python "$tmp_dir/venv/bin/python" --no-index --find-links "$tmp_dir/dist" bluetape-benchmark==0.1.0
"$tmp_dir/venv/bin/python" -c 'import bluetape.benchmark as b; assert b.BenchmarkReport and b.summarize_timings'
```

Expected: build/import succeeds with no runtime dependency metadata.

- [ ] **Step 5: Run all six Type A reviews and repair P0/P1**

Run performance, stability, security, Operator/Ops, Developer/API, and User/caller reviews against the complete diff. Record evidence in DoD. Any P0/P1 returns to the smallest relevant TDD task, followed by affected targeted and full gates.

- [ ] **Step 6: Confirm clean intentional commit series**

Run: `git status --short && git log --oneline origin/develop..HEAD`

Expected: clean status and issue-scoped commits only.

### Task 13: Create PR, require green CI, merge, sync, and clean up

**Files:**
- No source edits unless live review or CI exposes a concrete defect.

- [ ] **Step 1: Push and create the PR**

```bash
git push -u origin feat/issue-65-coordination-benchmarks
gh pr create --base develop --head feat/issue-65-coordination-benchmarks \
  --title "feat: add Redis coordination benchmark matrix" \
  --body-file /tmp/issue-65-pr-body.md
```

The body links `Closes #65`, summarizes the private package/matrix/evidence, lists exact verification and six review results, and ends with `## DoD Status`.

- [ ] **Step 2: Wait for every required check**

Run: `pr_number="$(gh pr view --json number --jq .number)" && gh pr checks "$pr_number" --watch`

Expected: every required check succeeds. Do not merge pending, unexpectedly skipped, cancelled, or failed checks.

- [ ] **Step 3: Repair any CI/review failure with TDD**

Inspect logs, reproduce locally, add a failing test, implement the smallest repair, rerun targeted/full gates, commit, push, and wait for a new all-green suite. Never bypass required checks.

- [ ] **Step 4: Merge only the green PR**

Run: `pr_number="$(gh pr view --json number --jq .number)" && gh pr merge "$pr_number" --squash --delete-branch`

Expected: merged to `develop`; issue #65 closes.

- [ ] **Step 5: Synchronize develop and remove obsolete worktree/branches**

```bash
git -C /Users/debop/work/bluetape4k/bluetape-py fetch origin --prune
git -C /Users/debop/work/bluetape4k/bluetape-py switch develop
git -C /Users/debop/work/bluetape4k/bluetape-py pull --ff-only origin develop
git -C /Users/debop/work/bluetape4k/bluetape-py worktree remove /Users/debop/work/bluetape4k/bluetape-py/.worktrees/issue-65-coordination-benchmarks
git -C /Users/debop/work/bluetape4k/bluetape-py branch -d feat/issue-65-coordination-benchmarks
git -C /Users/debop/work/bluetape4k/bluetape-py push origin --delete feat/issue-65-coordination-benchmarks || true
git -C /Users/debop/work/bluetape4k/bluetape-py worktree prune
```

Expected: local `develop` equals `origin/develop`; issue worktree and unnecessary local/remote feature branches are absent.

## Spec Coverage Check

- Shared stdlib-only/private package, exact exports, buildability, and publish exclusion: Tasks 1-4 and 11-12.
- Immutable schema, scalar/type validation, deterministic ordering, atomic safe writer, and documented JSON example: Tasks 2-4.
- Honest p50/p95/p99/throughput contracts and raw samples: Task 2.
- Exact smoke/full registries, totals, resource ceilings, canonical registry/lock/seed digests, fixed Redis policy, safe bytes codec, and allowlists: Task 5.
- Separate correctness/warmup/measurement phases, uninstrumented timing, post-clock verification, non-timed RSS, and six sync/async strategies: Task 6.
- Spawn-only sync containment, ordered resource ownership, repeated async cancellation, barriers, and bounded cleanup: Task 7.
- Strict CLI, clean-source and external-artifact pairing preflight, stable redacted diagnostics, exit codes, signals, and sentinel-secret scans: Task 8.
- Real Redis sequential lifecycle and zero-leak evidence: Task 9.
- Checked smoke artifact, analysis, caveats, and no capacity claim: Task 10.
- Executable #63 generation/comparison and AB/BA gates: Tasks 4, 8, and 11.
- Bilingual docs, release allowlist, PyPI defense in depth, changelog, and normal-CI/no-latency-threshold boundary: Task 11.
- Full local gates, six Type A reviews, green GitHub CI before merge, develop sync, and branch/worktree cleanup: Tasks 12-13.
