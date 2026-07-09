# AGENTS.md - bluetape-py

This repository inherits the workspace guidance from `../AGENTS.md`.
Read and follow the workspace root guide first. This file only adds
Python-specific layout, commands, domain rules, and local exceptions.

Python-native backend utilities for the bluetape ecosystem. This repository is
not a mechanical Kotlin, Go, or Rust port; sibling projects are references for
scope and discipline, while Python API shape and packaging conventions are the
source of truth here.

## Skills

- Use `bluetape4k-workflow` for task classification, issue/PR discipline,
  release gates, and DoD reporting.
- Use `bluetape-py-patterns` for Python implementation, tests, async behavior,
  packaging, public API design, release preflight, and Python review gates.
- Use `bluetape4k-maintenance` for README, docs, `.gitignore`, `AGENTS.md`,
  release guidance, and workflow-only changes.

## Commands

```bash
uv sync --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
git diff --check
```

Use targeted `uv run pytest <path>` for narrow changes, then escalate to the
full command set when package metadata, release readiness, CI, or shared public
contracts change.

## Package Boundaries

- Python version policy is Python 3.13+.
- `bluetape` is a thin meta distribution and should not create a root
  `bluetape/__init__.py` import surface.
- The default `bluetape` install should depend only on `bluetape-core`.
- `bluetape-core` stays stdlib-only.
- `bluetape-logging` stays stdlib-only around `logging`, `contextvars`, and
  caller-owned redaction helpers.
- `bluetape-testing` may depend on `pytest`, starts internal-first, and should
  expose only the documented stable helper subset.
- Planned ecosystem packages belong in issues, WIP, or research notes until
  their Python package boundary and dependency choices are source-backed.

## Testing And Review

- Public helpers need tests for success, invalid input, boundary or empty input,
  and caller-owned value preservation.
- Async helpers need timeout/cancellation/resource-cleanup coverage when the
  behavior is part of the contract.
- Packaging changes require `uv build --all-packages` and an import or metadata
  smoke check when dependencies, extras, namespace packages, or Python version
  requirements change.
- Python code PRs must record P0/P1 review evidence through the active
  `bluetape4k-workflow` gates before being reported merge-ready.

## Documentation

- Keep `README.md` and `README.ko.md` aligned when user-facing behavior,
  install shape, package status, or roadmap guidance changes.
- Keep package READMEs current for active distributions under `packages/`.
- Durable release policy belongs under `docs/release*`; runtime OMX cache under
  `.omx/` is local state and must stay ignored.
- Internal planning can live in `WIP.md`; completed user-facing changes belong
  in `CHANGELOG.md`.

## Git Workflow

- `develop` is the integration branch.
- `main` is release-only and is promoted from `develop` through a release PR.
- Use issue- or task-scoped worktrees under `.worktrees/` for code and
  maintenance changes unless the user explicitly selects the current checkout.
- PR bodies must end with the workflow-required `## DoD Status` section.
