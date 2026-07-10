# Issue #8 Async Package Design

Date: 2026-07-10 KST
Target issue: #8 - `feat: add bluetape-async concurrency primitives`
Target milestone: `0.2.0`

## Problem

`bluetape-py` needs a focused, Python-native helper for common bounded async
fan-out. The helper must preserve `asyncio` structured-concurrency semantics:
callers retain cancellation and timeout visibility, failed sibling work is
cleaned up, and no task outlives the public call.

The existing workspace has focused namespace distributions, a thin default
`bluetape` meta distribution, and no async helper package. Issue #7 explicitly
excluded async collection helpers and assigned that scope to this issue.

## Current Evidence

- GitHub issue #8 requires bounded fan-out, cancellation-aware task groups,
  timeout/deadline support, cleanup-safe execution, and small Python-native
  APIs.
- `AGENTS.md` and `docs/package-layout.md` require a focused package boundary,
  stdlib-first dependencies, package documentation, tests, and preservation of
  the default `bluetape-core`-only install.
- `from bluetape.async import ...` is invalid Python syntax; `bluetape.asyncio`
  is a valid import path.
- Python 3.13 `asyncio.TaskGroup` waits for managed tasks at context exit and
  cancels siblings after a non-cancellation task failure. `asyncio.timeout()`
  uses cancellation internally and converts its own expiry to `TimeoutError`.
  Therefore this package must not swallow `asyncio.CancelledError`.
- `bluetape-go/concurrency` and the closed `bluetape-rs` async issues establish
  useful scope principles (explicit concurrency limits, cleanup, cancellation,
  and no task leaks), but their APIs are not Python API templates.

## Goals

1. Add a stdlib-only `bluetape-async` distribution with public import path
   `bluetape.asyncio`.
2. Expose one small bounded fan-out helper:

   ```python
   async def map_bounded(
       items: Iterable[T],
       mapper: Callable[[T], Awaitable[R]],
       *,
       limit: int,
       timeout: float | None = None,
   ) -> list[R]:
   ```

3. Keep at most `limit` mapper calls active and return results in input order.
4. Preserve native `asyncio.CancelledError`, `TimeoutError`, and
   `TaskGroup`/`ExceptionGroup` semantics without forcing a simplified
   exception shape during concurrent failure races.
5. Ensure every task created by the helper belongs to its call-scoped
   `asyncio.TaskGroup` and is complete before the helper returns or raises.
6. Keep the default `bluetape` install unchanged. Add only an `asyncio`
   optional extra for the focused distribution.
7. Document local-workspace availability and the existing PyPI publication
   hold accurately in the package and root README locale set.

## Non-Goals

- No public `WorkerPool` object, queue ownership, producer lifecycle, or
  streaming `AsyncIterable` API.
- No `for_each_bounded`; callers can discard `map_bounded` results, and a
  wrapper would add API surface without a distinct contract.
- No global event-loop state, detached/background tasks, threads, processes,
  executors, retries, rate limiting, or per-task timeout policy.
- A mapper must not rely on `asyncio.current_task().cancel()` self-cancellation
  as a supported contract. If it occurs without caller cancellation, the helper
  fails closed with `CancelledError` after cleanup rather than return partial
  result slots; cancellation-count and race behavior are not promised.
- No custom deadline type, custom cancellation token, AnyIO, or other new
  runtime dependency.
- No Go `context` or Kotlin coroutine API port.
- No PyPI publication, GitHub Release, tag, or merge in this issue.

## API and Runtime Contract

### Input and result behavior

- `items` is a synchronous, non-blocking `Iterable`; it is consumed
  incrementally, with no more than `limit` items admitted ahead of completed
  work. This non-streaming helper retains `O(n)` result slots and is not
  suitable for unbounded input.
- The helper obtains `iter(items)` before consuming an item. A non-iterable
  input therefore raises its native `TypeError` before mapper invocation.
- An ordinary exception from `next(iterator)` propagates with native task-group
  semantics. Leaving the enclosing task group cancels and awaits active mappers,
  and no later item is admitted. An iterator-raised `CancelledError` without a
  pending caller cancellation fails closed as invocation `CancelledError` after
  the same cleanup; an externally delivered cancellation remains unchanged.
- `limit` must be an `int` other than `bool` and greater than zero. Invalid
  limits raise `TypeError` or `ValueError` before consuming `items` or invoking
  `mapper`.
