# Issue #14 SQL, Repository, Audit, and Outbox Research Design

Date: 2026-07-16 KST
Target issue: #14 - `research: evaluate SQL, repository, and audit outbox strategy`
Target milestone: `0.2.0`
Work type: Type E - research and documentation

## Problem

`bluetape-py`에는 SQL 실행, repository helper, audit model, transactional outbox의
Python-native 경계가 아직 없다. 이 네 영역을 하나의 추상화로 먼저 묶으면 connection,
transaction, mapping, schema, relay lifecycle의 소유권이 library로 이동하고 특정 ORM이나
driver의 의미를 숨길 위험이 있다. 반대로 문서 비교만으로 결정하면 sync/async transaction
공유, rollback 원자성, PostgreSQL relay claim이 실제 public API로 가능한지 확인할 수 없다.

이 연구는 구현 전에 가장 작은 실행 증거를 만든다. 공식 문서와 sibling repository를
검토하고, repository에 남지 않는 disposable PostgreSQL Testcontainers spike로 후보 경계를
검증한 뒤, production package를 서로 독립적인 후속 이슈로 나눈다.

## Approved Scope

사용자는 다음 범위를 승인했다.

1. Type E research/maintenance로 수행하고 production package, public API, workspace
   dependency, `uv.lock`은 변경하지 않는다.
2. 공식 자료와 sibling evidence를 검토한다.
3. 임시 디렉터리에서 PostgreSQL Testcontainers를 한 번 실행해 다음 후보를 비교한다.
   - Psycopg DB-API sync
   - SQLAlchemy Core sync with Psycopg
   - SQLAlchemy `AsyncEngine` with asyncpg
4. 같은 PostgreSQL instance에서 caller-owned transaction, business + audit + outbox atomic
   write, forced rollback, explicit dataclass row mapping, `FOR UPDATE SKIP LOCKED` claim을
   검증한다.
5. spike source와 dependency는 commit하지 않는다. 명령, resolved version, 관찰 결과,
   한계만 durable research artifact에 남긴다.
6. SQL toolkit/repository, storage-neutral audit model, PostgreSQL transactional outbox를
   독립적인 후속 GitHub issue로 만든다. 기존 issue와 중복되면 새 issue 대신 기존 issue를
   좁히거나 연결하고 그 근거를 기록한다.
7. target repository는 `bluetape4k/bluetape-py`, base는 `develop`, head는
   `research/issue-14-sql-audit-outbox`이다. PR 생성은 승인 범위에 포함되지만 merge는 별도
   fresh approval이 필요하다.

## Current Evidence

### Repository

- `WIP.md`는 #14가 SQL/transaction ownership, repository scope, audit boundary, outbox
  storage, Testcontainers fixture를 결정해야 한다고 규정한다.
- `docs/package-layout.md`는 실제 backend 문제를 해결하는 SQL transaction/outbox handoff
  example을 요구한다.
- `bluetape-testcontainers`는 현재 Redis wrapper만 제공한다. PostgreSQL fixture는 아직
  production contract가 아니다.
- workspace에는 SQLAlchemy, Psycopg, asyncpg dependency가 없다. 따라서 spike dependency는
  `uv run --with ...`로만 공급하고 workspace metadata와 lock을 보존해야 한다.
- #25와 #30은 이미 audit/outbox 및 SQL/repository 구현 후보를 담지만 책임이 겹친다. 연구
  결과는 이 두 issue를 그대로 구현하기보다 세 경계로 재조정해야 한다.

### Official Sources

