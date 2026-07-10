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
4. Preserve `asyncio.CancelledError`, `TimeoutError`, mapper exceptions, and
   `ExceptionGroup` semantics without wrapping, translating, or suppressing
   them.
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
- No custom deadline type, custom cancellation token, AnyIO, or other new
  runtime dependency.
- No Go `context` or Kotlin coroutine API port.
- No PyPI publication, GitHub Release, tag, or merge in this issue.

## API and Runtime Contract

### Input and result behavior

- `items` is a synchronous `Iterable`; it is consumed incrementally, with no
  more than `limit` items admitted ahead of completed work.
- `limit` must be an `int` other than `bool` and greater than zero. Invalid
  limits raise `TypeError` or `ValueError` before consuming `items` or invoking
  `mapper`.
- An empty iterable returns `[]` without invoking `mapper`.
- The result list uses the original input order, not completion order.
- `timeout=None` means no package-owned timeout boundary.

### Failure, cancellation, and cleanup behavior

- The implementation uses one call-scoped `asyncio.TaskGroup`; it does not
  call bare `asyncio.create_task()` for public work ownership.
- A mapper failure retains the original task-group failure behavior and causes
  active sibling work to be cancelled and awaited before control leaves the
  helper.
- External caller cancellation remains `asyncio.CancelledError`; mapper
  `finally` blocks must get a chance to run before propagation completes.
- A non-`None` `timeout` is a total invocation budget implemented with
  `asyncio.timeout()`. Its expiry is exposed as `TimeoutError` outside that
  context, after active mapper cleanup.
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
| Eager task creation bypasses the concurrency limit or leaves orphan tasks. | P0 | Admit at most `limit` items, own tasks in one `TaskGroup`, and assert cleanup in cancellation/timeout tests. |
| Broad exception handling swallows `CancelledError`. | P1 | Do not catch cancellation; use `finally` in tests to prove cleanup and caller-visible cancellation. |
| Per-task timeout changes caller deadline and error meaning. | P1 | Support only a total call budget through `asyncio.timeout()`. |
| Result order, iterator admission, or `timeout=None` drifts from the intended contract. | P2 | Document each rule and add focused pytest coverage. |
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
3. It never runs more than `limit` mappers at once and preserves result order.
4. Empty input returns an empty list without mapper calls.
5. Mapper failure, external cancellation, and total timeout preserve their
   caller-visible exception contracts while all started mappers finish cleanup.
6. Tests prove no helper-owned orphan tasks remain after success, failure,
   cancellation, and timeout paths.
7. The default `bluetape` dependency set remains exactly `bluetape-core`.
8. Package/root README claims, extras, workspace metadata, and user-facing
   status are source-backed and aligned.

## Verification and DoD

- Targeted pytest covers success, empty input, ordering, invalid limits,
  bounded active work, mapper failure, external cancellation, timeout, cleanup,
  and orphan-task absence.
- Run `uv sync --all-packages`, `uv lock --check`, targeted and full
  `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv build --all-packages`, and `git diff --check`.
- Run import, metadata, isolated wheel, and default-meta smoke checks.
- Complete the Type A spec, plan, implementation, verification, six-lane
  7-Tier review, lessons, PR, post-PR review, CI, and final DoD gates before
  requesting a merge.
