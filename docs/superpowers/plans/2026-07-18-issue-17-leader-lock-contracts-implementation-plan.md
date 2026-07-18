# Issue #17 Leader Election and Distributed Lock Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stdlib-only backend-neutral leader contract distribution and a bounded single-primary Redis proof adapter with sync/async owner-safe locking, scoped renewal, fencing, cancellation cleanup, quantitative concurrency evidence, isolated packaging proof, and bilingual operational guidance.

**Architecture:** `bluetape.leader` owns generic options, immutable lease/result values, sanitized errors, and sync/async protocols parameterized by lease capability. `bluetape.leader.redis` composes exact pinned redis-py clients, SHA-256-derived same-slot keys, fixed `EVALSHA -> EVAL` Lua operations, explicit handle states, and separate synchronous/asyncio lifecycle owners. The design follows `bluetape4k-leader`'s core/backend split while keeping Python cancellation, typing, packaging, and borrowed-client rules authoritative.

**Tech Stack:** Python 3.13.14, stdlib dataclasses/typing/asyncio/threading/secrets/hashlib/hmac/ipaddress, redis-py 8.0.1, Redis 8 Testcontainers, uv workspace and `uv_build`, pytest, pytest-asyncio, Ruff, isolated wheel installs, and Lore commits.

---

## Approved Inputs and Stop Boundary

- Approved specification:
  `docs/superpowers/specs/2026-07-18-issue-17-leader-lock-contracts-design.md`
- Specification review:
  `docs/review/2026-07-18-issue-17-leader-lock-contracts-spec-review.md`
- Target issue/milestone: #17 / `0.2.0`
- Target repository: `bluetape4k/bluetape-py`
- Base/head: `develop` / `feat/issue-17-leader-lock-contracts`
- Core distribution/import: `bluetape-leader==0.1.0` / `bluetape.leader`
- Adapter distribution/import: `bluetape-leader-redis==0.1.0` /
  `bluetape.leader.redis`
- Core runtime dependencies: none
- Adapter runtime dependencies: `bluetape-leader==0.1.0`, `redis==8.0.1`
- Meta extras: `bluetape[leader]`, `bluetape[leader-redis]`; default install
  remains exactly `bluetape-core==0.1.0`
- The user approved the revised specification and implementation-planning step.
- PR creation, push, merge, issue closure, tag, release, publication, workflow
  dispatch, and destructive cleanup are not authorized by this plan. Each
  applicable external side effect remains a later explicit gate.

## Execution Rules

- Work only in
  `.worktrees/issue-17-leader-lock-contracts` on
  `feat/issue-17-leader-lock-contracts`.
- Apply `$bluetape-py-patterns`, `$test-driven-development`, and the mandatory
  micro-cycle to every behavior family: write one focused test, run RED for the
  intended missing behavior, implement the minimum, run GREEN, then run the
  owning test file.
- A RED test that passes, imports the wrong installed package, or errors before
  its intended assertion is invalid. Repair it and rerun until the expected
  failure is visible.
- Never expose a logical lock name, node ID, prefix, Redis key, URL, client,
  owner token, lease record, command argument, credential, raw redis-py error,
  or fencing value through package-generated `str`, `repr`, traceback, note,
  or log output.
- Keep `bluetape-leader` stdlib-only. Keep `bluetape-leader-redis` independent
  of cache, serde, compression, logging, observability, resilience, and
  testcontainers at runtime.
- Do not weaken the approved exact-client, zero-retry, numeric-IP/Unix-socket,
  no-TLS, zero-health-check, no-callback boundary while implementing bounded
  sync renewal. If pinned redis-py internals do not expose a required proof,
  stop that task and return to design review instead of guessing.
- Production commits contain complete executable behavior and tests. No TODO,
  placeholder branch, unbounded retry, permanent campaign, detached task,
  daemon thread, global registry, package-owned client, Redlock, group/slot,
  strategic election, or additional backend is allowed.
- Each commit follows the Lore protocol and records exact RED/GREEN or
  verification evidence.
- After rebase, conflict resolution, lock regeneration, or review correction,
  all evidence tied to the old head is stale. Rerun affected tests and the
  exact-head review/verifier gates.
- The known full-suite Redis benchmark startup failure remains a separate
  approved baseline exception. Targeted Issue #17 failures are never dismissed
  under that exception.

## Artifact Map

| Responsibility | Files |
|---|---|
| Workspace/package registration | root `pyproject.toml`, `packages/bluetape-leader/pyproject.toml`, `packages/bluetape-leader-redis/pyproject.toml`, `packages/bluetape/pyproject.toml`, `uv.lock` |
| Core errors and options | `packages/bluetape-leader/src/bluetape/leader/_errors.py`, `_options.py` |
| Core lease/result values | `packages/bluetape-leader/src/bluetape/leader/_values.py`, `_results.py` |
| Generic protocols/public API | `packages/bluetape-leader/src/bluetape/leader/_contracts.py`, `__init__.py` |
| Redis keys/records/client timing | `packages/bluetape-leader-redis/src/bluetape/leader/redis/_keys.py`, `_support.py` |
| Redis Lua and runner | `packages/bluetape-leader-redis/src/bluetape/leader/redis/_scripts.py` |
| Sync lock/elector | `packages/bluetape-leader-redis/src/bluetape/leader/redis/_lock.py`, `_elector.py` |
| Async lock/elector | `packages/bluetape-leader-redis/src/bluetape/leader/redis/_async_lock.py`, `_async_elector.py` |
| Adapter public API | `packages/bluetape-leader-redis/src/bluetape/leader/redis/__init__.py` |
| Core tests | `packages/bluetape-leader/tests/test_*.py` |
| Adapter fake/unit tests | `packages/bluetape-leader-redis/tests/test_*_unit.py`, `tests/_support.py` |
| Real Redis evidence | `packages/bluetape-leader-redis/tests/test_*_integration.py` |
| Wheel/meta evidence | `packages/bluetape/tests/test_leader_wheel_isolation.py`, `test_leader_readmes.py` |
| Publish classifier | `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`, `docs/release/pypi-preflight.md` |
| Required PR/push CI | `.github/workflows/ci.yml` dedicated `leader-redis` job with no-skip JUnit assertion |
| User/contributor docs | both package README pairs, root README pairs, `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` |
| Review and lesson evidence | `docs/review/2026-07-18-issue-17-leader-lock-contracts-*.md`, `docs/lessons/2026-07-18-issue-17-leader-lock-contracts.md` |

## Spec Coverage

| Specification requirement | Owning tasks |
|---|---|
| Two distributions, namespace extension, exact dependencies/extras | 1, 9 |
| Sanitized errors, backend-neutral options, immutable leases/results | 1-3 |
| Generic fencing-capable sync/async protocols | 3 |
| Exact client/configuration timing proof and safe keys/records | 4 |
| Atomic acquire/renew/release, corruption, NOSCRIPT, uncertainty | 4-6 |
| Explicit handle state, entry proof, manual/scoped release semantics | 5-6 |
| Sync worker lifecycle and quantitative thread ceiling | 5, 8 |
| Async cancellation, retained tasks, terminal cleanup | 6, 8 |
| Sync/async elector result and composite failure matrices | 7 |
| Real Redis expiry, contender, fencing, stale-holder evidence | 8 |
| English/Korean usage, caveats, topology, ACL, migration, rollback | 9 |
| Full commands, P0/P1 review, verifier, Type A lesson, PR gate | 10 |

## Step 3-P Risk Prediction

| Risk | Trigger | Prevention/proof | Rollback boundary |
|---|---|---|---|
| Secret capability leak | raw redis-py error or dataclass/client repr reaches caller | fixed redacted repr, sanitized `from None`, canary scan over str/repr/traceback/notes/properties | revert owning error/support commit |
| Backend-neutral core becomes Redis-shaped | millisecond or redis-py rule appears in `bluetape.leader` | core sub-ms acceptance test; Redis-only rejection in adapter tests | revert core task before adapter work |
| Stale owner deletes successor | unconditional delete or owner comparison outside script | byte-exact owner-checked Lua and stale-successor integration tests | revert script/lock commits together |
| Response-lost acquire creates ghost lease | redis-py retries script or client treats contention as no ownership | zero retry validation, one owner-token reconciliation, no redispatch fake test | disable adapter acquire and revert Task 4-5 |
| Renewal worker escapes scope | unbounded I/O, daemon thread, incomplete join | exact client gate, H/E/P/S/A/N/R timing, non-daemon thread, baseline thread-count test | disable auto-renew; retain explicit renew only after new design approval |
| Async cleanup detaches | shield raises and inner task survives | retain exact task, bounded cancel once, await terminal, pending-task-zero tests | disable async auto-renew until fixed |
| Context body runs after expiry | delayed enter does not probe owner | first-entry renew/probe RED tests for expiry/takeover/backend failure | revert context helper and require explicit handle API |
| Fencing is only decorative | example checks then writes separately or counter rolls back | atomic downstream high-watermark fixture, conditional guarantee and restore docs | remove unsafe example; do not claim fencing readiness |
| Namespace migration splits contenders | prefix/record version changes during rolling deploy | immutable coordination identity tests/docs and stop-the-world runbook | roll back to identical prefix/version only |
| Testcontainers flake hides regression | shared Redis state or cold startup race | serial marker, per-test digest names, flush only caller-owned test DB, bounded readiness probe | quarantine only evidence-backed infrastructure failure; never skip unit gates |
| Default install widens | Redis adapter added to core/default aggregate | isolated wheel metadata tests | revert metadata/lock together |

## Exact Production Blueprint

The core root export order is fixed:

```python
__all__ = [
    "LeaderError",
    "InvalidLeaderOptionsError",
    "InvalidLockNameError",
    "LeaderBackendError",
    "LeaderLeaseLostError",
    "LeaderReleaseError",
    "LeaderExecutionError",
    "LeaderElectionOptions",
    "LeaderLease",
    "FencedLeaderLease",
    "Elected",
    "Skipped",
    "ActionFailed",
    "LeaderRunResult",
    "Renewed",
    "NotHeld",
    "RenewBackendFailure",
    "RenewOutcome",
    "LockLease",
    "AsyncLockLease",
    "DistributedLock",
    "AsyncDistributedLock",
    "LeaderElector",
    "AsyncLeaderElector",
]
```

