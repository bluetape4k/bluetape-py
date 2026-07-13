# Issue #65 Redis Coordination Benchmark Design

Date: 2026-07-12
Issue: #65
Work type: Type A - Full Feature
Target branch: `develop`

## Problem

The Redis load coordinator delivered by #55 and PR #62 has one non-gating,
sync-only benchmark script. That script emits a single flat JSON object, mixes
correctness checks with timing, and cannot compare the sync and async contracts
or the six strategies named by #65. It is useful as a contention sample but is
not a reusable benchmark contract for #63 or future provider work under #32.

The repository also lacks a shared Python-native benchmark package. Repeating
percentile, environment, schema, and atomic artifact logic in every provider
would make results hard to compare and easy to corrupt.

## Approved Outcome

Create an internal, reusable `bluetape-benchmark` workspace distribution and
replace the current Redis coordination sample with a versioned sync/async
benchmark matrix.

- The shared package is built and tested in CI but is not published.
- The checked-in Redis coordination evidence uses a bounded `smoke` profile.
- A larger `full` profile is available for local and future nightly execution.
- Correctness invariants are proved before timing is accepted.
- Results are machine-readable, environment-qualified snapshots, not production
  capacity or SLO claims.

## Current Evidence

- `packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py` measures
  one sync local-hit case and one 64-caller, eight-coordinator cold burst.
- It has no async runner, schema version, CLI profile, result artifact test, or
  reusable report model.
- `docs/review/artifacts/issue-50-local-cache-benchmark.json` demonstrates that
  checked-in raw samples and environment metadata are useful, but its schema is
  feature-specific and should not become an implicit cross-provider contract.
- `bluetape-testcontainers.RedisServer` is the repository-owned Redis lifecycle
  boundary and remains mandatory for real Redis benchmark runs.
- Root CI runs `uv sync --all-packages` and `uv build --all-packages`; therefore
  every workspace member must remain buildable even when it is not publishable.
- uv documents `Private :: Do Not Upload` as the PyPI rejection classifier for
  internal packages. Build validation and publication eligibility are separate
  concerns.

## Alternatives

### A. Expand the existing single script

This has the smallest initial file count, but scenario execution, sync/async
lifecycle, schema validation, CLI parsing, percentiles, and artifact writing
would become one large untestable unit. Rejected because the next provider would
copy the same infrastructure.

### B. Keep a package-local core and thin CLI

This keeps production distributions unchanged and supports focused tests, but
it still duplicates general benchmark primitives across provider packages.
Rejected after user review in favor of a shared internal package.

### C. Add an internal shared workspace package

Selected. Generic benchmark contracts live in `bluetape-benchmark`; Redis
scenario ownership stays in `bluetape-cache-redis`. The package participates in
workspace sync/build/test while publication is blocked by metadata and release
allowlisting.

## Package Boundary

### Distribution

- Directory: `packages/bluetape-benchmark`
- Distribution: `bluetape-benchmark`
- Import namespace: `bluetape.benchmark`
- Python: 3.13+
- Runtime dependencies: stdlib only
- Status: internal, pre-alpha, source-workspace only
- Classifier: `Private :: Do Not Upload`
- Root `bluetape` dependency/extra: none
- Public registry publication: forbidden for this issue and excluded from the
  release allowlist

The package is a real workspace member so `uv sync --all-packages`, workspace
pytest, Ruff, and `uv build --all-packages` prove it remains usable. It is not a
default or optional dependency of the `bluetape` meta distribution.

### Dependency Direction

`bluetape-benchmark` must not import Redis, Testcontainers, cache, codec, serde,
or another bluetape distribution. Provider-specific benchmark code may depend
on it through a non-published test/benchmark dependency group.

```text
bluetape-benchmark (stdlib only)
          ^
          |
bluetape-cache-redis benchmark group
          |
          +-- bluetape-cache-redis runtime package
          +-- bluetape-testcontainers
```

No root `bluetape/__init__.py` is created.

## Shared Benchmark API

The first API is intentionally small. It provides measurement and artifact
contracts, not a benchmark framework or plugin registry.

