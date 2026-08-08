# Issue #14 SQL, Repository, Audit, Outbox 전략

Issue: [#14](https://github.com/bluetape4k/bluetape-py/issues/14)
Milestone: `0.2.0`
Date: 2026-07-16

## 결정

하나의 SQL/audit/outbox package 대신 세 가지 focused production boundary를 사용합니다.

1. 향후 `bluetape-sql` distribution은 SQLAlchemy Core 2.x를 expression/result layer로 사용합니다. Caller-owned `Connection` 또는 `AsyncConnection`을 받는 sync/async helper family를 분리하여 노출하고 connection을 생성, close, commit, rollback하지 않습니다.
2. 향후 `bluetape-audit` distribution은 표준 라이브러리 전용 storage-neutral package입니다. Immutable audit event/value contract와 conformance behavior를 소유하되 SQL schema, engine, repository base class, publisher process, broker는 소유하지 않습니다.
3. Durable audit delivery는 별도의 PostgreSQL-first adapter를 사용합니다. Enqueue는 caller의 application transaction에 참여하고 claim/mark는 bounded PostgreSQL transaction과 `FOR UPDATE SKIP LOCKED`를 사용합니다. Relay invocation, scheduling, cancellation, publisher client, shutdown은 caller가 소유합니다.

Psycopg는 지원하는 PostgreSQL DB-API baseline이자 escape hatch이며 두 번째 public toolkit이 아닙니다. Direct asyncpg도 parallel query API로 노출하지 않고 검증된 SQLAlchemy async driver로 유지합니다.

Generic repository base class, unit-of-work container, identity map, engine factory, implicit CRUD surface, automatic migration, hidden relay worker, exactly-once claim을 추가하지 않습니다. Application repository는 transaction-bound connection을 받으면서 SQL statement와 domain mapping을 소유하는 명시적 function 또는 composed class로 유지합니다.

이 research decision은 implementation을 승인하지 않습니다. 각 production slice에는 별도의 승인된 design, dependency policy, public API, test, packaging impact, release evidence가 필요합니다.

## SQLAlchemy Core를 선택한 이유

첫 SQL surface는 ORM session state 없이 sync/async application에서 하나의 expression/result model이 필요합니다. SQLAlchemy Core가 이 경계를 제공합니다.

- `Connection`과 `AsyncConnection`은 transaction-bound execution capability를 전달합니다.
- Core statement는 sync/async path에서 공유할 수 있습니다.
- `RowMapping`은 application dataclass로 명시적이고 검토 가능한 변환을 지원합니다.
- PostgreSQL dialect는 Psycopg와 asyncpg를 지원합니다.
- Connection, engine, pool, isolation, commit, rollback ownership은 helper function 밖에 둘 수 있습니다.

SQLAlchemy Core를 generic SQL abstraction의 구실로 선택한 것은 아닙니다. 첫 conformance target은 PostgreSQL뿐입니다. Helper는 portable Core construct를 사용할 수 있지만 MySQL, MariaDB, SQLite, CockroachDB 또는 다른 backend는 자체 test와 semantics review가 생길 때까지 지원한다고 주장하지 않습니다.

## Candidate matrix

| Candidate | 결과 | 이유 |
|---|---|---|
| Psycopg DB-API sync | PostgreSQL baseline 및 escape hatch로 유지 | 작고 명시적인 transaction surface와 진단 기준을 제공하지만 별도 DB-API helper family는 sync/async mapping과 statement contract를 중복합니다. |
| SQLAlchemy Core sync + Psycopg | 첫 sync toolkit으로 선택 | 명시적 connection/transaction boundary, 조합 가능한 statement와 mapping, ORM session 불필요. |
| SQLAlchemy `AsyncEngine` + asyncpg | 첫 async toolkit으로 선택 | 동일한 Core statement model을 사용하면서 명시적인 async connection ownership을 유지합니다. |
| Direct asyncpg public helper | 첫 toolkit에서는 거부 | PostgreSQL 전용 placeholder, result, pool, transaction API가 두 번째 public query/mapping contract를 만듭니다. SQLAlchemy async dialect 뒤에 둡니다. |
| SQLAlchemy ORM 또는 SQLModel repository base | 거부 | Application repository가 소유해야 하는 session identity, flush, relationship, model lifecycle 결정을 추가합니다. |
| DB-API/Core/asyncpg 위의 driver-neutral protocol | 거부 | Lowest common denominator가 transaction/result semantics를 지우면서도 backend-specific implementation을 요구합니다. |

## Transaction ownership contract

### Application write

Application service가 business transaction의 단일 owner입니다.

```text
application transaction owner
  -> application repository write
  -> audit repository append
  -> PostgreSQL outbox enqueue
  -> commit or rollback once
```

모든 nested helper는 같은 transaction-bound connection을 받습니다. SQL을 실행하고 value/error를 반환할 수 있지만 commit, rollback, close, engine 교체, 묵시적인 다른 connection open을 해서는 안 됩니다. 이 규칙은 sync/async helper에 동일합니다.

### Relay transaction

Outbox relay work에는 다른 owner가 있습니다. Caller가 하나의 bounded relay iteration을 명시적으로 호출합니다. Adapter는 그 호출 안에서 짧은 claim/mark transaction을 소유할 수 있지만 surrounding loop, timer, task, thread, process, broker client, application shutdown은 소유하지 않습니다.

Implementation issue는 claim ownership token, lease expiry, retry/attempt state, stale-claim recovery, publisher failure, mark-published compare-and-set behavior를 정의해야 합니다. Spike는 서로 다른 concurrent claim만 입증했고 crash recovery나 production lease schema는 입증하지 않았습니다.

## Mapping과 repository 범위

SQL package는 반복되는 typed behavior가 입증된 경우에만 좁은 mapping utility를 제공합니다. 기본 repository pattern은 application-owned function 또는 class입니다.

```python
def find_order(connection: Connection, order_id: str) -> Order | None:
    row = connection.execute(statement, {"order_id": order_id}).mappings().one_or_none()
    return None if row is None else Order(id=row["id"], status=row["status"])
```

Async code는 대응하는 `AsyncConnection`과 명시적인 `await`를 사용합니다. Public helper는 모든 driver error를 하나의 generic exception으로 바꾸지 않고 missing-row, duplicate-row, constraint, cancellation, caller value behavior를 보존해야 합니다.

Concrete caller가 반복을 입증한 뒤에만 typed pagination input, bounded result helper, mapper protocol을 고려할 수 있습니다. Model discovery, reflection-driven CRUD, dynamic repository generation, global registry, session-local cache, implicit retry는 제공하지 않습니다.

## Storage-neutral audit 경계

`bluetape-audit`는 immutable Python value contract로 시작하고 표준 라이브러리 전용으로 유지합니다. 후속 design이 정확한 field와 serialization을 정하되 최소한 다음을 구분해야 합니다.

- stable event identity와 occurrence time;
- action/type;
- subject identity와 optional actor identity;
- correlation/causation metadata;
- caller-owned payload 또는 change representation;
- 명시적 validation, redaction, size policy.

Package가 global current user, request, logger, trace, database session을 읽어서는 안 됩니다. SQL schema나 broker를 선택하지 않습니다. In-memory conformance helper는 contract test에 유용할 수 있지만 durable history나 outbox가 아닙니다.

## PostgreSQL outbox 경계

Durable adapter는 PostgreSQL-specific이어야 하며 delivery guarantee를 명시해야 합니다.

- enqueue는 정확히 caller-owned application transaction을 공유합니다.
- claim은 bounded ordered batch를 선택합니다.
- Concurrent claimer는 queue-like row에만 `FOR UPDATE SKIP LOCKED`를 사용합니다.
- Publish 성공 후 durable mark 전에 crash하면 duplicate가 발생할 수 있습니다.
- 따라서 publisher와 consumer는 event identity로 idempotency를 보장해야 합니다.
- Claim lease와 attempt state는 deterministic stale-claim recovery를 허용해야 합니다.
- Relay execution은 caller-driven이며 hidden scheduler나 worker가 없습니다.
- Migration, role permission, TLS, pool sizing, retention, partitioning, operational monitoring은 caller/operator가 소유합니다.

At-least-once가 첫 contract로 정직합니다. 이 scope에는 distributed transaction이나 broker-specific coordination이 없으므로 PostgreSQL transaction과 external broker 사이의 exactly-once publication은 거부합니다.

## PostgreSQL Testcontainers 경계

Issue [#15](https://github.com/bluetape4k/bluetape-py/issues/15)가 fixture package를 이미 소유합니다. PostgreSQL slice는 공식 `PostgresContainer` lifecycle을 감싸고 DB-API, SQLAlchemy sync, SQLAlchemy async caller가 사용할 sanitized connection coordinate 또는 명시적 URL renderer를 노출해야 합니다.

Fixture는 application engine을 만들거나 pool size를 선택하거나 migration, transaction, domain seed, container reuse를 실행하거나 global singleton state를 보유하지 않습니다. PostgreSQL 또는 다른 external container를 사용하는 test는 공유 Docker resource가 충돌할 수 있는 경우 serial로 실행합니다.

## Disposable PostgreSQL 근거

Spike는 repository 밖 `/tmp/bluetape-issue14-spike/spike.py`에서 실행했습니다. Source와 dependency는 commit하지 않았으며 `pyproject.toml`, `uv.lock`, production package, CI는 바뀌지 않았습니다.

성공한 command:

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
|---|---|
| Python | `3.13.14` |
| PostgreSQL server | `18.4` from `postgres:18-alpine` |
| Testcontainers Python | `4.14.2` |
| Psycopg | `3.3.4` |
| SQLAlchemy | `2.0.51` |
| asyncpg | `0.31.0` |

Proof result:

| Proof | Result | Evidence |
|---|---|---|
| Psycopg commit + explicit dataclass mapping | PASS | business/audit/outbox count `[1, 1, 1]` |
| Psycopg forced rollback | PASS | count `[0, 0, 0]` |
| SQLAlchemy Core sync commit + `RowMapping` to dataclass | PASS | count `[1, 1, 1]` |
| SQLAlchemy Core sync forced rollback | PASS | count `[0, 0, 0]` |
| SQLAlchemy Core async + asyncpg commit + mapping | PASS | count `[1, 1, 1]` |
| SQLAlchemy Core async forced rollback | PASS | count `[0, 0, 0]` |
| Two concurrent `SKIP LOCKED` claim | PASS | 첫 connection은 lock을 열어 둔 채 `claim-1`, 둘째는 `claim-2`를 claim |

Dependency installation 후 성공 run은 `5.890`초가 걸렸습니다. 첫 bounded run은 plain `sqlalchemy`를 사용하여 별도로 선언한 asyncio runtime extra 없이 async phase에 도달했고 `ValueError`로 실패했습니다. Transaction proof는 다시 쓰지 않았습니다. 유일한 retry는 dependency를 `sqlalchemy[asyncio]`로 바꾸었고, 이는 SQLAlchemy 공식 asyncio installation guidance가 요구하는 async `greenlet` runtime을 설치합니다. 이후 일곱 proof가 모두 통과했습니다. 향후 async test environment는 platform-dependent transitive installation에 기대지 말고 asyncio extra를 명시해야 합니다.

## Spike가 입증하지 않은 항목

- Production throughput, latency, pool sizing, backpressure.
- Cross-database SQL portability.
- ORM 또는 SQLModel behavior.
- Nested transaction/savepoint policy.
- Serialization, encryption, payload size, schema evolution.
- Claim lease expiry, stale-claim recovery, retry schedule, retention, dead-letter policy.
- Broker publishing, idempotent consumer, exactly-once delivery.
- PostgreSQL failover, commit-unknown recovery, network partition, TLS, role permission.

이 제한은 후속 implementation design과 Testcontainers integration suite에 기록해야 합니다.

## 후속 mapping

- [#30](https://github.com/bluetape4k/bluetape-py/issues/30)은 SQLAlchemy Core toolkit과 application repository guidance로 좁힙니다. Outbox storage와 optional encrypted-column scope는 첫 slice에서 제거합니다.
- [#25](https://github.com/bluetape4k/bluetape-py/issues/25)은 표준 라이브러리 전용 storage-neutral audit model과 conformance contract로 좁힙니다. Broker와 SQL adapter는 별도 follow-up이 됩니다.
- [#77](https://github.com/bluetape4k/bluetape-py/issues/77)은 enqueue, bounded claim/mark/fail operation, lease recovery, at-least-once semantics, caller-driven relay behavior를 포함한 focused PostgreSQL transactional outbox adapter를 소유합니다.
- [#15](https://github.com/bluetape4k/bluetape-py/issues/15)은 #30과 #77에 필요한 PostgreSQL Testcontainers fixture owner로 남습니다.

## 거부한 대안

| Alternative | 거부 이유 |
|---|---|
| 하나의 `bluetape-data` 또는 SQL/audit/outbox distribution | Storage-neutral value, query helper, PostgreSQL schema, delivery lifecycle을 결합합니다. |
| Generic repository base class | Application query, mapping, aggregate, transaction, error 결정을 inheritance 뒤에 숨깁니다. |
| ORM/SQLModel first | Concrete ORM consumer 전에 session, identity, flush, model lifecycle을 도입합니다. |
| Separate DB-API와 direct asyncpg public toolkit | Divergent sync/async statement, placeholder, mapping, error를 만듭니다. |
| Storage-neutral durable outbox | Claim, lock, lease, recovery behavior는 database-specific이므로 generic promise가 오해를 만듭니다. |
| Relay-owned background worker | Task/process lifecycle, scheduling, cancellation, shutdown, publisher ownership을 숨깁니다. |
| Exactly-once publication | 더 넓은 distributed coordination contract 없이 PostgreSQL과 external publisher 사이에서 지원할 수 없습니다. |
| Committed spike harness | Production design 승인 전에 dependency, CI, maintenance surface를 만듭니다. |

## Source

공식 Python 및 database source:

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

Repository 및 sibling 근거:

- `WIP.md`
- `docs/package-layout.md`
- `packages/bluetape-testcontainers/`
- `bluetape-go/docs/research/2026-06-25-issue-41-audit-scope.md`
- `bluetape-go/docs/research/2026-06-26-issue-100-sql-repository-scope.md`
- `bluetape-go/docs/research/2026-06-27-issue-58-audit-outbox-design.md`
- `bluetape-go/docs/superpowers/specs/2026-06-28-issue-346-sql-audit-outbox-spec.md`
- `bluetape-go/docs/lessons/2026-06-28-issue-346-sql-audit-outbox.md`

## Version과 retrieval note

- 공식 source와 live GitHub issue를 2026-07-16 KST에 가져왔습니다.
- SQLAlchemy 공식 documentation은 `2.0.51`을 current 2.0 release로 식별했으며 disposable environment에서도 같은 version을 resolve했습니다.
- 위 package version은 정확한 `uv run --no-project` environment이며 새로운 workspace constraint가 아닙니다.
- PostgreSQL `SKIP LOCKED`는 queue-like claim work에만 사용하고 general consistent read mechanism으로 사용하지 않습니다.
- 외부 image는 필요하지 않았습니다.
