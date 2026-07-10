# Issue #7 Collections Package Plan

Date: 2026-07-10 KST
Target issue: #7 - `feat: add bluetape-collections helper package`
Target milestone: `0.2.0`

## Objective

Implement the first Python-native collections package as a narrow,
stdlib-only distribution. The package exposes eager helpers under
`bluetape.collections`, keeps the default `bluetape` meta install thin, and
documents the package in root and package-level README files.

## Inputs

- Approved spec:
  `docs/superpowers/specs/2026-07-10-issue-7-collections-design.md`
- GitHub issue #7 acceptance criteria.
- Existing package layout and packaging conventions in `packages/bluetape-*`.
- `bluetape-go/collections` as inspiration only, not a parity target.

## Implementation Steps

1. Add a failing pytest suite first under
   `packages/bluetape-collections/tests/test_collections.py`.
   - Cover exports, success behavior, empty input, invalid sizes, missing
     callables, exception propagation, unhashable `distinct` values, and input
     mutation preservation.
   - Run `uv run pytest packages/bluetape-collections/tests/test_collections.py`
     and confirm the expected red failure before production code exists.

2. Add the package scaffold.
   - Create `packages/bluetape-collections/pyproject.toml`.
   - Match existing focused package metadata:
     `name = "bluetape-collections"`, `version = "0.1.0"`,
     `description`, `readme = "README.md"`, `requires-python = ">=3.13"`,
     `dependencies = []`, `[build-system].requires =
     ["uv_build>=0.11.28,<0.12"]`, `build-backend = "uv_build"`, and
     `module-name = "bluetape.collections"`.
   - Create `packages/bluetape-collections/src/bluetape/collections/__init__.py`.
   - Register the package in root `pyproject.toml` workspace members and
     workspace sources.
   - Add `bluetape-collections==0.1.0` to `collections`, `dev`, and `all`
     extras in `packages/bluetape/pyproject.toml` without changing the default
     dependency list.
   - Add `bluetape-collections = { workspace = true }` to
     `packages/bluetape/pyproject.toml` workspace sources.
   - Run `uv sync --all-packages` after metadata edits to update the workspace
     environment and `uv.lock` before import or build smoke tests.

3. Implement the public helper surface.
   - Use Python 3.13 signatures with PEP 695 function generics,
     `collections.abc.Iterable` / `Callable`, and built-in generics such as
     `list[T]` and `dict[K, list[T]]`.
   - Process inputs in a single pass. Do not pre-materialize the full input
     iterable beyond returned containers, the current chunk, the `seen` set, or
     grouped/count outputs.
   - `chunked`
   - `chunk_by`
   - `distinct`
   - `distinct_by`
   - `group_by`
   - `count_by`
   - `partition`
   - `map_or_raise`
   - `filter_or_raise`

4. Update user-facing documentation.
   - Add `packages/bluetape-collections/README.md`.
   - README install text must distinguish source-tree/workspace availability
     from future PyPI availability. Do not imply `pip install
     bluetape-collections` or `pip install "bluetape[collections]"` works from
     PyPI until publishing is complete.
   - Package README API examples must explain `map_or_raise` and
     `filter_or_raise` as eager container-returning helpers that do not wrap
     callable exceptions, and must say when native Python comprehensions are
     clearer.
   - Package README must include an "Unsupported" section: no async helpers, no
     lazy pipeline API, no Go/Kotlin parity data structures, no unhashable
     `distinct` support except through hashable `distinct_by` keys, and no PyPI
     publication in this PR.
   - Package README must include a short sibling compatibility note mapping
     `bluetape-go/collections` concepts to Python names and naming unsupported
     sibling capabilities.
   - Update `packages/bluetape/README.md` for the optional extra.
   - Update root `README.md` and `README.ko.md` with active package state,
     installation examples, and import-backed snippets.
   - Update `docs/package-layout.md`, `WIP.md`, and `CHANGELOG.md`.
   - Run `uv run ruff format .` during implementation cleanup after edits are
     complete. Final verification uses format check only.