```python
type BenchmarkScalar = str | int | float | bool | None

@dataclass(frozen=True, slots=True, kw_only=True)
class TimingSummary:
    operations_per_sample: int
    raw_samples_ns: tuple[int, ...]
    min_ns: int
    median_ns: int
    p95_ns: int | None
    p99_ns: int | None
    max_ns: int
    throughput_ops_per_sec: float

def nearest_rank(samples: Sequence[int], percentile: float) -> int: ...

def summarize_timings(
    samples_ns: Sequence[int],
    *,
    operations_per_sample: int = 1,
) -> TimingSummary: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkEnvironment:
    python: str
    implementation: str
    platform: str
    processor: str
    cpu_count: int | None
    git_sha: str
    source_dirty: bool
    seed: int
    profile_registry_digest: str
    dependency_lock_digest: str
    dependencies: tuple[tuple[str, str], ...]
    extensions: tuple[tuple[str, BenchmarkScalar], ...] = ()

@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkScenarioResult:
    scenario_id: str
    mode: str
    parameters: tuple[tuple[str, BenchmarkScalar], ...]
    timing: TimingSummary
    metrics: tuple[tuple[str, BenchmarkScalar], ...]
    invariants: tuple[tuple[str, bool], ...]

@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkRunIdentity:
    mode_order: tuple[str, ...]
    role: str = "snapshot"
    runner_id: str | None = None
    pair_id: str | None = None
    pair_index: int | None = None
    candidate_order: str | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkReport:
    schema_version: int
    profile: str
    environment: BenchmarkEnvironment
    run: BenchmarkRunIdentity
    scenarios: tuple[BenchmarkScenarioResult, ...]
    production_capacity_claim: bool = False

def write_report(path: Path, report: BenchmarkReport) -> None: ...
def read_report(path: Path) -> BenchmarkReport: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkDelta:
    mode: str
    scenario_id: str
    case_id: str
    statistic: str
    baseline_ns: int
    candidate_ns: int
    absolute_delta_ns: int
    relative_delta_percent: float

@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkComparison:
    schema_version: int
    comparable: bool
    reasons: tuple[str, ...]
    baseline_git_sha: str
    candidate_git_sha: str
    deltas: tuple[BenchmarkDelta, ...]

def compare_reports(
    baseline: BenchmarkReport,
    candidate: BenchmarkReport,
) -> BenchmarkComparison: ...

def write_comparison(path: Path, comparison: BenchmarkComparison) -> None: ...
```

All constructors require exact primitive types where `bool` versus `int`
matters, finite floats, non-negative timings/counts, non-empty unique field
names, sorted deterministic fields, unique `(mode, scenario_id, case_id)`
identity, at least one sample, and every invariant equal to `True`. Input
mappings are copied into immutable sorted tuples so caller-owned values cannot
be mutated through the report.

Registry and lock digests are lowercase SHA-256 hex. `mode_order` contains each
selected mode exactly once. A normal evidence artifact has role `snapshot` and
all pairing fields `null`. Roles `baseline` and `candidate` require a
non-sensitive opaque `runner_id` and `pair_id` matching `[a-z0-9-]{1,64}`, a
non-negative `pair_index`, and `candidate_order` equal to `baseline-first` or
`candidate-first`. Pairing fields are all-or-none and never derive from a
hostname, home path, endpoint, or credential.

The profile-registry digest is SHA-256 of UTF-8 JSON containing the complete
registry as arrays/objects, with sorted object keys, compact separators
`(',', ':')`, decimal integers, finite JSON numbers, and no ASCII escaping. The
dependency-lock digest is SHA-256 of the exact `uv.lock` bytes. Both are
computed internally. A per-case RNG seed is the unsigned big-endian integer
from the first eight bytes of SHA-256 over the same canonical JSON encoding of
`[root_seed, profile, mode, scenario_id, case_id, phase, repetition]`.

`source_dirty` is computed from Git's tracked, staged, and untracked status. A
paired run or a snapshot written under `docs/review/artifacts/` refuses to start
unless it is `False`; exploratory stdout or output outside that directory may
record `True`. The reproducible checked-evidence sequence is: commit the runner
and tests, run from that clean commit, then commit only the generated artifact
and analysis. Staged, unstaged, and untracked-source refusal is tested.

`nearest_rank` accepts percentiles in `(0, 100]`, sorts a copy, and returns the
sample at `ceil(percentile / 100 * count) - 1`. Median uses nearest-rank p50 so
all reported percentiles use one documented method. Throughput is
`operations_per_sample * sample_count / total_sample_seconds` and requires a
positive total duration. `operations_per_sample` is the number of completed
public cache/coordinator calls in one measured repetition, not an internal
Redis command count. `summarize_timings` emits `p95_ns` only with at least 20
samples and `p99_ns` only with at least 100; otherwise the JSON value is
`null`. Smoke evidence therefore reports raw/min/median/max without pretending
that three-to-five samples support tail-latency claims.

`write_report` validates the full report before touching the filesystem. The
destination parent and each existing ancestor below the filesystem anchor must
be a real directory, not a symlink; an existing destination must be a regular
file and not a symlink. It creates an unpredictable, exclusively owned `0600`
temporary file with `tempfile.mkstemp` in that directory, writes sorted indented
JSON, flushes and fsyncs the file, closes it, and then uses `os.replace`.
Concurrent valid writers use last-complete-writer-wins semantics; each writer
may clean up only its own temporary path. POSIX implementations fsync the parent
directory after replacement for rename durability; on platforms without that
operation the guarantee is limited to atomic visibility and process-level
failure recovery. Validation or pre-replace write failure preserves an
existing destination.

## Redis Benchmark Architecture

### Files

- `packages/bluetape-benchmark/src/bluetape/benchmark/_comparison.py`: strict
  report loading, comparison gates, and delta assembly
- `packages/bluetape-benchmark/src/bluetape/benchmark/compare.py`: internal
  `python -m` comparison CLI
