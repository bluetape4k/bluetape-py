# Issue #7 Collections Package Design

Date: 2026-07-10 KST
Target issue: #7 - `feat: add bluetape-collections helper package`
Target milestone: `0.2.0`

## Problem

`bluetape-py` has a released `v0.1.0` foundation with focused `core`,
`logging`, and `testing` packages. The first `0.2.0` implementation issue adds
a Python-native collections package inspired by `bluetape-go/collections` and
bluetape4k collection helpers.

The package must improve common backend collection transformations without
becoming a catch-all utility namespace or a mechanical port of Go/Kotlin APIs.

## Current Evidence

- Issue #7 asks for focused iterable/list/dict helpers for chunking, grouping,
  distinct, partitioning, and error-aware transforms.
- `docs/package-layout.md` requires every new distribution to have a clear
  domain boundary, README, tests, explicit dependency impact, and root README /
  WIP visibility.
- Repo `AGENTS.md` requires Python 3.13+, a thin default `bluetape` meta
  distribution, package README updates, root README locale parity, and
  `CHANGELOG.md` for completed user-facing changes.
- `bluetape-go/collections` provides `Chunk`, `ChunkBy`, `Distinct`,
  `DistinctBy`, `GroupBy`, `CountBy`, `MapErr`, `FilterErr`, and related
  helpers.
- `bluetape-go` lesson `2026-07-03-issue-360-collections-helper-scope.md`
  warns against broad collection parity and favors narrow helpers over standard
  library wrappers.

## Goals

1. Add `bluetape-collections` as a stdlib-only public distribution.
2. Expose focused helpers under import path `bluetape.collections`.
3. Preserve caller-owned containers: helpers must return new containers and
   must not mutate input lists, mappings, or other mutable containers. Single
   pass iterators and generators are consumed by design.
4. Use Python-native names and contracts:
   `chunked`, `chunk_by`, `distinct`, `distinct_by`, `group_by`, `count_by`,
   `partition`, `map_or_raise`, and `filter_or_raise`.
5. Keep the default `bluetape` install thin. The meta distribution may expose a
   `collections` optional extra, but default dependencies must remain
   `bluetape-core` only.
6. Cover success, empty/boundary input, invalid input, import behavior, and
   caller-owned mutation preservation with pytest.
7. Update package docs, root README locale files, `WIP.md`, and
   `CHANGELOG.md`.

## Non-Goals

- No async collection helpers in this issue. Async belongs to issue #8.
- No bounded stack, ring buffer, pagination, permutations, synchronized
  containers, sequence DSL, Java/Kotlin parity surface, or primitive-array
  adapters.
- No third-party dependencies.
- No root `bluetape/__init__.py` import surface.
- No PyPI publication in this issue.

## API Design

Package:

- Distribution: `bluetape-collections`
- Import path: `bluetape.collections`
- Package version: `0.1.0`, aligned with existing workspace packages until the
  next repository release policy changes it. This is distinct from the target
  GitHub milestone `0.2.0`.
- Dependencies: none.

Public helpers:

| Helper | Contract |
|---|---|
| `chunked(iterable, size)` | Return `list[list[T]]` of fixed-size chunks; reject `size <= 0`. |
| `chunk_by(iterable, starts_new)` | Split whenever `starts_new(value)` is true after the first item; reject `None` predicate. |
| `distinct(iterable)` | Preserve first-seen order using equality for hashable values. |
| `distinct_by(iterable, key)` | Preserve first item per derived key; reject `None` key. |
| `group_by(iterable, key)` | Return `dict[K, list[T]]`; reject `None` key. |
| `count_by(iterable, key)` | Return `dict[K, int]`; reject `None` key. |
| `partition(iterable, predicate)` | Return `(matches, misses)` lists; reject `None` predicate. |
| `map_or_raise(iterable, mapper)` | Map eagerly and let mapper exceptions remain caller-visible; reject `None` mapper. |
| `filter_or_raise(iterable, predicate)` | Filter eagerly and let predicate exceptions remain caller-visible; reject `None` predicate. |

