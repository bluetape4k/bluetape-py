# Issue #14 SQL, Repository, Audit, and Outbox Research Lessons

## Context And Decision

Issue #14 had to choose a Python-native SQL layer and divide repository, audit,
and outbox ownership before implementation. Official documentation alone was
not enough to prove that one caller-owned transaction could carry business,
audit, and outbox writes through DB-API, SQLAlchemy sync, and SQLAlchemy async
paths. A disposable PostgreSQL Testcontainers spike provided that evidence
without adding workspace dependencies or production code.

The final boundary uses SQLAlchemy Core for a future shared sync/async SQL
toolkit, keeps audit values stdlib-only and storage-neutral, and assigns
PostgreSQL claim/relay semantics to a separate adapter.

## Reusable Findings

### Async extras are part of the executable dependency contract

Installing plain `sqlalchemy` was enough to import and construct the async
surface in the disposable environment, but the first run failed when async
execution began because the declared asyncio runtime extra was absent. The
single retry changed only the dependency to `sqlalchemy[asyncio]`; all seven
semantic proofs then passed.

Async integration tests and package extras must name the upstream asyncio
extra explicitly. A successful import, type check, or engine construction is
not proof that the runtime bridge dependency is installed on every platform.
Do not rely on a transitive or platform-dependent `greenlet` installation.

### Prove transaction ownership with both positive and negative state

A commit assertion alone can pass even when a nested helper opens a different
connection or commits too early. The useful proof writes one unique business,
audit, and outbox row and verifies counts `[1, 1, 1]`, then repeats with a forced
exception and verifies `[0, 0, 0]`.

This paired proof should be reused by every sync and async repository/outbox
implementation. Helpers receive the same transaction-bound connection and do
not own commit or rollback. The transaction owner is the only layer allowed to
end the unit of work.

### A locking proof is narrower than a relay proof

Holding the first PostgreSQL row lock while a second connection selected the
next row proved that `FOR UPDATE SKIP LOCKED` can produce distinct concurrent
queue claims. It did not prove claim tokens, lease expiry, stale recovery,
publisher failure, mark-published compare-and-set, retention, or crash
reconciliation.

Record the narrow proof honestly. A follow-up outbox design still needs a
lease/ownership state machine and failure tests. `SKIP LOCKED` is unsuitable as
a general consistent-read abstraction because PostgreSQL explicitly permits an
inconsistent view for skipped rows.

### Disposable spikes need durable evidence, not durable source

The spike stayed under `/tmp`, dependencies came from `uv run --no-project
--with`, and only versions, commands, bounded proof booleans, identifiers,
counts, duration, failure category, and limitations entered the repository.
This preserved reviewable evidence without creating a package, lockfile, CI,
or maintenance surface.

A disposable research harness should fail closed on semantic assertions, hide
credentials and connection URLs, and allow only a predeclared environmental
retry. When the outcome is sufficient to choose a boundary, deleteability is a
feature: production implementation must return to an approved design rather
than promote exploratory code.

## Verification Evidence

- PostgreSQL `18.4` via `postgres:18-alpine` and Testcontainers Python `4.14.2`.
- Psycopg `3.3.4`, SQLAlchemy `2.0.51`, asyncpg `0.31.0`, Python `3.13.14`.
- Sync DB-API, SQLAlchemy sync, and SQLAlchemy async commit counts:
  `[1, 1, 1]` each.
- Forced rollback counts: `[0, 0, 0]` each.
- Concurrent queue claim: `claim-1` and `claim-2` selected by separate
  transactions while the first lock remained open.
- Workspace `pyproject.toml`, `uv.lock`, packages, and workflows were not
  changed by the spike.

## Future Guard

Future SQL/outbox changes must declare async runtime extras explicitly, test
commit and forced rollback through the exact borrowed connection, distinguish
queue locking from lease/recovery correctness, and keep disposable research
source out of production packages. Any helper that creates a hidden
connection, commits nested work, owns a relay loop, or claims exactly-once
delivery violates this research boundary and requires a new approved design.