- `packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py`: thin CLI
- `packages/bluetape-cache-redis/benchmarks/_coordination_matrix.py`: profile,
  recorder, sync/async runner, invariant, and report assembly
- `packages/bluetape-cache-redis/tests/test_coordination_benchmark.py`: pure
  profile/schema/invariant/CLI contract tests
- `packages/bluetape-cache-redis/tests/test_coordination_benchmark_integration.py`:
  serial Redis smoke proof for sync and async

The private matrix module remains outside `src/` and is not included in the
`bluetape-cache-redis` wheel. Tests load it from the repository benchmark path;
production imports never depend on benchmark code.

### CLI

```bash
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
  --profile smoke \
  --mode both \
  --output docs/review/artifacts/issue-65-redis-coordination-benchmark.json \
  --seed 20260712 \
  --role snapshot
```

Supported arguments are:

- `--profile smoke|full` (required)
- `--mode sync|async|both` (default `both`)
- repeatable `--scenario <id>` filters from the fixed scenario registry
- `--output <path>` (required; `-` is allowed for exploratory stdout)
- `--seed <int>` (always required)
- `--role snapshot|baseline|candidate` (default `snapshot`)
- `--runner-id`, `--pair-id`, `--pair-index`, and
  `--candidate-order baseline-first|candidate-first` (all required exactly for
  baseline/candidate and forbidden for snapshot)

Unknown scenarios, duplicate filters, invalid seeds, non-file output parents,
or an empty selected matrix fail before Redis starts. JSON is the only stdout
payload when `--output -`; progress and errors use stderr.

With `artifact_dir` set to an absolute directory outside the source worktree,
the generic comparison command is:

```bash
uv run python -m bluetape.benchmark.compare \
  --baseline "$artifact_dir/issue-63-pair-000-baseline.json" \
  --candidate "$artifact_dir/issue-63-pair-000-candidate.json" \
  --output "$artifact_dir/issue-63-pair-000-comparison.json"
```

It loads schema-v1 reports through `read_report`, applies every comparison
gate, and writes `BenchmarkComparison` atomically. Comparable output has empty
`reasons` and fixed per-scenario `median_ns`, optional `p95_ns`, absolute-ns,
and relative-percent delta fields. Non-comparable output has an allowlisted,
sorted reason code tuple and empty `deltas`, exits 4, and never prints or writes
percentage deltas. Parse/input failure exits 2 and preserves an existing output.
Delta rows are ordered by mode/registry/case/statistic; `absolute_delta_ns` is
candidate minus baseline and relative percent is
`absolute_delta_ns / baseline_ns * 100`. Reason codes are fixed identifiers for
each named comparison gate and never contain input values or exception text.

### Redis Report And Codec Boundary

The generic package accepts bounded scalar fields, but the Redis assembler is
fail-closed. Its exact parameter allowlist is `case_id`, `callers`,
`coordinators`, `keys`, `payload_bytes`, `loader_delay_seconds`, `warmups`, and
`repetitions`; its metric allowlist is `correctness_loader_count`,
`correctness_redis_commands`, `correctness_active_result_bytes`,
`correctness_completed_result_bytes`, `correctness_overlap_observed`, and
nullable `process_high_water_bytes`; its environment extension allowlist is
`redis_version`, `redis_image_digest`, `redis_configuration_profile`,
`coordination_policy_id`, and `coordination_policy_digest`.
String scalars must be printable ASCII, at most 128 characters, and match the
field-specific identifier/version grammar.

Endpoint, username, password, credentials, namespace, raw key, owner token,
payload, exception text, current directory, home directory, and hostname are
forbidden in artifact fields, stdout, stderr, and temporary filenames. A
sentinel-secret test injects those values through provider, codec, loader, and
failure paths and scans every output surface before a report is accepted.

Completed-result cases use a benchmark-only bytes codec. It accepts exactly
format `raw-bytes`, version `1`, content type `application/octet-stream`, and
`TrustProfile.UNTRUSTED` (wire value `untrusted`); `benchmark-ephemeral` is only
a scenario/environment label, not a trust-profile value. The codec validates
the declared and actual payload sizes against the 15,728,640-byte ceiling, and
returns `payload.data` without additional decoded-value construction. The
existing envelope and serialized-payload objects remain part of the wire
contract. The codec never imports or invokes pickle, Fory, serde, dynamic
classes, or caller-provided deserializers. Forged metadata,
`trusted_internal` or unknown trust values, unsupported formats, mismatched
lengths, and oversize values fail as redacted invariant categories without
echoing metadata or bytes.

## Scenario Contract

Every profile contains the same six stable scenario IDs for sync and async.
Case IDs distinguish the bounded parameter selections within a scenario.

| Scenario ID | Purpose | Required invariant |
|---|---|---|
| `local-only` | Independent local caches without Redis coordination | loader count equals independent cold caches; Redis commands are zero |
| `local-hit` | Coordinator local-hit fast path | loader count and Redis commands are zero |
| `single-coordinator` | Same-key in-process collapse | one loader execution and zero waiter errors |
| `multi-coordinator` | Same-key collapse across independent coordinators | one loader execution and all callers receive equal bytes |
| `completed-reuse` | Reuse a matching completed result | waiter loader count is zero and completed-result bytes are observed |
| `unrelated-keys` | Independent progress under contention | loader count equals key count and loader overlap is observed |