The Redis root export order is fixed:

```python
__all__ = [
    "RedisDistributedLock",
    "AsyncRedisDistributedLock",
    "RedisLeaderElector",
    "AsyncRedisLeaderElector",
]
```

The internal Redis state and timing vocabulary is exact:

```python
class _HandleState(Enum):
    ACQUIRED = auto()
    ENTERED = auto()
    LOST = auto()
    RELEASED = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class _Timing:
    handshake_round_trips: int
    connect: float      # E
    command: float      # P
    script: float       # S = 2P
    acquire: float      # A = S + P
    probe: float        # S
    renew: float        # N = S
    release: float      # R = 2S + P
```

The adapter uses these exact keys and record:

```text
<prefix>:{<sha256(lock_name UTF-8)>}:lease
<prefix>:{<sha256(lock_name UTF-8)>}:fence
v1:<32-character token_urlsafe(24)>:<canonical positive decimal fence>
```

The four concrete constructors are fixed and own no client shutdown:

```python
class RedisDistributedLock(DistributedLock[FencedLeaderLease]):
    def __init__(
        self,
        client: redis.Redis,
        *,
        prefix: str = "bluetape-leader",
    ) -> None: ...


class AsyncRedisDistributedLock(AsyncDistributedLock[FencedLeaderLease]):
    def __init__(
        self,
        client: redis.asyncio.Redis,
        *,
        prefix: str = "bluetape-leader",
    ) -> None: ...


class RedisLeaderElector(LeaderElector[FencedLeaderLease]):
    def __init__(
        self,
        client: redis.Redis,
        *,
        prefix: str = "bluetape-leader",
    ) -> None: ...


class AsyncRedisLeaderElector(AsyncLeaderElector[FencedLeaderLease]):
    def __init__(
        self,
        client: redis.asyncio.Redis,
        *,
        prefix: str = "bluetape-leader",
    ) -> None: ...
```

Each elector constructs exactly one corresponding internal lock from the
borrowed client and prefix. Constructor tests use `inspect.signature`, prove
wrong-family/subclass/proxy rejection before I/O, and prove neither class closes
the borrowed client.

## Task 1: Register both packages and implement the sanitized error boundary

**Depends on:** approved specification and approved implementation plan

**Files:**

- Create `packages/bluetape-leader/pyproject.toml`
- Create `packages/bluetape-leader/README.md`
- Create `packages/bluetape-leader/README.ko.md`
- Create `packages/bluetape-leader/src/bluetape/leader/_errors.py`
- Create `packages/bluetape-leader/src/bluetape/leader/__init__.py`
- Create `packages/bluetape-leader/tests/test_errors.py`
- Create `packages/bluetape-leader/tests/test_packaging.py`
- Create `packages/bluetape-leader-redis/pyproject.toml`
- Create `packages/bluetape-leader-redis/README.md`
- Create `packages/bluetape-leader-redis/README.ko.md`
- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/__init__.py`
- Create `packages/bluetape-leader-redis/tests/test_packaging.py`
- Modify root `pyproject.toml`
- Modify `packages/bluetape/pyproject.toml`
- Modify `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`
- Modify `docs/release/pypi-preflight.md`
- Modify `uv.lock`

- [ ] **Step 1: Write RED metadata, namespace, and error tests.** Pin both
  distributions, Python floor, exact runtime dependencies, `uv_build`, absent
  root namespace initializer, extended `bluetape.leader.__path__`, exact error
  inheritance, fixed safe messages, meta extras, default dependency, aggregate
  policy, publish classifier, and initial public export prefix.

```python
def test_backend_error_does_not_retain_raw_cause() -> None:
    marker = "redis://user:secret@127.0.0.1:6379 owner-123"
    error = LeaderBackendError()

    assert str(error) == "leader backend operation failed"
    assert marker not in repr(error)
    assert not hasattr(error, "cause")
    assert error.__cause__ is None
    assert error.__context__ is None
    assert getattr(error, "__notes__", []) == []


def test_composite_redacts_both_properties_from_representation() -> None:
    action = RuntimeError("caller-value-canary")
    lifecycle = LeaderBackendError()
    error = LeaderExecutionError(action, lifecycle)

    assert error.action_cause is action
    assert error.lifecycle_cause is lifecycle
    assert repr(error) == "LeaderExecutionError(<redacted>)"
    assert "caller-value-canary" not in repr(error)


def test_meta_defaults_remain_core_only(meta_pyproject: dict[str, object]) -> None:
    project = meta_pyproject["project"]
    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    extras = project["optional-dependencies"]
    assert extras["leader"] == ["bluetape-leader==0.1.0"]
    assert extras["leader-redis"] == ["bluetape-leader-redis==0.1.0"]
    assert "bluetape-leader==0.1.0" in extras["dev"]
    assert "bluetape-leader-redis==0.1.0" not in extras["dev"]
```

- [ ] **Step 2: Run RED and confirm missing distributions/errors.**

```bash
uv run pytest packages/bluetape-leader/tests/test_errors.py packages/bluetape-leader/tests/test_packaging.py packages/bluetape-leader-redis/tests/test_packaging.py packages/bluetape-benchmark/tests/test_benchmark_packaging.py -v
```

Expected: FAIL because the package directories, error symbols, workspace
members, extras, and publish classifications do not exist.

- [ ] **Step 3: Implement minimal package metadata and sanitized errors.** Use
  constant messages, no raw-cause property, redacted composite properties, and
  namespace extension before importing adapter-owned children.

```python
class LeaderError(Exception):
    """Base error for backend-neutral leader contracts."""


class LeaderBackendError(LeaderError):
    def __init__(self) -> None:
        super().__init__("leader backend operation failed")


class LeaderExecutionError(LeaderError):
    def __init__(self, action_cause: Exception, lifecycle_cause: LeaderError) -> None:
        super().__init__("leader action and lifecycle both failed")
        self.action_cause = action_cause
        self.lifecycle_cause = lifecycle_cause

    def __repr__(self) -> str:
        return "LeaderExecutionError(<redacted>)"
```

The first core `__init__.py` exports only error symbols but installs
`__path__ = extend_path(__path__, __name__)`; later tasks extend the exact list.
The first Redis `__init__.py` is importable but exports an empty list until its
classes exist. Run `uv lock` only after both package registrations and meta
sources are complete.

- [ ] **Step 4: Run GREEN plus lock/metadata checks.**

```bash
uv lock
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv run pytest packages/bluetape-leader/tests/test_errors.py packages/bluetape-leader/tests/test_packaging.py packages/bluetape-leader-redis/tests/test_packaging.py packages/bluetape-benchmark/tests/test_benchmark_packaging.py -v
uv run ruff check packages/bluetape-leader packages/bluetape-leader-redis
```

Expected: all selected tests PASS; lock is current; Ruff reports no violations.

- [ ] **Step 5: Commit the package/error foundation.**

```bash
git add pyproject.toml uv.lock packages/bluetape-leader packages/bluetape-leader-redis packages/bluetape/pyproject.toml packages/bluetape-benchmark/tests/test_benchmark_packaging.py docs/release/pypi-preflight.md
git commit -m "Establish separate leader contracts before backend behavior" \
  -m "Constraint: Core must remain stdlib-only while Redis stays opt-in" \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: focused packaging and error tests plus Ruff"
```

## Task 2: Implement backend-neutral options and immutable lease values

**Depends on:** Task 1

**Files:**

- Create `packages/bluetape-leader/src/bluetape/leader/_options.py`
- Create `packages/bluetape-leader/src/bluetape/leader/_values.py`
- Create `packages/bluetape-leader/tests/test_options.py`
- Create `packages/bluetape-leader/tests/test_values.py`
- Modify `packages/bluetape-leader/src/bluetape/leader/__init__.py`

- [ ] **Step 1: Write RED validation and preservation tests.** Cover exact
  built-in types, hostile subclasses/custom truthiness, zero/negative/order
  boundaries, whitespace-only and oversized
  node ID, positive sub-millisecond core acceptance, frozen/slotted values,
  aware UTC observations, physical-node/fencing separation, and fixed redacted
  repr.

```python
def test_core_accepts_positive_sub_millisecond_lease() -> None:
    options = LeaderElectionOptions(lease_time=timedelta(microseconds=500))
    assert options.lease_time == timedelta(microseconds=500)


def test_fenced_lease_keeps_node_and_fence_distinct() -> None:
    lease = FencedLeaderLease(
        audit_leader_id="42",
        node_id="node-a",
        elected_at=datetime(2026, 7, 18, tzinfo=UTC),
        lease_until=datetime(2026, 7, 18, 0, 1, tzinfo=UTC),
        fencing_token=42,
    )
    assert lease.node_id == "node-a"
    assert lease.fencing_token == 42
    assert repr(lease) == "FencedLeaderLease(<redacted>)"
```

- [ ] **Step 2: Run RED for missing option/value symbols.**

```bash
uv run pytest packages/bluetape-leader/tests/test_options.py packages/bluetape-leader/tests/test_values.py -v
```

Expected: FAIL on missing modules and exports.

- [ ] **Step 3: Implement exact core validation and values.** Do not convert to
  milliseconds here. Derive an exact `lease_time / 3` only when auto-renew is
  true and interval is absent. Preserve accepted caller strings and datetimes.

```python
@final
@dataclass(frozen=True, slots=True, kw_only=True)
class LeaderElectionOptions:
    wait_time: timedelta = timedelta(seconds=5)
    lease_time: timedelta = timedelta(seconds=60)
    node_id: str | None = None
    min_lease_time: timedelta = timedelta(0)
    auto_renew: bool = False
    renew_interval: timedelta | None = None

    def __post_init__(self) -> None:
        _require_exact_timedelta(self.wait_time, "wait_time")
        _require_exact_timedelta(self.lease_time, "lease_time")
        _require_exact_timedelta(self.min_lease_time, "min_lease_time")
        _require_exact_bool(self.auto_renew, "auto_renew")
        if self.renew_interval is not None:
            _require_exact_timedelta(self.renew_interval, "renew_interval")
        if self.node_id is not None:
            _require_exact_str(self.node_id, "node_id")
        if self.wait_time < timedelta(0) or self.lease_time <= timedelta(0):
            raise InvalidLeaderOptionsError()
        if not timedelta(0) <= self.min_lease_time <= self.lease_time:
            raise InvalidLeaderOptionsError()
        if self.node_id is not None:
            _validate_node_id(self.node_id)
        interval = self.renew_interval
        if self.auto_renew and interval is None:
            object.__setattr__(self, "renew_interval", self.lease_time / 3)
        elif interval is not None and not timedelta(0) < interval < self.lease_time:
            raise InvalidLeaderOptionsError()