- `mapper` must be callable. A non-callable mapper raises
  `TypeError("mapper must be callable")` before consuming `items`.
- A callable mapper must return an `Awaitable`. A non-awaitable result fails
  inside the call-scoped task group with native `TypeError`/`ExceptionGroup`
  behavior; no later item is admitted after that terminal failure is observed.
- `timeout` must be `None` or a finite, non-negative `int` or `float` other
  than `bool`. A non-numeric or boolean value raises `TypeError`; a negative,
  NaN, or infinite value raises `ValueError`, each before input consumption.
- An empty iterable returns `[]` without invoking `mapper`.
- The result list uses the original input order, not completion order.
- `timeout=None` means no package-owned timeout boundary.

### Failure, cancellation, and cleanup behavior

- The implementation uses one call-scoped `asyncio.TaskGroup`; it does not
  call bare `asyncio.create_task()` for public work ownership.
- Mapper invocation and its work before the first `await` must be non-blocking
  and cooperative. Blocking CPU or I/O belongs outside this helper; neither
  `asyncio.timeout()` nor external cancellation can preempt event-loop-blocking
  iterator advancement or mapper code.
- An ordinary mapper failure retains native task-group aggregation behavior:
  active siblings are cancelled and awaited, and even one ordinary child
  failure may be delivered as an `ExceptionGroup`.
- External caller cancellation remains `asyncio.CancelledError`; mapper
  `finally` blocks must get a chance to run before propagation completes.
- A mapper-originated cancellation means a direct `raise asyncio.CancelledError`
  or mapper self-cancellation when the invocation owner has no pending external
  cancellation. It is treated as cancellation of the `map_bounded` invocation:
  the helper stops new admission, cancels active siblings, awaits cooperative
  cleanup, and raises `CancelledError` rather than returning partial result
  slots. Self-cancellation remains unsupported except for this fail-closed
  safety behavior.
- To distinguish external caller cancellation, the private runner also checks
  the invocation-owner task's `cancelling()` state. It re-raises cancellation
  while the owner has a pending external request; otherwise a mapper
  cancellation becomes an internal terminal signal that cancels siblings. A
  direct mapper raise has the specified contract above; mapper self-cancellation
  only receives the fail-closed no-partial-result behavior. The parent never
  calls `uncancel()`, and the implementation must preserve external cancellation
  counts.
- Before raising any non-external terminal mapper or iterator signal, a worker
  records call-scoped terminal state. Every worker checks that state immediately
  before its next `next(iterator)` call, so no item is admitted after terminal
  failure is observed.
- A worker also checks its own pending cancellation immediately after a mapper
  returns normally. If the invocation owner has no pending external cancellation
  but the worker does, it records terminal state and raises the private terminal
  signal before recording a result or advancing the iterator. Tests cover both
  self-cancel delivery at the mapper's next `await` and immediate mapper return.
- A non-`None` `timeout` is a total invocation budget implemented with
  `asyncio.timeout()` over cooperative awaited work. Its expiry is exposed as
  `TimeoutError` outside that context, after active mapper cleanup.
- Simultaneous timeout, external cancellation, and mapper failure keep the
  native `TaskGroup`/`asyncio.timeout()` outcome; the helper does not promise a
  single exception type for these races. A race that includes external caller
  cancellation must keep caller cancellation observable and preserve its count.
- The public API does not catch broad exceptions in a way that changes these
  observable exception contracts.

## Approach Options

### Option A - One call-scoped bounded map (selected)

Implement `map_bounded` with a `TaskGroup`, bounded admission, ordered result
slots, and an optional total timeout.

Pros:

- Small, Python-native API with a single ownership boundary.
- Directly exercises Python 3.13 structured concurrency.
- Keeps worker-pool behavior internal and short-lived.
- Gives clear tests for cancellation, timeout, and orphan-task prevention.

Cons:

- Does not serve streaming producers or persistent queues.

### Option B - Map plus for-each

Expose `map_bounded` and a result-discarding `for_each_bounded`.

Pros:

- Familiar surface for some callers.

Cons:

- Adds documentation, tests, and compatibility burden without a distinct
  lifecycle or failure contract.

Decision: reject for this issue.

### Option C - Public worker-pool context manager

Expose a queue-backed `WorkerPool` with `start`, `submit`, `close`, and `join`
behavior.

Pros:

- Could support streaming producer/consumer workloads.

Cons:

- Requires separate contracts for backpressure, producer closure, failure
  propagation, shutdown, and join behavior.