### Smoke Profile

The checked-in profile is small enough for local reproduction while still
covering all strategies in both modes. Its registry is exactly:

| Scenario | Case ID | Callers | Coordinators/caches | Keys | Payload bytes | Delay seconds | Operations/sample | Warmups | Repetitions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `local-only` | `moderate-small-short` | 8 | 4 | 1 | 1,024 | 0.005 | 8 | 1 | 5 |
| `local-hit` | `steady-small` | 1 | 1 | 1 | 1,024 | 0 | 1,000 | 1 | 5 |
| `single-coordinator` | `moderate-small-short` | 8 | 1 | 1 | 1,024 | 0.005 | 8 | 1 | 5 |
| `multi-coordinator` | `moderate-small-short` | 8 | 4 | 1 | 1,024 | 0.005 | 8 | 1 | 5 |
| `completed-reuse` | `moderate-small-immediate` | 8 | 4 | 1 | 1,024 | 0 | 8 | 1 | 5 |
| `unrelated-keys` | `moderate-small-short` | 8 | 4 | 4 | 1,024 | 0.005 | 8 | 1 | 5 |

This produces 12 scenario results, 60 measured samples, and 10,400 completed
public calls across both modes: per mode the five burst scenarios perform eight
calls per sample (200 total) and local-hit performs 1,000 calls per sample
(5,000 total). Tail percentiles are `null` because each result has five samples.

### Full Profile

The full profile is a fixed representative registry, not a Cartesian product.
It retains the six smoke parameter tuples per mode and adds exactly these six:

| Scenario | Case ID | Callers | Coordinators/caches | Keys | Payload bytes | Delay seconds | Operations/sample |
|---|---|---:|---:|---:|---:|---:|---:|
| `local-only` | `high-small-long` | 64 | 8 | 1 | 1,024 | 0.050 | 64 |
| `local-hit` | `single-near-boundary` | 1 | 1 | 1 | 15,728,640 | 0 | 3 |
| `single-coordinator` | `moderate-medium-immediate` | 16 | 1 | 1 | 65,536 | 0 | 16 |
| `multi-coordinator` | `high-medium-short` | 64 | 8 | 1 | 65,536 | 0.005 | 64 |
| `completed-reuse` | `single-near-boundary` | 1 | 1 | 1 | 15,728,640 | 0 | 1 |
| `unrelated-keys` | `high-empty-immediate` | 64 | 8 | 8 | 0 | 0 | 64 |

The retained smoke tuples use their smoke values except that `local-hit` uses
10,000 operations per sample. Full uses three warmups and 20 measured
repetitions for every result except the two near-boundary results per mode,
which use three repetitions. Thus `both` is exactly 24 results, 412 measured
samples, 409,944 completed public calls, and 72 warmups; p95 is available for
the 20 normal results and p99 remains `null` everywhere. A registry test locks
every case ID, tuple, repetition count, operations count, and these totals.

The hard workload ceilings are 24 results, 64 callers, eight coordinators or
caches, eight distinct keys, 15,728,640 payload bytes, 32 MiB nominal aggregate
payload bytes in flight per case, 30 seconds per normal case, 120 seconds per
near-boundary case, 120 seconds for smoke, and 900 seconds for full. The runner
rejects a registry exceeding a ceiling before Redis starts. These are safety
limits, not capacity claims.

### Fixed Redis Coordination Policy

Every case uses policy ID `redis-coordination-benchmark-v1`. Standard sync and
async Redis connection pools use `decode_responses=False`,
`socket_connect_timeout=0.1`, `socket_timeout=0.1`,
`retry_on_timeout=False`, `retry_on_error=()`, `retry=None`, and
`max_connections=128`; `BlockingConnectionPool` and opaque/custom pools are
forbidden. The discovered `RedisCommandPolicy` must equal connect timeout 0.1,
socket timeout 0.1, and max retries zero before Redis work begins.

Every coordinator uses `RedisLoadOptions` with the per-repetition digest-safe
namespace plus `lease_ttl=2.0`, `result_ttl=2.0`,
`poll_interval=0.001`, `max_poll_interval=0.01`, `wait_timeout=2.0`,
`max_attempts=3`, `max_polls=100`, and `redis_io_timeout=0.4`. The report
serializes `coordination_policy_id` and a SHA-256 digest of canonical JSON for
all values except namespace; both are fixed Redis environment fields and #63
equality gates. Tests reject policy drift, retrying, unbounded, blocking, or
opaque clients, and any digest or artifact that does not match constructed
options.

The bytes payload codec is composed with `BinaryEnvelopeFormat` and
`ResultEnvelopeCodec`, both using `max_encoded_size=16,777,216`; the largest
15,728,640-byte payload leaves bounded envelope headroom. Compression is absent
and the reader decompressor registry is empty. These codec settings are part of
the same policy digest.

## Measurement And Instrumentation