```

- [ ] **Step 4: Run GREEN, full core tests, and Ruff.**

```bash
uv run pytest packages/bluetape-leader/tests/test_options.py packages/bluetape-leader/tests/test_values.py packages/bluetape-leader/tests/test_errors.py -v
uv run ruff check packages/bluetape-leader
uv run ruff format --check packages/bluetape-leader
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit options and lease snapshots.**

```bash
git add packages/bluetape-leader
git commit -m "Separate leader identity from fencing capability" \
  -m "Constraint: Backend-neutral durations must not inherit Redis resolution" \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: option and immutable lease tests"
```

## Task 3: Implement precise results, renewal outcomes, and generic protocols

**Depends on:** Task 2

**Files:**

- Create `packages/bluetape-leader/src/bluetape/leader/_results.py`
- Create `packages/bluetape-leader/src/bluetape/leader/_contracts.py`
- Create `packages/bluetape-leader/tests/test_results.py`
- Create `packages/bluetape-leader/tests/test_contracts.py`
- Modify `packages/bluetape-leader/src/bluetape/leader/__init__.py`
- Modify `packages/bluetape-leader/tests/test_packaging.py`

- [ ] **Step 1: Write RED result/protocol tests.** Cover `Elected(None)` versus
  singleton-like `Skipped`, sanitized renewal failure typing, generic
  `FencedLeaderLease` propagation through runtime stubs, exact signatures,
  context methods, cancellation-friendly async methods, and final 24-symbol
  export order.

```python
def test_elected_none_is_not_skipped() -> None:
    lease = sample_lease()
    result: LeaderRunResult[None, FencedLeaderLease] = Elected(None, lease)
    assert isinstance(result, Elected)
    assert result.value is None
    assert not isinstance(result, Skipped)


def test_renew_backend_failure_accepts_only_sanitized_error() -> None:
    outcome = RenewBackendFailure(LeaderBackendError())
    assert isinstance(outcome.cause, LeaderBackendError)
    assert "redis" not in repr(outcome)
```

- [ ] **Step 2: Run RED for missing results/contracts.**

```bash
uv run pytest packages/bluetape-leader/tests/test_results.py packages/bluetape-leader/tests/test_contracts.py packages/bluetape-leader/tests/test_packaging.py -v
```

Expected: FAIL because results, aliases, protocols, and final exports are absent.

- [ ] **Step 3: Implement the generic public contract exactly.** Use Python
  3.13 type-parameter syntax, `@runtime_checkable`, no method bodies beyond
  protocol ellipses, `types.TracebackType` for context exits, and no Redis
  import.

```python
@dataclass(frozen=True, slots=True)
class Elected[T, LeaseT: LeaderLease]:
    value: T
    lease: LeaseT


@final
@dataclass(frozen=True, slots=True)
class Skipped:
    pass


type LeaderRunResult[T, LeaseT: LeaderLease] = (
    Elected[T, LeaseT] | Skipped | ActionFailed[LeaseT]
)


@runtime_checkable
class LockLease[LeaseT: LeaderLease](Protocol):
    @property
    def lease(self) -> LeaseT: ...

    def renew(self, lease_time: timedelta | None = None) -> RenewOutcome: ...
    def is_held(self) -> bool: ...
    def assert_held(self) -> None: ...
    def release(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@runtime_checkable
class AsyncLockLease[LeaseT: LeaderLease](Protocol):
    @property
    def lease(self) -> LeaseT: ...

    async def renew(self, lease_time: timedelta | None = None) -> RenewOutcome: ...
    async def is_held(self) -> bool: ...
    async def assert_held(self) -> None: ...
    async def release(self) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@runtime_checkable
class DistributedLock[LeaseT: LeaderLease](Protocol):
    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LockLease[LeaseT] | None: ...


@runtime_checkable
class AsyncDistributedLock[LeaseT: LeaderLease](Protocol):
    async def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> AsyncLockLease[LeaseT] | None: ...


@runtime_checkable
class LeaderElector[LeaseT: LeaderLease](Protocol):
    def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> T | None: ...

    def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LeaderRunResult[T, LeaseT]: ...


@runtime_checkable
class AsyncLeaderElector[LeaseT: LeaderLease](Protocol):
    async def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], Awaitable[T]],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> T | None: ...

    async def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], Awaitable[T]],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LeaderRunResult[T, LeaseT]: ...
```

Update the exact export list in the blueprint and assert all six protocols are
runtime-checkable without importing Redis.

- [ ] **Step 4: Run GREEN and prove stdlib-only import isolation.**

```bash
uv run pytest packages/bluetape-leader -v
uv run python -c 'import bluetape.leader as m; assert m.__all__ == ["LeaderError", "InvalidLeaderOptionsError", "InvalidLockNameError", "LeaderBackendError", "LeaderLeaseLostError", "LeaderReleaseError", "LeaderExecutionError", "LeaderElectionOptions", "LeaderLease", "FencedLeaderLease", "Elected", "Skipped", "ActionFailed", "LeaderRunResult", "Renewed", "NotHeld", "RenewBackendFailure", "RenewOutcome", "LockLease", "AsyncLockLease", "DistributedLock", "AsyncDistributedLock", "LeaderElector", "AsyncLeaderElector"]'
uv run ruff check packages/bluetape-leader
```

Expected: all core tests PASS and no redis-py import is required.

- [ ] **Step 5: Commit the backend-neutral public contract.**

```bash
git add packages/bluetape-leader
git commit -m "Make fencing capability explicit across leader contracts" \
  -m "Constraint: Precise results must distinguish skipped work from a None result" \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: complete core contract and packaging tests"
```

## Task 4: Implement safe Redis configuration, keys, records, timing, and scripts

**Depends on:** Task 3

**Files:**

- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_keys.py`
- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_support.py`
- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_scripts.py`
- Create `packages/bluetape-leader-redis/tests/_support.py`
- Create `packages/bluetape-leader-redis/tests/test_keys_unit.py`
- Create `packages/bluetape-leader-redis/tests/test_support_unit.py`
- Create `packages/bluetape-leader-redis/tests/test_scripts_unit.py`
- Create `packages/bluetape-leader-redis/tests/test_timing_integration.py`

- [ ] **Step 1: Prepare fixtures and record the validation/key/record/timing
  coverage inventory.** Do not author behavior assertions yet. The inventory
  must cover exact sync
  and async client types, exact built-in prefix/name, 1,024-byte name bound,
  64-byte prefix allowlist, NFC/NFD distinction, same hash tag, static auth,
  zero retry/health check, numeric IP/Unix socket, rejected TLS/hostname,
  URL-derived or custom pool/callback/provider/hook, positive millisecond
  conversion, fixed maximum
  handshake count, H/E/P/S/A/N/R arithmetic, exact public constructor
  signatures, 32-character owner token, strict record parse, and canary-safe
  failures. Monkeypatch DNS resolution, socket connect, credential callbacks,
  and command dispatch with hostile sentinels and prove every rejected client
  shape fails before any sentinel runs.

```python
def test_keys_share_hash_tag_without_raw_name() -> None:
    keys = _redis_keys("tenant-secret-job", "bluetape-leader")
    assert keys.lease.startswith("bluetape-leader:{")
    assert keys.fence.startswith("bluetape-leader:{")
    assert keys.lease.split("}", 1)[0] == keys.fence.split("}", 1)[0]
    assert "tenant-secret-job" not in keys.lease


def test_retry_enabled_client_is_rejected(bounded_client_kwargs: dict[str, object]) -> None:
    client = redis.Redis(**bounded_client_kwargs, retry_on_timeout=True)
    with pytest.raises(TypeError, match="unsupported Redis client configuration"):
        _validated_sync_client(client)
```

Enumerate the complete supported handshake-shape matrix: no auth, password
auth, or username/password auth; RESP2 or RESP3; client name absent/present;
database zero/nonzero; numeric TCP or Unix socket. Arbitrary safe values within
one shape do not add a command. Force cold connect and reconnect for every
shape and observe the exact AUTH/HELLO, CLIENT SETNAME, built-in CLIENT SETINFO,
and SELECT response sequence. A caller-owned stalled RESP/TCP fixture pauses
connect, each handshake response, and a primitive command response separately
to prove `E` and `P`; derive `S/A/N/R` from those witnessed bounds. Reject any
pinned redis-py configuration whose command path or finite pool wait cannot be
observed and bounded before Task 5.

- [ ] **Step 2: Prepare the fake script runner and record the status coverage
  inventory.** Do not author behavior assertions yet. The fake
  command runner records calls and injects `NoScriptError`, response loss,
  wrong type, malformed value, no TTL, counter at `2^53`, signed overflow,
  owner mismatch, minimum-TTL release, and raw-error canaries.

```python
def test_script_runner_falls_back_once_without_script_load() -> None:
    commands = FakeCommands(evalsha_effects=[NoScriptError()], eval_result=[b"ACQUIRED", b"7"])
    result = _run_script(commands, ACQUIRE_SCRIPT, (b"lease", b"fence"), (b"owner", b"1000"))
    assert result == [b"ACQUIRED", b"7"]
    assert commands.calls == ["evalsha", "eval"]
