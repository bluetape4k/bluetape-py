# bluetape-py Initial Design

## Context

`bluetape-py` is a Python-native member of the bluetape ecosystem. It should not mechanically port JVM, Go, or Rust APIs. It should expose Python 3.13+ helpers that are small, typed, dependency-conscious, and useful for backend service code.

## Decisions

- Use one GitHub repository, `bluetape4k/bluetape-py`.
- Use `uv` workspace members under `packages/*`.
- Publish multiple PyPI distributions but one import namespace, `bluetape.*`.
- Keep `pip install bluetape` thin: it installs only `bluetape-core`.
- Require Python `>=3.13`.
- Start `0.1.0` with `bluetape-core`, `bluetape-logging`, and `bluetape-testing`.
- Treat `bluetape-testing` as internal-first, while documenting only stable helpers for external users.
- Keep `bluetape-core` and `bluetape-logging` stdlib-only.

## Initial Package Boundaries

| Distribution | Import path | Contract |
|---|---|---|
| `bluetape` | none | Meta distribution depending only on `bluetape-core`. |
| `bluetape-core` | `bluetape.core` | Validation and tiny foundation helpers with no third-party runtime dependencies. |
| `bluetape-logging` | `bluetape.logging` | Thin `logging` and `contextvars` helpers, not a logging framework replacement. |
| `bluetape-testing` | `bluetape.testing` | Pytest-oriented waiting and async assertion helpers. |

## Validation

- `uv sync --all-packages`
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format --check .`