Sync uses threads and async uses tasks, but both consume the same immutable
scenario specs and emit the same result fields.

A recording provider wraps only benchmark-owned providers during the separate
correctness phase and counts:

- acquisition commands;
- snapshot commands;
- publication commands;
- cleanup commands;
- total Redis commands;
- active snapshot result bytes;
- completed snapshot result bytes.

It delegates to the real fixed-script providers and does not change production
provider behavior. The recorder is concurrency-safe and exposes an immutable
snapshot after correctness. Raw keys, namespaces, owner tokens, endpoints,
payloads, and exception text are never serialized.

Each case uses fresh resources for three distinct phases: correctness,
warmups, and measurement. Correctness uses the recorder and counting loader to
prove loader, command, byte, equality, and overlap invariants. Warmups and
measurement use unwrapped production providers and a loader with no recorder,
counter, tracing, allocation probe, or benchmark lock on the timed path.
Instrumentation metrics serialized beside timing come only from correctness
and are explicitly labeled `correctness_*`; they are not claimed to describe a
timed repetition.

Warmup and measurement share one freshly created, preconnected set of
unwrapped production clients/providers. Connection establishment and readiness
complete before warmup and before any measured clock; unique repetition
namespaces preserve cold/warm scenario semantics without reconnecting.

Workers/tasks and their two-phase ready/release barrier are created before the
clock. The runner waits for every caller to report ready, starts the monotonic
clock, releases all callers, waits for bounded completion and joins/converges
them, and stops the clock immediately after the last join. Result equality,
loader metrics, command metrics, and invariant verification occur after the
timestamp. Readiness, first scheduling, setup, seed publication, result
comparison, and teardown are excluded. A failed join rejects the repetition;
it is never a latency sample.

Random choices use an injected `random.Random` whose seed is derived from
`(root_seed, profile, mode, scenario_id, case_id, phase, repetition)` with a
stable hash. Benchmark code never mutates module-global randomness. This makes
case filtering and ordering deterministic; it does not claim to control OS,
Python, network, or Redis scheduling.

Memory evidence is a separate non-timed phase. It may record
`process_high_water_bytes` from an OS process-resource API when comparable on
the current platform, but never enables `tracemalloc` or another allocation
probe during latency measurement. The field is nullable and cannot be compared
across unlike platforms. Per-object allocation analysis is explicitly outside
issue #65.

## Redis Lifecycle

One `RedisServer` is owned for a benchmark invocation. It is an isolated,
ephemeral, unauthenticated test container; the CLI cannot accept or reuse an
external or production Redis URL, credentials, or client. Cases execute
sequentially; sync completes before async when mode is `both`. Each case uses a
unique digest-safe namespace derived from profile, mode, scenario, case,
repetition, and seed. Connection details pass only through private in-process
or child-process configuration and never enter the report or diagnostics.

The ready-barrier budget is 5 seconds, each loader and Redis operation is
bounded by the provider's case deadline, normal join/convergence is 30 seconds,
near-boundary join/convergence is 120 seconds, and cleanup is 10 seconds.
Release gates are abortable so a setup or readiness failure wakes callers
without starting work.

Because Python cannot cancel a blocked thread, every sync case runs in a fresh
child process created from an explicit `multiprocessing.get_context("spawn")`.
The child receives only immutable case data and minimal serializable private
connection configuration, closes unused IPC endpoints, and never inherits or
receives a provider, Redis client, Docker client, or `RedisServer` object. The
child owns its clients, providers, and worker threads. On a
deadline the parent first signals the abort gate and allows the bounded cleanup
window; if the child does not report zero live threads and exit, the parent
terminates it, waits five seconds, then kills and joins it within another five
seconds. The parent never closes a client/provider beneath a live child thread.
Only after child convergence does normal teardown close providers, separately
owned clients, and finally the parent-owned `RedisServer`. Regression tests
inject readiness, loader, Redis-call, and join failures and require zero live
child processes/threads.

For async, the runner retains the first `CancelledError`, stops task admission
and aborts release gates, cancels every owned unfinished task exactly once, and
awaits all of them with `gather(..., return_exceptions=True)` inside one
runner-owned shielded cleanup task. It then closes providers, separately owned
clients, and finally Redis. Repeated cancellation awaits the same cleanup task;
after convergence the first cancellation is re-raised. Cleanup failures are
attached as redacted diagnostic categories and never replace the original
cancellation. Tests cover cancellation during release, loader/Redis wait, task
convergence, and provider close, including repeated cancellation and zero
pending tasks.

Testcontainers and real Redis commands never run concurrently with another
repository benchmark lane.

### CLI Signals And Diagnostics

The first SIGINT/`KeyboardInterrupt` enters the same abort protocol: it aborts
barriers, converges or terminates/kills a sync child, or cancels and shieldedly
converges async tasks, then closes providers, clients, and Redis in order. It
preserves any existing artifact, emits one redacted `interrupted` diagnostic,
and exits 130. SIGTERM performs the same bounded best-effort cleanup and exits
143. A second SIGINT/SIGTERM during cleanup immediately exits with its
conventional code; this explicit escalation may leave OS/container cleanup to
Testcontainers/Docker and is never reported as successful.