```

Use this ordered micro-cycle ledger. For each row, first run the selector and
create only that row's focused test, record the intended assertion failure, add
only the named production behavior, rerun that selector GREEN, then rerun its
owning file before advancing. The example tests above are authored only when
their ledger row becomes active.

| Cycle | Focused selector | Minimum GREEN behavior |
|---|---|---|
| 4A | `test_support_unit.py -k rejected_client_has_no_io` | exact client/config/signature validation before DNS, callback, connect, or command |
| 4B | `test_keys_unit.py -k identity` | exact name/prefix validation and SHA-256 same-slot keys |
| 4C | `test_support_unit.py -k record` | strict private slotted record parse/format and fixed redacted repr |
| 4D | `test_support_unit.py -k timing_arithmetic` | integer millisecond conversion and H/E/P/S/A/N/R formulas |
| 4E | `test_timing_integration.py -k handshake_matrix` | cold/reconnect command-shape observation for every supported configuration |
| 4F | `test_timing_integration.py -k stalled_stage` | connect/handshake/command stall terminates inside the computed bound; cancelled async redis-py command reaches terminal state within 100ms |
| 4G | `test_scripts_unit.py -k noscript` | locally hashed `EVALSHA` plus exactly one `EVAL`, never `SCRIPT LOAD` |
| 4H | `test_scripts_unit.py -k acquire` | atomic acquire statuses, fence validation, and string-safe counter readback |
| 4I | `test_scripts_unit.py -k probe` | atomic HELD/NOT_HELD/CORRUPT type/value/PTTL probe |
| 4J | `test_scripts_unit.py -k reconcile` | one direct read-only EVAL validates type/value/positive PTTL and never falls back |
| 4K | `test_scripts_unit.py -k renew` | exact-owner renew without creation or redispatch |
| 4L | `test_scripts_unit.py -k release` | exact-owner delete/minimum-TTL statuses without unconditional delete |
| 4M | `test_support_unit.py -k sanitized_exception_graph` | raw backend canary absent from the entire public exception graph |
| 4N | `test_support_unit.py -k owner_token` | one private `token_urlsafe(24)` value per logical `try_acquire` call |

- [ ] **Step 3: Start the ordered ledger with one focused RED.** Begin at 4A
  with the exact command form below. Do not author 4B until 4A has received its
  minimum implementation in Step 4, passed GREEN, and passed its owning file;
  then repeat that RED -> Step 4 minimum GREEN cycle through 4N.

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_support_unit.py -k rejected_client_has_no_io -v
```

After all rows, run the four owning files together and require PASS.

- [ ] **Step 4: Implement each ledger row minimally, then return to Step 3 for
  the next RED.** For the active row only, implement validation, record parsing,
  timing, or fixed Lua as specified below.
  Keep raw exceptions in the failing frame only. Construct the sanitized error
  while handling the raw exception, leave the `except` block, and only then
  raise the sanitized error `from None`, so `__context__` is also absent. Use
  locally computed SHA-1, `EVALSHA`, then one `EVAL` fallback.
  The acquire script validates an existing string record plus positive PTTL,
  validates the fence key, calls `INCR`, rereads the canonical decimal with
  `GET`, writes `v1:owner:fence` with `PX`, and returns the fence as a string.
  Store the following five scripts as fixed module constants; their only
  inputs are the listed `KEYS` and `ARGV` values.

```lua
-- ACQUIRE: KEYS[1]=lease, KEYS[2]=fence, ARGV[1]=owner, ARGV[2]=ttl_ms
local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type ~= 'none' then
  if lease_type ~= 'string' then return {'CORRUPT'} end
  local current = redis.call('GET', KEYS[1])
  local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
  if not owner or string.len(owner) ~= 32 or redis.call('PTTL', KEYS[1]) <= 0 then
    return {'CORRUPT'}
  end
  return {'CONTENDED'}
end
local fence_type = redis.call('TYPE', KEYS[2]).ok
if fence_type ~= 'none' then
  if fence_type ~= 'string' then return {'CORRUPT'} end
  local previous = redis.call('GET', KEYS[2])
  if not string.match(previous, '^[1-9][0-9]*$') then return {'CORRUPT'} end
end
redis.call('INCR', KEYS[2])
local fence = redis.call('GET', KEYS[2])
if not string.match(fence, '^[1-9][0-9]*$') then return {'CORRUPT'} end
local record = 'v1:' .. ARGV[1] .. ':' .. fence
redis.call('SET', KEYS[1], record, 'PX', ARGV[2])
return {'ACQUIRED', fence}
```

```lua
-- RENEW: KEYS[1]=lease, ARGV[1]=expected_record, ARGV[2]=ttl_ms
local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'NOT_HELD'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'NOT_HELD'} end
if current ~= ARGV[1] then return {'NOT_HELD'} end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return {'RENEWED'}
```

```lua
-- PROBE: KEYS[1]=lease, ARGV[1]=expected_record
local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'NOT_HELD'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'NOT_HELD'} end
if current ~= ARGV[1] then return {'NOT_HELD'} end
return {'HELD'}
```

```lua
-- RECONCILE: KEYS[1]=lease; dispatched once with direct EVAL, never EVALSHA
local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'ABSENT'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'ABSENT'} end
return {'PRESENT', current}
```

```lua
-- RELEASE: KEYS[1]=lease, ARGV[1]=expected_record,
--          ARGV[2]=canonical remaining_min_ttl_ms or "0"
local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'NOT_HELD'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'NOT_HELD'} end
if current ~= ARGV[1] then return {'NOT_HELD'} end
if ARGV[2] == '0' then
  redis.call('DEL', KEYS[1])
  return {'DELETED'}
end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return {'MIN_TTL_APPLIED'}
```

The Python runner validates the owner token and canonical millisecond arguments
before dispatch. The probe follows the bounded `EVALSHA -> EVAL` script
operation. Response-lost acquire/release reconciliation dispatches the fixed
read-only reconciliation source through exactly one direct `EVAL`, then uses
`hmac.compare_digest` only for the private owner field. This keeps the
reconciliation at `P`, atomically rejects no-expiry state, and never falls back
or redispatches after another lost response. No Lua script constructs a key or
converts a fencing token through a Lua number.

The private entropy seam calls `secrets.token_urlsafe(24)` exactly once per
logical `try_acquire()` call. Contention retries and that call's single
response-loss reconciliation retain the same 32-character value; the next
public acquisition call receives a different value. The caller cannot inject
or read it, and the private record/handle types are slotted with fixed redacted
representations.

The redaction test raises a raw canary exception through the real sync and async
backend conversion helpers. It walks `args`, `__cause__`, `__context__`, notes,
`str`, `repr`, and formatted traceback; it also checks
`RenewBackendFailure.cause` and `LeaderExecutionError.lifecycle_cause`. The raw
canary must be absent everywhere. `action_cause` remains the documented caller
exception and is tested only for representation redaction.

- [ ] **Step 5: Run GREEN, redaction scan, and Ruff.**

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_keys_unit.py packages/bluetape-leader-redis/tests/test_support_unit.py packages/bluetape-leader-redis/tests/test_scripts_unit.py packages/bluetape-leader-redis/tests/test_timing_integration.py -v
uv run ruff check packages/bluetape-leader-redis
uv run ruff format --check packages/bluetape-leader-redis
```

Expected: all selected tests PASS; fake call counts match exact envelopes.

- [ ] **Step 6: Commit the atomic Redis substrate.**

```bash
git add packages/bluetape-leader-redis
git commit -m "Bound Redis ownership before exposing a lock" \
  -m "Constraint: Uncertain scripts must reconcile without redispatch" \
  -m "Rejected: TLS and opaque command hooks | no enforceable whole-operation bound" \
  -m "Confidence: high" \
  -m "Scope-risk: broad" \
  -m "Tested: key, client, timing, record, Lua, uncertainty, and redaction unit tests"
```

## Task 5: Implement the synchronous Redis lock and scoped renewal state machine

**Depends on:** Task 4

**Files:**

- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_lock.py`
- Create `packages/bluetape-leader-redis/tests/test_sync_lock_unit.py`
- Modify `packages/bluetape-leader-redis/src/bluetape/leader/redis/__init__.py`

- [ ] **Step 1: Record the acquire/deadline/reconciliation coverage inventory.**
  Do not author its behavior assertions before the matching ledger row. Cover one
  attempt at zero wait, 40-60ms deterministic jitter, no post-deadline dispatch,
  `wait_time + A`, contention-only retry, one token per public acquisition call,
  exact owner-field
  response-loss recovery, absent/different/malformed/second-uncertain outcomes,
  and no script redispatch.

```python
def test_uncertain_acquire_recovers_matching_owner_without_redispatch() -> None:
    runner = FakeRunner(
        acquire_effects=[TimeoutError("marker")],
        reconcile_effects=[
            ("PRESENT", b"v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:9")
        ],
    )
    lock = new_sync_lock(runner=runner, token="A" * 32)
    handle = lock.try_acquire("job", short_options())
    assert handle is not None
    assert handle.lease.fencing_token == 9
    assert runner.acquire_calls == 1
    assert runner.reconcile_calls == [("eval", "lease-key")]
```

- [ ] **Step 2: Record the handle-state/manual-operation coverage inventory.**
  Do not author its behavior assertions before the matching ledger row. Cover
  `ACQUIRED/ENTERED/LOST/RELEASED/UNKNOWN`, one bounded probe script, renew
  status, direct release status, full uncertain-release matrix, minimum lease,
  double release, delayed entry proof, worker-start failure cleanup, no-I/O
  terminal methods, safe repr, and borrowed client remaining open.

The release response-loss matrix is exact for sync and later mirrored by async.
The public error below is the lifecycle result before the outer action/body
failure-precedence matrix composes it into `LeaderExecutionError` when needed:

| Read-only reconciliation result | Follow-up or repeat result | Terminal state | Direct `release()` | Scoped cleanup |
|---|---|---|---|---|
| canonical same owner | recompute remaining minimum TTL from the original monotonic acquisition instant; repeat returns `DELETED` or `MIN_TTL_APPLIED` | `RELEASED` | success | success |
| canonical same owner | repeat returns `NOT_HELD` | `LOST` | `LeaderReleaseError` | `LeaderLeaseLostError` |
| canonical same owner | repeat returns `CORRUPT` or an ordinary backend failure | `UNKNOWN` | `LeaderBackendError` | `LeaderBackendError` |
| canonical same owner | repeat response is also lost | `UNKNOWN` | `LeaderReleaseError` | `LeaderReleaseError` |
| missing | no script redispatch | `UNKNOWN` | `LeaderReleaseError` | `LeaderReleaseError` |
| canonical different owner | no script redispatch; never delete or shorten successor | `LOST` | `LeaderReleaseError` | `LeaderLeaseLostError` |
| malformed/wrong type/no expiry | no script redispatch | `UNKNOWN` | `LeaderBackendError` | `LeaderBackendError` |
| reconciliation transport failure | no script redispatch | `UNKNOWN` | `LeaderBackendError` | `LeaderBackendError` |

