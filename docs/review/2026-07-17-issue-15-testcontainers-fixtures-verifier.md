# Issue #15 Testcontainers Fixture Families 검증

## 주장

Issue #15는 Redis contract나 기본 `bluetape` install을 변경하지 않고
caller-owned PostgreSQL 18 및 selected-service LocalStack fixture family를
추가한다. Focused/full test, real Docker service, package metadata, format/static
check, bilingual docs, cleanup, Type A review가 reviewed head에서 통과하면
implementation을 완료한 것으로 본다.

## 검토 head

- 브랜치: `feat/issue-15-testcontainers-fixtures`
- Validated implementation head: `a88a81da8c3335494782d4a460ca3f5cc19b60c9`
- 기준: `origin/develop`
- Review result: `P0=0, P1=0, P2=0, P3=2`

## 새 검증 근거

| Gate | Command/evidence | 결과 |
|---|---|---|
| Focused non-Docker | `uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest packages/bluetape-testcontainers -m "not testcontainers" -q` | 114 passed, 3 deselected |
| Real services, serial | Focused locked environment; `pytest -m testcontainers packages/bluetape-testcontainers -q` | 3 passed, 114 deselected, skip 없음 |
| Full workspace | Locked all-package/all-extra sync 후 `uv run pytest -q` | 2,365 passed, 1 skipped, 8 deselected |
| Observability regression | Focused observability selection | 8 passed, 58 deselected |
| Lint | `uv run ruff check .` | 통과 |
| Format | `uv run ruff format --check .` | 185 files already formatted |
| Build | `uv build --all-packages` | 19 package를 sdist/wheel로 build |
| Workflow syntax | `actionlint` | 통과 |
| Patch hygiene | `git diff --check origin/develop...HEAD` | 통과 |
| Docker preflight | `docker info` | 통과 |
| CI cap | `.github/workflows/ci.yml` | `testcontainers-services`, serial, 30분 |
| Cleanup | Redis/PostgreSQL/LocalStack service-label-filtered `docker ps -a` | Wrapper-owned service container 0 |

Full-workspace의 단일 skip은 general workspace sync가 Psycopg를 설치하지 않아
PostgreSQL real-service test를 건너뛴 것이다. Dedicated locked service environment가
caller client를 소유하고 Redis, PostgreSQL, LocalStack을 skip 없이 실행했으므로
dependency-boundary 근거이지 미검증 service path가 아니다.

## Real image 근거

- `redis:8` -> `redis@sha256:2838d5524559494f6f1cd66e97e76b200d64a633a8614200620755ed395daf32`
- `postgres:18-alpine` -> `postgres@sha256:1b1689b20d16a014a3d195653381cf2caa75a41a92d93b255a9d6ea29fd353aa`
- `localstack/localstack:4.14.0` -> `localstack/localstack@sha256:3ebc37595918b8accb852f8048fef2aff047d465167edd655528065b07bc364a`

## Acceptance 검증

- Existing Redis public type, error message, lifecycle behavior는 shared support
  추출 후에도 covered/green
- PostgreSQL과 LocalStack은 lazy private loader 뒤 official provider module을
  사용하고 provider instance를 export하지 않음
- LocalStack service normalization은 duplicate를 제거하면서 order를 보존하고
  selection을 정확히 한 번 forward하며 default-all-services mode를 사용하지 않음
- Frozen connection detail, percent-encoded PostgreSQL URL, redacted secret,
  loopback-only port, synthetic LocalStack credential을 unit/integration test
- Base import isolation, focused extra, root meta stability, wheel metadata,
  namespace coexistence build 성공
- Failure classification, invalid/boundary input, cleanup retry, caller exception
  preservation, real Redis/PostgreSQL/LocalStack round trip, zero-container cleanup covered
- English/Korean docs, WIP/CHANGELOG, mandatory Type A lesson committed
- Six-lens implemented-diff review가 P0=0/P1=0으로 수렴

## 변경 surface

- Runtime: shared support, Redis compatibility, PostgreSQL/LocalStack module와 root export
- Tests: shared spy, unit matrix, real-service integration, packaging assertion
- Packaging/CI: focused extra와 client test group, lockfile, serial service job
- Documentation/governance: paired root/package docs, WIP, CHANGELOG, approved
  spec/plan/review, lesson, code review, verifier report

## 남은 외부 gate

Local verification은 완료했다. PR creation 후 exact-head GitHub check rollup과
unresolved non-outdated review-thread verification이 필요하다. Evidence가
green이고 user가 새 merge approval을 주기 전에는 merge할 수 없다.