5. Run verification.
   - `uv sync --all-packages`
   - `uv lock --check`
   - `uv sync --all-packages --locked`
   - Confirm `uv.lock` includes `bluetape-collections`.
   - `uv run pytest packages/bluetape-collections/tests/test_collections.py`
   - `uv run pytest`
   - `uv run ruff format --check .`
   - `uv run ruff check .`
   - `uv build --all-packages`
   - Stdlib stress/allocation smoke for representative finite generators:
     `chunked`, `distinct_by`, `group_by`, `count_by`, and `partition` over at
     least 10k elements with `timeit`/`tracemalloc`, checking bounded runtime
     and no accidental full-input duplicate materialization.
   - `git diff --check`
   - Import smoke:
     `uv run python -c "from bluetape.collections import chunked; print(chunked(range(3), 2))"`
   - Meta package smoke:
     `uv run python -c "import tomllib; d=tomllib.load(open('packages/bluetape/pyproject.toml','rb')); e=d['project']['optional-dependencies']; assert d['project']['dependencies'] == ['bluetape-core==0.1.0']; assert e['collections'] == ['bluetape-collections==0.1.0']; assert 'bluetape-collections==0.1.0' in e['dev']; assert 'bluetape-collections==0.1.0' in e['all']; assert d['tool']['uv']['sources']['bluetape-collections'] == {'workspace': True}"`
   - Root package smoke:
     `test ! -f packages/bluetape/src/bluetape/__init__.py`
   - Isolated artifact smoke:
     build wheels, install the built `bluetape-collections` wheel in a
     temporary virtual environment, and verify
     `from bluetape.collections import chunked`.
   - Isolated default meta smoke:
     install the built `bluetape` wheel without extras in a temporary virtual
     environment and prove only the default `bluetape-core` dependency is
     required.
   - Documentation smoke:
     verify README.md, README.ko.md, and package README do not imply current
     PyPI availability, keep install/status wording aligned, include unsupported
     capabilities, and have examples matching the implemented `__all__`.

6. Complete workflow artifacts.
   - Add a short lesson under `docs/lessons/` because the selected workflow
     requires a durable lesson for full-feature work.
   - Run final review and verifier gates.
   - Open a PR against `develop`, assigned to `debop`, with milestone `0.2.0`,
     linked to issue #7, and ending with `## DoD Status`.
   - This PR does not create a tag, GitHub Release, or PyPI publication.
     Existing PyPI publish HOLD remains in place; `0.2.0` release work must
     re-confirm target distributions and trusted publishing separately.
   - After PR creation, check `gh pr view --json statusCheckRollup,mergeStateStatus`
     and confirm the required `test` check is green and the PR is mergeable.

## Rollback Notes

- Before merge: close/drop the PR branch or revert the PR diff. No published
  artifact exists.
- After merge but before publish: revert the PR to remove workspace member,
  workspace sources, meta extras, package directory, docs, changelog, and
  lockfile entries together.
- After publish: do not delete package history; prefer a patch release or yanked
  artifact according to the release policy.

## Test Matrix

| Area | Test evidence |
|---|---|
| Package import | Import each helper from `bluetape.collections` and assert `__all__`. |
| Chunking | `chunked` handles exact, remainder, empty, generator, and `size <= 0`. |
| Predicate split | `chunk_by` splits after the first item and rejects missing predicate. |
| Distinct | `distinct` and `distinct_by` preserve first-seen order. |
| Group/count | `group_by` and `count_by` build new containers with stable counts. |
| Partition | `partition` returns `(matches, misses)` without mutating input. |
| Error-aware transforms | `map_or_raise` and `filter_or_raise` propagate callable exceptions. |
| Failure contracts | `chunked(size <= 0)` raises `ValueError`; `None` and non-callable callable arguments raise `TypeError`; unhashable `distinct` values raise `TypeError`; unhashable `distinct_by` keys raise `TypeError`; mapper/predicate/key internal exceptions propagate without wrapping. |
| Runtime invariants | Helper implementations process input once and avoid full-input pre-materialization beyond required output/state containers. |

## Review Focus

- No default dependency drift in the `bluetape` meta distribution.
- No root `bluetape/__init__.py`.
- No third-party dependencies.
- No claims that planned future packages are already active.
- No broad parity helpers beyond issue #7.