Every row asserts the complete command trace, including absence of unconditional
`DEL`. A renew timeout/disconnect never redispatches its script: it enters
`UNKNOWN`, retains one value-free lifecycle error, and every later
renew/release/probe/entry call raises it without new Redis I/O.

Acquire uncertainty has its own exact table:

| Failing stage | Read-only reconciliation result | Public result | Command trace |
|---|---|---|---|
| `EVALSHA` response loss | canonical same owner with positive TTL | acquired handle with recovered fence | one `EVALSHA`, one read-only `EVAL`; no acquire redispatch |
| `NOSCRIPT -> EVAL` response loss | canonical same owner with positive TTL | acquired handle with recovered fence | one `EVALSHA`, one mutating `EVAL`, one read-only `EVAL`; no further script |
| either response loss | absent or canonical different owner | raised `LeaderBackendError` after proving no ownership | one bounded read-only `EVAL`; no script redispatch |
| either response loss | malformed/wrong type/no expiry | raised `LeaderBackendError` | one bounded read-only `EVAL`; no script redispatch |
| either response loss | reconciliation timeout/disconnect | raised `LeaderBackendError` | one read-only `EVAL`; no redispatch |

Renew uncertainty covers response loss after `EVALSHA` and after the NOSCRIPT
fallback `EVAL`; both enter `UNKNOWN` without reconciliation or redispatch and
reuse the same retained lifecycle error for every later no-I/O method.
Sync and async elector tests prove missing and different-owner acquire
reconciliations are raised and never converted to `Skipped`; only an explicit
script `CONTENDED` status is `None`/`Skipped`.

- [ ] **Step 3: Prepare controlled runner/clock fixtures and record the scoped
  worker coverage inventory.** Do not author worker behavior assertions before
  their ledger row. Use a controlled runner and
  fake monotonic clock to prove one non-daemon worker per entered auto-renew
  handle, initial renew before body, interruptible interval wait, loss/backend
  terminal state, `N + 100ms` join, release after join only, manual release
  inside context, and zero remaining worker threads.

```python
def test_context_proves_ownership_before_body() -> None:
    handle = acquired_handle(probe_result=False)
    body_started = False
    with pytest.raises(LeaderLeaseLostError):
        with handle:
            body_started = True
    assert body_started is False
    assert handle.state_name_for_test == "LOST"
```

Use this ordered micro-cycle ledger, witnessing RED then minimum GREEN for one
row at a time. Create only the active row's focused test, rerun
`test_sync_lock_unit.py` after its GREEN, and do not author later-row tests
before the current row is GREEN:

| Cycle | Focused selector | Minimum GREEN behavior |
|---|---|---|
| 5A | `-k zero_wait` | one acquire dispatch with monotonic deadline |
| 5B | `-k contention_retry` | capped 40-60ms jitter and no post-deadline dispatch |
| 5C | `-k uncertain_acquire` | one direct read-only EVAL reconciliation with no acquire redispatch |
| 5D | `-k manual_state` | ACQUIRED operations and terminal no-I/O transitions |
| 5E | `-k entry_proof` | probe/initial renew succeeds before body or body never starts |
| 5F | `-k uncertain_renew` | terminal UNKNOWN without renew redispatch |
| 5G | `-k uncertain_release` | complete table above and original-instant minimum TTL |
| 5H | `-k worker_lifecycle` | one non-daemon worker, interruptible wait, bounded join |
| 5I | `-k worker_start_failure` | start-before-live failure proves no worker exists before owner-checked cleanup |
| 5J | `-k worker_crash` | unexpected worker exit is retained as sanitized failure and terminal UNKNOWN |
| 5K | `-k worker_join_deadline` | exit returns by outer deadline, forbids release/success, and retains UNKNOWN |
| 5L | `-k state_operation_matrix` | every state × operation, re-entry, concurrent entry, and terminal no-I/O rule |
| 5M | `-k process_control` | exact KeyboardInterrupt/SystemExit/GeneratorExit survives bounded cleanup |
| 5N | `-k context_failure_matrix` | body/loss/backend/release precedence without masking |

- [ ] **Step 4: Start the sync ledger with one focused RED.** Begin at 5A using
  the exact selector form below. Add only its Step 5 behavior, rerun GREEN and
  the owning file, then repeat that cycle through 5N.

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_sync_lock_unit.py -v
```

The first row initially fails on missing `RedisDistributedLock`; later rows
must fail on their intended missing behavior rather than import/setup errors.

- [ ] **Step 5: Implement only the active sync ledger row, then return for the
  next RED.** Keep the
  public class generic as `DistributedLock[FencedLeaderLease]`; keep concrete
  handle type private. Use `time.monotonic_ns`, `threading.Event`, one named
  non-daemon thread, a private mutex only for local state transitions, and no
  user callback while holding it.

```python
class RedisDistributedLock(DistributedLock[FencedLeaderLease]):
    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LockLease[FencedLeaderLease] | None:
        keys = _redis_keys(lock_name, self._prefix)
        token = _new_owner_token()
        return self._try_acquire(keys, token, options)


def __enter__(self) -> Self:
    self._transition_for_entry()
    outcome = self.renew() if self._options.auto_renew else self._probe()
    self._require_entry_proof(outcome)
    self._start_worker_if_enabled()
    return self
```

The state-operation matrix parameterizes
`ACQUIRED/ENTERED/LOST/RELEASED/UNKNOWN` against renew, probe/is-held,
assert-held, release, enter, and exit for both sync and async parity. It adds
two-thread/two-task concurrent first entry, re-entry, entry after every terminal
state, explicit release inside context, and idempotent later exit. Every cell
asserts state, exact exception/result, command trace, worker/task count, and
terminal no-I/O behavior.

Fault-injected start, crash, and stuck-worker tests are distinct. A start
failure may release only after proving no worker is alive. An unexpected crash
is retained as a sanitized lifecycle failure. A worker exceeding `N + 100ms`
makes context exit return inside a separate outer deadline, enters `UNKNOWN`,
never dispatches release, and forbids action success. Its fixture always
unblocks and joins the injected worker in `finally` so the test process cannot
hang; later calls reuse the retained error without I/O.

Direct manual contexts and both electors inject the exact same
`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` objects with successful
and failed cleanup. The original object remains primary, cleanup failure adds
only value-free evidence, no result wrapper is produced, all owned workers/tasks
terminate, and borrowed clients remain usable.

- [ ] **Step 6: Run GREEN, repeat leak-sensitive tests, and commit.**

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_sync_lock_unit.py -v
uv run ruff check packages/bluetape-leader-redis
git add packages/bluetape-leader-redis
git commit -m "Keep synchronous Redis renewal inside the acquired scope" \
  -m "Constraint: A worker must stop before owner-checked release" \
  -m "Confidence: high" \
  -m "Scope-risk: broad" \
  -m "Tested: sync acquisition, state, uncertainty, renewal, join, and leak tests"
```

Execute the sync lock unit command five separate times and record all five
results. Do not add `pytest-repeat` or any other dependency for repetition.

## Task 6: Implement the asyncio Redis lock and cancellation-safe cleanup

**Depends on:** Task 5

**Files:**

- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_async_lock.py`
- Create `packages/bluetape-leader-redis/tests/test_async_lock_unit.py`
- Modify `packages/bluetape-leader-redis/src/bluetape/leader/redis/__init__.py`

- [ ] **Step 1: Record the async parity coverage inventory.** Do not author its
  behavior assertions before the matching ledger row. Mirror sync acquisition,
  contention, owner recovery, state, delayed entry, probe, renew, release,
  minimum TTL, and terminal no-I/O behavior using `AsyncMock`/controlled await
  points rather than timing sleeps.

- [ ] **Step 2: Prepare controlled await fixtures and record the retained-task
  cancellation coverage inventory.** Do not author cancellation behavior
  assertions before their ledger row. Cover cancellation
  during renew, `EVALSHA`, fallback `EVAL`, read-only reconciliation `EVAL`, initial
  release, same-owner repeat release, repeated outer cancellation, deadline
  cancellation, one retained task identity, and `asyncio.all_tasks()` returning
  to baseline before the caller receives `CancelledError`.

```python
@pytest.mark.asyncio
async def test_cancelled_exit_reawaits_the_same_cleanup_task() -> None:
    release_started = asyncio.Event()
    release_finish = asyncio.Event()
    handle = async_handle(release_started=release_started, release_finish=release_finish)
    task = asyncio.create_task(run_cancelled_context(handle))
    await release_started.wait()
    task.cancel()
    assert not task.done()
    release_finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert handle.cleanup_task_count_for_test == 1
    assert handle.pending_owned_tasks_for_test == 0
```

Use this ordered micro-cycle ledger. Each row must show its own intended RED,
minimum GREEN, and owning-file regression before the next row begins. Create
only the active row's test; later-row tests remain unwritten until the active
row is GREEN:

| Cycle | Focused selector | Minimum GREEN behavior |
|---|---|---|
| 6A | `-k async_zero_wait` | awaited acquisition and contention parity |
| 6B | `-k async_uncertain_acquire` | retained call plus one awaited read-only EVAL reconciliation |
| 6C | `-k async_state_and_entry` | delayed-entry proof and terminal no-I/O states |
| 6D | `-k async_uncertain_renew` | no redispatch and terminal UNKNOWN |
| 6E | `-k async_uncertain_release` | complete sync release-loss table with one retained repeat |
| 6F | `-k renew_task_lifecycle` | one retained renew task and absolute `N + 100ms` terminal deadline |
| 6G | `-k incoming_cancellation` | original cancellation identity survives bounded cleanup |
| 6H | `-k repeated_cancellation` | repeated outer cancellation re-awaits the same task without resetting deadline |
| 6I | `-k release_deadline` | one cancel at `R`, terminal by `R + 100ms`, zero pending tasks |
| 6J | `-k async_context_failure_matrix` | cancellation/process-control/action/lifecycle precedence |

- [ ] **Step 3: Start the async ledger with one focused RED.** Begin at 6A,
  implement only its Step 4 behavior, rerun GREEN and the owning file, then
  repeat that cycle through 6J.

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_async_lock_unit.py -v
```