Every stderr failure is one sorted compact JSON line prefixed
`bluetape-benchmark-error `. Its exact fields are `code`, `category`, `mode`,
`scenario_id`, `case_id`, `phase`, and `repetition`; inapplicable context is
`null`, repetition is a bounded non-negative integer, and identifiers must come
from the fixed registries. Phase is `startup`, `correctness`, `warmup`,
`measurement`, `cleanup`, `comparison`, or `write`. Categories are exactly `input-invalid`,
`source-dirty`, `docker-unavailable`, `redis-startup`, `correctness-failed`,
`deadline`, `live-worker`, `redis-failed`, `provider-failed`, `codec-failed`,
`cancelled`, `interrupted`, `cleanup-failed`, `artifact-write-failed`, and
`not-comparable`. Exception messages and all forbidden sensitive fields remain
excluded. `code` is the stable `BTBENCH_` prefix plus the category uppercased
with hyphens replaced by underscores, for example
`BTBENCH_LIVE_WORKER`.

CLI exit codes are 0 success, 2 input/preflight/parse failure, 3 benchmark,
correctness, deadline, provider, codec, or cleanup failure, 4 not comparable,
5 Docker/Redis environment unavailable, 6 artifact-write failure, 130 SIGINT,
and 143 SIGTERM. Tests assert exact records and codes for every category,
including interrupts during Redis startup, sync-child wait, async wait,
cleanup, and pre-replace writing; all first-signal paths require no partial
report and zero live child/container/task.

## Failure Semantics

1. **Invalid profile or CLI input:** fail before Redis startup and do not create
   an output file.
2. **Correctness invariant failure:** abort the case, emit a concise redacted
   stderr diagnostic, return non-zero, and preserve any existing artifact.
3. **Timeout or live worker/task:** use the containment and ordered convergence
   protocol above, return non-zero, and never classify the run as latency.
4. **Redis/provider/codec failure:** preserve the stable public exception type
   internally, emit only a redacted benchmark failure category, and do not
   serialize backend exception text.
5. **Async cancellation:** preserve and rethrow the first `CancelledError` only
   after shielded owned-task/provider/client convergence; never convert it to a
   successful partial report.
6. **Atomic write failure:** remove only the writer-owned temporary file and
   preserve the previous checked-in report unless another complete writer won
   the documented last-complete-writer race.
7. **Queue/recorder inconsistency:** fail the invariant phase rather than infer
   missing command or byte counts.
8. **Process signal:** follow the signal contract above; a first signal never
   publishes a partial report and a second signal is explicit hard escalation.

No scenario silently retries a failed benchmark repetition. Redis provider
retry policy remains zero and every wait is bounded.

## JSON Schema V1

The serialized top-level shape is:

```json
{
  "environment": {
    "cpu_count": 10,
    "dependency_lock_digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "dependencies": [["redis", "8.0.1"]],
    "extensions": [
      ["coordination_policy_digest", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
      ["coordination_policy_id", "redis-coordination-benchmark-v1"],
      ["redis_configuration_profile", "ephemeral-default"],
      ["redis_image_digest", "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
      ["redis_version", "8.0.1"]
    ],
    "git_sha": "0123456789abcdef0123456789abcdef01234567",
    "implementation": "CPython",
    "platform": "darwin-arm64",
    "processor": "arm",
    "profile_registry_digest": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    "python": "3.13.14",
    "seed": 20260712,
    "source_dirty": false
  },
  "production_capacity_claim": false,
  "profile": "smoke",
  "run": {
    "candidate_order": null,
    "mode_order": ["sync"],
    "pair_id": null,
    "pair_index": null,
    "role": "snapshot",
    "runner_id": null
  },
  "scenarios": [
    {
      "invariants": [["loader_count", true]],
      "metrics": [["correctness_loader_count", 1]],
      "mode": "sync",
      "parameters": [
        ["callers", 8],
        ["case_id", "moderate-small-short"],
        ["coordinators", 4],
        ["keys", 1],
        ["loader_delay_seconds", 0.005],
        ["payload_bytes", 1024],
        ["repetitions", 5],
        ["warmups", 1]
      ],
      "scenario_id": "multi-coordinator",
      "timing": {
        "max_ns": 1,
        "median_ns": 1,
        "min_ns": 1,
        "operations_per_sample": 8,
        "p95_ns": null,
        "p99_ns": null,
        "raw_samples_ns": [1, 1, 1, 1, 1],
        "throughput_ops_per_sec": 8000000000.0
      }
    }
  ],
  "schema_version": 1
}
```

The JSON writer sorts object keys. Scenario order is mode (`sync`, `async`),
then the fixed registry order, then case ID. Metric/parameter/invariant entries
are sorted by name. Environment timestamps are excluded because the artifact
must compare content without a non-semantic clock diff; the git SHA and full
clean-source environment identify the snapshot. A test extracts this JSON block
and validates it as a smoke-profile schema-v1 result so the documented metric
allowlist, sample count, and derived fields cannot drift.