- [PEP 249](https://peps.python.org/pep-0249/)는 DB-API connection의 명시적
  `commit()`/`rollback()` 계약을 정의한다.
- [Psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)는
  기본적으로 database operation이 transaction을 시작하며 connection context가 commit 또는
  rollback을 결정한다고 설명한다.
- [SQLAlchemy Core transactions](https://docs.sqlalchemy.org/en/20/core/connections.html#using-transactions)는
  `Connection`과 `Transaction`을 명시적인 sync transaction 경계로 제공한다.
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)는
  `AsyncEngine.begin()`과 `AsyncConnection`을 같은 Core model의 async 경계로 제공한다.
- [SQLAlchemy PostgreSQL dialects](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)는
  Psycopg sync/async와 asyncpg dialect를 지원한다.
- [asyncpg transactions](https://magicstack.github.io/asyncpg/current/usage.html#transactions)는
  `Connection.transaction()`의 explicit async context를 제공한다.
- [PostgreSQL `SELECT`](https://www.postgresql.org/docs/current/sql-select.html)는
  `SKIP LOCKED`가 inconsistent view를 만들므로 general query가 아니라 queue-like table의
  multiple consumer contention 회피에 적합하다고 한정한다.
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)는
  default `READ COMMITTED`에서 각 command가 새 snapshot을 볼 수 있음을 설명한다.
- [Testcontainers Python PostgreSQL](https://testcontainers-python.readthedocs.io/en/latest/modules/postgres/README.html)는
  `PostgresContainer`를 공식 integration-test surface로 제공한다.

### Sibling Evidence

- `bluetape-go/sqlkit`은 transaction owner가 commit/rollback을 한 번만 수행하고 nested
  helper는 전달받은 session만 사용하게 한다.
- `bluetape-go/audit`은 storage-neutral event/repository model을 먼저 안정화했다.
- `bluetape-go/audit/sqloutbox`는 domain write와 outbox enqueue를 같은 SQL transaction에서
  수행하고, PostgreSQL relay를 별도 concrete adapter로 둔다.
- sibling relay는 at-least-once delivery와 duplicate 가능성을 public contract로 남긴다.
  Python 연구는 이 의미를 참고하지만 Go API나 generic interface를 기계적으로 옮기지 않는다.

## Approaches Considered

### 1. Disposable sync/async PostgreSQL spike — selected

공식 자료로 후보를 정리한 후 동일 PostgreSQL container에서 Psycopg, SQLAlchemy Core sync,
SQLAlchemy async를 비교한다. repository에는 spike code나 dependency를 남기지 않으므로
research classification을 유지하면서 transaction/rollback/claim 의미를 실행으로 확인할 수
있다.

### 2. Commit a reusable spike harness — rejected

재현성은 높지만 CI, dependency, maintenance, package ownership을 새로 만든다. 이는 Type E
research를 production implementation으로 확장하고 #15/#30의 설계를 선점한다.

### 3. Documentation-only comparison — rejected

dependency 변화가 없다는 장점은 있지만, 사용자 요청에 포함된 executable evidence를 제공하지
못하고 async connection sharing과 `SKIP LOCKED` claim을 실제 PostgreSQL에서 검증하지 못한다.

## Research Hypotheses

spike는 다음 가설을 검증한다. 결과가 다르면 최종 research note가 가설을 수정하고 이유를
기록한다.

1. SQL toolkit의 첫 후보는 ORM repository base class가 아니라 SQLAlchemy Core expression과
   explicit row mapping을 사용하는 작은 helper surface다.
2. sync helper는 caller-owned `sqlalchemy.Connection`, async helper는 caller-owned
   `sqlalchemy.ext.asyncio.AsyncConnection`을 받는다. helper는 connection을 생성·닫거나
   commit·rollback하지 않는다.
3. Psycopg DB-API는 최소 baseline과 PostgreSQL-specific escape hatch로 유용하지만, 별도 sync
   public toolkit과 asyncpg toolkit을 동시에 설계하는 것보다 SQLAlchemy Core의 공통 expression
   model이 sync/async parity에 유리하다.
4. generic repository base class, unit-of-work container, identity map, implicit CRUD, automatic
   retry는 첫 SQL package에 포함하지 않는다. application repository가 explicit functions 또는
   composition으로 query와 domain mapping을 소유한다.
5. audit event는 stdlib-only immutable dataclass/protocol로 시작할 수 있다. actor, subject,
   action, occurred-at, correlation, metadata의 validation과 redaction policy는 storage와 분리한다.
6. durable outbox는 storage-neutral audit package에 포함하지 않고 PostgreSQL-specific adapter로
   분리한다. enqueue는 caller-owned SQL transaction을 사용하고 relay는 caller가 명시적으로
   `run_once` 형태로 호출한다.
7. relay claim은 ordered bounded batch + `FOR UPDATE SKIP LOCKED`를 사용한다. delivery는
   at-least-once이며 publisher 성공 후 mark-published 사이의 failure에서 duplicate가 가능하다.
   library는 hidden worker, scheduler, global registry, broker client를 소유하지 않는다.
8. PostgreSQL Testcontainers fixture는 connection URL과 lifecycle만 제공하고 engine, pool,
   schema migration, transaction, seed data는 caller-owned로 남겨야 한다.

## Disposable Spike Contract

### Environment

- One `PostgresContainer` instance and one serial command.
- Python 3.13 through `uv run`.
- Temporary source outside the repository worktree.
- `--with` dependencies only; resolved versions are captured from runtime metadata.
- No workspace sync, `pyproject.toml`, `uv.lock`, package, or CI changes.
- One environmental retry is allowed only when the first failure is container startup or package
  acquisition, not when a semantic assertion fails.

### Schema

The disposable schema has three tables:

- `business_item(id, value)`
- `audit_event(id, subject_id, action, occurred_at, payload)`
- `outbox_event(id, topic, payload, created_at, claimed_at, published_at, attempts)`

The schema exists only to prove transaction and relay boundaries. It is not a future migration or
public schema contract.

### Required Proofs

1. Psycopg sync transaction inserts one row into all three tables and explicit dataclass mapping
   reconstructs the selected business row.
2. A forced exception inside a Psycopg transaction leaves all three table counts unchanged.
3. SQLAlchemy Core sync executes the same atomic write through a caller-owned `Connection` and
   maps `RowMapping` explicitly to a dataclass.
4. A forced exception inside `Engine.begin()` leaves all three table counts unchanged.
5. SQLAlchemy `AsyncEngine` + asyncpg executes the same atomic write through a caller-owned
   `AsyncConnection`, maps a row explicitly, and rolls back all three writes on failure.
6. Two concurrent relay connections demonstrate that a locked oldest row is skipped and a
   different available row is claimed with `FOR UPDATE SKIP LOCKED`.
7. The spike prints a bounded JSON result containing versions, proof booleans, row identifiers,
   and counts. It must not print credentials, the full connection URL, or raw container logs.

### Stop Conditions

- Stop and record `BLOCKED` if Docker/PostgreSQL cannot start after the one allowed environmental
  retry.
- Stop and record the failing candidate if atomic rollback or claim isolation is false. Do not
  rewrite the assertion to obtain a pass.
- Do not promote spike code into the repository during this issue.

## Expected Production Boundaries

The research note will recommend, reject, or amend these candidate slices:

| Slice | Candidate responsibility | Explicit exclusions |
| --- | --- | --- |
| SQL toolkit/repository | Core statements, sync/async caller-owned connection protocols, explicit dataclass mapping helpers, narrow error translation | ORM base model, session registry, engine factory, migration runner, transaction owner, generic CRUD repository |
| Audit model | Immutable storage-neutral event/value contracts, validation, redaction-ready metadata policy, in-memory conformance helpers | SQL schema, outbox relay, broker, global actor/context registry |
| PostgreSQL outbox | PostgreSQL schema guidance, enqueue on caller transaction, bounded claim/mark/fail operations, caller-driven relay | generic dialect promise, hidden worker, exactly-once claim, broker SDK ownership, automatic migration |
| Testcontainers PostgreSQL | container lifecycle and sanitized connection coordinates for integration tests | application engine/pool/schema/transaction/data ownership |

## Durable Artifacts

After this spec is approved, the execution step will produce:

- `docs/research/2026-07-16-issue-14-sql-repository-audit-outbox-strategy.md`
- aligned entries in `docs/research/README.md` and `docs/research/README.ko.md`
- roadmap/boundary updates in `WIP.md` and `docs/package-layout.md`
- implementation plan and review evidence under `docs/superpowers/plans/` and `docs/review/`
- a copyright-safe Korean source summary in `bluetape4k-wiki/research/`
- three non-overlapping follow-up issue outcomes, reusing or splitting #25/#30 as live evidence
  requires
- an exact-head PR from `research/issue-14-sql-audit-outbox` to `develop`

No diagram is required by default. A diagram will be added only if the final transaction/outbox
ownership and relay sequence cannot be stated clearly in the research note without one; if added,
it must use `bluetape-diagram` and include source, SVG, PNG, and rendered inspection evidence.

## Validation

Before PR creation:

1. Verify the disposable spike and capture its bounded result.
2. Verify every official URL and every local/sibling source path referenced by the research note.
3. Check English/Korean research index parity.
4. Run `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, and the
   smallest relevant repository tests. Escalate to broader tests only if shared executable or
   packaging contracts change unexpectedly.
5. Record Type E lesson-gate evidence. A durable lesson is required if the spike exposes reusable
   failure, recovery, design, or operational guidance; otherwise record evidence-backed `N/A`.
6. Complete P0/P1 review convergence and exact local/remote head verification before reporting the
   PR merge-ready.

## Non-Goals

- Production SQL, repository, audit, outbox, relay, or Testcontainers PostgreSQL implementation
- New workspace dependency, extra, lockfile entry, distribution, import path, migration, or schema
- ORM model/session abstraction or framework integration
- MySQL, MariaDB, SQLite, CockroachDB, cloud database, AWS, Kafka, NATS, Redis Streams, or HTTP adapter
- Benchmark or throughput comparison
- Background relay process, scheduler, retry worker, exactly-once delivery, or distributed consensus
- Release, tag, publish, merge, or auto-merge
