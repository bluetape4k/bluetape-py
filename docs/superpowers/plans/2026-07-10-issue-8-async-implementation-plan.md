# Async Bounded Fan-out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the stdlib-only `bluetape-async` distribution and its small,
structured-concurrency `map_bounded` API without changing the default
`bluetape` dependency set.

**Architecture:** The public module `bluetape.asyncio` owns a single bounded
fan-out function. Each invocation validates all public values before iterator
consumption, owns a fixed set of private workers in one `asyncio.TaskGroup`,
and stores results in input order. A direct mapper-raised `CancelledError` is
converted into a private ordinary exception so `TaskGroup` cancels siblings;
the owner task distinguishes external cancellation, while unsupported mapper
self-cancellation fails closed rather than return partial results.

**Tech Stack:** Python 3.13+, `asyncio.TaskGroup`, `asyncio.timeout`, `uv`,
`uv_build`, pytest with pytest-asyncio, Ruff.

---

## File Structure

| Path | Responsibility |
|---|---|
| `packages/bluetape-async/pyproject.toml` | Distribution metadata and `bluetape.asyncio` build mapping. |
| `packages/bluetape-async/src/bluetape/asyncio/__init__.py` | Public `map_bounded` API and private validation/cancellation helpers. |
| `packages/bluetape-async/tests/test_map_bounded.py` | Async contract tests for ordering, bounds, validation, failure, cancellation, timeout, and cleanup. |
| `packages/bluetape-async/README.md` | Package-specific usage, ownership, failure, and installation contract. |
| `pyproject.toml`, `uv.lock` | Workspace membership and locked editable package metadata. |
| `packages/bluetape/pyproject.toml` | Optional `asyncio` extra and aggregate extras only. |
| `packages/bluetape/README.md`, `README.md`, `README.ko.md` | Focused install and usage documentation. |
| `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Durable package-boundary, roadmap, and user-facing change records. |

### Task 1: Register the focused distribution

**Files:**
- Create: `packages/bluetape-async/pyproject.toml`
- Create: `packages/bluetape-async/src/bluetape/asyncio/__init__.py`
- Create: `packages/bluetape-async/tests/test_map_bounded.py`
- Create: `packages/bluetape-async/README.md`
- Modify: `pyproject.toml`
- Modify: `packages/bluetape/pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add package metadata and an import-only placeholder.**

```toml
# packages/bluetape-async/pyproject.toml
[project]
name = "bluetape-async"
version = "0.1.0"
description = "Stdlib-only bounded asyncio helpers for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.asyncio"
```

```python
# packages/bluetape-async/src/bluetape/asyncio/__init__.py
"""Bounded structured-concurrency helpers for bluetape-py."""

__all__: list[str] = []
```

```markdown
<!-- packages/bluetape-async/README.md -->
# bluetape-async

Stdlib-only bounded asyncio helpers for bluetape-py. The package documentation
is completed with the public API in Task 4.
```

- [ ] **Step 2: Register only the intended optional dependency paths.**

Add `bluetape-async==0.1.0` to the root workspace dependencies and
`[tool.uv.sources]`; add `packages/bluetape-async` to workspace members. Add
the same workspace source to `packages/bluetape/pyproject.toml`, then add:

```toml
asyncio = ["bluetape-async==0.1.0"]
```

to optional dependencies and include `bluetape-async==0.1.0` in `dev` and
`all`. Do not add it to `project.dependencies`, which must remain exactly
`["bluetape-core==0.1.0"]`.

- [ ] **Step 3: Refresh and validate the workspace lock.**

Run: `uv lock && uv sync --all-packages && uv lock --check`

Expected: the lock includes editable `bluetape-async`; all workspace packages
install successfully.

- [ ] **Step 4: Prove the placeholder imports through the workspace.**

Run: `uv run python -c "import bluetape.asyncio; print(bluetape.asyncio.__all__)"`

Expected: `[]`.

- [ ] **Step 5: Commit the package boundary.**

Run: `git add pyproject.toml uv.lock packages/bluetape-async/pyproject.toml packages/bluetape-async/README.md packages/bluetape-async/src/bluetape/asyncio/__init__.py packages/bluetape/pyproject.toml && git diff --cached --check`

Commit intent: `build: register focused async package`, with Lore trailers
recording the default-install constraint and lock validation.

### Task 2: Lock the public contract with failing tests

**Files:**
- Modify: `packages/bluetape-async/tests/test_map_bounded.py`

