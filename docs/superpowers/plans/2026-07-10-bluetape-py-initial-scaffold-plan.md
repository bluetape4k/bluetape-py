# bluetape-py Initial Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the initial `bluetape-py` repo with Python 3.13+, uv workspace packaging, and public `core`, `logging`, and `testing` packages.

**Architecture:** The repository is a single workspace with multiple PyPI distributions. Runtime modules share the `bluetape.*` native namespace while keeping dependency-heavy capabilities outside the default `bluetape` installation.

**Tech Stack:** Python 3.13, uv workspace, uv_build, setuptools metadata-only meta package, pytest, ruff.

---

### Task 1: Workspace And Package Metadata

**Files:**
- Create: `pyproject.toml`
- Create: `packages/bluetape/pyproject.toml`
- Create: `packages/bluetape-core/pyproject.toml`
- Create: `packages/bluetape-logging/pyproject.toml`
- Create: `packages/bluetape-testing/pyproject.toml`

- [x] **Step 1: Define Python 3.13 workspace root**

The root project is not publishable and exists to install workspace members for development.

- [x] **Step 2: Define thin `bluetape` meta package**

`bluetape` depends only on `bluetape-core`; optional extras pull `logging` and `testing`.

- [x] **Step 3: Define native namespace package members**

Each package uses `tool.uv.build-backend.module-name` with `bluetape.core`, `bluetape.logging`, or `bluetape.testing`.

### Task 2: Test-First Public API

**Files:**
- Create: `packages/bluetape-core/tests/test_validation.py`
- Create: `packages/bluetape-logging/tests/test_context.py`
- Create: `packages/bluetape-testing/tests/test_eventually.py`

- [x] **Step 1: Write tests before production code**

Tests define the initial behavior for validation, scoped log context, redaction, and eventually helpers.

- [x] **Step 2: Run RED verification**

Run: `uv run pytest`

Observed: FAIL because the package modules were not implemented yet.

### Task 3: Minimal Implementation

**Files:**
- Create: `packages/bluetape-core/src/bluetape/core/__init__.py`
- Create: `packages/bluetape-logging/src/bluetape/logging/__init__.py`
- Create: `packages/bluetape-testing/src/bluetape/testing/__init__.py`

- [x] **Step 1: Implement only the tested public functions**

Implement `require_not_blank`, `require_not_none`, `log_context`, `get_log_context`, `ContextLogFilter`, `redact`, `eventually`, and `eventually_async`.

- [x] **Step 2: Run GREEN verification**

Run: `uv run pytest`

Observed: PASS, 11 tests.

### Task 4: Repository Verification And First Push

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

- [x] **Step 1: Add CI for Python 3.13**

Run `uv sync --all-packages`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.

- [x] **Step 2: Run local verification**

Run:

```bash
uv sync --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Observed: `uv sync --all-packages`, `uv build --all-packages`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `git diff --check` exit `0`.

### Self-Review

- Spec coverage: the plan covers repo, workspace, meta package, initial modules, tests, and validation.
- Placeholder scan: no `TBD` or open-ended implementation placeholder remains.
- Type consistency: package names and import paths match the design.