## Tests

### Shared package

- exact exports and Python 3.13 typing;
- nearest-rank p50/p95/p99 success, unsorted input, singleton, empty, invalid
  percentile, `bool`, negative, and caller-list preservation;
- timing summary count, throughput, zero-duration rejection, non-finite values,
  immutable raw samples, and p95/p99 minimum-sample nullability;
- exact scalar/name validation, duplicate fields, duplicate scenarios, failed
  invariant rejection, deterministic ordering, and `production_capacity_claim`
  fixed to `False`;
- SHA-256 registry/lock digests, mode-order uniqueness, snapshot null pairing,
  paired-field all-or-none validation, role/order enums, opaque identifier
  grammar, and caller-owned run-value preservation;
- canonical registry JSON, exact lock bytes, per-case seed vectors, dirty-source
  detection, report round-trip/loading, all comparison gates, AB/BA parity,
  non-comparable empty deltas/exit 4, and atomic comparison output;
- atomic writer success, invalid report, serialization failure, replacement,
  previous-file preservation, exclusive temp ownership, concurrent writers,
  destination/parent symlinks, non-regular targets, permissions, directory
  fsync behavior, and temporary-file cleanup;
- packaging metadata proves stdlib-only runtime, private classifier, namespace
  import, and no meta-distribution dependency/extra.

### Redis matrix

- exact smoke/full registry membership and value coverage;
- exact fixed Redis client/load policy construction, discovery, digest, report
  fields, drift rejection, and #63 policy comparison gate;
- sync/async result field parity;
- CLI success, filtering, stdout, invalid profile/scenario/seed/output;
- recorder command and active/completed result-byte accounting;
- exact Redis field allowlists and sentinel-secret absence from JSON, stdout,
  stderr, diagnostics, and temporary filenames;
- safe bytes-codec success plus `trusted_internal`, unknown trust value, forged
  metadata, size mismatch, and oversize rejection without raw metadata or
  payload disclosure;
- every scenario invariant plus injected loader/result/timeout/cleanup failure;
- abortable ready/release barriers, child-process thread containment, ordered
  teardown, bounded thread/task convergence, and repeated async cancellation;
- explicit spawn context/minimal child config/IPC ownership plus exact signal
  diagnostics and exit codes during startup, wait, cleanup, and artifact write;
- derived-RNG repeatability under case filtering and registry reordering;
- snapshot/paired dirty-tree refusal for staged, unstaged, and untracked source;
- baseline/candidate CLI generation, full report loading, comparable and every
  non-comparable result, comparison CLI output, filenames, and exit codes;
- exact separate-clean-worktree/external-artifact sequencing, proving the
  baseline output cannot dirty or block candidate preflight;
- serial Testcontainers smoke execution for sync and async;
- checked-in JSON parses as schema v1 and contains exactly the 12 smoke results.

Timing assertions use only positive, bounded structural facts. No latency or
throughput threshold is a normal CI gate.

## Documentation And Evidence

- Add aligned `packages/bluetape-benchmark/README.md` and `README.ko.md` with
  source-workspace, internal-only, and non-publishable status.
- Update root `README.md` and `README.ko.md` package status tables.
- Update `packages/bluetape-cache-redis/README.md` and `README.ko.md` with smoke
  and full commands, schema, caveats, and #63 before/after procedure.
- Both package README pairs state Python/Docker/Testcontainers prerequisites,
  smoke/full 120/900-second upper bounds and payload/process ceilings, exit-code
  and existing-output preservation behavior, dirty-source rules, signal
  recovery, and that `correctness_*` metrics are untimed invariant evidence.
- Update `docs/package-layout.md`, `docs/release.md`, and
  `docs/release/release-guide.md` with the private package exclusion.
- Update `CHANGELOG.md`.
- Check in
  `docs/review/artifacts/issue-65-redis-coordination-benchmark.json`.
- Add
  `docs/research/2026-07-12-issue-65-redis-coordination-benchmark-analysis.md`
  with environment, exact commands, result table, trade-offs, caveats, and no
  production capacity claims.

No chart or diagram asset is required because the primary artifact is JSON and
the comparison is compact enough for a Markdown table.

### Issue #63 Paired Comparison Protocol

Issue #63 must produce separate baseline and candidate artifacts; it never
overwrites one result with another. Each artifact serializes the registry and
lock digests plus `BenchmarkRunIdentity`. A percentage comparison is valid only
when schema version, profile registry digest, case tuples, seed, mode order,
opaque runner ID, pair ID/index, Python implementation/version,
platform/processor/CPU count, dependency-lock digest, Redis version, Redis
image digest, Redis configuration profile, coordination policy ID/digest, and
clean source state are equal. Among environment and run-identity fields, Git
SHA and role are required to differ and all others must match; scenario timings
may of course differ.