- [ ] **Step 1: Write the complete API contract test module.**

```python
import asyncio
from collections.abc import Iterator

import pytest

from bluetape.asyncio import __all__, map_bounded


def _assert_no_helper_tasks() -> None:
    assert not [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and task.get_name().startswith("bluetape.map_bounded.")
    ]


def _raising_iterable() -> Iterator[int]:
    raise AssertionError("items must not be consumed")
    yield 0


def test_all_exports_map_bounded() -> None:
    assert __all__ == ["map_bounded"]


async def test_map_bounded_preserves_input_order_and_limit() -> None:
    active = 0
    maximum = 0

    async def mapper(value: int) -> int:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.001 * (4 - value))
        active -= 1
        return value * 10

    assert await map_bounded([1, 2, 3], mapper, limit=2) == [10, 20, 30]
    assert maximum == 2


async def test_map_bounded_admits_only_limit_items_before_completion() -> None:
    admitted = 0
    started = asyncio.Event()
    release = asyncio.Event()

    def items() -> Iterator[int]:
        nonlocal admitted
        for value in range(3):
            admitted += 1
            yield value

    async def mapper(value: int) -> int:
        if value == 1:
            started.set()
        await release.wait()
        return value

    task = asyncio.create_task(map_bounded(items(), mapper, limit=2))
    await started.wait()
    assert admitted == 2
    release.set()
    assert await task == [0, 1, 2]


async def test_map_bounded_returns_empty_list_without_mapper_call() -> None:
    async def mapper(_: int) -> int:
        raise AssertionError("mapper must not be called")

    assert await map_bounded([], mapper, limit=1) == []


async def test_map_bounded_accepts_explicit_timeout_none() -> None:
    assert await map_bounded([1], _identity, limit=1, timeout=None) == [1]


async def _identity(value: int) -> int:
    return value


@pytest.mark.parametrize(
    ("limit", "error"),
    [(True, TypeError), (False, TypeError), (1.5, TypeError), (0, ValueError), (-1, ValueError)],
)
async def test_map_bounded_validates_limit_before_consuming(
    limit: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        await map_bounded(_raising_iterable(), _identity, limit=limit)  # type: ignore[arg-type]


async def test_map_bounded_rejects_non_callable_mapper_before_consuming() -> None:
    with pytest.raises(TypeError, match="mapper must be callable"):
        await map_bounded(_raising_iterable(), None, limit=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("timeout", "error"),
    [
        (True, TypeError),
        (False, TypeError),
        ("1", TypeError),
        (-0.1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
    ],
)
async def test_map_bounded_validates_timeout_before_consuming(
    timeout: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        await map_bounded(
            _raising_iterable(),
            _identity,
            limit=1,
            timeout=timeout,  # type: ignore[arg-type]
        )


async def test_map_bounded_preserves_native_non_iterable_and_non_awaitable_failures() -> None:
    mapper_called = False

    async def mapper(value: int) -> int:
        nonlocal mapper_called
        mapper_called = True
        return value

    with pytest.raises(TypeError):
        await map_bounded(None, mapper, limit=1)  # type: ignore[arg-type]
    assert not mapper_called

    admitted = 0

    def items() -> Iterator[int]:
        nonlocal admitted
        for value in range(3):
            admitted += 1
            yield value

    with pytest.raises(ExceptionGroup):
        await map_bounded(items(), lambda value: value, limit=1)  # type: ignore[arg-type]
    assert admitted == 1
    _assert_no_helper_tasks()


async def test_map_bounded_cleans_up_after_iterator_and_mapper_failures() -> None:
    cleaned = asyncio.Event()

    def failing_items() -> Iterator[int]:
        yield 1
        raise RuntimeError("iterator boom")

    async def waiting_mapper(_: int) -> int:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises(ExceptionGroup, match="iterator boom"):
        await map_bounded(failing_items(), waiting_mapper, limit=2)
    assert cleaned.is_set()

    async def broken_mapper(_: int) -> int:
        raise RuntimeError("mapper boom")

    with pytest.raises(ExceptionGroup, match="mapper boom"):
        await map_bounded([1], broken_mapper, limit=1)


async def test_map_bounded_propagates_direct_mapper_cancellation_after_cleanup() -> None:
    cleaned = asyncio.Event()
    sibling_started = asyncio.Event()
    admitted = 0

    def items() -> Iterator[int]:
        nonlocal admitted
        for value in range(3):
            admitted += 1
            yield value

    async def mapper(value: int) -> int:
        if value == 0:
            sibling_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        await sibling_started.wait()
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await map_bounded(items(), mapper, limit=2)
    assert admitted == 2
    assert cleaned.is_set()
    _assert_no_helper_tasks()


async def test_map_bounded_self_cancellation_fails_closed() -> None:
    async def mapper(_: int) -> int:
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        await asyncio.sleep(0)
        return 1

    with pytest.raises(asyncio.CancelledError):
        await map_bounded([1], mapper, limit=1)
    _assert_no_helper_tasks()


async def test_map_bounded_preserves_external_cancellation_and_cleanup() -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def mapper(_: int) -> int:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    task = asyncio.create_task(map_bounded([1], mapper, limit=1))
    await started.wait()
    task.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelling() == 2
    assert cleaned.is_set()
    _assert_no_helper_tasks()


async def test_map_bounded_times_out_after_cleanup() -> None:
    cleaned = asyncio.Event()

    async def mapper(_: int) -> int:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises(TimeoutError):
        await map_bounded([1], mapper, limit=1, timeout=0.01)
    assert cleaned.is_set()
    _assert_no_helper_tasks()


async def test_map_bounded_timeout_is_a_total_budget() -> None:
    cleaned: list[int] = []

    async def mapper(value: int) -> int:
        try:
            await asyncio.sleep(0.02)
            return value
        finally:
            cleaned.append(value)

    with pytest.raises(TimeoutError):
        await map_bounded([1, 2, 3], mapper, limit=1, timeout=0.03)
    assert cleaned == [1, 2]
    _assert_no_helper_tasks()


async def test_map_bounded_timeout_and_mapper_failure_keep_native_outcomes() -> None:
    cleaned = asyncio.Event()

    async def mapper(value: int) -> int:
        if value == 0:
            await asyncio.sleep(0.01)
            raise RuntimeError("boom")
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises((TimeoutError, ExceptionGroup)):
        await map_bounded([0, 1], mapper, limit=2, timeout=0.01)
    assert cleaned.is_set()
    _assert_no_helper_tasks()


async def test_map_bounded_external_cancellation_race_preserves_count() -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def mapper(value: int) -> int:
        started.set()
        try:
            if value == 0:
                await asyncio.sleep(0)
                raise RuntimeError("boom")
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    task = asyncio.create_task(map_bounded([0, 1], mapper, limit=2))
    await started.wait()
    task.cancel()
    task.cancel()
    with pytest.raises((asyncio.CancelledError, ExceptionGroup)):
        await task
    assert task.cancelling() >= 2
    assert cleaned.is_set()
    _assert_no_helper_tasks()


async def test_map_bounded_leaves_no_named_worker_tasks() -> None:
    async def mapper(value: int) -> int:
        await asyncio.sleep(0)
        return value

    assert await map_bounded([1, 2], mapper, limit=2) == [1, 2]
    _assert_no_helper_tasks()
```

