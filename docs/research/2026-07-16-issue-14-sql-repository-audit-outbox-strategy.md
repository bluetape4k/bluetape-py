# Issue #14 SQL, Repository, Audit, and Outbox Strategy

Issue: [#14](https://github.com/bluetape4k/bluetape-py/issues/14)
Milestone: `0.2.0`
Date: 2026-07-16

## Decision

Use three focused production boundaries instead of one SQL/audit/outbox package:

1. A future `bluetape-sql` distribution should use SQLAlchemy Core 2.x as its
   expression and result layer. It should expose separate sync and async helper
   families that accept a caller-owned `Connection` or `AsyncConnection` and
   never create, close, commit, or roll back that connection.
2. A future `bluetape-audit` distribution should be stdlib-only and
   storage-neutral. It should own immutable audit event/value contracts and
   conformance behavior, not a SQL schema, engine, repository base class,
   publisher process, or broker.
3. Durable audit delivery should use a separate PostgreSQL-first adapter. Its
   enqueue operation participates in the caller's application transaction;
   its claim/mark operations use bounded PostgreSQL transactions and
   `FOR UPDATE SKIP LOCKED`. The caller owns relay invocation, scheduling,
   cancellation, publisher clients, and shutdown.

Psycopg remains the supported PostgreSQL DB-API baseline and escape hatch. It
is not a second public toolkit. Direct asyncpg is similarly retained as the
validated SQLAlchemy async driver rather than exposed as a parallel query API.

Do not add a generic repository base class, unit-of-work container, identity
map, engine factory, implicit CRUD surface, automatic migration, hidden relay
worker, or exactly-once claim. Application repositories should remain explicit
functions or composed classes that own SQL statements and domain mapping while
receiving a transaction-bound connection.

This research decision does not authorize implementation. Each production
slice still requires a separately approved design, dependency policy, public
API, tests, packaging impact, and release evidence.

## Why SQLAlchemy Core

The first SQL surface needs one expression and result model across sync and
async applications without adopting ORM session state. SQLAlchemy Core
provides that boundary:

- `Connection` and `AsyncConnection` carry the transaction-bound execution
  capability;
- Core statements are shared across sync and async paths;
- `RowMapping` supports explicit, reviewable conversion into application
  dataclasses;
- the PostgreSQL dialect supports Psycopg and asyncpg;
- connection, engine, pool, isolation, commit, and rollback ownership can stay
  outside helper functions.

SQLAlchemy Core is not selected as an excuse for generic SQL abstraction. The
first conformance target is PostgreSQL only. Helpers may use portable Core
constructs, but the package must not claim MySQL, MariaDB, SQLite, CockroachDB,
or another backend until that backend has its own tests and semantics review.

## Candidate Matrix

| Candidate | Result | Reason |
| --- | --- | --- |
| Psycopg DB-API sync | Keep as PostgreSQL baseline and escape hatch | Small explicit transaction surface and useful diagnostic baseline, but a separate DB-API helper family would duplicate sync/async mapping and statement contracts. |
| SQLAlchemy Core sync + Psycopg | Select for the first sync toolkit | Explicit connection/transaction boundary, composable statements, mappings, and no ORM session requirement. |
| SQLAlchemy `AsyncEngine` + asyncpg | Select for the first async toolkit | Uses the same Core statement model while preserving explicit async connection ownership. |
| Direct asyncpg public helpers | Reject for the first toolkit | PostgreSQL-only placeholder, result, pool, and transaction APIs would create a second public query/mapping contract. Keep it behind SQLAlchemy's async dialect. |
| SQLAlchemy ORM or SQLModel repository base | Reject | Adds session identity, flush, relationship, and model lifecycle decisions that application repositories must own. |
| Driver-neutral protocol over DB-API/Core/asyncpg | Reject | The lowest common denominator would erase transaction and result semantics while still requiring backend-specific implementations. |

## Transaction Ownership Contract

### Application writes

The application service is the single owner of a business transaction:

```text
application transaction owner
  -> application repository write
  -> audit repository append
  -> PostgreSQL outbox enqueue
  -> commit or rollback once
```

Every nested helper receives the same transaction-bound connection. It may
execute SQL and return values or errors, but it must not commit, roll back,
close the connection, replace it with an engine, or silently open another
connection. This rule applies equally to sync and async helpers.

### Relay transactions

Outbox relay work has a different owner. A caller explicitly invokes one
bounded relay iteration. The adapter may own short claim and mark transactions
inside that invocation, but it must not own the surrounding loop, timer, task,
thread, process, broker client, or application shutdown.

The implementation issue must define claim ownership tokens, lease expiry,
retry/attempt state, stale-claim recovery, publisher failure, and mark-published
compare-and-set behavior. The spike proved distinct concurrent claims only; it
did not prove crash recovery or a production lease schema.

## Mapping And Repository Scope

The SQL package should provide narrow mapping utilities only where repeated
typed behavior is demonstrated. The default repository pattern remains an
application-owned function or class:

```python
def find_order(connection: Connection, order_id: str) -> Order | None:
    row = connection.execute(statement, {"order_id": order_id}).mappings().one_or_none()
    return None if row is None else Order(id=row["id"], status=row["status"])
```

Async code uses the matching `AsyncConnection` and an explicit `await`. Public
helpers must preserve missing-row, duplicate-row, constraint, cancellation,
and caller value behavior without turning every driver error into one generic
exception.

The first toolkit may consider typed pagination inputs, bounded result helpers,
and mapper protocols only after concrete callers prove repetition. It should
not provide model discovery, reflection-driven CRUD, dynamic repository
generation, global registries, session-local caches, or implicit retries.

## Storage-Neutral Audit Boundary

`bluetape-audit` should begin with immutable Python value contracts and remain
stdlib-only. A follow-up design should settle exact fields and serialization,
but the boundary should distinguish at least:

- stable event identity and occurrence time;
- action/type;
- subject identity and optional actor identity;
- correlation/causation metadata;
- caller-owned payload or change representation;
- explicit validation, redaction, and size policy.

The package must not read a global current user, request, logger, trace, or
database session. It must not choose a SQL schema or broker. In-memory
conformance helpers may be useful for contract tests, but they are not durable
history or an outbox.

## PostgreSQL Outbox Boundary

The durable adapter should be PostgreSQL-specific and explicit about its
delivery guarantee:

- enqueue shares the exact caller-owned application transaction;
- claim selects a bounded ordered batch;
- concurrent claimers use `FOR UPDATE SKIP LOCKED` only for queue-like rows;
- successful publish followed by a crash before durable mark can cause a
  duplicate;
- publishers and consumers therefore require idempotency by event identity;
- claim lease and attempt state must permit deterministic stale-claim recovery;
- relay execution is caller-driven and contains no hidden scheduler or worker;
- migrations, role permissions, TLS, pool sizing, retention, partitioning, and
  operational monitoring remain caller/operator-owned.

At-least-once is the honest first contract. Exactly-once publication across a
PostgreSQL transaction and an external broker is rejected because this scope
does not introduce distributed transactions or broker-specific coordination.

## PostgreSQL Testcontainers Boundary

Issue [#15](https://github.com/bluetape4k/bluetape-py/issues/15) already owns
the fixture package. Its PostgreSQL slice should wrap the official
`PostgresContainer` lifecycle and expose sanitized connection coordinates or
explicit URL renderers suitable for DB-API, SQLAlchemy sync, and SQLAlchemy
async callers.

The fixture must not create an application engine, choose pool sizes, run
migrations, begin transactions, seed domain data, enable container reuse, or
hold global singleton state. Tests that use PostgreSQL or other external
containers remain serial where shared Docker resources can conflict.

## Disposable PostgreSQL Evidence

The spike ran outside the repository from
`/tmp/bluetape-issue14-spike/spike.py`. The source and dependencies are not
committed, and `pyproject.toml`, `uv.lock`, production packages, and CI remain
unchanged.

Successful command:

```bash
uv run --no-project \
  --with 'testcontainers[postgres]' \
  --with 'psycopg[binary]' \
  --with 'sqlalchemy[asyncio]' \
  --with asyncpg \
  python /tmp/bluetape-issue14-spike/spike.py
```

Resolved environment:

| Component | Version |
| --- | --- |
| Python | `3.13.14` |
| PostgreSQL server | `18.4` from `postgres:18-alpine` |
| Testcontainers Python | `4.14.2` |
| Psycopg | `3.3.4` |
| SQLAlchemy | `2.0.51` |
| asyncpg | `0.31.0` |

Proof results:

| Proof | Result | Evidence |
| --- | --- | --- |
| Psycopg commit + explicit dataclass mapping | PASS | business/audit/outbox counts `[1, 1, 1]` |
| Psycopg forced rollback | PASS | counts `[0, 0, 0]` |
| SQLAlchemy Core sync commit + `RowMapping` to dataclass | PASS | counts `[1, 1, 1]` |
| SQLAlchemy Core sync forced rollback | PASS | counts `[0, 0, 0]` |
| SQLAlchemy Core async + asyncpg commit + mapping | PASS | counts `[1, 1, 1]` |
| SQLAlchemy Core async forced rollback | PASS | counts `[0, 0, 0]` |
| Two concurrent `SKIP LOCKED` claims | PASS | first connection claimed `claim-1`; second claimed `claim-2` while the first lock remained open |

The successful run took `5.890` seconds after dependency installation. The
first bounded run used plain `sqlalchemy` and reached the async phase without
the separately declared asyncio runtime extra. It failed there with
`ValueError`; no transaction proof was rewritten. The only retry changed the
dependency to `sqlalchemy[asyncio]`, which installs the async `greenlet`
runtime required by SQLAlchemy's official asyncio installation guidance. All
seven proofs then passed. Future async test environments must declare the
asyncio extra explicitly instead of relying on platform-dependent transitive
installation.

## What The Spike Does Not Prove

- Production throughput, latency, pool sizing, or backpressure.
- Cross-database SQL portability.
- ORM or SQLModel behavior.
- Nested transaction/savepoint policy.
- Serialization, encryption, payload size, or schema evolution.
- Claim lease expiry, stale-claim recovery, retry schedule, retention, or
  dead-letter policy.
- Broker publishing, idempotent consumers, or exactly-once delivery.
- PostgreSQL failover, commit-unknown recovery, network partition, TLS, or role
  permissions.

These limitations belong in the follow-up implementation designs and their
Testcontainers integration suites.

## Follow-Up Mapping

- [#30](https://github.com/bluetape4k/bluetape-py/issues/30) should narrow to
  the SQLAlchemy Core toolkit and application repository guidance. Remove
  outbox storage and optional encrypted-column scope from its first slice.
- [#25](https://github.com/bluetape4k/bluetape-py/issues/25) should narrow to
  the stdlib-only storage-neutral audit model and conformance contracts. Broker
  and SQL adapters should become separate follow-ups.
- [#77](https://github.com/bluetape4k/bluetape-py/issues/77) owns the focused
  PostgreSQL transactional outbox adapter, including enqueue, bounded
  claim/mark/fail operations, lease recovery, at-least-once semantics, and
  caller-driven relay behavior.
- [#15](https://github.com/bluetape4k/bluetape-py/issues/15) remains the owner
  of the PostgreSQL Testcontainers fixture required by #30 and #77.

## Rejected Alternatives

| Alternative | Reason for rejection |
| --- | --- |
| One `bluetape-data` or SQL/audit/outbox distribution | Couples storage-neutral values, query helpers, PostgreSQL schema, and delivery lifecycle. |
| Generic repository base class | Hides application query, mapping, aggregate, transaction, and error decisions behind inheritance. |
| ORM/SQLModel first | Introduces session, identity, flush, and model lifecycle before a concrete ORM consumer exists. |
| Separate DB-API and direct asyncpg public toolkits | Creates divergent sync/async statements, placeholders, mappings, and errors. |
| Storage-neutral durable outbox | Claim, locking, lease, and recovery behavior is database-specific; a generic promise would be misleading. |
| Relay-owned background worker | Hides task/process lifecycle, scheduling, cancellation, shutdown, and publisher ownership. |
| Exactly-once publication | Not supportable across PostgreSQL and an external publisher without a broader distributed coordination contract. |
| Committed spike harness | Would create a dependency, CI, and maintenance surface before production design approval. |

## Sources

Official Python and database sources:

- [PEP 249 - Python Database API Specification v2.0](https://peps.python.org/pep-0249/)
- [Psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [Psycopg row factories](https://www.psycopg.org/psycopg3/docs/api/rows.html)
- [SQLAlchemy Core connections and transactions](https://docs.sqlalchemy.org/en/20/core/connections.html)
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy PostgreSQL dialects](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [asyncpg transactions](https://magicstack.github.io/asyncpg/current/usage.html#transactions)
- [PostgreSQL `SELECT` and `SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html)
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [Testcontainers Python PostgreSQL](https://testcontainers-python.readthedocs.io/en/latest/modules/postgres/README.html)

Repository and sibling evidence:

- `WIP.md`
- `docs/package-layout.md`
- `packages/bluetape-testcontainers/`
- `bluetape-go/docs/research/2026-06-25-issue-41-audit-scope.md`
- `bluetape-go/docs/research/2026-06-26-issue-100-sql-repository-scope.md`
- `bluetape-go/docs/research/2026-06-27-issue-58-audit-outbox-design.md`
- `bluetape-go/docs/superpowers/specs/2026-06-28-issue-346-sql-audit-outbox-spec.md`
- `bluetape-go/docs/lessons/2026-06-28-issue-346-sql-audit-outbox.md`

## Version And Retrieval Notes

- Official sources and live GitHub issues were retrieved on 2026-07-16 KST.
- SQLAlchemy official documentation identified `2.0.51` as the current 2.0
  release; the disposable environment independently resolved the same version.
- Package versions above are the exact `uv run --no-project` environment, not
  new workspace constraints.
- PostgreSQL `SKIP LOCKED` is used only for queue-like claim work and not as a
  general consistent read mechanism.
- No external images were required.
