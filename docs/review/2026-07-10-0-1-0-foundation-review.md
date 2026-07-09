# 0.1.0 Foundation Review

## Scope

- Branch: `feat/0.1.0-foundation-closure`
- Base: `origin/develop`
- Issues: #1, #2, #3, #5
- Applied guidance: `bluetape4k-workflow`, `bluetape-py-patterns`,
  test-driven development, and worktree isolation

## Findings

- P0: 0
- P1: 0

The new `bluetape-core` helper keeps the validation package narrow:
`require_instance` returns a typed value on success and raises `TypeError` for
type contract violations. Existing `ValueError` contracts for presence,
blank-string, and empty-sized values remain unchanged.

`bluetape-logging` remains stdlib-only at runtime. Context merge behavior is
still opt-out safe by default, while `override=False` gives callers a duplicate
key guard for scoped logging context. Redaction now defaults to
case-insensitive key matching, which covers common HTTP header capitalization
without mutating the original mapping.

`bluetape-testing` remains internal-first and keeps `pytest` as its only runtime
dependency. `eventually` and `eventually_async` now treat falsy non-`None`
values such as `0` as successful probe results, while `None` and `False` remain
unsatisfied. Non-positive timeout and interval inputs fail fast with
`ValueError`.

Release readiness is still intentionally pre-publish. CI builds all workspace
distributions, and `docs/release/pypi-preflight.md` records the intended
distribution set plus the trusted-publishing hold.

## Validation

- `uv sync --all-packages`: pass
- `uv run pytest`: pass, 21 tests
- `uv run ruff check .`: pass
- `uv run ruff format --check .`: pass
- `uv build --all-packages`: pass, 8 artifacts
- Import and metadata smoke: pass
- `actionlint`: pass
- `rg -n "\\'" .github/workflows || true`: pass, no matches
- `git diff --check`: pass

## Residual Risk

The PyPI trusted-publishing setup is documented but not performed in this
branch. Publishing remains blocked until repository ownership and PyPI project
configuration are confirmed outside the source tree.