- [ ] **Step 2: Run the contract tests before implementation.**

Run: `uv run pytest packages/bluetape-async/tests/test_map_bounded.py -q`

Expected: collection/import failure because `map_bounded` is not yet exported.

- [ ] **Step 3: Commit the failing contract.**

Run: `git add packages/bluetape-async/tests/test_map_bounded.py && git diff --cached --check`

Commit intent: `test: define bounded async map contract`, with Lore trailers
recording native asyncio exception-shape constraints.

### Task 3: Implement one call-scoped bounded map

**Files:**
- Modify: `packages/bluetape-async/src/bluetape/asyncio/__init__.py`

- [ ] **Step 1: Replace the placeholder with the complete implementation.**

```python
"""Bounded structured-concurrency helpers for bluetape-py."""

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import cast


class _InvocationCancelled(Exception):
    """Private task-group signal for a non-external cancellation."""


def _require_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit must be an integer")
    if limit <= 0:
        raise ValueError("limit must be greater than 0")


def _require_mapper[T, R](
    mapper: Callable[[T], Awaitable[R]] | object,
) -> Callable[[T], Awaitable[R]]:
    if not callable(mapper):
        raise TypeError("mapper must be callable")
    return cast(Callable[[T], Awaitable[R]], mapper)


def _require_timeout(timeout: float | None) -> None:
    if timeout is None:
        return
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be a finite non-negative number")
    if timeout < 0 or not math.isfinite(timeout):
        raise ValueError("timeout must be a finite non-negative number")


async def _invoke_mapper[T, R](
    mapper: Callable[[T], Awaitable[R]],
    item: T,
    owner: asyncio.Task[object],
    terminal: asyncio.Event,
) -> R:
    try:
        return await mapper(item)
    except asyncio.CancelledError:
        if owner.cancelling():
            raise
        terminal.set()
        raise _InvocationCancelled from None
    except BaseException:
        terminal.set()
        raise


async def map_bounded[T, R](
    items: Iterable[T],
    mapper: Callable[[T], Awaitable[R]],
    *,
    limit: int,
    timeout: float | None = None,
) -> list[R]:
    """Map synchronous input with bounded asyncio concurrency.

    The iterable is consumed incrementally and results retain input order.
    `timeout` is a total cooperative invocation budget. A direct mapper-raised
    `CancelledError` cancels sibling work; unsupported mapper self-cancellation
    fails closed without returning partial result slots.
    """
    _require_limit(limit)
    mapper_fn = _require_mapper(mapper)
    _require_timeout(timeout)
    iterator = iter(items)
    owner = asyncio.current_task()
    if owner is None:
        raise RuntimeError("map_bounded requires a running task")
    results: list[R | None] = []
    terminal = asyncio.Event()

    async def worker() -> None:
        while True:
            if terminal.is_set():
                return
            try:
                item = next(iterator)
            except StopIteration:
                return
            except asyncio.CancelledError:
                if owner.cancelling():
                    raise
                terminal.set()
                raise _InvocationCancelled from None
            except BaseException:
                terminal.set()
                raise
            index = len(results)
            results.append(None)
            results[index] = await _invoke_mapper(mapper_fn, item, owner, terminal)

    async def run_workers() -> None:
        async with asyncio.TaskGroup() as task_group:
            for worker_index in range(limit):
                task_group.create_task(
                    worker(),
                    name=f"bluetape.map_bounded.{worker_index}",
                )

    try:
        if timeout is None:
            await run_workers()
        else:
            async with asyncio.timeout(timeout):
                await run_workers()
    except* _InvocationCancelled:
        raise asyncio.CancelledError from None

    return cast(list[R], results)


__all__ = ["map_bounded"]
```