The first row fails on the missing async lock; subsequent rows must fail on the
named missing behavior rather than import/setup errors.

- [ ] **Step 4: Implement only the active async ledger row, then return for the
  next RED.** Use the
  event-loop monotonic clock, `asyncio.Event`, and exactly one renew task plus
  one cleanup task per scope. Compute one absolute command deadline when the
  operation starts; repeated caller cancellation never resets it. If the task
  is still pending at `N` or `R`, cancel that exact task once and require it to
  reach terminal state by the already-fixed `N + 100ms` or `R + 100ms`
  deadline. Never create a task without storing its reference first.

```python
async def _wait_owned_until[T](
    task: asyncio.Task[T],
    *,
    deadline: float,
    first_cancel: asyncio.CancelledError | None,
) -> tuple[bool, asyncio.CancelledError | None]:
    loop = asyncio.get_running_loop()
    owner = asyncio.current_task()
    assert owner is not None
    while not task.done():
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False, first_cancel
        try:
            await asyncio.wait_for(asyncio.shield(task), remaining)
        except TimeoutError:
            return task.done(), first_cancel
        except asyncio.CancelledError as caught:
            if first_cancel is None and owner.cancelling() > 0:
                first_cancel = caught
            if task.done():
                break
    return True, first_cancel
```

The lifecycle owner calls `_wait_owned_until` with the absolute `N`/`R`
deadline. On `False`, it calls `task.cancel()` exactly once, then calls the same
helper with the precomputed terminal deadline `started + N/R + 0.100`; no new
task and no new relative timeout is created. The pinned redis-py stalled-command
test from Task 4 must prove terminal cancellation within that margin before
Task 6 may proceed. If it fails, return to design review: Python cannot both
hard-bound and synchronously eliminate a cancellation-resistant arbitrary
coroutine. After `task.done()` is true, read its result synchronously, classify
cleanup, attach only a value-free note when needed, and re-raise the first
incoming `CancelledError` object.

The repeated-cancellation RED matrix includes a same-event-loop-turn race that
cancels both the lifecycle owner and owned cleanup task. It proves cancellation
origin from `owner.cancelling()`, re-raises the exact first caller cancellation
object, calls owned-task cancel at most once, and leaves zero pending tasks.

- [ ] **Step 5: Run GREEN, repeat cancellation matrix, and commit.**

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_async_lock_unit.py -v
uv run pytest packages/bluetape-leader-redis/tests/test_sync_lock_unit.py packages/bluetape-leader-redis/tests/test_async_lock_unit.py -v
uv run ruff check packages/bluetape-leader-redis
git add packages/bluetape-leader-redis
git commit -m "Await every asyncio lease task before leaving its scope" \
  -m "Constraint: Cancellation must not detach Redis cleanup" \
  -m "Confidence: high" \
  -m "Scope-risk: broad" \
  -m "Tested: async acquisition, cancellation, task identity, deadline, and parity tests"
```

## Task 7: Implement sync and async leader electors and failure precedence

**Depends on:** Tasks 5-6

**Files:**

- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_elector.py`
- Create `packages/bluetape-leader-redis/src/bluetape/leader/redis/_async_elector.py`
- Create `packages/bluetape-leader-redis/tests/test_sync_elector_unit.py`
- Create `packages/bluetape-leader-redis/tests/test_async_elector_unit.py`
- Modify `packages/bluetape-leader-redis/src/bluetape/leader/redis/__init__.py`
- Modify `packages/bluetape-leader-redis/tests/test_packaging.py`

- [ ] **Step 1: Write RED result matrix tests.** Cover contention without action,
  `None` action result, ordinary action exception, process-control propagation,
  renewal loss, backend failure, release `NOT_HELD`, corrupt/uncertain release,
  action plus lifecycle composite, exact `FencedLeaderLease` callback typing,
  and final four-symbol Redis export order.

```python
def test_result_api_distinguishes_none_from_contention() -> None:
    elected = elector_with_handle().run_if_leader_result("job", lambda lease: None)
    skipped = contended_elector().run_if_leader_result("job", lambda lease: None)
    assert isinstance(elected, Elected)
    assert elected.value is None
    assert isinstance(skipped, Skipped)


def test_action_and_release_uncertainty_raise_composite() -> None:
    elector = elector_with_uncertain_release()
    with pytest.raises(LeaderExecutionError) as captured:
        elector.run_if_leader_result("job", raising_action)
    assert isinstance(captured.value.action_cause, ExpectedActionError)
    assert isinstance(captured.value.lifecycle_cause, LeaderError)
```

- [ ] **Step 2: Write RED async cancellation/result parity tests.** Assert the
  original `CancelledError` object is re-raised after cleanup; ordinary action
  failures become `ActionFailed` only with proven release; lease loss prevents
  success but does not force-cancel arbitrary action code.

- [ ] **Step 3: Run RED for missing electors.**

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_sync_elector_unit.py packages/bluetape-leader-redis/tests/test_async_elector_unit.py packages/bluetape-leader-redis/tests/test_packaging.py -v
```

Expected: FAIL on missing elector implementations and exports.

- [ ] **Step 4: Implement electors by composing lock handles.** Do not duplicate
  scripts, deadlines, tokens, state, or cleanup. Set the `elected` flag only
  after context entry proves ownership. Catch only `Exception`; process-control
  and cancellation flow through the handle cleanup path.

```python
def run_if_leader_result[T](
    self,
    lock_name: str,
    action: Callable[[FencedLeaderLease], T],
    options: LeaderElectionOptions = LeaderElectionOptions(),
) -> LeaderRunResult[T, FencedLeaderLease]:
    handle = self._lock.try_acquire(lock_name, options)
    if handle is None:
        return Skipped()
    result_lease: FencedLeaderLease | None = None
    action_value: T | None = None
    action_error: Exception | None = None
    try:
        with handle as held:
            result_lease = held.lease
            try:
                action_value = action(result_lease)
            except Exception as caught:
                action_error = caught
    except LeaderError as lifecycle_error:
        if action_error is not None:
            raise LeaderExecutionError(action_error, lifecycle_error) from None
        raise
    assert result_lease is not None
    if action_error is not None:
        return ActionFailed(action_error, result_lease)
    return Elected(cast(T, action_value), result_lease)
```

The implementation retains the action value/error, exits the context, and only
then applies the approved failure matrix. The async implementation uses the
same ordering while preserving the original `CancelledError` identity; neither
implementation returns from inside its lock context.

- [ ] **Step 5: Run GREEN, exact exports, and commit.**

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_sync_elector_unit.py packages/bluetape-leader-redis/tests/test_async_elector_unit.py packages/bluetape-leader-redis/tests/test_packaging.py -v
uv run python -c 'import bluetape.leader.redis as m; assert len(m.__all__) == 4'
uv run ruff check packages/bluetape-leader-redis
git add packages/bluetape-leader-redis
git commit -m "Report leader action outcomes only after proven cleanup" \
  -m "Constraint: Lifecycle uncertainty cannot be hidden as ActionFailed" \
  -m "Confidence: high" \
  -m "Scope-risk: broad" \
  -m "Tested: sync and async elector outcome matrices plus export checks"
```

## Task 8: Prove real Redis safety, contention, fencing, and resource cleanup

**Depends on:** Task 7

**Files:**

- Create `packages/bluetape-leader-redis/tests/test_sync_redis_integration.py`
- Create `packages/bluetape-leader-redis/tests/test_async_redis_integration.py`
- Create `packages/bluetape-leader-redis/tests/test_concurrency_integration.py`
- Modify `packages/bluetape-leader-redis/tests/_support.py`
- Modify `packages/bluetape-leader-redis/pyproject.toml`

- [ ] **Step 1: Add a caller-owned serial Redis fixture.** Use existing
  `RedisServer`; resolve its published host to a numeric IP before constructing
  supported clients, set finite timeouts, zero retries/health check, no TLS,
  close both borrowed clients in the fixture, and generate unique logical names
  without exposing them in assertion output.

  Mark the package tests `testcontainers`, fail collection when
  `PYTEST_XDIST_WORKER` is present, and run the dedicated CI command in one
  pytest process. The module owns one isolated Redis container/DB; no other test
  may share it. Every sync/async client, ACL user, commandstats client,
  executor, gate, and contender task is registered before use and released in
  `yield`/`finally` cleanup.

```python
@pytest.fixture(scope="module")
def redis_endpoint() -> Iterator[tuple[str, int]]:
    with RedisServer() as server:
        numeric_host = str(ip_address(socket.gethostbyname(server.host)))
        deadline = time.monotonic() + 15.0
        while True:
            probe = redis.Redis(
                host=numeric_host,
                port=server.port,
                socket_connect_timeout=0.10,
                socket_timeout=0.05,
            )
            try:
                if probe.ping():
                    break
            except redis.RedisError:
                pass
            finally:
                probe.close()
            if time.monotonic() >= deadline:
                pytest.fail("Redis readiness deadline exceeded")
            time.sleep(0.05)
        yield numeric_host, server.port


def sync_client(host: str, port: int) -> redis.Redis:
    return redis.Redis(
        host=host,
        port=port,
        decode_responses=False,
        socket_connect_timeout=0.10,
        socket_timeout=0.05,
        retry_on_timeout=False,
        retry_on_error=[],
        health_check_interval=0,
    )
```

The readiness client is caller-owned and closed on every loop iteration; record
startup duration separately from adapter assertions. Integration timing uses
the observed `H`, `E = 0.10 + H * 0.05`, `P = E + 0.05`, `S = 2P`, `N = S`,
and `R = 2S + P`. The long-action case uses `lease_time=2.0s`,
`renew_interval=0.4s`, action duration `6.1s`, and an `8.0s` outer deadline;
it first asserts `N + 0.4 < 2.0` for that client's observed handshake shape.

- [ ] **Step 2: Write real sync/async lifecycle tests.** Cover acquire, renew,
  release, reacquire, owner mismatch, natural expiry, successor takeover,
  minimum lease, long action across three original TTLs, cancellation cleanup,
  action failure, delayed entry, malformed/no-TTL/wrong-type state, NOSCRIPT
  fallback, counter at `2^53`, overflow, and borrowed clients remaining usable.