One pair is two whole benchmark invocations, not interleaved samples. Mode order
is fixed (`sync` then `async`). Even `pair_index` requires `baseline-first`; odd
index requires `candidate-first`. Repeated evaluation creates separately named
artifact pairs with successive indices, which provides explicit AB/BA order
without pretending that aggregate artifacts prove repetition-level scheduling.
The runner ID is operator-supplied, non-sensitive, and opaque; it identifies a
stable comparison runner without serializing hostname, path, or hardware IDs.

For even pair 0, create separate clean baseline/candidate worktrees on the same
named runner and one shared artifact directory outside both Git worktrees. The
runner rejects a paired output path contained by either worktree. The exact
generation sequence is:

```bash
artifact_dir="$(mktemp -d "${TMPDIR:-/tmp}/bluetape-py-issue-63-pair-000.XXXXXX")"

# Run from the clean baseline worktree.
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
  --profile full --mode both --seed 20260712 --role baseline \
  --runner-id runner-a --pair-id issue-63-pair-000 --pair-index 0 \
  --candidate-order baseline-first \
  --output "$artifact_dir/issue-63-pair-000-baseline.json"

# Run from the separate clean candidate worktree.
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
  --profile full --mode both --seed 20260712 --role candidate \
  --runner-id runner-a --pair-id issue-63-pair-000 --pair-index 0 \
  --candidate-order baseline-first \
  --output "$artifact_dir/issue-63-pair-000-candidate.json"

uv run python -m bluetape.benchmark.compare \
  --baseline "$artifact_dir/issue-63-pair-000-baseline.json" \
  --candidate "$artifact_dir/issue-63-pair-000-candidate.json" \
  --output "$artifact_dir/issue-63-pair-000-comparison.json"
```

The comparison command is the `python -m bluetape.benchmark.compare` invocation
defined in the CLI section. Odd pair 1 uses filenames/pair ID/index ending 001,
`candidate-first`, and runs the candidate command first.

The comparison tool verifies opposite baseline/candidate roles and rejects
missing/null, parity-invalid, or unequal gates as “not comparable”; it does not
compute a percentage anyway. Comparable output retains
both raw sample arrays and reports absolute nanosecond and relative percentage
deltas for median and available p95 only. p99 is not compared by this registry.
The result is evidence about this bounded workload on this machine, not a
capacity, SLO, or general performance claim.

## Release And CI Boundary

- Add `bluetape-benchmark` to workspace members and workspace sources, but not
  root dependencies or any `bluetape` extra.
- Add the exact internal dependency only to the cache-redis non-published
  test/benchmark group.
- Refresh `uv.lock`.
- `uv build --all-packages` must build the private package; buildability is not
  publication authority.
- The release guide uses an explicit publish allowlist that excludes
  `bluetape-benchmark`.
- `Private :: Do Not Upload` is a defense-in-depth PyPI rejection guard.
- A fail-closed release preflight test enumerates every publishable workspace
  distribution and proves `bluetape-benchmark` is absent. An unknown workspace
  distribution fails the preflight until explicitly classified; the PyPI
  classifier is not treated as protection for another registry.
- No tag, release, workflow dispatch, or registry publication is authorized.
- Normal CI runs unit/schema checks and the existing bounded Redis integration
  lane. The full benchmark matrix is not added to normal CI; future recurring
  heavy execution belongs to #32.

Rollback removes the private workspace member/source/dependency-group entries,
restores the previous coordination script, refreshes `uv.lock`, and deletes only
issue #65 docs/artifacts. Production package APIs and Redis data do not migrate.

## Acceptance Mapping

| Issue requirement | Design evidence |
|---|---|
| Six sync/async strategies | Fixed scenario registry with equivalent fields |
| Bounded workload matrix | Explicit smoke and non-Cartesian full profiles |
| Machine-readable JSON | Immutable schema v1 and atomic writer |
| Correctness separate from timing | Invariant phase before warmup/measurement |
| Real Redis and serial lifecycle | One owned `RedisServer`, sequential cases, bounded cleanup |
| Warmups/repetitions/percentiles | Profile values plus nearest-rank definition |
| Loader/command/result-byte metrics | Recording providers and fixed metric names |
| Checked analysis | JSON artifact and Markdown analysis path |
| #63 comparison | Stable scenario filters and documented before/after command |
| No noisy CI threshold | Structural CI checks only; full matrix deferred to #32 |
| Non-published shared package | Private classifier, no meta dependency, release allowlist exclusion |

## Definition Of Done

- The shared package boundary is stdlib-only, internal, buildable, and guarded
  against publication.
- Sync and async smoke/full profiles share one scenario contract and schema.
- All correctness, failure, lifecycle, packaging, schema, and artifact tests
  pass.
- The checked smoke artifact contains 12 valid scenario results and the analysis
  states its exact environment and limitations.
- `uv sync --all-packages --all-extras --locked`, targeted and full pytest,
  Ruff check/format, `uv build --all-packages`, isolated import/metadata smoke,
  `actionlint`, and `git diff --check` pass.
- Spec, plan, implementation, and live PR review converge at P0=0 and P1=0.
- Required GitHub CI succeeds before merge.
- After merge, local `develop` is synchronized and the issue worktree plus local
  and remote feature branches are removed.
