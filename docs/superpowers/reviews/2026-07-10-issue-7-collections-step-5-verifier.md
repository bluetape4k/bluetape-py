# Step 5 Verifier - Issue #7 Collections

Date: 2026-07-10 KST
Scope: `bluetape-collections` implementation, metadata, docs, and lockfile.

## Verdict

PASS

## Requirement Trace

- New stdlib-only distribution:
  `packages/bluetape-collections/pyproject.toml` uses `uv_build`,
  `requires-python = ">=3.13"`, `dependencies = []`, and module name
  `bluetape.collections`.
- Public import path:
  `packages/bluetape-collections/src/bluetape/collections/__init__.py`.
- Thin meta package:
  `packages/bluetape/pyproject.toml` keeps default dependencies at
  `["bluetape-core==0.1.0"]` and adds collections only to extras.
- Tests:
  `packages/bluetape-collections/tests/test_collections.py` covers exports,
  success paths, empty/boundary inputs, invalid inputs, pre-consumption
  `chunked` size validation, unhashable distinct values/keys, exception
  propagation, and caller-owned container preservation.
- Documentation:
  root README files, package README, `docs/package-layout.md`, `WIP.md`, and
  `CHANGELOG.md` reflect source-workspace availability and PyPI publish hold.

## Fresh Evidence

- TDD red:
  `uv run pytest packages/bluetape-collections/tests/test_collections.py`
  failed before implementation with
  `ModuleNotFoundError: No module named 'bluetape.collections'`.
- Targeted green:
  `uv run pytest packages/bluetape-collections/tests/test_collections.py` -
  `30 passed`.
- Full test:
  `uv run pytest` - `51 passed`.
- Formatting/lint:
  `uv run ruff format --check .` - pass.
  `uv run ruff check .` - pass.
- Lock/build:
  `uv lock --check` - pass.
  `uv sync --all-packages --locked` - pass.
  `uv build --all-packages` - built all five distributions.
- Diff hygiene:
  `git diff --check` - pass.
- Runtime smoke:
  `from bluetape.collections import chunked; chunked(range(3), 2)` returned
  `[[0, 1], [2]]`.
- Metadata smoke:
  default `bluetape` dependencies remain `["bluetape-core==0.1.0"]`; the
  `collections`, `dev`, and `all` extras include
  `bluetape-collections==0.1.0`; workspace source is present.
- Root import smoke:
  `packages/bluetape/src/bluetape/__init__.py` does not exist.
- Isolated artifact smoke:
  built `bluetape-collections` wheel installs in a temporary Python 3.14 venv
  and imports `bluetape.collections`.
- Isolated default meta smoke:
  built `bluetape` wheel installs without extras in a temporary Python 3.14
  venv and requires `bluetape-core` by default without default
  `bluetape-collections`.

## Stress/Allocation Smoke

Representative finite generators with `SIZE = 20_000`:

| Helper | Elapsed | Peak memory |
|---|---:|---:|
| `chunked` | 0.0022s | 800632B |
| `distinct_by` | 0.0023s | 410664B |
| `group_by` | 0.0026s | 811536B |
| `count_by` | 0.0011s | 3840B |
| `partition` | 0.0022s | 799352B |

Thresholds: elapsed `< 1.0s`, peak memory `< 10_000_000B`.

Performance review follow-up replaced the duplicate-key `group_by`
`setdefault(..., [])` path with bucket creation only for new keys. A refreshed
duplicate-heavy `group_by` smoke over 20,000 values and 64 keys passed after the
change with the same `timeit`/`tracemalloc` script used for the table above.

## Known Gaps

- No Python 3.13 interpreter is installed locally; verification used Python
  3.14.6, which satisfies the `>=3.13` package policy.
- PyPI publication remains on HOLD and is explicitly out of scope for this PR.
