# Issue #50 Local Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stdlib-only synchronous and asynchronous bounded TTL loading caches under `bluetape.cache` without widening the default `bluetape` installation.

**Architecture:** A focused `bluetape-cache` distribution exposes `TTLCache` and `AsyncTTLCache`. A private pure-state core owns TTL validation, monotonic expiry, bounded LRU metadata, mutation generations, and counters; separate sync and asyncio modules own their locks, flights, waiters, cancellation, and lifecycle. Redis coordination remains outside this package in issue #51.

**Tech Stack:** CPython 3.13.14, `uv_build`, Python 3.13 generics, `OrderedDict`, `heapq`, `threading.RLock`/`Condition`, `asyncio.Lock`/`Task`/`shield`, `ContextVar`, pytest, pytest-asyncio, Ruff, and uv.

---

Date: 2026-07-11
Issue: [#50](https://github.com/bluetape4k/bluetape-py/issues/50)
Approved spec: `docs/superpowers/specs/2026-07-11-issue-50-local-cache-design.md`
Status: Step 3-R reviewed — P0=0 P1=0; implementation remains blocked until user approval

## Execution Constraints

- Apply `$bluetape-py-patterns`, `$test-driven-development`, and `$verification-before-completion` at their workflow gates.
- Keep production dependencies empty and keep the default `bluetape` install dependent only on `bluetape-core`.
- Keep sync and async flight implementations separate. Share only deterministic validation, entry, expiry, LRU, version, and counter state transitions.
- Use fake monotonic clocks, `threading.Barrier`/`Event`, and `asyncio.Event`; do not use long sleeps for correctness or lifecycle proof.
- Treat task/thread leak, stale loader publication, swallowed cancellation, unbounded entry/flight metadata, default-install leakage, or public contract drift as P0/P1 blockers.
- Preserve original loader exception types and causes. Do not log or expose raw keys, values, loader identities, or exception messages through cache-owned observability.
- `set`, `invalidate`, and `clear` supersede current-generation flights but do not cancel sync loaders or async loaders with surviving waiters.
- Active, superseded, and abandoned owned flights all consume `max_inflight` until terminal cleanup.
- No workflow YAML change is planned: `.github/workflows/ci.yml` already syncs, tests, and builds all workspace packages. Re-open that file after registration and prove the new package is covered; edit it only if the existing commands fail to exercise the package.
- No README diagram is required: the existing workspace diagram already depicts the planned cache distribution, and this change activates that row without changing the topology.

## Step 3-P Risk Prediction

| Risk | Early signal | Mitigation and proof | Rollback or rerun point |
| --- | --- | --- | --- |
| A superseded or abandoned loader overwrites a newer explicit mutation | a post-race `get()` returns the loader result instead of the explicit value/miss | capture clear epoch and key version, require active-flight identity before publication, and test set/invalidate/clear races for sync and async | revert the affected loading task to its last green commit and rerun all mutation-generation tests |
| Async waiter cancellation leaks tasks or cancels work still needed by another waiter | named cache tasks remain after terminal cleanup, or surviving waiters receive cancellation | shield the shared task, count waiters under the lock, abandon only after the last waiter leaves, retain strong ownership until done, and inspect `asyncio.all_tasks()` | revert Task 5 and rerun the full async cancellation/lifecycle subset before later tasks |
| A cancellation-resistant loader creates unbounded replacement tasks | repeated last-waiter cancellation starts more than `max_inflight` owned tasks | keep abandoned tasks in the owned set and charge them to `max_inflight` until terminal completion | stop rollout, retain hard-limit behavior, and rerun saturation/recovery tests with a cancellation-suppressing loader |
| Entry or expiry metadata grows without bound under overwrite/expiry pressure | expiry heap exceeds `2 * max_size` after an operation or key-version entries outlive entries/flights | version stale nodes, rebuild the heap above the threshold, and assert internal boundedness in deterministic tests | revert the core state slice and rerun overwrite/expiry/version cleanup tests at multiple capacities |
| Lock scope serializes different-key loader bodies or causes deadlock | a barrier-based different-key test cannot start both loaders, or bounded joins time out | run loader bodies outside instance locks and keep lock sections limited to state/flight transitions | stop at Task 3/5, capture thread/task stacks, and rerun the concurrency subset after repair |
| Package registration widens the default installation | base meta wheel exposes `bluetape.cache` or depends on `bluetape-cache` | add only a `cache` forwarding extra, inspect wheel metadata, and run isolated no-index base/extra installs | revert root/meta pyproject and lock changes, then rebuild all wheels and rerun isolation smoke checks |
| Relative hot-path cost is disproportionate | hit median exceeds 25x the same-process `OrderedDict` reference, expiry-heavy normalized median exceeds 2.5x at 10x capacity, or fixed-batch tail/rebuild-trigger duration exceeds 15x | record non-gating benchmark JSON with environment, warm-up, repetitions, percentiles, throughput, and allocation/RSS data; profile before accepting a threshold breach | return to the last green implementation commit and optimize only with unchanged tests and a new measured hypothesis |

Risk gate: required because the feature combines cache hot paths, thread and task ownership, cancellation, mutation ordering, bounded metadata, public APIs, and new-package registration.

## File Structure

| Path | Responsibility |
| --- | --- |
| `packages/bluetape-cache/pyproject.toml` | Stdlib-only focused distribution metadata and `bluetape.cache` build mapping. |
| `packages/bluetape-cache/src/bluetape/cache/__init__.py` | Exact five-name public export surface. |
| `packages/bluetape-cache/src/bluetape/cache/_core.py` | Public stats/errors plus private TTL validation, entries, expiry heap, LRU, versions, epochs, and counters. |
| `packages/bluetape-cache/src/bluetape/cache/_sync.py` | `TTLCache`, sync flights, owner/waiter coordination, and recursion detection. |
| `packages/bluetape-cache/src/bluetape/cache/_async.py` | `AsyncTTLCache`, loop binding, task ownership, shielded waiters, abandonment, and async recursion detection. |
| `packages/bluetape-cache/tests/_support.py` | Fake monotonic clock and bounded task/thread inspection helpers. |
| `packages/bluetape-cache/tests/test_contracts.py` | Exports, constructor/TTL validation, stats immutability, typing-visible surface, and basic miss/value contracts. |
| `packages/bluetape-cache/tests/test_ttl_cache.py` | Sync TTL/LRU, mutation, loading, coalescing, saturation, and cleanup contracts. |
| `packages/bluetape-cache/tests/test_async_ttl_cache.py` | Async parity, loop binding, cancellation, abandonment, recursive load, saturation, and cleanup contracts. |
| `packages/bluetape-cache/tests/test_packaging.py` | Source-tree namespace and metadata assertions that remain fast in normal pytest. |
| `packages/bluetape-cache/benchmarks/cache_benchmark.py` | Deterministic non-gating latency, throughput, scaling, allocation, and RSS observation script. |
| `docs/review/artifacts/issue-50-local-cache-benchmark.json` | Committed raw benchmark samples, parameters, environment, and scenario results for independent threshold recalculation. |
| `packages/bluetape-cache/README.md` | Direct/meta-extra installation, sync/async examples, semantics, limits, and unsupported behavior. |
| `pyproject.toml`, `packages/bluetape/pyproject.toml`, `uv.lock` | Workspace membership/source, explicit meta extra, and reproducible resolution. |
| `README.md`, `README.ko.md`, `packages/bluetape/README.md`, `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Locale-parity package activation, meta-extra/package layout, usage, roadmap, and user-facing change record. |
| `docs/review/2026-07-11-issue-50-local-cache-*.md` | TDD, performance/stability, Step 6-R, and PR review evidence. |
| `docs/lessons/2026-07-11-issue-50-local-cache.md` | Durable implementation and review learning committed before PR creation. |

## Spec Coverage Map

| Approved requirement | Plan tasks |
| --- | --- |
| Exact public API, validation taxonomy, `KeyError` miss, `None` value, stats snapshot | 1, 2 |
| Monotonic TTL, exact boundary, bounded LRU, expiry heap rebuild, live size | 2 |
| Sync same-key coalescing, different-key loader concurrency, recursion, failures, mutation ordering | 3 |
| Async parity, single-loop ownership, shielded waiters, cancellation, abandonment, recursion | 4, 5 |
| Bounded active/superseded/abandoned flights and current gauges | 3, 5 |
| Thin default install, direct distribution, `bluetape[cache]`, workspace/lock/build/import proof | 1, 6 |
| English package README plus root English/Korean parity, WIP, changelog | 7 |
| Performance/stability evidence and bounded metadata/lifecycle scans | 8 |
| Full verification, six-lens review, lesson, PR/CI/knowledge gates | 9 |

## Exact Public Contract Blueprint

The implementation tasks must preserve these names, field order, signatures, and return types exactly:

```python
import time
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    loads: int
    load_failures: int
    load_rejections: int
    coalesced_waiters: int
    evictions: int
    expirations: int
    invalidations: int
    inflight_loads: int
    abandoned_loads: int
    superseded_loads: int


class RecursiveLoadError(RuntimeError): ...
class CacheLoadLimitError(RuntimeError): ...


class TTLCache(Generic[K, V]):
    def __init__(self, *, default_ttl: float, max_size: int,
                 max_inflight: int | None = None,
                 clock: Callable[[], int] = time.monotonic_ns) -> None: ...
    def get(self, key: K) -> V: ...
    def set(self, key: K, value: V, *, ttl: float | None = None) -> None: ...
    def invalidate(self, key: K) -> bool: ...
    def clear(self) -> None: ...
    def get_or_load(self, key: K, loader: Callable[[K], V], *,
                    ttl: float | None = None) -> V: ...
    def stats(self) -> CacheStats: ...
    def __len__(self) -> int: ...


class AsyncTTLCache(Generic[K, V]):
    def __init__(self, *, default_ttl: float, max_size: int,
                 max_inflight: int | None = None,
                 clock: Callable[[], int] = time.monotonic_ns) -> None: ...
    async def get(self, key: K) -> V: ...
    async def set(self, key: K, value: V, *, ttl: float | None = None) -> None: ...
    async def invalidate(self, key: K) -> bool: ...
    async def clear(self) -> None: ...
    async def get_or_load(self, key: K,
                          loader: Callable[[K], Awaitable[V]], *,
                          ttl: float | None = None) -> V: ...
    async def stats(self) -> CacheStats: ...
    async def size(self) -> int: ...
```

The ellipses in this blueprint denote signature-only documentation, not implementation placeholders. Tasks 1-5 replace each surface with the named RED/GREEN behavior below before its commit.

## Mandatory Per-Test TDD Micro-Cycle

For every named test in Tasks 1-5, execute these as separate checkboxes before moving to the next named test:

- [ ] Add exactly one named test and its deterministic fixture/teardown.
- [ ] Run `uv run pytest <test-file>::<test-name> -q`; expect failure from the one missing contract (missing method/type for the first slice, then an assertion mismatch for later slices), never collection/environment failure.
- [ ] Implement only the state transition or terminal branch required by that test, using the exact public blueprint and private algorithms in the owning task.
- [ ] Rerun the identical node ID and expect one pass.
- [ ] Run the whole owning test file and expect all accumulated tests to pass before adding the next node.

Task-level RED/GREEN commands below are integration checks after the individual node cycles; they do not replace them. Commit only at each task's explicit commit point so a task remains one reviewable behavior family.

## Task 1: Register the focused package and lock the public contract

**Complexity:** Medium
**Depends on:** Approved spec only
**Write scope:** Package scaffold, root workspace metadata, public initializer, `_core.py`, contract tests
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache/pyproject.toml`
- Create: `packages/bluetape-cache/README.md`
- Create: `packages/bluetape-cache/src/bluetape/cache/__init__.py`
- Create: `packages/bluetape-cache/src/bluetape/cache/_core.py`
- Create: `packages/bluetape-cache/src/bluetape/cache/_sync.py`
- Create: `packages/bluetape-cache/src/bluetape/cache/_async.py`
- Create: `packages/bluetape-cache/tests/_support.py`
- Create: `packages/bluetape-cache/tests/test_contracts.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add the failing public-contract tests**

Create `test_exact_exports_and_stats_shape`, `test_cache_constructors_are_keyword_only`, `test_constructor_rejects_invalid_default_ttl`, `test_constructor_rejects_invalid_max_size`, and `test_constructor_rejects_invalid_max_inflight`. Verify frozen/slotted `CacheStats`, exact constructor signatures, and validation order. The parameter table must include bool, string, NaN, infinities, zero, negative, and positive sub-nanosecond TTL values:

```python
INVALID_TTLS = [
    (True, TypeError),
    ("1", TypeError),
    (float("nan"), ValueError),
    (float("inf"), ValueError),
    (0.0, ValueError),
    (-1.0, ValueError),
    (0.5e-9, ValueError),
]

EXPECTED_EXPORTS = [
    "TTLCache",
    "AsyncTTLCache",
    "CacheStats",
    "RecursiveLoadError",
    "CacheLoadLimitError",
]
```

The constructor table must separately prove `max_size` and `max_inflight` reject bool/non-int with `TypeError` and values below one with `ValueError`. Assert `max_inflight=None` is accepted and resolves to `max_size` through behavior rather than a public attribute.

- [ ] **Step 2: Register the package and run the tests red**

Add `bluetape-cache==0.1.0` to the root workspace dependencies/sources/members and create:

```toml
[project]
name = "bluetape-cache"
version = "0.1.0"
description = "Stdlib-only bounded local caches for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.cache"
```

Create a minimal package README with the title and source-workspace availability note so metadata resolution can run; Task 7 expands it into the complete public guide. Then execute:

```bash
uv lock
uv sync --all-packages --all-extras --locked
uv run pytest packages/bluetape-cache/tests/test_contracts.py -q
```

Expected: lock/sync succeed and pytest fails because the public implementation does not exist.

- [ ] **Step 3: Implement public values and deterministic validation**

In `_core.py`, define frozen/slotted `CacheStats`, the two public exceptions, and private validators. Convert seconds with `math.isfinite()` and `int(value * 1_000_000_000)` only after type/range validation; reject a converted value below one nanosecond. Keep messages stable and parameter-specific:

```python
def _ttl_ns(value: float, parameter: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{parameter} must be a finite positive number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{parameter} must be a finite positive number")
    nanoseconds = int(value * 1_000_000_000)
    if nanoseconds < 1:
        raise ValueError(f"{parameter} must be at least one nanosecond")
    return nanoseconds


def _positive_int(value: int, parameter: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{parameter} must be an integer")
    if value < 1:
        raise ValueError(f"{parameter} must be greater than 0")
    return value
```

Create constructor-complete `TTLCache`/`AsyncTTLCache` types in `_sync.py` and `_async.py`: validate and store the clock, default TTL nanoseconds, `max_size`, and resolved `max_inflight`; initialize the lock/state ownership fields named in later tasks. Task 2 adds public state methods and Task 3/4 add loading methods after their RED tests. Export exactly the five approved names from `__init__.py`.

- [ ] **Step 4: Run contract tests green and commit**

```bash
uv run pytest packages/bluetape-cache/tests/test_contracts.py -q
uv lock --check
git diff --check
```

Inspect the broad CI ownership immediately after registration:

```bash
rg -n 'uv sync --all-packages|uv run .*pytest|uv build --all-packages' .github/workflows/ci.yml
uv run pytest --collect-only packages/bluetape-cache/tests -q
```

Expected: all contract tests pass, the lock is current, the diff check is clean, and normal CI's all-package sync/test/build path collects the new package tests. If any broad command is absent or excludes the package, add the narrow workflow repair in this task, run `actionlint`, and include that workflow file in the commit; otherwise leave CI YAML unchanged.

Commit intent: `feat: establish bounded local cache contracts` with Lore trailers recording stdlib-only scope, thin-install constraint, focused tests, and implementation gaps still pending.

**Rollback/rerun:** Revert only the package registration/public-contract commit if workspace resolution or namespace ownership fails; rerun `uv lock`, contract tests, and `uv build --package bluetape-cache` before Task 2.

## Task 2: Implement TTL, LRU, expiry, mutation, and stats state

**Complexity:** High
**Depends on:** Task 1
**Write scope:** `_core.py`, basic sync/async state methods, contract and sync tests
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-cache/src/bluetape/cache/_core.py`
- Modify: `packages/bluetape-cache/src/bluetape/cache/_sync.py`
- Modify: `packages/bluetape-cache/src/bluetape/cache/_async.py`
- Modify: `packages/bluetape-cache/src/bluetape/cache/__init__.py`
- Create: `packages/bluetape-cache/tests/test_ttl_cache.py`
- Create: `packages/bluetape-cache/tests/test_async_ttl_cache.py`
- Modify: `packages/bluetape-cache/tests/test_contracts.py`

- [ ] **Step 1: Write RED tests for deterministic entry state**

Add these named tests for both public classes, using the fake clock and no wall-clock sleeps:

- `test_non_loading_state_method_signatures_match_public_contract`
- `test_set_get_preserves_none_and_mutable_identity`
- `test_get_missing_and_unhashable_keys_preserve_native_errors`
- `test_default_and_per_entry_ttl_expire_at_exact_tick`
- `test_clock_rollback_is_clamped`
- `test_successful_access_and_overwrite_move_entry_to_mru`
- `test_insert_purges_expired_before_evicting_live_lru`
- `test_growing_write_compacts_expiry_heap_after_push`
- `test_invalidate_result_clear_and_stats_lifetime`
- `test_size_reports_only_live_entries`

For `AsyncTTLCache`, also add `test_first_public_use_binds_event_loop`, `test_second_event_loop_is_rejected`, and `test_simultaneous_first_use_has_one_winning_loop`. Every loop is closed and every thread is joined in `finally` with finite timeouts.

Add a focused internal boundedness test that repeatedly overwrites and expires keys, then asserts the private expiry heap is no larger than `2 * max_size` after an operation and key-version metadata is removed when no entry or flight owns the key.

- [ ] **Step 2: Run the state tests red**

```bash
uv run pytest packages/bluetape-cache/tests/test_contracts.py packages/bluetape-cache/tests/test_ttl_cache.py packages/bluetape-cache/tests/test_async_ttl_cache.py -q
```

Expected: failures identify missing expiry/LRU/version/counter behavior and missing atomic async loop ownership.

- [ ] **Step 3: Implement the pure state machine and thin lock wrappers**

Use one `_CacheState[K, V]` owned by each cache instance. Its mutation methods are called only while the owning sync/async lock is held. Use these concrete private values:

```python
@dataclass(slots=True)
class _Entry[V]:
    value: V
    expires_at: int
    version: int


class _CacheState[K: Hashable, V]:
    entries: OrderedDict[K, _Entry[V]]
    expiry_heap: list[tuple[int, int, K, int]]
    key_versions: dict[K, int]
    clear_epoch: int
    last_tick: int
```

Every public operation samples/clamps the clock once. `_purge_expired(now)` pops heap nodes through `now`, removes only matching live entry versions, and increments `expirations`. Every heap-growing `set()` or successful loader publication performs this exact order: purge expiry, supersede/version the key, insert the MRU entry, push its versioned expiry node, evict live LRU entries until capacity fits, then rebuild from current live entries when `len(expiry_heap) > 2 * max_size`. The post-push/post-eviction rebuild guarantees the bound after every completed write. `invalidate()` removes an expired/live entry consistently, supersedes any active flight through a callback owned by the wrapper, increments `invalidations` only for a removed live entry, and returns that boolean. `clear()` increments the epoch, clears entries/heap, and preserves lifetime counters.

The shared write primitive has this concrete ordering:

```python
def store(self, key: K, value: V, *, ttl_ns: int, now: int,
          owned_keys: AbstractSet[K]) -> None:
    self.purge_expired(now)
    version = self.bump_version(key)
    expires_at = now + ttl_ns
    self.entries[key] = _Entry(value=value, expires_at=expires_at, version=version)
    self.entries.move_to_end(key)
    self.sequence += 1
    heapq.heappush(self.expiry_heap, (expires_at, self.sequence, key, version))
    while len(self.entries) > self.max_size:
        evicted_key, _ = self.entries.popitem(last=False)
        self.evictions += 1
        self.drop_unused_version(evicted_key, owned_keys=owned_keys)
    if len(self.expiry_heap) > 2 * self.max_size:
        self.rebuild_expiry_heap()
```

Loader publication calls this same primitive only after its generation/identity gate; it does not duplicate heap logic.

Implement `TTLCache` public state methods under `threading.RLock`. Before any async public method touches state, atomically bind the instance through a dedicated `threading.Lock`; the winning loop creates and owns the `asyncio.Lock`, and a losing simultaneous caller receives `RuntimeError` without replacing or using that lock:

```python
def _require_loop(self) -> asyncio.AbstractEventLoop:
    loop = asyncio.get_running_loop()
    with self._loop_guard:
        if self._loop is None:
            self._loop = loop
            self._lock = asyncio.Lock()
        elif self._loop is not loop:
            raise RuntimeError("AsyncTTLCache is bound to a different event loop")
    return loop
```

Run `get`, `set`, `invalidate`, `clear`, `stats`, and `size` only after this guard and under the winning loop's lock.

- [ ] **Step 4: Run state tests green and commit**

```bash
uv run pytest packages/bluetape-cache/tests/test_contracts.py packages/bluetape-cache/tests/test_ttl_cache.py packages/bluetape-cache/tests/test_async_ttl_cache.py -q
git diff --check
```

Expected: deterministic state tests and atomic cross-loop ownership tests pass, all test loops/threads terminate, and no loader test has been enabled prematurely.

Commit intent: `feat: bound local cache entry state` with tested TTL/LRU/expiry/mutation/stat commands.

**Rollback/rerun:** Revert the state commit if metadata bounds or counter semantics cannot be proved without exposing new public API. Rerun Task 1 plus all Task 2 state tests after repair.

## Task 3: Implement synchronous loading and flight ownership

**Complexity:** High
**Depends on:** Task 2
**Write scope:** `_sync.py`, sync tests, shared gauges only
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-cache/src/bluetape/cache/_sync.py`
- Modify: `packages/bluetape-cache/src/bluetape/cache/_core.py`
- Modify: `packages/bluetape-cache/tests/test_ttl_cache.py`

- [ ] **Step 1: Write RED tests for sync loading lifecycle**

Use finite timeouts on every `Barrier.wait()`, `Event.wait()`, condition, and `Thread.join()` boundary. Each test owns `try/finally` teardown that aborts barriers, releases events, and joins every created thread even after assertion failure. Add these named tests:

- `test_same_key_uses_one_owner_loader_and_ttl`
- `test_get_or_load_signature_matches_public_contract`
- `test_different_key_loader_bodies_enter_concurrently`
- `test_loader_failure_is_shared_not_cached_and_preserves_exception`
- `test_owner_only_success_and_failure_cleanup_flights_and_versions`
- `test_same_thread_same_key_recursion_is_rejected`
- `test_set_invalidate_and_clear_supersede_without_stale_publication`
- `test_post_mutation_caller_never_joins_superseded_flight`
- `test_active_and_superseded_flights_consume_limit_until_terminal`
- `test_sync_loading_stats_change_at_exact_ownership_transitions`

- [ ] **Step 2: Run sync loading tests red**

```bash
uv run pytest packages/bluetape-cache/tests/test_ttl_cache.py -q
```

Expected: failures are limited to missing loading/flight behavior.

- [ ] **Step 3: Implement sync flight coordination outside loader bodies**

Define a per-flight condition sharing the cache `RLock` and explicit state:

```python
@dataclass(slots=True, eq=False, repr=False)
class _SyncFlight[K, V]:
    key: K
    epoch: int
    version: int
    ttl_ns: int
    owner_thread: int
    condition: threading.Condition
    terminal: bool = False
    superseded: bool = False
    result: V | None = None
    error: BaseException | None = None
```

Keep `_active_flights: dict[K, _SyncFlight[K, V]]` separate from `_owned_flights: set[_SyncFlight[K, V]]`. A waiter holds its flight reference while `Condition.wait_for(flight.terminal)` releases the lock. The owner invokes `loader(key)` outside the lock, records the original result/error under the lock, publishes only when epoch/version/identity still match, removes terminal ownership on every path, notifies all waiters, and re-raises the original exception. Detect recursion with a thread-local set of `(id(cache), key)` tokens restored in `finally`; `get_or_load()` checks membership before cache lookup or flight joining so a recursive call cannot evade rejection through a concurrent hit.

Use one terminal helper on success and failure so no branch omits cleanup:

```python
def _finish_flight(self, flight: _SyncFlight[K, V], *,
                   result: V | None, error: BaseException | None) -> None:
    with self._lock:
        can_publish = (
            error is None
            and not flight.superseded
            and self._state.clear_epoch == flight.epoch
            and self._state.version(flight.key) == flight.version
            and self._active_flights.get(flight.key) is flight
        )
        if can_publish:
            self._state.store(
                flight.key,
                cast(V, result),
                ttl_ns=flight.ttl_ns,
                now=self._state.now(),
                owned_keys={owned.key for owned in self._owned_flights},
            )
        flight.result = result
        flight.error = error
        flight.terminal = True
        if self._active_flights.get(flight.key) is flight:
            del self._active_flights[flight.key]
        self._owned_flights.discard(flight)
        self._state.drop_unused_version(
            flight.key,
            owned_keys={owned.key for owned in self._owned_flights},
        )
        flight.condition.notify_all()
```

The real implementation uses a private result sentinel so a successful `None` is distinct from “no result assigned.” The owner calls `_finish_flight` in `finally` after capturing either the returned value or original exception, then returns the value or raises the same exception object.

Increment `loads` per invocation, `load_failures` per loader exception, `coalesced_waiters` per joining caller, and `load_rejections` per hard-limit rejection. Derive all current flight gauges under the same lock from the owned set rather than maintaining independently drifting counts.

- [ ] **Step 4: Run sync tests green and commit**

```bash
uv run pytest packages/bluetape-cache/tests/test_ttl_cache.py -q
uv run pytest packages/bluetape-cache/tests/test_contracts.py -q
git diff --check
```

Expected: all sync and contract tests pass with bounded joins and no live helper threads.

Commit intent: `feat: coalesce bounded synchronous cache loads`.

**Rollback/rerun:** Any join timeout, stale publication, or owned-flight residue blocks Task 4. Capture thread stacks, revert Task 3 if necessary, and rerun the entire sync file rather than accepting a retry pass.

## Task 4: Implement async loading, coalescing, and mutation generations

**Complexity:** High
**Depends on:** Task 2; follows Task 3 so shared counter/version semantics are already fixed
**Write scope:** `_async.py`, async loading tests
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-cache/src/bluetape/cache/_async.py`
- Modify: `packages/bluetape-cache/tests/test_async_ttl_cache.py`

- [ ] **Step 1: Write RED tests for async loading without caller cancellation**

Add `test_async_get_or_load_signature_matches_public_contract`, `test_async_same_key_uses_one_owner_loader_and_ttl`, `test_async_different_key_loader_bodies_progress_together`, `test_async_loader_failure_is_shared_not_cached`, `test_async_owner_only_terminal_paths_cleanup`, `test_inherited_child_task_same_key_recursion_is_rejected`, `test_async_mutations_prevent_stale_publication`, and `test_async_post_mutation_caller_uses_new_generation`. Every event wait and task completion uses a finite `asyncio.timeout()` or `wait_for()` boundary and `finally` cancels/releases/gathers all test-owned tasks.

- [ ] **Step 2: Run async parity tests red**

```bash
uv run pytest packages/bluetape-cache/tests/test_async_ttl_cache.py -q
```

Expected: failures identify missing async flight/coalescing/generation behavior.

- [ ] **Step 3: Implement strongly owned active flights and recursion scope**

Create an `_AsyncFlight` identity under the cache lock, add it to separate active and owned collections, initialize the owner waiter count, and create an opaque-sequence named task before releasing the lock. Existing same-generation callers join that flight and increment the waiter count. The task invokes the loader outside the lock, then publishes only when epoch/version/active identity still match.

```python
@dataclass(slots=True, eq=False, repr=False)
class _AsyncFlight[K, V]:
    key: K
    epoch: int
    version: int
    ttl_ns: int
    sequence: int
    task: asyncio.Task[V] | None = None
    waiters: int = 0
    abandoned: bool = False
    superseded: bool = False


_LOAD_SCOPE: ContextVar[frozenset[tuple[int, Hashable]]] = ContextVar(
    "bluetape_cache_load_scope",
    default=frozenset(),
)
```

Add `(id(cache), key)` through the returned ContextVar token and reset it in task `finally`; `get_or_load()` rejects any key already in the inherited stack before cache lookup, flight creation, or joining, so a recursive call cannot evade rejection through a concurrent hit. Terminal cleanup removes owned state and unused versions on every ordinary success/failure path. Task 5 adds shielded cancellation, abandonment, and saturation behavior.

The loader task follows one concrete terminal structure; `_complete_async_flight()` performs the same epoch/version/identity publication gate and post-publication heap compaction as the sync helper:

```python
async def _run_loader(self, flight: _AsyncFlight[K, V],
                      loader: Callable[[K], Awaitable[V]]) -> V:
    token = _LOAD_SCOPE.set(_LOAD_SCOPE.get() | {(id(self), flight.key)})
    try:
        result = await loader(flight.key)
    except BaseException:
        async with self._lock:
            self._state.load_failures += 1
            self._complete_async_flight(flight, result=None, publish=False)
        raise
    else:
        async with self._lock:
            publish = self._can_publish(flight)
            self._complete_async_flight(flight, result=result, publish=publish)
        return result
    finally:
        _LOAD_SCOPE.reset(token)
```

`_complete_async_flight()` removes the matching active identity, discards owned state, drops unused key-version metadata, and never formats caller objects. Task 5 extends this terminal structure for abandoned cancellation-resistant loaders without changing ordinary success/failure semantics.

- [ ] **Step 4: Run async parity tests green and commit**

```bash
uv run pytest packages/bluetape-cache/tests/test_async_ttl_cache.py -q -k 'not cancel and not abandon and not saturation'
git diff --check
```

Expected: async state and non-cancellation loading tests pass with no owned-flight or ContextVar residue.

Commit intent: `feat: coalesce asynchronous cache loads`.

**Rollback/rerun:** Any stale publication, inherited recursion miss, or owned-flight residue blocks Task 5. Revert Task 4 and rerun the complete non-cancellation async loading subset after repair.

## Task 5: Implement async loading, cancellation, abandonment, and saturation

**Complexity:** Very high
**Depends on:** Tasks 3 and 4
**Write scope:** `_async.py`, async lifecycle tests, shared gauge access only
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-cache/src/bluetape/cache/_async.py`
- Modify: `packages/bluetape-cache/tests/test_async_ttl_cache.py`
- Modify: `packages/bluetape-cache/src/bluetape/cache/_core.py` only if a pure state transition is missing

- [ ] **Step 1: Write RED tests for shared-task lifecycle**

Every event wait and task completion uses finite `asyncio.timeout()`/`wait_for()` bounds. Each test owns `finally` teardown that releases cancellation-resistant loaders, cancels remaining test-owned tasks, and gathers them with `return_exceptions=True` before asserting zero residual cache tasks. Add these named tests:

- `test_cancelled_waiter_does_not_cancel_surviving_waiter_load`
- `test_last_waiter_cancellation_returns_before_slow_loader_cleanup`
- `test_cancellation_suppressing_loader_cannot_publish_and_keeps_slot`
- `test_new_generation_never_joins_abandoned_or_superseded_flight`
- `test_loader_self_cancellation_cleans_owned_state_and_counts_failure`
- `test_async_saturation_allows_joiners_rejects_new_keys_and_recovers`
- `test_async_loading_counters_and_current_gauges_are_exact`
- `test_task_names_and_stats_never_expose_secret_sentinel`
- `test_every_terminal_scenario_leaves_no_named_cache_task`

- [ ] **Step 2: Run async loading tests red**

```bash
uv run pytest packages/bluetape-cache/tests/test_async_ttl_cache.py -q
```

Expected: failures are limited to missing async flight behavior.

- [ ] **Step 3: Extend the owned flights with shielded cancellation**

Under the cache lock, initialize the owner caller's waiter count, add the flight to active and owned collections, and create the task with an opaque sequence name before releasing the lock; joining callers increment the same count under that lock. Await only through `asyncio.shield(task)`. In caller `finally`, decrement waiters under the cache lock. When the last waiter leaves a non-terminal task, mark abandoned, remove matching active identity, increment the key generation, then call `task.cancel()` outside the lock and immediately finish caller cancellation.

Use this exact cancellation ownership shape:

```python
task_to_cancel: asyncio.Task[V] | None = None
try:
    return await asyncio.shield(flight.task)
finally:
    async with self._lock:
        flight.waiters -= 1
        if flight.waiters == 0 and flight.task is not None and not flight.task.done():
            flight.abandoned = True
            if self._active_flights.get(flight.key) is flight:
                del self._active_flights[flight.key]
            self._state.bump_version(flight.key)
            task_to_cancel = flight.task
    if task_to_cancel is not None:
        task_to_cancel.cancel()
```

Do not await `task_to_cancel` from the cancelled caller. The owned set and done callback keep it observable until `_run_loader` reaches terminal cleanup.

The loader task uses the Task 4 recursion stack, so nested different-key loads and inherited child tasks still detect re-entry into any active ancestor key. Under the cache lock it publishes only if epoch/version/active identity match and the flight is neither abandoned nor superseded. Its terminal cleanup always removes owned state and unused key-version metadata. Add a done callback that calls `task.exception()` and suppresses only native `CancelledError` so no orphan exception warning remains. Private flight dataclasses use `repr=False`, and cache code never formats flight/key/value/loader/error objects for diagnostics.

- [ ] **Step 4: Run async lifecycle tests green and repeat the riskiest cases**

```bash
uv run pytest packages/bluetape-cache/tests/test_async_ttl_cache.py -q
for iteration in 1 2 3 4 5 6 7 8 9 10; do
  uv run pytest packages/bluetape-cache/tests/test_async_ttl_cache.py -q \
    -k 'cancel or abandon or supersed or first_use' || exit 1
done
```

Do not add a repeat plugin. Preserve any raw failure from the loop and investigate it as lifecycle evidence. Expected: all iterations pass with no pending task warnings.

- [ ] **Step 5: Run combined cache tests and commit**

```bash
uv run pytest packages/bluetape-cache/tests -q
uv run ruff check packages/bluetape-cache
uv run ruff format --check packages/bluetape-cache
git diff --check
```

Commit intent: `feat: preserve async cache loads across waiter cancellation`.

**Rollback/rerun:** Any pending task, swallowed cancellation, stale write, or retry-only pass blocks packaging. Revert Task 5 to the last green loop-bound cache and rerun the complete async file after root-cause repair.

## Task 6: Complete meta extras and isolated packaging proof

**Complexity:** Medium
**Depends on:** Tasks 1-5
**Write scope:** Meta package metadata, lock, packaging tests
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape/pyproject.toml`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `packages/bluetape-cache/tests/test_packaging.py`

- [ ] **Step 1: Write RED metadata and namespace tests**

Assert the focused package has no production dependencies, requires Python 3.13+, uses `bluetape.cache`, and the meta package has an exact `cache = ["bluetape-cache==0.1.0"]` extra. Assert `cache` is present in `dev` and `all` only if the repository convention is to aggregate every stdlib package; the chosen plan is to include it in both because those extras currently aggregate active workspace packages, while default dependencies remain core-only.

- [ ] **Step 2: Add the forwarding extra and refresh the lock**

Add:

```toml
cache = ["bluetape-cache==0.1.0"]
```

Add `bluetape-cache==0.1.0` to `dev` and `all`. Verify, but do not duplicate, the workspace dependency/source/member entries created in Task 1; Task 6 mutates only the meta extras and resulting lock state. Then run:

```bash
uv lock
uv sync --all-packages --all-extras --locked
uv run pytest packages/bluetape-cache/tests/test_packaging.py -q
```

Expected: metadata tests pass and the default dependency list remains exactly `bluetape-core==0.1.0`.

- [ ] **Step 3: Build and perform isolated no-index installation smoke checks**

```bash
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
uv build --all-packages --out-dir "$tmp_dir/dist"

uv venv "$tmp_dir/base"
uv pip install --python "$tmp_dir/base/bin/python" --no-index --find-links "$tmp_dir/dist" "bluetape==0.1.0"
"$tmp_dir/base/bin/python" -c 'import importlib.util; import bluetape.core; assert importlib.util.find_spec("bluetape.cache") is None'

uv venv "$tmp_dir/cache"
uv pip install --python "$tmp_dir/cache/bin/python" --no-index --find-links "$tmp_dir/dist" "bluetape[cache]==0.1.0"
"$tmp_dir/cache/bin/python" -c 'from bluetape.cache import AsyncTTLCache, TTLCache; assert TTLCache and AsyncTTLCache'
```

Expected: base installation cannot discover `bluetape.cache`; explicit extra imports both public classes from local wheels only.

- [ ] **Step 4: Commit packaging state**

```bash
uv lock --check
git diff --check
```

Commit intent: `build: expose cache through an explicit meta extra`.

**Rollback/rerun:** If base isolation fails, revert the meta/root metadata and lock together, inspect wheel `METADATA`, then rebuild into a fresh temporary directory before retrying.

## Task 7: Document installation, semantics, and roadmap parity

**Complexity:** Medium
**Depends on:** Task 6 public/package shape
**Write scope:** README and roadmap/changelog files only
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Replace scaffold content: `packages/bluetape-cache/README.md`
- Modify: `packages/bluetape/README.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write executable package README examples**

Document future direct and `bluetape[cache]` registry installation separately from the currently executable source-workspace path. Include `uv sync --all-packages --locked` followed by `uv run --package bluetape-cache python -c 'from bluetape.cache import AsyncTTLCache, TTLCache; assert TTLCache and AsyncTTLCache'`. Document sync/async default/per-entry TTL, `KeyError` miss, cached `None`, invalidation results, same-key owner loader/TTL precedence, tenant/auth context in keys, mutable identity, async waiter cancellation, active-loader mutation behavior, `max_inflight`, stats gauges, and unsupported Redis/background-expiry/byte-sizing behavior. State explicitly that lifetime counters survive `clear()`, gauges are point-in-time values, no callback/listener surface exists, and monitoring integrations must poll snapshots or wrap public operations in caller-owned instrumentation. Warn that `KeyError(key)` and original loader exceptions are unsanitized caller-visible surfaces: secret-bearing keys/exceptions must not be logged or sent to telemetry before caller redaction. State that a cancellation-resistant loader keeps its owned slot until terminal and therefore requires caller-owned deadlines/cooperative cancellation. State that this is a new API with no compatibility alias or migration path, and that Redis behavior belongs to #51.

Every Python example must run unchanged under:

```bash
uv run --package bluetape-cache python -m doctest packages/bluetape-cache/README.md
```

If narrative async examples are not valid doctest blocks, mark them `python` rather than `pycon` and add an equivalent executable smoke snippet to `test_contracts.py`.

- [ ] **Step 2: Update root English/Korean parity and status**

Change the `bluetape-cache` row from planned to active/source workspace, add future `pip install "bluetape[cache]"` and direct-install lines, and add the same currently executable `uv sync`/`uv run --package bluetape-cache` smoke path to both root locales. Add matched sync/async usage sections in both locales and state that Redis coordination is deferred to #51. Keep those root examples behaviorally identical to the package README examples and lock the same flows in `test_contracts.py`. Update the meta-package README extra table and `docs/package-layout.md` distribution map without creating a root import surface. Update `WIP.md` so #11 is the umbrella, #50 is implemented by this branch, and #51 remains pending. Add an `[Unreleased]` entry describing bounded sync/async TTL loading caches and that no migration alias is needed for this new API.

- [ ] **Step 3: Validate docs and commit**

```bash
uv run --package bluetape-cache python -m doctest packages/bluetape-cache/README.md
git diff --check
```

Manually compare root README headings, install commands, package table rows, examples, and Redis deferral line across locales. Expected: semantic parity with audience-appropriate language.

Commit intent: `docs: make local cache adoption and limits explicit`.

**Rollback/rerun:** Documentation can be reverted independently only if no public source/metadata name changes. Any source/docs mismatch returns to the first affected implementation task.

## Task 8: Record deterministic performance and stability evidence

**Complexity:** High
**Depends on:** Tasks 3-7
**Write scope:** Benchmark script and review evidence; production code only after a measured P0/P1 finding
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-cache/benchmarks/cache_benchmark.py`
- Create: `docs/review/artifacts/issue-50-local-cache-benchmark.json`
- Create: `docs/review/2026-07-11-issue-50-local-cache-performance-stability.md`
- Modify: production/tests only for evidence-backed repairs

- [ ] **Step 1: Add the deterministic non-gating benchmark harness**

The script accepts `--capacity`, `--operations`, `--warmups`, `--repetitions`, and `--output`. Defaults are capacity 10,000, operations 100,000, 3 warm-ups, and 7 measured repetitions. Use fixed integer key sequences and `perf_counter_ns`. JSON contains Python/platform/CPU count, git SHA, parameters, raw samples, p50/p95/p99/max, throughput, rebuild count/durations, traced peak, and normalized RSS high-water.

Run timing without `tracemalloc`. Run allocation measurement in a separate in-process phase. Run each RSS scenario in a fresh subprocess, normalize macOS byte versus Linux KiB `ru_maxrss` units, and label the result process high-water rather than retained memory.

Measure:

- direct `OrderedDict` hit/touch reference;
- `TTLCache.get` hit, miss, set, and `get_or_load` hit;
- same-key contention invocation count and different-key loader overlap as separate deterministic coordination observations;
- fixed-worker lock contention with 8 workers, 20,000 operations per worker, one start barrier, a 90% get/10% set mix, and either one hot key or one distinct key per worker; report p50/p95 latency and throughput for both distributions;
- expiry-heavy overwrite at capacity 1,000 with 10,000 operations and capacity 10,000 with 100,000 operations, using the identical 10-overwrites-per-key sequence and clock-advance distribution; report normalized ns/op plus fixed 100-operation batch p95/p99/max. Run a separate constant-fake-clock overwrite phase where no entry can expire, inspect private heap length around the known `2 * max_size` threshold, classify only the threshold-crossing shrink as a rebuild, and record the externally timed triggering operation as a documented upper-bound proxy for rebuild-only time;
- async hit and coalesced-loading scenarios in one event loop.

- [ ] **Step 2: Run correctness/stress repetitions before timing**

```bash
for iteration in 1 2 3 4 5 6 7 8 9 10; do
  uv run pytest packages/bluetape-cache/tests/test_ttl_cache.py packages/bluetape-cache/tests/test_async_ttl_cache.py -q || exit 1
done
```

Expected: 10/10 green with no join timeout, pending task, or warning.

- [ ] **Step 3: Run and evaluate the benchmark**

```bash
uv run python packages/bluetape-cache/benchmarks/cache_benchmark.py \
  --capacity 10000 --operations 100000 --warmups 3 --repetitions 7 \
  --output docs/review/artifacts/issue-50-local-cache-benchmark.json
```

Acceptance signals:

- same-key actual loader count equals one per contention round;
- different-key loader bodies overlap in the deterministic observation;
- the distinct-key fixed-worker workload does not fall below 0.5x hot-key throughput or exceed 2.5x hot-key p95 latency without investigation;
- median cache-hit cost is no more than 25x the same-process `OrderedDict` reference;
- expiry-heavy 10,000-capacity normalized median ns/op is no more than 2.5x the 1,000-capacity result;
- expiry-heavy 10,000-capacity p99/max fixed-batch latency and maximum rebuild-trigger operation proxy are no more than 15x the 1,000-capacity results for the 10x capacity, and every observed heap rebuild is counted;
- owned flight/task/thread and heap/version boundedness tests remain green after the run.

Threshold breaches do not get hidden as benchmark noise. Profile, form one hypothesis, repair with tests unchanged, and rerun the full Task 8 evidence.

- [ ] **Step 4: Record evidence and commit**

Write environment, exact command, committed raw JSON path and SHA-256, summarized results, thresholds, lifecycle observations, caveats, and final `P0=0 P1=0` or blocker state. Commit the final JSON so reviewers can recalculate every percentile/ratio; `/tmp` remains scratch-only for discarded reruns.

Commit intent: `test: make cache performance and lifecycle evidence repeatable`.

**Rollback/rerun:** Revert any unproven optimization; retain the benchmark harness and correctness tests, then rerun from the last green behavior commit.

## Task 9: Complete verification, review, lesson, PR, and CI gates

**Complexity:** High
**Depends on:** Tasks 1-8
**Write scope:** Evidence/lesson/PR preparation; code only for review repairs
**Pattern skills:** `$verification-before-completion`, `$bluetape-py-patterns`

**Files:**

- Create: `docs/review/2026-07-11-issue-50-local-cache-tdd-evidence.md`
- Create: `docs/review/2026-07-11-issue-50-local-cache-code-review.md`
- Create: `docs/lessons/2026-07-11-issue-50-local-cache.md`
- Modify: implementation/tests/docs only for verified repairs

- [ ] **Step 1: Run the fresh local validation ladder**

```bash
git diff --check
uv run ruff format --check .
uv run ruff check .
uv run pytest packages/bluetape-cache/tests -q
uv run pytest -q
uv lock --check
uv build --all-packages
actionlint
```

Expected: every command passes. The full pytest count must exceed the approved baseline of 737 by the exact number of new collected tests. `actionlint` is verification of the unchanged broad CI path; no workflow edit is required if CI's all-package commands cover the registered package.

- [ ] **Step 2: Verify spec, plan, repository hazards, and packaging**

Read the approved spec, this plan, current diff, test collection, root/meta/package pyprojects, lock, README locales, and `.github/workflows/ci.yml`. Produce an acceptance map showing every spec row and plan task with file/test/command evidence. Verify:

- workspace dependencies/sources/members include `bluetape-cache` once;
- default meta dependencies remain core-only;
- `cache`, `dev`, and `all` extras resolve intentionally;
- no root `bluetape/__init__.py` exists;
- normal CI sync/test/build commands include the new workspace package;
- no nightly, Kover, BOM/catalog, Testcontainers, external backend, or diagram update is triggered, with concrete repository evidence for each N/A.

- [ ] **Step 3: Run six-lens Step 6-R review and repair to zero**

Dispatch read-only performance, stability, security, operator/Ops, developer/API, and user/caller lanes against the exact branch diff and evidence. The main session deduplicates findings, repairs every P0/P1 with TDD, reruns affected validation and lenses, records P2/P3 disposition, and closes only at:

```text
P0=0 P1=0
```

- [ ] **Step 4: Commit the durable lesson before PR creation**

The lesson records context, concurrency/cancellation design decisions, surprising RED/failure evidence, outcome, commands, review misses, and future guard for issue #51. Commit it separately with a Lore message and ensure the branch is clean.

- [ ] **Step 5: Create and verify the PR only within the approved workflow scope**

Read issue #50 live. Create an English PR assigned to `debop`, milestone `0.2.0`, label `enhancement`, and a body ending with `## DoD Status`. Verify live title/body/assignee/milestone/labels and run the six-lens post-PR review against the actual PR diff.

- [ ] **Step 6: Wait for CI/reviews and stop at the merge boundary**

Use `ci-status --watch` or live `gh pr checks`, reread reviews and unresolved threads after green CI, repair/revalidate new blockers, update the final DoD section, and report `PENDING - PR ready for explicit merge decision`. Never merge automatically.

**Rollback/rerun:** Any verifier gap returns to the first task that owns the missing contract. Any CI/review regression returns to implementation and reruns targeted plus full validation. PR metadata/body failures are repaired live before reporting readiness.

## Step 3-R Self-Review Checklist

- [ ] Every approved spec acceptance criterion maps to a task and fresh command.
- [ ] No task consumes a file, API, lock entry, or artifact produced by a later task.
- [ ] Success, failure, boundary, concurrency, cancellation, lifecycle, mutation, saturation, packaging, and documentation cases are named.
- [ ] All code changes have exact files, RED command, minimal implementation contract, GREEN command, and commit point.
- [ ] Public docs cover root English/Korean parity plus the English package README.
- [ ] New-package registration, broad CI coverage, lock, build, isolated install, and default-install isolation are assigned.
- [ ] Risk signals, mitigations, rollback/rerun points, and performance thresholds are explicit.
- [ ] Placeholder and deferred-implementation wording scan is clean.
- [ ] Latest six-lens plan review and main integration conclude P0=0/P1=0 before implementation approval.
