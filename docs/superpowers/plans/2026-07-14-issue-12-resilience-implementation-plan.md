# Issue #12 Resilience Policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stdlib-only `bluetape-resilience` distribution with explicit sync/async retry, circuit breaker, bulkhead, cooperative async timeout, low-cardinality events, and immutable decorator pipelines.

**Architecture:** Shared private modules own validation, enums, frozen value objects, errors, backoff, events, callable-shape checks, and circuit transition logic. Separate sync and asyncio policy classes own their native locks, bounded waits, cancellation, and event-loop binding. Immutable sync/async pipelines retain policy instances and compose wrappers in last-added-outermost order without hidden workers, schedulers, or tasks.

**Tech Stack:** CPython 3.13.14, stdlib `asyncio`, `threading`, `time`, `random`, `enum`, `dataclasses`, `typing`/`ParamSpec`, `functools`, `uv_build`, pytest, pytest-asyncio, Ruff, uv, and actionlint.

---

Date: 2026-07-14 KST
Issue: [#12](https://github.com/bluetape4k/bluetape-py/issues/12)
Approved spec: `docs/superpowers/specs/2026-07-14-issue-12-resilience-design.md`
Status: Step 3-R reviewed — P0=0 P1=0; implementation remains blocked until user approval

## Execution Constraints

- Apply `$bluetape-py-patterns`, `$test-driven-development`, and `$verification-before-completion` at their workflow gates.
- Keep `bluetape-resilience` stdlib-only and keep the default `bluetape` dependency exactly `bluetape-core==0.1.0`.
- Implement no sync timeout, executor, worker thread, reset timer, scheduler, detached task, global registry, global logger, or exporter.
- Keep sync and async policy classes separate. Share only immutable public values, validation, error classification, backoff, callable checks, and pure circuit transition data.
- Treat swallowed cancellation, permit/probe leakage, stale circuit-generation mutation, observer-under-lock execution, cross-loop admission, unbounded waiting, secret-bearing events, public signature drift, or default-install widening as P0/P1 blockers.
- Run user operations, predicates, clocks, observers, sleepers, and random sources outside internal locks. Constructor validation must not invoke them.
- Use fake clocks/sleepers, `threading.Barrier`/`Event`, and `asyncio.Event`; correctness tests must use bounded waits and no long wall-clock sleeps.
- `.github/workflows/ci.yml` already runs provider-free workspace pytest and `uv build --all-packages`. Re-open it after package registration and prove collection/build coverage; add no dedicated job unless that proof fails.
- No Testcontainers, native provider, external service, benchmark threshold, or nightly workflow is required: the package is stdlib-only and its concurrency properties are deterministically testable in the normal suite.
- No architecture diagram is required: two short composition traces and the existing package table explain the only new topology and order relationship.
- Publication, release, tag, PR creation, and merge remain outside this plan's execution authority.

## Step 3-P Risk Prediction

| Risk | Early signal | Mitigation and proof | Rollback or rerun point |
| --- | --- | --- | --- |
| Cancellation is retried, observed, translated, or counted | retry sleeper runs after cancellation, circuit counters change, or an event is emitted | catch and re-raise `asyncio.CancelledError` before classifiers/events; cancellation tests snapshot counters and event lists | revert the owning async policy task and rerun every `cancel` node before composition work |
| A permit or half-open probe leaks | snapshot remains non-zero after operation, observer, predicate, timeout, or waiter failure | single-owner admission token plus exactly one `finally` release; deterministic terminal-path matrices | revert Task 5 or 6 to its last green commit and rerun the full policy file |
| Late circuit completion mutates a newer epoch | an old success closes a reopened breaker or an old failure reopens a closed one | generation-tag every admission; mutate only when completion generation equals current generation | revert Task 5 and rerun stale-success/stale-failure races in both modes |
| Observer execution deadlocks or masks cleanup/cancellation | reentrant `snapshot()` blocks, capacity remains consumed, or cancellation becomes observer error | emit outside locks after state/permit reconciliation; emit no cancellation event | stop at the owning policy task and rerun reentrancy plus observer-error matrices |
| Pipeline order silently changes retry/breaker semantics | trace differs from last-added-outermost or breaker counts wrong layer | immutable policy tuple, one wrapping algorithm, exact trace and contrasting-order tests | revert Task 7 only and rerun all policy suites plus pipeline traces |
| Async object is admitted on a second loop | operation body starts or state changes before rejection | atomic first-running-loop binding before admission for stateful async policies | revert the async slice and rerun two-loop misuse tests in isolated threads |
| Bounded wait hangs or waiter accounting drifts | test teardown times out, waiters stay non-zero, or late admission exceeds deadline | finite monotonic deadline, cancellation-safe waiter decrement, no `max_wait=None` | stop rollout and rerun immediate/bounded/timeout/cancel saturation matrices |
| Backoff/duration accepts bool, NaN, infinity, or invalid callback output | sleeper sees invalid delay or a test hangs | eager scalar validation plus post-callback finite/non-negative validation before sleep | revert Task 1/2 and rerun validation tables before policy work |
| Package registration breaks release fail-closed policy | workspace distribution is absent from publishable/private classification | packaging test compares workspace names with `pypi-preflight.md`; classify resilience as publishable but not a `v0.1.0` target | revert Task 8 metadata/docs together, run `uv lock`, rebuild, rerun classifier |
| Events leak caller data or raw exceptions | sentinel arg/result/exception text appears in event/repr/docs | fixed frozen fields only, no dynamic labels, negative sentinel tests | revert event-producing task and rerun observability/privacy tests |

Risk gate: required because this feature combines public decorator APIs, native sync/async concurrency, cancellation, state epochs, bounded admission, and a new publishable workspace distribution.

## File Structure

| Path | Responsibility |
| --- | --- |
| `packages/bluetape-resilience/pyproject.toml` | Stdlib-only focused distribution metadata and `bluetape.resilience` build mapping. |
| `packages/bluetape-resilience/src/bluetape/resilience/__init__.py` | Exact ordered 24-name public export contract. |
| `packages/bluetape-resilience/src/bluetape/resilience/_core.py` | Enums, frozen events/snapshots, public errors, validation, observer emission, loop binding, and callable-family checks. |
| `packages/bluetape-resilience/src/bluetape/resilience/_backoff.py` | Runtime-checkable `Backoff`, immutable constant/exponential implementations, and output validation. |
| `packages/bluetape-resilience/src/bluetape/resilience/_retry.py` | `Retry` and `AsyncRetry`, exhaustion, classification, sleepers, and terminal events. |
| `packages/bluetape-resilience/src/bluetape/resilience/_timeout.py` | Cooperative `AsyncTimeout` and owned-expiry translation. |
| `packages/bluetape-resilience/src/bluetape/resilience/_circuit.py` | Sync/async circuit breakers, generation admissions, lazy transitions, and snapshots. |
| `packages/bluetape-resilience/src/bluetape/resilience/_bulkhead.py` | Sync/async bounded admission, waiter ownership, release, and snapshots. |
| `packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py` | Immutable sync/async fluent pipelines and signature-preserving wrapper composition. |
| `packages/bluetape-resilience/tests/_support.py` | Fake clocks/sleepers, bounded thread/task coordination, event recorder, and two-loop helpers. |
| `packages/bluetape-resilience/tests/test_contracts.py` | Exports, signatures, enums, dataclasses, errors, validation, and callback non-invocation. |
| `packages/bluetape-resilience/tests/test_backoff.py` | Constant/exponential schedules, cap/jitter boundaries, and invalid callback results. |
| `packages/bluetape-resilience/tests/test_retry.py` | Sync/async retry results, classifiers, exhaustion, cancellation, events, and observer errors. |
| `packages/bluetape-resilience/tests/test_timeout.py` | Owned expiry, direct timeout, cancellation, cleanup, events, and misuse. |
| `packages/bluetape-resilience/tests/test_circuit.py` | Sync/async transitions, concurrency, generations, loop binding, predicates, snapshots, and observers. |
| `packages/bluetape-resilience/tests/test_bulkhead.py` | Sync/async capacity, bounded wait, cancellation, loop binding, cleanup, snapshots, and observers. |
| `packages/bluetape-resilience/tests/test_pipeline.py` | Immutable fluent methods, direct/decorator calls, order, metadata/signature, bound methods, and misuse. |
| `packages/bluetape-resilience/tests/test_observability.py` | Exact event order, low-cardinality/privacy proof, reentrancy, and cross-policy traces. |
| `packages/bluetape-resilience/tests/test_packaging.py` | Workspace/meta/lock/release classification, source import, CI coverage, and default boundary. |
| `packages/bluetape-resilience/tests/test_readme_examples.py` | Executable package/root README examples and locale marker parity. |
| `packages/bluetape-resilience/README.md`, `README.ko.md` | Install, API, sync/async composition order, cancellation, observer, ownership, and limits. |
| `pyproject.toml`, `packages/bluetape/pyproject.toml`, `uv.lock` | Workspace/source/member, `resilience` extra, stdlib `dev`/`all`, and reproducible resolution. |
| `README.md`, `README.ko.md`, `packages/bluetape/README.md`, `packages/bluetape/README.ko.md` | Root/meta bilingual activation, installation, examples, and package links. |
| `AGENTS.md`, `docs/package-layout.md`, `docs/release/pypi-preflight.md`, `docs/release/release-guide.md`, `WIP.md`, `CHANGELOG.md` | Durable package boundary, fail-closed publish classification, roadmap, and release notes. |
| `docs/review/2026-07-14-issue-12-resilience-*.md` | TDD, performance/stability, implementation, and verifier evidence. |
| `docs/lessons/2026-07-14-issue-12-resilience.md` | Required Type A reusable lesson before completion reporting. |

## Spec Coverage Map

| Approved requirement | Plan tasks |
| --- | --- |
| Exact exports, enums, frozen values/errors, keyword-only validation, callback non-invocation | 1-7 |
| Deterministic constant/exponential backoff and output validation | 2 |
| Sync/async retry, classification, exhaustion cause, cancellation, events | 3 |
| Cooperative async timeout, owned expiry distinction, no detached work | 4 |
| Sync/async circuit state, lazy recovery, bounded probes, generations, snapshots | 5 |
| Sync/async bulkhead capacity, bounded wait, cancellation, permit ownership | 6 |
| Individual decorators/direct calls, immutable pipelines, order, signatures, misuse rejection | 7 |
| Low-cardinality event order, observer cleanup/reentrancy/privacy | 3-7 |
| Workspace/meta/lock/build/default isolation/fail-closed release classification | 1, 8 |
| Bilingual package/root/meta docs, order examples, package layout, WIP/changelog/guidance | 9 |
| Full tests, concurrency/lifecycle proof, six-lens reviews, lesson and exact-head evidence | 10 |

## Exact Public Contract Blueprint

The implementation must preserve the approved ordered `__all__` and public value shape:

```python
__all__ = [
    "Retry", "AsyncRetry", "CircuitBreaker", "AsyncCircuitBreaker",
    "Bulkhead", "AsyncBulkhead", "AsyncTimeout", "ResiliencePipeline",
    "AsyncResiliencePipeline", "Backoff", "constant_backoff",
    "exponential_backoff", "PolicyEvent", "PolicyType", "EventKind",
    "PolicyOutcome", "FailureCategory", "CircuitState", "CircuitSnapshot",
    "BulkheadSnapshot", "RetryExhaustedError", "PolicyTimeoutError",
    "CircuitOpenError", "BulkheadRejectedError",
]

@dataclass(frozen=True, slots=True)
class PolicyEvent:
    policy_name: str
    policy_type: PolicyType
    kind: EventKind
    outcome: PolicyOutcome | None
    failure_category: FailureCategory
    attempt: int | None
    delay: float | None
    timeout: float | None
    state: CircuitState | None
    previous_state: CircuitState | None
    in_flight: int | None
    waiters: int | None

@dataclass(frozen=True, slots=True)
class CircuitSnapshot:
    name: str
    state: CircuitState
    consecutive_failures: int
    recovery_successes: int
    half_open_in_flight: int

@dataclass(frozen=True, slots=True)
class BulkheadSnapshot:
    name: str
    max_concurrency: int
    in_flight: int
    waiters: int
```

Public constructors and fluent methods remain exactly as written in the approved spec. Use `ParamSpec` and a return `TypeVar` for every `.call()`/decorator surface. The ellipses in plan snippets mean signature documentation only; implementation tasks may not leave ellipses, `pass`, `TODO`, `NotImplementedError`, or placeholder branches in production code.

Constructor signatures are fixed as follows; `AsyncCircuitBreaker` and
`AsyncBulkhead` use the same parameters and defaults as their sync counterparts:

| Type | Keyword-only constructor |
| --- | --- |
| `Retry` | `name`, `max_attempts`, `backoff=constant_backoff(0)`, `retry_if=None`, `observer=None`, `sleeper=time.sleep` |
| `AsyncRetry` | `name`, `max_attempts`, `backoff=constant_backoff(0)`, `retry_if=None`, `observer=None`, `sleeper=asyncio.sleep` |
| `CircuitBreaker` / `AsyncCircuitBreaker` | `name`, `failure_threshold`, `open_duration`, `half_open_max_calls=1`, `recovery_success_threshold=1`, `failure_if=None`, `observer=None`, `clock=time.monotonic` |
| `Bulkhead` / `AsyncBulkhead` | `name`, `max_concurrency`, `max_wait=0`, `observer=None` |
| `AsyncTimeout` | `name`, `timeout`, `observer=None` |
| `ResiliencePipeline` / `AsyncResiliencePipeline` | no arguments |

The sync pipeline has `with_retry(Retry)`,
`with_circuit_breaker(CircuitBreaker)`, and `with_bulkhead(Bulkhead)`. The async
pipeline has the matching async methods plus `with_timeout(AsyncTimeout)`. Every
policy and pipeline has `.call(operation, *args, **kwargs)` and decorator
`__call__(operation)` with the matching sync or async return type.

Event payload tests must lock these common rules: successful terminals use
`outcome=SUCCESS` and `failure_category=NONE`; ordinary failed terminals use
`outcome=FAILURE` and the category derived from the escaping error; admission
rejections use `outcome=REJECTION` and the matching circuit/bulkhead category;
`RETRY_SCHEDULED`, `ADMITTED`, and `CIRCUIT_TRANSITIONED` use `outcome=None`;
unused fields are `None`. Retry events carry the one-based current/failed attempt,
timeout events carry the configured timeout, transition events carry both states,
and circuit/bulkhead events capture reconciled in-flight/waiter values at their
documented emission point. Cancellation adds no terminal/cancellation event, though
an admission or retry-scheduled event already emitted before later cancellation is
not retracted.

## Mandatory Per-Test TDD Micro-Cycle

For every named behavior below, repeat this cycle before adding the next behavior:

- [ ] Add one named test plus deterministic fixture/teardown.
- [ ] Run its exact node ID and confirm RED is the intended missing contract or assertion mismatch, never collection/environment failure.
- [ ] Implement only the smallest owning transition/terminal branch.
- [ ] Rerun the identical node ID and confirm one pass.
- [ ] Run the whole owning test file and confirm accumulated GREEN.

Task-level commands are integration checks after these node cycles. Each task ends in one reviewable commit; do not combine unfinished behavior families.

## Task 1: Register the scaffold and lock shared public contracts

**Complexity:** Medium
**Depends on:** Approved spec
**Write scope:** New package scaffold, root workspace registration, core public values/errors/validation, contract and packaging tests
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-resilience/pyproject.toml`
- Create: `packages/bluetape-resilience/README.md`
- Create: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`
- Create: `packages/bluetape-resilience/src/bluetape/resilience/_core.py`
- Create: `packages/bluetape-resilience/tests/__init__.py`
- Create: `packages/bluetape-resilience/tests/_support.py`
- Create: `packages/bluetape-resilience/tests/test_contracts.py`
- Create: `packages/bluetape-resilience/tests/test_packaging.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] Add RED tests `test_shared_public_exports_are_ordered`, `test_public_enums_have_fixed_string_values`, `test_public_values_are_frozen_slotted_and_ordered`, `test_domain_error_hierarchy_and_safe_messages`, and private validator unit tables covering blank/surrounding-space names, bool, wrong types, zero, negative, NaN, and infinities. The exact final 24-name export test belongs to Task 7 after every owning module exists.
- [ ] Add source-import tests proving no sync `Timeout` export and no root `bluetape/__init__.py` is introduced. Each owning policy task must repeat public constructor validation through that policy and prove its predicate, observer, sleeper, clock, or random source is not invoked merely by construction.
- [ ] Register only the focused package in the root dependency/source/member lists, create a minimal README, and use:

```toml
[project]
name = "bluetape-resilience"
version = "0.1.0"
description = "Stdlib-only sync and async resilience policies for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.resilience"
```

- [ ] Run `uv lock && uv sync --all-packages --extra fory --extra native --python 3.13.14 --locked`; expect success. Run `uv run pytest packages/bluetape-resilience/tests/test_contracts.py packages/bluetape-resilience/tests/test_packaging.py -q`; expect RED only for missing public contracts.
- [ ] Implement exact string enums, frozen/slotted values, error types, `_validate_name`, `_positive_int`, `_finite_non_negative`, `_finite_positive`, `_validate_callable`, failure-category mapping, safe error formatting, and an observer helper that never catches observer errors.
- [ ] Make `__init__.py` extend the namespace path and export only the shared names actually implemented in this task. Do not create temporary policy classes or placeholders in `_core.py`; each later task adds its real names, and Task 7 locks the final exact ordered list.
- [ ] Run the two test files; expect all Task 1 tests green. Run `uv run ruff check packages/bluetape-resilience && uv run ruff format --check packages/bluetape-resilience`; expect clean.
- [ ] Commit:

```bash
git add pyproject.toml uv.lock packages/bluetape-resilience
git commit -m "feat: scaffold resilience policy contracts"
```

Rollback/rerun: revert this commit as one unit if workspace registration or exact exports fail; rerun `uv lock` before every subsequent package task.

## Task 2: Implement deterministic backoff contracts

**Complexity:** Small
**Depends on:** Task 1
**Write scope:** Backoff implementation, exports, tests
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-resilience/src/bluetape/resilience/_backoff.py`
- Create: `packages/bluetape-resilience/tests/test_backoff.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`

- [ ] Add RED tests `test_backoff_protocol_is_runtime_checkable`, `test_constant_backoff_is_immutable_and_attempt_independent`, `test_constant_backoff_rejects_invalid_delay`, `test_exponential_backoff_uses_one_based_failed_attempt`, `test_exponential_backoff_caps_before_bounded_jitter`, `test_exponential_backoff_accepts_jitter_boundaries`, `test_exponential_backoff_rejects_invalid_configuration`, and `test_exponential_backoff_rejects_invalid_random_output_before_return`.
- [ ] Implement a runtime-checkable protocol and frozen private callables. Use this deterministic schedule contract:

```python
base = min(initial_delay * multiplier ** (failed_attempt - 1), max_delay)
factor = 1 - jitter + (2 * jitter * random_source())
delay = base * factor
```

Require `failed_attempt` to be a positive non-bool integer. Apply `max_delay` to the base before jitter, then validate the final result as finite and non-negative. A zero constant delay is valid; exponential `initial_delay`, `multiplier`, and non-`None` `max_delay` are strictly positive.
- [ ] Run `uv run pytest packages/bluetape-resilience/tests/test_backoff.py -q`; expect green. Run Task 1 contract tests to prove export/order identity remains unchanged.
- [ ] Commit:

```bash
git add packages/bluetape-resilience
git commit -m "feat: add deterministic resilience backoff"
```

Rollback/rerun: revert Task 2 without touching the package scaffold; rerun the fixed random-source boundary table.

## Task 3: Implement sync and async retry

**Complexity:** Medium
**Depends on:** Tasks 1-2
**Write scope:** Retry policies, retry tests, shared event helpers
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-resilience/src/bluetape/resilience/_retry.py`
- Create: `packages/bluetape-resilience/tests/test_retry.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/_core.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`

- [ ] Add sync RED nodes for constructor keyword-only/name/attempt/callable validation without callback invocation, first-attempt success/return preservation, retry then success, max-attempt exhaustion and `__cause__`, non-retryable identity propagation, default rejection exclusions, predicate error propagation, invalid backoff output before sleeper, sleeper error, terminal event sequence, observer error, direct `.call()`, decorator metadata/signature, and generator rejection.
- [ ] Implement `Retry.call()` with one-based attempts. Catch only ordinary `Exception`; classify `CircuitOpenError`, `BulkheadRejectedError`, and policy-owned `PolicyTimeoutError` as terminal by default, while still allowing a caller predicate to make its own explicit decision. Emit `RETRY_SCHEDULED` after classification and delay validation but before sleeper, then exactly one terminal `SUCCEEDED` or `FAILED`. On exhaustion, raise `RetryExhaustedError(name, attempts)` from the last operation exception.
- [ ] Add async RED parity plus `test_async_retry_propagates_cancellation_without_predicate_event_or_sleep`, `test_async_retry_cancellation_during_backoff_starts_no_new_attempt`, `test_async_retry_rejects_sync_and_async_generator_functions`, and `test_async_retry_binds_no_state_or_task`.
- [ ] Implement `AsyncRetry` with the same attempt machine and awaited sleeper. Handle `asyncio.CancelledError` before `Exception`; do not emit an event or invoke `retry_if` after cancellation. Await the operation directly and create no package task.
- [ ] Use `functools.wraps`, `ParamSpec`, and `TypeVar` for individual policy decorators. Validate callable family at decoration and `.call()` entry before protected work; sync rejects coroutine/generator/async-generator functions and async rejects ordinary sync/generator/async-generator functions.
- [ ] Run `uv run pytest packages/bluetape-resilience/tests/test_retry.py packages/bluetape-resilience/tests/test_backoff.py -q`; expect green. Run `uv run ruff check packages/bluetape-resilience/src packages/bluetape-resilience/tests/test_retry.py`.
- [ ] Commit:

```bash
git add packages/bluetape-resilience
git commit -m "feat: add sync and async retry policies"
```

Rollback/rerun: revert Task 3 and keep backoff green; rerun cancellation and exhaustion node IDs before continuing.

## Task 4: Implement cooperative async timeout

**Complexity:** Medium
**Depends on:** Tasks 1 and 3 callable/event helpers
**Write scope:** Async timeout and tests
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-resilience/src/bluetape/resilience/_timeout.py`
- Create: `packages/bluetape-resilience/tests/test_timeout.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`

- [ ] Add RED tests for keyword-only/name/positive-timeout/observer validation without observer invocation, plus `test_timeout_preserves_success`, `test_policy_expiry_raises_policy_timeout_with_cause`, `test_operation_timeout_error_is_not_translated`, `test_external_cancellation_is_not_translated_or_observed`, `test_operation_failure_emits_failed`, `test_timeout_observer_error_propagates_after_context_cleanup`, `test_timeout_creates_no_task`, `test_timeout_preserves_decorator_signature_and_bound_method`, and family/generator misuse nodes.
- [ ] Implement with the timeout context object so owned expiry is distinguished from an operation-raised `TimeoutError`:

```python
context = asyncio.timeout(self._timeout)
try:
    async with context:
        result = await operation(*args, **kwargs)
except asyncio.CancelledError:
    raise
except TimeoutError as error:
    if context.expired():
        raise PolicyTimeoutError(self.name, self._timeout) from error
    raise
```

Emit `SUCCEEDED`, `TIMED_OUT`, or ordinary `FAILED` only after the timeout context has exited. Do not create or shield a task. Document and test that cancellation-suppressing operations are outside the supported contract rather than attempting forced cleanup.
- [ ] Run `uv run pytest packages/bluetape-resilience/tests/test_timeout.py packages/bluetape-resilience/tests/test_retry.py -q`; expect green. Inspect `asyncio.all_tasks()` before/after a coordinated call and expect no package-owned delta.
- [ ] Commit:

```bash
git add packages/bluetape-resilience
git commit -m "feat: add cooperative async timeout policy"
```

Rollback/rerun: revert Task 4 only; rerun direct-operation-timeout and external-cancel nodes because those guard the translation boundary.

## Task 5: Implement generation-safe sync and async circuit breakers

**Complexity:** High
**Depends on:** Tasks 1 and 3 callable/event helpers
**Write scope:** Circuit state/admission ownership, sync/async wrappers, tests
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-resilience/src/bluetape/resilience/_circuit.py`
- Create: `packages/bluetape-resilience/tests/test_circuit.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/_core.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`

- [ ] Add RED keyword-only/name/positive-count/positive-duration/callable validation and snapshot nodes, proving constructor validation invokes neither clock, predicate, nor observer; then add closed success/reset, threshold opening, exact lazy deadline transition, open rejection, half-open probe bound, recovery success threshold, probe failure reopening, and transition-event order. Use a fake monotonic clock; no sleep.
- [ ] Model every accepted call with a private immutable admission containing `generation`, admitted state, and whether it owns a half-open slot. Under the short-held state lock: lazily transition expired `OPEN` to `HALF_OPEN`, reject excess probes, increment owned slot, and snapshot event data. Increment generation on every transition into `OPEN`, `HALF_OPEN`, or `CLOSED`.
- [ ] Invoke the clock, operation, failure predicate, and observers outside the lock. Capture monotonic time before entering the lock for lazy recovery. Re-enter only to reconcile an admission whose generation still matches. A stale completion may emit its terminal call result using its captured admission but must not mutate current counters/state.
- [ ] Add deterministic thread races `test_stale_closed_success_cannot_close_new_epoch`, `test_stale_closed_failure_cannot_reopen_recovered_epoch`, `test_half_open_concurrent_limit_never_exceeded`, `test_predicate_error_releases_probe_without_recording`, `test_admitted_observer_error_releases_probe_before_propagating`, `test_observer_reentrant_snapshot_does_not_deadlock`, and `test_terminal_observer_error_sees_reconciled_state`. Require bounded joins and empty live-thread teardown.
- [ ] Add async parity, then `test_async_circuit_cancellation_releases_probe_without_terminal_event_or_count` (the already emitted `ADMITTED` event remains), `test_async_circuit_first_loop_binding_is_atomic`, `test_async_circuit_second_loop_rejected_before_admission`, and async stale-generation races. Bind to the first running loop before any admission/state access and use an async lock; do not hold it across callbacks or operation awaits.
- [ ] Run `uv run pytest packages/bluetape-resilience/tests/test_circuit.py -q`; expect green. Repeat the concurrency subset with `--count` unavailable by using a bounded shell loop only if stable locally; record each run, never hide an intermittent failure.
- [ ] Commit:

```bash
git add packages/bluetape-resilience
git commit -m "feat: add generation-safe circuit breakers"
```

Rollback/rerun: revert Task 5 as one state-machine unit; do not proceed until all stale-generation, probe-release, reentrancy, and cross-loop tests are deterministic.

## Task 6: Implement bounded sync and async bulkheads

**Complexity:** High
**Depends on:** Tasks 1 and 3 callable/event helpers
**Write scope:** Bulkhead admission/permit ownership, sync/async wrappers, tests
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-resilience/src/bluetape/resilience/_bulkhead.py`
- Create: `packages/bluetape-resilience/tests/test_bulkhead.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`

- [ ] Add RED keyword-only/name/positive-capacity/non-negative-finite-wait/callable validation and snapshot nodes, proving construction does not invoke the observer; then add immediate admission/rejection, exact maximum in-flight, positive bounded wait success, bounded deadline rejection, ordinary failure release, observer failure release, direct/decorator use, and snapshot immutability.
- [ ] Implement sync ownership with a condition and monotonic deadline. Mutate `waiters` exactly once on entering/leaving bounded wait, mutate `in_flight` only after acquisition, and release only an acquired permit in `finally`. Do not promise FIFO fairness. Run operation and observer outside the condition lock.
- [ ] Add bounded thread tests `test_sync_bulkhead_never_exceeds_capacity`, `test_sync_wait_timeout_decrements_waiter`, `test_sync_waiter_can_enter_after_release`, `test_sync_operation_and_observer_reentrancy_do_not_deadlock`, and terminal-path parameterization for success/error/observer error. Every thread join has a finite timeout and teardown asserts no live workers.
- [ ] Add async parity plus `test_async_waiter_cancellation_does_not_release_unowned_permit`, `test_async_admitted_cancellation_releases_permit_without_terminal_event` (the already emitted `ADMITTED` event remains), atomic first-loop binding, second-loop rejection before waiter accounting, and simultaneous saturation. Use an async condition/lock and `asyncio.timeout(max_wait)` for bounded acquisition; distinguish owned wait expiry without translating operation errors.
- [ ] Emit `ADMITTED` only after acquisition, `REJECTED` after immediate/deadline failure, and one terminal `SUCCEEDED`/`FAILED` only for admitted ordinary completion. If the admitted observer raises, release the newly owned permit before propagating and do not invoke the operation. Reconcile permit and snapshot counts before every terminal observer invocation; cancellation emits no terminal event.
- [ ] Run `uv run pytest packages/bluetape-resilience/tests/test_bulkhead.py -q`; expect green. Run circuit and timeout files together to catch shared loop/event helper regressions.
- [ ] Commit:

```bash
git add packages/bluetape-resilience
git commit -m "feat: add bounded sync and async bulkheads"
```

Rollback/rerun: revert Task 6 as one ownership unit; rerun the complete saturation/cancel/observer matrix and assert zero final in-flight/waiters before composition.

## Task 7: Implement immutable decorator pipelines and integrated observability

**Complexity:** High
**Depends on:** Tasks 3-6
**Write scope:** Pipeline composition, callable-shape integration, cross-policy event/privacy tests
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py`
- Create: `packages/bluetape-resilience/tests/test_pipeline.py`
- Create: `packages/bluetape-resilience/tests/test_observability.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/_core.py`
- Modify: `packages/bluetape-resilience/src/bluetape/resilience/__init__.py`

- [ ] Add `test_exact_public_exports` first and make the final `__all__` equal the approved ordered 24-name list with no compatibility aliases. Add RED tests proving `ResiliencePipeline()`/`AsyncResiliencePipeline()` take no arguments, empty pipelines pass through, every `.with_*()` returns a new object, originals remain unchanged, stored policy identity/state is shared, foreign-family policies are rejected, and each fluent method accepts exactly its approved policy type.
- [ ] Store policies in an immutable private tuple in addition order. Compose with one algorithm so each newly added policy becomes outermost:

```python
wrapped = operation
for policy in self._policies:
    wrapped = policy(wrapped)
return wrapped(*args, **kwargs)
```

Do not clone policies. Validate the operation family before building or invoking wrappers. Reuse the resulting wrapper logic for `.call()` and decorator `__call__` without changing state semantics.
- [ ] Add exact sync and async traces for the approved examples. Prove `.with_circuit_breaker(breaker).with_retry(retry)` makes retry outermost and the breaker sees individual attempts; reverse order and prove the breaker sees only terminal retry exhaustion/success.
- [ ] Add `inspect.signature`, `__name__`, `__doc__`, annotations, original return identity, bound instance/class/static method, positional-only/keyword-only, and generic `ParamSpec` smoke tests for individual policies and empty/non-empty pipelines.
- [ ] Add decoration-time rejection for sync coroutine functions, async ordinary functions, generator functions, and async-generator functions. Cover callable objects whose `__call__` defines the family. Add `.call()` misuse tests proving known wrong-family bodies are never invoked and no hidden thread adaptation occurs; if a nominal sync callable returns an awaitable or a nominal async callable returns a non-awaitable, raise `TypeError` at the first observable contract violation and clean up any newly created coroutine object.
- [ ] Add integrated observer tests with a fixed event recorder: within-policy order, nested cross-policy order, observer stops subsequent events, observer reentrant snapshots, state/permit already reconciled before terminal observer, and outer policy handling of an inner observer error.
- [ ] Add privacy sentinels in arguments, return value, exception message, predicate object, and operation repr. Recursively inspect event fields and repr; assert none appears. Assert no wall timestamp, id, traceback, raw exception, logger, callable, key, result, or dynamic label field exists.
- [ ] Add a lifecycle scan around representative async pipelines; after coordinated success/failure/timeout/cancellation, `asyncio.all_tasks()` contains only caller/test tasks and every snapshot is reconciled.
- [ ] Run `uv run pytest packages/bluetape-resilience/tests/test_pipeline.py packages/bluetape-resilience/tests/test_observability.py -q`; expect green. Then run `uv run pytest packages/bluetape-resilience/tests -q`; expect all package tests green.
- [ ] Commit:

```bash
git add packages/bluetape-resilience
git commit -m "feat: compose immutable resilience pipelines"
```

Rollback/rerun: revert Task 7 without changing policy implementations; rerun both contrasting-order traces plus every signature/misuse/privacy node.

## Task 8: Complete meta packaging, lock, release classification, and wheel isolation

**Complexity:** Medium
**Depends on:** Tasks 1-7 public surface complete
**Write scope:** Meta extras, lock, packaging/release classification tests and docs, CI coverage proof
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape/pyproject.toml`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `docs/release/pypi-preflight.md`
- Inspect and modify only if inconsistent: `docs/release/release-guide.md`
- Modify: `packages/bluetape-resilience/tests/test_packaging.py`
- Inspect only unless proof fails: `.github/workflows/ci.yml`

- [ ] Extend packaging RED tests to parse root/focused/meta TOML and assert: Python `>=3.13`; focused dependencies `[]`; root dependency/source/member exactly once; meta `resilience = ["bluetape-resilience==0.1.0"]`; resilience included in `dev` and `all`; default meta dependency unchanged; no Redis/Testcontainers/native dependency leaks.
- [ ] Add fail-closed RED proof modeled on `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`: parsed workspace distributions equal documented publishable plus private sets. Add `bluetape-resilience` to the publishable classification, but not to the fixed `v0.1.0` target table. Preserve publication HOLD and explicit approval language.
- [ ] Add a CI ownership test or source assertion proving the generic test job runs provider-free pytest and `uv build --all-packages`. Do not add a resilience-only job because there is no external runtime/service. If generic commands do not collect/build the package, repair `.github/workflows/ci.yml` minimally and run `actionlint`.
- [ ] Update metadata and run:

```bash
uv lock
uv sync --all-packages --extra fory --extra native --python 3.13.14 --locked
uv run pytest packages/bluetape-resilience/tests/test_packaging.py -q
uv build --package bluetape-resilience
uv build --package bluetape
```

Expected: all succeed; the focused wheel metadata has no `Requires-Dist`, while the meta wheel has the opt-in resilience extra and its default requirement remains only core.

- [ ] Run isolated wheel smoke checks from a temporary directory. Build `bluetape`, core, and resilience wheels; create separate venvs; install with `--no-index --find-links`. Prove base `bluetape` cannot resolve/import `bluetape.resilience`, direct focused install can import all 24 names, and `bluetape[resilience]` can import them. Delete the temporary directory in a trap.
- [ ] Inspect `uv.lock` and assert the workspace/meta entries contain resilience in the intended sets only. Run `git diff --check`.
- [ ] Commit:

```bash
git add pyproject.toml packages/bluetape/pyproject.toml uv.lock docs/release packages/bluetape-resilience/tests/test_packaging.py
git commit -m "build: register resilience distribution"
```

Rollback/rerun: revert metadata, lock, release classification, and packaging tests together; rerun `uv lock`, classifier, both builds, and all three isolated install modes.

## Task 9: Document bilingual usage and ownership contracts

**Complexity:** Medium
**Depends on:** Task 8 final install shape
**Write scope:** Package/root/meta READMEs, durable guidance, layout, roadmap, changelog, executable examples
**Pattern skill:** `$bluetape-maintenance`, `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-resilience/README.md`
- Create: `packages/bluetape-resilience/README.ko.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `packages/bluetape/README.md`
- Modify: `packages/bluetape/README.ko.md`
- Modify: `AGENTS.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`
- Create: `packages/bluetape-resilience/tests/test_readme_examples.py`

- [ ] Write package README locale twins with direct and `bluetape[resilience]` install commands; exact public policy table; sync/async decorator and `.call()` examples; last-added-outermost rule; contrasting retry/breaker orders; timeout cooperation; cancellation; bounded bulkhead waits; circuit lazy recovery/state sharing; inline observer requirements; safe low-cardinality names; no sync timeout/generator/adapter/global background work; source-workspace and publication-HOLD status.
- [ ] Add executable fenced snippets using deterministic zero-delay/small-success operations. `test_readme_examples.py` extracts marked Python blocks or imports shared snippet functions so both the decorator surface requested by the user and direct `.call()` surface execute in sync and async modes.
- [ ] Update root and meta English/Korean tables, install commands, smoke commands, examples, and package-document links in lockstep. Add explicit `resilience` extra while preserving the core-only default statement.
- [ ] Add the active distribution and stdlib-only/no-hidden-worker boundary to `AGENTS.md` and `docs/package-layout.md`. Update `WIP.md` issue #12 from planned to implemented-on-branch without claiming PR/merge/release. Add a Keep-a-Changelog entry describing the new source-workspace package and publication hold.
- [ ] Add locale parity assertions for required headings/markers and package-table names. Run:

```bash
uv run pytest packages/bluetape-resilience/tests/test_readme_examples.py packages/bluetape-resilience/tests/test_packaging.py -q
uv run ruff check packages/bluetape-resilience
uv run ruff format --check packages/bluetape-resilience
git diff --check
```

Expected: examples and parity tests pass, docs contain no unsupported sync timeout or universal order recommendation, and formatting checks are clean.

- [ ] Commit:

```bash
git add README.md README.ko.md AGENTS.md CHANGELOG.md WIP.md docs/package-layout.md packages/bluetape packages/bluetape-resilience
git commit -m "docs: document resilience policy package"
```

Rollback/rerun: revert the documentation commit only; rerun executable examples and locale markers after any wording repair.

## Task 10: Run full verification, reviews, and Type A lesson gate

**Complexity:** High
**Depends on:** Tasks 1-9
**Write scope:** Review/evidence/lesson artifacts and fixes discovered by gates
**Pattern skill:** `$verification-before-completion`, `$requesting-code-review`, `$bluetape-workflow`

**Files:**

- Create: `docs/review/2026-07-14-issue-12-resilience-tdd-evidence.md`
- Create: `docs/review/2026-07-14-issue-12-resilience-performance-stability.md`
- Create: `docs/review/2026-07-14-issue-12-resilience-implementation-review.md`
- Create: `docs/review/2026-07-14-issue-12-resilience-verifier.md`
- Create: `docs/lessons/2026-07-14-issue-12-resilience.md`
- Modify only as findings require: files owned by Tasks 1-9

- [ ] Re-run targeted policy tests and record RED/GREEN node evidence from task history, exact commit SHAs, and deterministic synchronization controls in the TDD artifact. Do not invent a RED result that was not observed.
- [ ] Run the stability matrix at least five consecutive times in both families using bounded test selection for circuit generation, bulkhead saturation/cancellation, timeout cancellation, observer reentrancy, and pipeline order. Record commands, counts, elapsed times, zero hangs, final snapshots, and task/thread cleanup. No performance benchmark threshold is required; record this as evidence-backed N/A because no hot-loop performance acceptance was approved.
- [ ] Run the exact full validation from the worktree:

```bash
uv sync --all-packages --extra fory --extra native --python 3.13.14 --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
git diff --check
```

Expected: all commands exit 0. Capture the pytest pass count/time and all-package artifact list at the exact implementation HEAD.

- [ ] Repeat the isolated base/direct/meta-extra wheel smoke checks from Task 8 against freshly built artifacts. Verify exact 24-name exports, no sync `Timeout`, core-only default metadata, focused no-dependency metadata, and no source-tree leakage.
- [ ] Run six review perspectives plus integration: performance, stability, security/privacy, operator/ops, developer/API, and user/caller. Repair every P0/P1, rerun the owning targeted tests, then rerun the complete gate. Record final `P0=0 P1=0` in the implementation review.
- [ ] Verify acceptance criteria 1-10 line by line against tests/docs/metadata. Record external-service/nightly/Testcontainers/native-provider/diagram changes as N/A with the stdlib-only and deterministic-normal-suite evidence; do not mark an unverified item complete.
- [ ] Write the Type A lesson with reusable findings on cooperative timeout ownership, generation-tagged circuit completion, cancellation-before-observer ordering, and last-added-outermost decorator semantics. Commit it before reporting completion.
- [ ] Inspect `git status --short`, `git diff --check`, and `git log --oneline origin/develop..HEAD`. Ensure only issue #12 scope is present and the worktree is clean after the evidence commit:

```bash
git add docs/review docs/lessons
git commit -m "docs: record resilience verification evidence"
```

- [ ] Stop and report exact-head evidence. Do not create a PR, merge, tag, publish, or dispatch a workflow without a new explicit user authorization.

Rollback/rerun: any P0/P1 reopens the owning task and invalidates later exact-head evidence. Apply the smallest fix, commit it separately, rerun targeted plus full gates, and regenerate evidence with the new HEAD.

## Planned Commit Sequence

1. `feat: scaffold resilience policy contracts`
2. `feat: add deterministic resilience backoff`
3. `feat: add sync and async retry policies`
4. `feat: add cooperative async timeout policy`
5. `feat: add generation-safe circuit breakers`
6. `feat: add bounded sync and async bulkheads`
7. `feat: compose immutable resilience pipelines`
8. `build: register resilience distribution`
9. `docs: document resilience policy package`
10. `docs: record resilience verification evidence`

Each commit is independently testable at its stated task boundary. If a task requires a corrective commit after review, keep the correction scoped and name the violated contract rather than rewriting history.

## Stop Condition

This plan is complete only when Step 3-R review records `P0=0 P1=0`. Plan approval authorizes implementation tasks only; PR creation, merge, publication, release, tag, workflow dispatch, and milestone closure each require their normal later workflow gates and explicit authority.
