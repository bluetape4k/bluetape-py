# Issue #14 SQL, Repository, Audit, and Outbox Research Review

Date: 2026-07-16 KST
Branch: `research/issue-14-sql-audit-outbox`
Base: `develop` at `07f1f050f744651706d59fa398fee4f2811a8478`
Work type: Type E - research and documentation

## Scope Review

The branch contains research design/plan authority, the final decision note,
research index parity, roadmap/package-boundary updates, and a durable lesson.
The executable spike remained outside the repository. No production package,
public import, dependency, lockfile, workflow, release, tag, or publish surface
is included.

External outcomes:

- #25 narrowed to `bluetape-audit` storage-neutral contracts.
- #30 narrowed to SQLAlchemy Core sync/async helpers.
- #77 created for the PostgreSQL transactional audit outbox.
- #15 remains the PostgreSQL Testcontainers fixture owner.
- The source summary is preserved in `bluetape4k-wiki` at exact pushed head
  `d49a683155ac391ede2e3aa81f72f93cd9007834`.

## Evidence Review

| Claim | Source | Verdict |
| --- | --- | --- |
| DB-API uses explicit commit/rollback | PEP 249 and Psycopg official transaction docs | PASS |
| SQLAlchemy Core exposes explicit sync connection/transaction ownership | SQLAlchemy 2.0 Core docs | PASS |
| SQLAlchemy shares Core statements with async connections | SQLAlchemy 2.0 asyncio and PostgreSQL dialect docs | PASS |
| asyncpg provides an explicit async transaction API | asyncpg official usage/API docs | PASS |
| `SKIP LOCKED` is queue-oriented and inconsistent for general reads | PostgreSQL current `SELECT` docs | PASS |
| PostgreSQL Testcontainers is an upstream-supported Python module | Testcontainers Python official docs/source | PASS |
| Caller-owned transaction and rollback work in all three candidates | Disposable PostgreSQL 18.4 bounded spike output | PASS |
| Existing issues can be split without duplicate implementation lanes | Live #15, #25, #30 search and verified #77 creation | PASS |

## Spike Review

- First run: `FAIL`, phase `sqlalchemy-async`, category `ValueError`; plain
  `sqlalchemy` omitted the declared asyncio runtime extra.
- Allowed dependency-environment retry: changed only to
  `sqlalchemy[asyncio]`; no schema, statement, assertion, or expected result
  changed.
- Final run: seven proofs PASS.
- Commit counts for Psycopg, SQLAlchemy sync, SQLAlchemy async:
  `[1, 1, 1]` each.
- Forced rollback counts: `[0, 0, 0]` each.
- Concurrent claims: `claim-1`, `claim-2`.
- No credentials, URL, raw logs, or spike source were committed.

## P0/P1 Review

Initial review found two P1 documentation consistency defects:

1. The execution plan named plain `sqlalchemy` even though the async proof
   requires SQLAlchemy's declared asyncio extra. The command now uses
   `sqlalchemy[asyncio]` and records the single retry without widening semantic
   acceptance.
2. `WIP.md` still listed #14 as a pending `0.3.0` research decision. It now
   lists #14 with #10/#23 as completed research authority.

After repair:

- P0: `0`
- P1: `0`
- P2: `0`

## Boundary Review

- Production packages and public API: N/A; research-only branch.
- Workspace dependencies and `uv.lock`: unchanged.
- README locale pair: N/A; no current user-facing package/install behavior
  changed.
- Research index locale pair: PASS; English and Korean point to the same note.
- Diagram: N/A. The transaction ownership sequence and package split are clear
  in text/table form; no measured data or complex topology requires a visual.
- Release/publish: N/A and unauthorized.

## Lesson Gate

PASS through committed lesson
`docs/lessons/2026-07-16-issue-14-sql-repository-audit-outbox.md`.
The async-extra failure, paired commit/rollback proof, narrow `SKIP LOCKED`
interpretation, and disposable-spike evidence rules are reusable design and
operational guidance.

## Verification

- `git diff --check`: PASS
- `uv run ruff check .`: PASS, `All checks passed!`
- `uv run ruff format --check .`: PASS, `165 files already formatted`
- `uv run pytest packages/bluetape/tests/test_value_readmes.py -q`: PASS,
  `2 passed in 0.18s`
- Changed-path exclusion check: PASS; no `pyproject.toml`, `uv.lock`,
  `packages/`, or `.github/workflows/` path changed.
- Wiki preservation: PASS; `gno update`, `gno embed --collection
  bluetape4k-wiki` (`3/3` chunks), and representative searches returned the
  new note. Local/upstream wiki head both equal
  `d49a683155ac391ede2e3aa81f72f93cd9007834`.
- Live GitHub metadata: PASS; #25, #30, and #77 are OPEN, assigned to `debop`,
  labeled `enhancement`, and attached to milestone `0.2.0`; #25 and #30 link
  #77.

The remaining pre-PR steps are the final scoped diff review, converged commit,
exact local/remote head publication, and live PR verification.