- [ ] **Step 2: Run the targeted contract suite.**

Run: `uv run pytest packages/bluetape-async/tests/test_map_bounded.py -q`

Expected: all contract tests pass. If a race assertion fails, preserve the
native TaskGroup/timeout result and narrow only the test assertion; do not add
custom exception wrapping or `uncancel()`.

- [ ] **Step 3: Run style checks for the changed package.**

Run: `uv run ruff check packages/bluetape-async && uv run ruff format --check packages/bluetape-async`

Expected: both commands succeed with no changes required.

- [ ] **Step 4: Commit the implementation.**

Run: `git add packages/bluetape-async/src/bluetape/asyncio/__init__.py && git diff --cached --check`

Commit intent: `feat: add bounded asyncio map`, with Lore trailers preserving
the no-detached-task, direct-cancellation, and no-`uncancel()` decisions.

### Task 4: Publish the source-workspace contract in documentation

**Files:**
- Modify: `packages/bluetape-async/README.md`
- Modify: `packages/bluetape/README.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write the async package README.**

Document this exact usage example:

```python
import asyncio

from bluetape.asyncio import map_bounded


async def fetch_order(order_id: int) -> str:
    await asyncio.sleep(0.01)
    return f"order-{order_id}"


orders = await map_bounded([1, 2, 3], fetch_order, limit=2, timeout=1.0)
```

State that source-workspace use is available now, PyPI publication remains on
hold, results preserve input order, mapper and iterator work must cooperate
with the event loop, timeout is total, direct mapper cancellation terminates
the invocation, and unsupported mapper self-cancellation fails closed without
partial results. State that `limit` controls the number of call-scoped workers,
so callers must choose a resource-appropriate positive value.

- [ ] **Step 2: Align meta and root documentation.**

Add `bluetape-async` / `bluetape.asyncio` to both root package tables, add
`pip install "bluetape[asyncio]"` and direct `pip install bluetape-async` to
the intended post-publication install shapes, link the package README, and add
the bounded-map example above in both English and Korean root README files.
Add the same extra to the meta-package README. Keep the default-install text
explicitly limited to `bluetape-core`.

- [ ] **Step 3: Update durable package records.**

In `docs/package-layout.md`, list `bluetape-async` as an active focused
distribution and require cooperative ownership/cancellation documentation for
async packages. In `WIP.md`, mark issue #8 as implemented in the source
workspace while keeping PyPI publication on hold. In `CHANGELOG.md` under
`Unreleased / Added`, add one bullet naming `bluetape-async`, its import path,
and its bounded structured-concurrency purpose.

- [ ] **Step 4: Validate documentation and commit it.**

Run: `git diff --check && uv run python -c "from bluetape.asyncio import map_bounded; print(map_bounded.__name__)"`

Expected: no whitespace errors and `map_bounded`.

Commit intent: `docs: document bounded async package`, with Lore trailers
recording the PyPI-hold and thin-default constraints.

### Task 5: Run the release-quality verification matrix

**Files:**
- Modify only if verification exposes a concrete defect in the preceding tasks.

- [ ] **Step 1: Verify package metadata and extras.**

Run: `uv lock --check && uv run python -c "from importlib.metadata import metadata; print(metadata('bluetape-async')['Requires-Python'])"`

Expected: lock is current, the package requires Python `>=3.13`, and the meta
default remains core-only while the async extra exists.

- [ ] **Step 2: Run targeted and full static/test verification.**

Run: `uv sync --all-packages && uv run pytest packages/bluetape-async/tests/test_map_bounded.py && uv run pytest && uv run ruff check . && uv run ruff format --check .`

Expected: all tests and Ruff checks pass.

- [ ] **Step 3: Build every distribution and inspect built-wheel metadata.**

Run: `uv build --all-packages && uv run python - <<'PY'
from email.parser import BytesParser
from zipfile import ZipFile