All helpers eagerly consume the input iterable and return concrete containers.
This keeps behavior predictable for tests, logging, and repeated inspection in
backend code.

## Approach Options

### Option A - Eager List/Dict Helpers

Create small eager helpers that accept any `Iterable` and return concrete lists,
dicts, or tuple-of-lists. This mirrors common Python expectations and keeps
error handling simple.

Pros:

- Easy to test and document.
- Clear caller ownership and mutation behavior.
- Good fit for backend request/task utility code.
- No dependency or iterator lifecycle surprises.

Cons:

- Large iterables are materialized.

Decision: choose Option A for issue #7.

### Option B - Lazy Iterator Pipeline

Return iterators/generators for every transformation.

Pros:

- Lower memory for large streams.

Cons:

- Harder to explain failure timing.
- More likely to surprise callers when exceptions surface later.
- Overlaps with Python's generator expressions and `itertools`.

Decision: reject for the first package. Reconsider only when a concrete
streaming use case exists.

### Option C - Broad Go/Kotlin Parity Package

Port most `bluetape-go/collections` and bluetape4k collection helpers.

Pros:

- Maximizes sibling feature count.

Cons:

- Violates Python-native package discipline.
- Pulls in data structures and helper families without proven Python demand.
- Increases review and documentation surface before issue #7 needs it.

Decision: reject. Use issues #8+ and future scoped issues for separate helper
families.

## Risks And Failure Modes

1. **Unhashable inputs in `distinct`**
   - Python equality-based distinct usually needs hashable keys for a compact
     implementation.
   - Decision: document and allow `TypeError` from Python set membership for
     unhashable values. Callers can use `distinct_by` with a hashable key.

2. **Unexpected input mutation**
   - Helpers must not sort, pop, append to, or otherwise mutate input
     containers.
   - Tests must assert original caller-owned lists remain unchanged.
   - Tests may use generators, but generator consumption is expected for eager
     helpers and must not be described as mutation.

3. **Too-broad utility surface**
   - The package can become a generic utility sink.
   - Keep the first release to nine helpers and record non-goals in README.

4. **Meta package dependency drift**
   - Adding `bluetape-collections` as a default dependency would violate the
     thin default install rule.
   - Add it only as an optional extra in `packages/bluetape/pyproject.toml`.

5. **Docs claiming planned packages as active**
   - Root README distribution table must distinguish active
     `bluetape-collections` from still-planned packages.
   - Package snippets must be import-backed by tests.

## Acceptance Criteria

- `packages/bluetape-collections/pyproject.toml` registers a stdlib-only
  distribution with module name `bluetape.collections`.
- Root `pyproject.toml` includes the package in workspace members and
  workspace sources.
- `packages/bluetape/pyproject.toml` exposes `collections` and includes it in
  `dev` / `all` extras without changing the default dependency list.
- `packages/bluetape/pyproject.toml` includes
  `bluetape-collections = { workspace = true }` under `[tool.uv.sources]` so
  the optional extra resolves to the local workspace package during
  development.
- Public helpers are exported from `bluetape.collections.__all__`.
- TDD red evidence is captured before implementation by running the new
  collections pytest target while the production module is absent.
- Pytest covers success, empty/boundary input, invalid input, exception
  propagation, caller-owned mutation preservation, and package import behavior.
- `uv build --all-packages`, `uv run pytest`, `uv run ruff check .`,
  `uv run ruff format --check .`, and `git diff --check` pass.
- An isolated metadata/default-install smoke check proves the `bluetape` meta
  distribution still depends only on `bluetape-core` by default and does not
  publish a root `bluetape/__init__.py` package.
- `README.md`, `README.ko.md`, package README, `WIP.md`, and `CHANGELOG.md`
  describe the same user-facing package state.

## Open Questions

None. The user approved the narrow first package direction and Python 3.13+
policy, and issue #7 supplies the initial helper family.