Every real lifecycle test has an explicit outer deadline derived from its
`A/N/R` envelope plus a fixed scheduling margin. Sync cases run blocking work
behind a timed future/thread boundary and always release gates plus bounded-join
helpers in `finally`; async cases use one absolute `asyncio.timeout` and cancel
then await every retained test task in `finally`. Timeout messages identify
only the phase, never a lock/key/token/client value.

Hang-sensitive real sync lifecycle and 16x10 contention scenarios execute in a
spawned child process, not the pytest process that owns the deadline. The child
creates its own borrowed clients and returns exactly one fixed, secret-free
terminal record through a queue:

```python
@dataclass(frozen=True, slots=True)
class ChildResult:
    scenario_id: Literal["sync-lifecycle", "sync-contention"]
    status: Literal["passed", "failed"]
    public_outcome: Literal[
        "elected", "skipped", "action-failed", "backend-error",
        "lease-lost", "release-error", "execution-error",
    ]
    action_count: int
    fencing_relation: Literal["strictly-increasing", "not-applicable"]
    lease_cleanup: Literal["released", "ttl-only", "not-applicable"]
    worker_delta: int
    task_delta: int
    borrowed_client_usable: bool
    failure_kind: Literal["none", "assertion", "unexpected-public-outcome"]
```

No message, traceback, exception args, lock/key/token/client value, or raw
fencing number crosses the process boundary. The child converts a caught
assertion only to `failure_kind="assertion"` and exits nonzero; unexpected raw
exceptions produce a nonzero exit without serialization. The parent requires
exit code zero, exactly one terminal record, `status="passed"`, the scenario's
expected public outcome category, exact action count/fencing relation,
lease-key cleanup, zero worker/task delta, and usable borrowed client. Missing,
duplicate, malformed, failed, or unexpected-category records and every abnormal
exit fail the test after cleanup.

The parent enforces the computed deadline; on expiry it terminates and
joins the child, opens/cleans parent-owned fixtures, and reports only the phase.
Controlled in-process worker tests remain acceptable because their `finally`
blocks always unblock and join injected threads. This subprocess boundary
prevents an implementation deadlock or non-daemon worker leak from hanging the
pytest/CI process until the workflow timeout.

Add the exact stale-owner sequence for sync and async: old handle acquires,
expires, successor acquires, then old renew and release run. Assert the successor
record bytes are unchanged, its PTTL only decreases with elapsed time rather
than being extended/shortened by the old handle, and the old command trace
never reports successful `PEXPIRE` or `DEL`.

Create a temporary ACL user with only the documented `EVALSHA`, `EVAL`, `GET`
and in-script `TYPE`, `PTTL`, `INCR`, `SET`, `PEXPIRE`, `DEL` permissions plus
the leader prefix key pattern. Prove lifecycle success, then prove `SCRIPT
LOAD`, an unrelated command, and a key outside the prefix are denied. Remove the
test user in fixture cleanup; credentials never enter assertion text.

Run that ACL proof across the pinned connection-shape matrix from Task 4. The
default shape grants only adapter commands. RESP negotiation, non-default DB,
client name, and connection metadata shapes add only the exact conditional
HELLO/SELECT/CLIENT subcommand permissions witnessed by the handshake test;
document that mapping without credential values. Arbitrary commands, unrelated
keys, `SCRIPT LOAD`, and out-of-prefix access remain denied in every shape.

- [ ] **Step 3: Write quantitative contender/fencing tests.** For sync and async
  separately, prewarm scripts with a sacrificial logical name, then run 16
  contenders across 10 generations. Start each generation behind a barrier
  with `wait_time=0`; the winner holds its context until all 15 losers have
  returned, and only then releases. Assert exactly 16 acquire attempts, one
  action, strictly increasing fence tokens, each call inside its computed
  envelope, and zero extra workers/tasks after every generation. Measure
  `EVALSHA`/`EVAL`/`GET` deltas with a separate caller-owned `INFO commandstats`
  client so owner tokens and command arguments are never observed or logged.

Each generation has one absolute `A + R + scheduling_margin` deadline. Sync
uses timed `Barrier.wait`, loser-event waits, and `Future.result`; on failure it
opens every gate, requests cancellation, performs non-blocking executor
shutdown, and bounded-joins all contender threads in `finally`. Async wraps
barrier, winner gate, and gather in one `asyncio.timeout`; `finally` opens gates,
cancels unfinished contenders, awaits all with `return_exceptions=True`, and
asserts the pre-generation pending-task baseline.

For nonzero-wait unit cases, use integer monotonic arithmetic:
`max_attempts = 1 if wait_ns == 0 else ceil_div(wait_ns, 40_000_000)` and assert
`attempts <= max_attempts`; assert exactly one attempt separately at zero wait.

```python
def assert_strict_generations(results: list[list[int]]) -> None:
    assert len(results) == 10
    assert all(len(generation) == 1 for generation in results)
    fences = [generation[0] for generation in results]
    assert fences == sorted(set(fences))
```

- [ ] **Step 4: Write an atomic downstream fencing fixture.** A Lua-protected
  test resource stores `high_watermark` and payload together, accepts only
  `incoming > stored`, rejects equal replay and stale predecessor, and contrasts
  a deliberately non-atomic check/write test marked as unsupported evidence.
  After storing a high watermark, use an admin-only test hook to delete or roll
  back the Redis fence counter, acquire a lower token, and prove the downstream
  atomic write rejects it. This is evidence that counter persistence is a
  prerequisite for Redis monotonic issuance and downstream high-watermark
  enforcement is the final stale-write guard.

- [ ] **Step 5: Run RED against incomplete real behavior, then GREEN.** Before
  any integration correction, run the smallest failing test and record the
  intended failure. Fix only implementation defects, not acceptance assertions.

```bash
uv run pytest packages/bluetape-leader-redis/tests/test_sync_redis_integration.py -v -m testcontainers
uv run pytest packages/bluetape-leader-redis/tests/test_async_redis_integration.py -v -m testcontainers
uv run pytest packages/bluetape-leader-redis/tests/test_concurrency_integration.py -v -m testcontainers
```

Expected final result: all Issue #17 integration tests PASS with no leaked
threads, tasks, clients, or lease keys for proven-released contexts. Fencing
counter keys remain present and are never reset or deleted by production code.

- [ ] **Step 6: Commit real Redis evidence.**

```bash
git add packages/bluetape-leader-redis
git commit -m "Prove Redis lease safety under real contention" \
  -m "Constraint: Fencing is meaningful only with atomic downstream rejection" \
  -m "Confidence: high" \
  -m "Scope-risk: broad" \
  -m "Tested: Redis 8 sync, async, expiry, cancellation, 16x10 contention, and fencing integration"
```

## Task 9: Complete packaging, isolated installs, and bilingual operational docs

**Depends on:** Task 8

**Files:**

- Create `packages/bluetape-leader/tests/test_readme_examples.py`
- Create `packages/bluetape-leader-redis/tests/test_readme_examples.py`
- Create `packages/bluetape/tests/test_leader_wheel_isolation.py`
- Create `packages/bluetape/tests/test_leader_readmes.py`
- Modify both leader package README pairs
- Modify root `README.md`, `README.ko.md`
- Modify `packages/bluetape/README.md`, `README.ko.md`
- Modify `docs/package-layout.md`
- Modify `WIP.md`
- Modify `CHANGELOG.md`
- Modify `packages/bluetape/pyproject.toml`
- Modify root `pyproject.toml`
- Modify `.github/workflows/ci.yml`
- Modify `uv.lock`

- [ ] **Step 1: Write RED isolated-wheel and README tests.** Build wheels and
  prove: core-only installs without redis-py; adapter installs exact core+Redis;
  meta `leader` and `leader-redis` extras; default remains core-only; no root
  `bluetape/__init__.py`; exact exports; EN/KO examples execute; EN/KO headings,
  warning tables, and unsupported-scope entries stay aligned. Assign stable
  scenario IDs for install, constructor, contention, precise result, identity,
  fencing, cancellation, manual lifecycle, unsupported topology, migration,
  rollback, operator action table, and deployment checklist. Assert both
  languages contain the same scenario set and normalized option/API calls, not
  merely matching headings.

```python
def test_default_meta_wheel_does_not_install_leader(tmp_path: Path) -> None:
    env = install_wheels(tmp_path, "bluetape")
    result = env.run("python", "-c", "import bluetape.leader")
    assert result.returncode != 0


def test_leader_core_wheel_imports_without_redis(tmp_path: Path) -> None:
    env = install_wheels(tmp_path, "bluetape-leader")
    env.run_checked("python", "-c", "import bluetape.leader")
    assert not env.distribution_installed("redis")
```

- [ ] **Step 2: Run RED and confirm missing docs/install behavior.**

```bash
uv build --all-packages
uv run pytest packages/bluetape-leader/tests/test_readme_examples.py packages/bluetape-leader-redis/tests/test_readme_examples.py packages/bluetape/tests/test_leader_wheel_isolation.py packages/bluetape/tests/test_leader_readmes.py -v
```

Expected: FAIL on incomplete README examples, meta metadata, or isolation probes.

- [ ] **Step 3: Write aligned English/Korean documentation.** Include direct
  and meta installs, exact supported redis-py client construction, numeric IP
  or Unix socket, no TLS/hostname/retries/health checks/hooks, borrowed close
  ownership, manual sync/async contention guard, precise result API,
  cancellation, owner mismatch, lease loss, `is_held` TOCTOU, atomic fencing,
  single-primary/failover/partition/clock limits, ACL command list,
  coordination identity migration, counter restore/high-watermark, safe signals,
  lease-loss runbook, rollback, and deferred Redlock/group/strategic/backends.

The aligned docs include these executable caller contracts:

- warn that `run_if_leader()` returns `None` both for contention and for a
  successful action returning `None`; require `run_if_leader_result()` whenever
  `T` may be `None`, with exhaustive `Elected`/`Skipped`/`ActionFailed` examples;
- show guarded sync and async contexts, and reject documentation that uses
  `with lock.try_acquire(...)` or `async with await lock.try_acquire(...)`
  without first checking for `None`;
