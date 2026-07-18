# Issue #15 Testcontainers Fixture Families Verification

## Claim

Issue #15 adds caller-owned PostgreSQL 18 and selected-service LocalStack fixture
families without changing the Redis contract or the default `bluetape` install. The
implementation is complete when focused and full tests, real Docker services, package
metadata, formatting/static checks, bilingual documentation, cleanup, and Type A review
all pass at the reviewed head.

## Reviewed head

- Branch: `feat/issue-15-testcontainers-fixtures`
- Validated implementation head: `a88a81da8c3335494782d4a460ca3f5cc19b60c9`
- Base: `origin/develop`
- Review result: `P0=0, P1=0, P2=0, P3=2`

## Fresh validation evidence

| Gate | Command/evidence | Result |
| --- | --- | --- |
| Focused non-Docker | `uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest packages/bluetape-testcontainers -m "not testcontainers" -q` | 114 passed, 3 deselected |
| Real services, serial | focused locked environment; `pytest -m testcontainers packages/bluetape-testcontainers -q` | 3 passed, 114 deselected, no skips |
| Full workspace | `uv run pytest -q` after locked all-package/all-extra sync | 2,365 passed, 1 skipped, 8 deselected |
| Observability regression | focused observability selection | 8 passed, 58 deselected |
| Lint | `uv run ruff check .` | passed |
| Format | `uv run ruff format --check .` | 185 files already formatted |
| Build | `uv build --all-packages` | 19 packages built as sdist and wheel |
| Workflow syntax | `actionlint` | passed |
| Patch hygiene | `git diff --check origin/develop...HEAD` | passed |
| Docker preflight | `docker info` | passed |
| CI cap | `.github/workflows/ci.yml` | `testcontainers-services`, serial, 30 minutes |
| Cleanup | service-label-filtered `docker ps -a` for Redis/PostgreSQL/LocalStack | zero wrapper-owned service containers remain |

The single full-workspace skip is the PostgreSQL real-service test when Psycopg is not
installed by the general workspace sync. The dedicated locked service environment owns
the caller clients and ran Redis, PostgreSQL, and LocalStack with no skips; therefore the
skip is dependency-boundary evidence rather than an untested service path.

## Real image evidence

- `redis:8` -> `redis@sha256:2838d5524559494f6f1cd66e97e76b200d64a633a8614200620755ed395daf32`
- `postgres:18-alpine` -> `postgres@sha256:1b1689b20d16a014a3d195653381cf2caa75a41a92d93b255a9d6ea29fd353aa`
- `localstack/localstack:4.14.0` -> `localstack/localstack@sha256:3ebc37595918b8accb852f8048fef2aff047d465167edd655528065b07bc364a`

## Acceptance-criterion verification

- Existing Redis public types, error messages, and lifecycle behavior remain covered and
  green after extracting shared support.
- PostgreSQL and LocalStack use official provider modules behind lazy private loaders;
  provider instances are not exported.
- LocalStack service normalization removes duplicates while preserving order and forwards
  the resulting selection exactly once, never default-all-services mode.
- Frozen connection details, percent-encoded PostgreSQL URLs, redacted secrets,
  loopback-only ports, and synthetic LocalStack credentials are unit- and integration-tested.
- Base import isolation, focused extras, root meta-package stability, wheel metadata, and
  namespace coexistence are asserted and built successfully.
- Failure classification, invalid/boundary inputs, cleanup retry, caller-exception
  preservation, real Redis/PostgreSQL/LocalStack round trips, and zero-container cleanup
  are covered.
- English and Korean docs, WIP/CHANGELOG, and the mandatory Type A lesson are committed.
- Six-lens implemented-diff review converged at P0=0/P1=0.

## Changed surface

- Runtime: shared support plus Redis compatibility changes and new PostgreSQL/LocalStack
  modules/root exports.
- Tests: shared spies, unit matrices, real-service integration tests, and packaging
  assertions.
- Packaging/CI: focused extras and client test group, lockfile, and serialized service job.
- Documentation/governance: paired root/package docs, WIP, CHANGELOG, approved spec/plan
  and reviews, mandatory lesson, this code review, and this verifier report.

## Remaining external gate

Local verification is complete. PR creation must be followed by exact-head GitHub check
rollup and unresolved non-outdated review-thread verification. Merge remains prohibited
until that evidence is green and the user gives a fresh explicit merge approval.