with ZipFile("dist/bluetape-0.1.0-py3-none-any.whl") as wheel:
    metadata_name = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
    metadata = BytesParser().parsebytes(wheel.read(metadata_name))

requirements = metadata.get_all("Requires-Dist", [])
default_requirements = [item for item in requirements if "extra ==" not in item]
assert len(default_requirements) == 1
assert default_requirements[0].startswith("bluetape-core")
assert not any(item.startswith("bluetape-async") for item in default_requirements)
assert any(
    item.startswith("bluetape-async") and "extra == 'asyncio'" in item
    for item in requirements
)
PY
python -m venv /tmp/bluetape-async-wheel-smoke
/tmp/bluetape-async-wheel-smoke/bin/pip install dist/bluetape_async-0.1.0-py3-none-any.whl
/tmp/bluetape-async-wheel-smoke/bin/python -c "from bluetape.asyncio import map_bounded; print(map_bounded.__name__)"`

Expected: all distributions build, the built meta-wheel keeps only core as its
default requirement while its async dependency is extra-gated, and the isolated
async wheel installs without source imports and prints `map_bounded`.

- [ ] **Step 4: Execute the documented examples through the workspace.**

Run: `uv run python - <<'PY'
import asyncio

from bluetape.asyncio import map_bounded


async def fetch_order(order_id: int) -> str:
    await asyncio.sleep(0)
    return f"order-{order_id}"


assert asyncio.run(map_bounded([1, 2, 3], fetch_order, limit=2, timeout=1.0)) == [
    "order-1",
    "order-2",
    "order-3",
]
PY`

Expected: the README bounded-map example completes with ordered results.

- [ ] **Step 5: Final diff and review evidence.**

Run: `git diff develop...HEAD --check && git status --short`

Expected: no whitespace error and only intentional tracked work. Record the
fresh test/build results in the implementation review artifact before PR work.

## Plan Self-Review

| Spec requirement | Implementing task |
|---|---|
| Focused optional package/import and thin default | Task 1, Task 4, Task 5. |
| Ordered bounded fan-out and incremental synchronous input | Task 2, Task 3. |
| Pre-consumption validation and native protocol errors | Task 2, Task 3. |
| TaskGroup ownership, no orphan tasks, cleanup | Task 2, Task 3, Task 5. |
| Direct mapper cancellation, external cancellation, timeout | Task 2, Task 3. |
| Documentation, WIP, changelog, PyPI hold | Task 4. |
| Lock, lint, tests, build, metadata, isolated wheel | Task 1, Task 5. |

Placeholder scan: no deferred implementation steps. Type names and the
`map_bounded(items, mapper, *, limit, timeout)` signature are consistent across
tests, implementation, documentation, and verification.