- state that `try_acquire()` starts no renewer, `auto_renew=True` begins only
  after context entry re-proves ownership, and the acquire-to-enter delay is
  covered only by the original TTL;
- show manual non-context sync/async use with explicit renew/checkpoints and
  `finally` release, alongside a lifecycle table contrasting it with scoped
  automatic renewal/cleanup;
- show async lock and elector cancellation that re-raises `CancelledError`
  after bounded owned cleanup and closes the borrowed client only in caller
  scope;
- include an identity table: `node_id` is physical caller identity,
  `audit_leader_id` is correlation text, and only integer `fencing_token`
  participates in downstream stale-write rejection;
- name a structured operator action table and deployment checklist. The
  checklist covers exact client construction, writable standalone primary,
  ACL, finite timeouts, TLS/hostname rejection, counter persistence/restore,
  downstream high-watermark, and rollback to an identical coordination
  identity.

The migration, restore, loss, and rollback procedures are ordered contracts,
not topic-only prose. EN/KO semantic tests require these exact steps:

1. stop every old and new contender and block new protected work;
2. prove the old lease absent without deleting or printing its value;
3. read and preserve every downstream resource high-watermark;
4. restore or seed the authoritative Redis counter strictly above the maximum
   downstream high-watermark;
5. configure every contender with one identical prefix, digest derivation,
   suffix set, and record version;
6. restart all contenders on that one coordination identity, then re-enable
   protected work.

The lease-loss runbook blocks new protected work, lets atomic downstream
fencing reject/abort stale writes, inspects caller-owned evidence, and never
deletes/resets coordination keys or prints lease values. Rollback removes
adapter usage/extras while leaving counters and expired lease keys intact; it
must not reintroduce a writer holding a token below a preserved downstream
high-watermark.

`LeaderBackendError` is intentionally non-diagnostic and exposes no backend
cause kind. EN/KO operator rows for suspected connection/pool timeout,
permission denial, protocol failure, and corruption must direct operators to
caller-owned Redis health, ACL, pool, and server evidence rather than branch on
or guess from the exception. Safe call-site signals label only public operation
and outcome categories and never names, IDs, keys, prefixes, tokens, or a
guessed backend cause.

Semantic parity tests require both languages to state that mutual exclusion is
only against one authoritative writable primary; asynchronous failover,
partitions, promotion, proxy/multi-primary routing, Sentinel, and Cluster can
violate that assumption. The exact caller-owned signal set is acquire
outcome/latency, renewal latency/loss, release failure, pool timeout, command
failure, and reconnect. Lock names, node/audit IDs, owner tokens, Redis
keys/prefixes, and fencing tokens are forbidden as log fields or metric labels.

```python
handle = lock.try_acquire("daily-job", options)
if handle is not None:
    with handle as held:
        update_if_newer(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

The docs must state that `update_if_newer` compares and commits high-watermark
plus business data in one transaction; it is not a check-then-write example.

- [ ] **Step 4: Wire required Redis leader CI, then update workspace status and
  release boundary.** Add a dedicated `leader-redis` required PR/push job with
  a job timeout, Docker runtime check, focused `--group test` sync, unit tests,
  and one non-xdist serial `-m testcontainers` invocation. Emit JUnit XML and
  assert collected tests are greater than zero with zero failures, errors, and
  skips. This is required because the generic job explicitly excludes
  `testcontainers` and the existing `redis-provider` job owns only
  `bluetape-cache-redis`.

  Mark Issue #17
  implemented in WIP/CHANGELOG only after all targeted tests pass. Register
  `leader` in meta `dev`/`all`; keep `leader-redis` explicit-only like
  `cache-redis`; keep default dependencies unchanged. The job remains in the
  existing `ci.yml`; do not create another workflow file.

  Nightly CI is evidence-backed `N/A`: the repository has no scheduled workflow
  and the full Redis leader integration suite is required on every PR/push
  instead. Coverage aggregation is evidence-backed `N/A`: the repository has
  no coverage plugin/reporting contract; do not add a dependency or invent a
  percentage in Issue #17. Record both decisions in the plan-review artifact.

- [ ] **Step 5: Run GREEN, build, metadata, and parity verification.**

```bash
uv lock
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv build --all-packages
uv run pytest packages/bluetape-leader packages/bluetape-leader-redis packages/bluetape/tests/test_leader_wheel_isolation.py packages/bluetape/tests/test_leader_readmes.py packages/bluetape-benchmark/tests/test_benchmark_packaging.py -v
uv run ruff check .
uv run ruff format --check .
actionlint
git diff --check
```

Expected: all focused tests/build/style checks exit 0.

- [ ] **Step 6: Commit packaging and documentation.**

```bash
git add pyproject.toml uv.lock README.md README.ko.md WIP.md CHANGELOG.md docs/package-layout.md packages/bluetape packages/bluetape-leader packages/bluetape-leader-redis
git commit -m "Document the bounded Redis leader operating contract" \
  -m "Constraint: First-slice topology and client exclusions must be explicit" \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: isolated wheels, README examples, metadata, build, Ruff, and diff hygiene"
```

## Task 10: Run full verification, reviews, lesson gate, and exact-head handoff

**Depends on:** Tasks 1-9

**Files:**

- Create `docs/review/2026-07-18-issue-17-leader-lock-contracts-tdd-evidence.md`
- Create `docs/review/2026-07-18-issue-17-leader-lock-contracts-performance-stability.md`
- Create `docs/review/2026-07-18-issue-17-leader-lock-contracts-code-review.md`
- Create `docs/review/2026-07-18-issue-17-leader-lock-contracts-verifier.md`
- Create `docs/lessons/2026-07-18-issue-17-leader-lock-contracts.md`
- Modify implementation files/tests/docs only when review findings require it

- [ ] **Step 1: Record complete RED/GREEN evidence.** For each task, capture
  exact failing test, intended failure, correction, passing command, and commit
  SHA. Do not claim TDD for a behavior without a witnessed intended RED.

- [ ] **Step 2: Run the performance/stability scan.** Record timing formulas,
  command counts, 16x10 contender results, peak/baseline thread counts, pending
  tasks, Redis startup evidence, and any flake reruns. Any regression or leak is
  blocking; do not average it away.

- [ ] **Step 3: Run the full fresh validation sequence.**

```bash
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv run pytest packages/bluetape-leader packages/bluetape-leader-redis -v
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
git diff --check
```

Expected:

- all Issue #17 targeted tests PASS;
- lint/format/build/actionlint/diff checks exit 0;
- full-suite result is recorded exactly. If the known benchmark startup failure
  recurs unchanged, report 2,373+ passes and that one approved baseline failure
  separately; any new failure blocks completion.

- [ ] **Step 4: Run six independent implementation review lenses.** Performance,
  stability, security, operator, developer/API, and user/caller reviewers return
  evidence-backed P0/P1/P2/P3 findings. The main session integrates all P0/P1,
  reruns affected tests/lenses, and records final P0=0/P1=0. P2/P3 are fixed or
  explicitly deferred with issue-backed rationale.

- [ ] **Step 5: Run the independent verifier.** Verify every acceptance criterion,
  exact exports/signatures, dependency isolation, client exclusions, timing
  envelopes, script statuses, failure tables, docs parity, build artifacts,
  baseline exception, and git cleanliness against the exact current HEAD.

- [ ] **Step 6: Write the mandatory Type A lesson.** Record reusable decisions:
  core/backend split, owner versus fencing identity, uncertainty reconciliation,
  bounded redis-py client restrictions, context-entry proof, terminal UNKNOWN,
  cancellation task retention, atomic downstream fencing, rejected Redlock/TLS,
  and the baseline-test distinction. Evidence-backed `N/A` is not appropriate
  because this feature creates reusable coordination rules.

- [ ] **Step 7: Commit review/lesson corrections and rerun stale evidence.**

```bash
git add docs/review docs/lessons packages pyproject.toml uv.lock README.md README.ko.md WIP.md CHANGELOG.md
git commit -m "Close leader delivery with reproducible safety evidence" \
  -m "Constraint: Exact-head review and lifecycle proof must match delivered code" \
  -m "Confidence: high" \
  -m "Scope-risk: broad" \
  -m "Tested: full targeted suite, workspace validation, six-lens review, and verifier"
```

If Step 4-6 require no file change beyond already committed evidence, do not
create an empty commit. Record the existing exact HEAD instead.

- [ ] **Step 8: Report merge-readiness prerequisites without creating a PR.**
  Provide branch, exact HEAD, commit list, targeted/full verification, known
  baseline exception, P0/P1 counts, worktree status, and remaining external
  gates. Because PR creation is not authorized by the approved scope, stop and
  request explicit repository/base/head PR authority. Merge remains a later
  fresh approval even after any PR becomes merge-ready.

## Final Definition of Done

- [ ] `bluetape-leader` is stdlib-only and imports without redis-py.
- [ ] `bluetape-leader-redis` depends only on core leader plus redis-py 8.0.1.
- [ ] Default meta installation remains core-only; extras and aggregate policy
  match the plan.
- [ ] Exact core and Redis exports/signatures are tested.
- [ ] Owner tokens are private, high entropy, stable per uncertain attempt, and
  absent from every caller-visible representation/error path.
- [ ] Acquire, renew, release, probe, corruption, NOSCRIPT, uncertainty, and
  minimum-lease semantics are atomic and classified.
- [ ] Sync/async handle states and first-entry proof match the specification.
- [ ] No renewal thread/task survives its scope; borrowed clients stay open.
- [ ] Result and manual-context failure matrices are fully tested.
- [ ] Real Redis tests prove expiry, takeover, cancellation, 16x10 contention,
  increasing fencing, stale-holder protection, and atomic downstream rejection.
- [ ] Bilingual docs state every topology, timing, security, migration,
  rollback, and unsupported-scope caveat.
- [ ] Targeted tests, Ruff, format, build, actionlint, and diff hygiene pass.
- [ ] Full-suite result is exact and the pre-existing benchmark exception is
  separated from Issue #17 behavior.
- [ ] Six-lens implementation review and verifier finish at P0=0/P1=0.
- [ ] Mandatory Type A lesson is committed.
- [ ] No PR, merge, release, publish, issue close, or cleanup side effect occurs
  without its separate explicit authority.