- Greatly increases the task-leak and cancellation surface.

Decision: reject for this issue; create a follow-up only with a concrete
streaming workload.

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Eager task creation bypasses the concurrency limit or leaves orphan tasks. | P0 | Admit at most `limit` items, own tasks in one `TaskGroup`, record terminal state before propagation, and assert cleanup plus terminal-path admission stop. |
| Broad exception handling swallows `CancelledError` or reports partial slots. | P1 | Preserve native external cancellation; make mapper-originated cancellation terminate the invocation; use `finally` tests. |
| Blocking iterator/mapper work defeats timeout and cancellation. | P1 | Document the cooperative boundary and test timeout only with cooperative suspension. |
| Invalid mapper or timeout values consume caller input. | P1 | Validate all public inputs before iterator advancement and test every invalid class. |
| Mapper self-cancellation is confused with external task cancellation. | P1 | Use the owner task to preserve external cancellation, define direct raise as the supported mapper contract, and fail closed without partial results for unsupported self-cancellation. |
| Result order, iterator admission, exception races, or `timeout=None` drifts from the intended contract. | P2 | Add iterator-probe, exception-race, and focused contract tests. |
| `bluetape[asyncio]` could be confused with the stdlib module. | P3 | Document the focused distribution and import path explicitly; keep the default install unchanged. |

## Packaging and Documentation

- Add `packages/bluetape-async/pyproject.toml` with distribution name
  `bluetape-async`, Python `>=3.13`, no runtime dependencies, and module name
  `bluetape.asyncio`.
- Register the package in the root `uv` workspace and workspace sources.
- Add `bluetape-async==0.1.0` only to the `asyncio`, `dev`, and `all` optional
  extras of `packages/bluetape`; do not change its default dependency list.
- Add package README documentation, update root `README.md` and `README.ko.md`,
  `packages/bluetape/README.md`, `docs/package-layout.md`, `WIP.md`, and
  `CHANGELOG.md`.
- Documentation must distinguish local source-workspace use from future PyPI
  installation while publication remains on hold.

## Acceptance Criteria

1. The package builds as `bluetape-async` and imports as `bluetape.asyncio`.
2. `map_bounded` rejects invalid limits before input consumption.
3. It rejects a non-callable mapper and invalid timeout before input consumption.
4. A non-iterable input fails with native `TypeError` before mapper invocation;
   a callable that returns a non-awaitable fails with native task-group error
   aggregation and stops further admission.
5. It never runs more than `limit` mappers at once, admits items incrementally,
   stops admission after every terminal path (including an iterator exception),
   and preserves result order.
6. Empty input returns an empty list without mapper calls.
7. Ordinary mapper failure retains native task-group `ExceptionGroup` behavior;
   direct mapper-originated cancellation and external cancellation do not return
   partial results. Mapper self-cancellation via `Task.cancel()` is unsupported
   but must fail closed without partial results.
8. Cooperative mapper failure, external cancellation, and total timeout preserve
   their caller-visible exception contracts while all started mappers finish
   cleanup. Concurrent failure races retain native asyncio outcomes.
9. Tests prove no helper-owned orphan tasks remain after success, failure,
   cancellation, and timeout paths.
10. The default `bluetape` dependency set remains exactly `bluetape-core`.
11. Package/root README claims, extras, workspace metadata, and user-facing
   status are source-backed and aligned.

## Verification and DoD

- Targeted pytest covers success, empty input, ordering, invalid limits,
  invalid mapper and timeout values, bounded active work, iterator-probe
  admission/replenishment, terminal-path admission stop, `O(n)` result-memory
  documentation, non-iterable, ordinary iterator-failure, iterator-cancellation,
  and non-awaitable protocol violations, ordinary mapper `ExceptionGroup`,
  direct mapper-originated cancellation, unsupported mapper self-cancellation
  fail-closed behavior (including immediate return),
  external cancellation-count preservation, timeout, concurrent failure races,
  cleanup, and orphan-task absence.
- Run `uv sync --all-packages`, `uv lock --check`, targeted and full
  `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv build --all-packages`, and `git diff --check`.
- Run import, metadata, isolated wheel, and default-meta smoke checks.
- Make README snippets executable: source-workspace setup, focused async extra
  install shape, and `from bluetape.asyncio import map_bounded` usage.
- Complete the Type A spec, plan, implementation, verification, six-lane
  7-Tier review, lessons, PR, post-PR review, CI, and final DoD gates before
  requesting a merge.
