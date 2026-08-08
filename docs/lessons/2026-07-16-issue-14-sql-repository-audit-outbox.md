# Issue #14 SQL, Repository, Audit 및 Outbox 연구 교훈

## 배경과 결정

Issue #14에서는 구현 전에 Python-native SQL layer를 선택하고 repository, audit,
outbox ownership을 나눠야 했다. Official documentation만으로는 하나의 caller-owned
transaction이 DB-API, SQLAlchemy sync, SQLAlchemy async 경로에서 business, audit,
outbox write를 함께 수행할 수 있음을 증명하기에 부족했다. disposable PostgreSQL
Testcontainers spike로 workspace dependency나 production code를 추가하지 않고 이
증거를 확보했다.

최종 경계는 향후 공용 sync/async SQL toolkit에 SQLAlchemy Core를 사용하고, audit value는
stdlib-only이면서 storage-neutral로 유지하며, PostgreSQL claim/relay semantics는
별도의 adapter에 맡기는 방식이다.

## 재사용 가능한 발견

### Async extra는 실행 가능한 dependency contract의 일부다

plain `sqlalchemy`를 설치하면 disposable environment에서 async surface를 import하고
구성하기에는 충분했지만, async execution이 시작되자 선언된 asyncio runtime extra가
없어 첫 실행이 실패했다. 한 번의 retry에서는 dependency만 `sqlalchemy[asyncio]`로
변경했고, 이후 일곱 가지 semantic proof가 모두 통과했다.

Async integration test와 package extra는 upstream asyncio extra를 명시적으로 선언해야
한다. import, type check, engine construction이 성공했다고 해서 모든 platform에
runtime bridge dependency가 설치됐다는 뜻은 아니다. transitive 또는 platform-dependent
`greenlet` 설치에 의존하지 않는다.

### positive state와 negative state를 함께 확인해 transaction ownership을 증명한다

commit assertion만으로는 nested helper가 다른 connection을 열거나 너무 일찍 commit해도
통과할 수 있다. 유효한 증명은 하나의 고유한 business, audit, outbox row를 쓰고 count가
`[1, 1, 1]`인지 확인한 다음, forced exception을 재현해 `[0, 0, 0]`인지 확인하는
것이다.

이 paired proof는 모든 sync 및 async repository/outbox 구현에 재사용해야 한다. helper는
같은 transaction-bound connection을 받고 commit이나 rollback을 소유하지 않는다.
transaction owner만 unit of work를 끝낼 수 있다.

### locking proof는 relay proof보다 범위가 좁다

첫 PostgreSQL row lock을 유지한 채 두 번째 connection이 다음 row를 선택하도록 한
검증은 `FOR UPDATE SKIP LOCKED`가 서로 다른 concurrent queue claim을 만들 수 있음을
증명했다. 그러나 claim token, lease expiry, stale recovery, publisher failure,
mark-published compare-and-set, retention, crash reconciliation까지 증명한 것은 아니다.

범위가 좁은 proof임을 정직하게 기록한다. 후속 outbox 설계에는 여전히 lease/ownership
state machine과 failure test가 필요하다. PostgreSQL은 skipped row에 대해 inconsistent
view를 명시적으로 허용하므로 `SKIP LOCKED`는 일반적인 consistent-read abstraction으로
사용하기에 적합하지 않다.

### Disposable spike에는 영속적인 source가 아니라 검토 가능한 증거가 필요하다

Spike는 `/tmp` 아래에 두고, dependency는 `uv run --no-project
--with`에서 가져왔으며,
version, command, bounded proof boolean, identifier, count, duration, failure category,
limitation만 repository에 남겼다. 이 방식으로 package, lockfile, CI, maintenance
surface를 만들지 않고 검토 가능한 증거를 보존했다.

Disposable research harness는 semantic assertion에서 fail closed해야 하고 credential과
connection URL을 숨겨야 하며, 미리 선언한 environmental retry만 허용해야 한다. boundary
선택에 충분한 결과를 얻으면 삭제 가능성이 장점이 된다. production implementation은
승인된 design으로 돌아가야 하며 exploratory code를 승격해서는 안 된다.

## 검증 증거

- PostgreSQL `18.4`를 `postgres:18-alpine`으로 실행하고 Testcontainers Python `4.14.2`를 사용했다.
- Psycopg `3.3.4`, SQLAlchemy `2.0.51`, asyncpg `0.31.0`, Python `3.13.14`.
- Sync DB-API, SQLAlchemy sync, SQLAlchemy async commit count는 각각 `[1, 1, 1]`.
- Forced rollback count는 각각 `[0, 0, 0]`.
- Concurrent queue claim에서는 첫 lock을 연 채 별도 transaction이 `claim-1`과
  `claim-2`를 선택했다.
- Spike에서 workspace `pyproject.toml`, `uv.lock`, package, workflow는 변경하지 않았다.

## 향후 보호 장치

향후 SQL/outbox 변경에서는 async runtime extra를 명시하고, 정확히 빌린 connection으로
commit과 forced rollback을 테스트하며, queue locking과 lease/recovery correctness를
구분하고, disposable research source를 production package 밖에 둔다. hidden connection을
만들거나 nested work를 commit하거나 relay loop를 소유하거나 exactly-once delivery를
주장하는 helper는 이 research boundary를 위반하므로 새로운 승인된 design이 필요하다.
