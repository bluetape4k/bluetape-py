# Issue #15 Testcontainers Fixture Families Design

- Issue: [#15](https://github.com/bluetape4k/bluetape-py/issues/15)
- Milestone: `0.2.0`
- Date: 2026-07-17 KST
- Work type: Type A - Full Feature
- Repository: `bluetape4k/bluetape-py`
- Base/head: `develop` <- `feat/issue-15-testcontainers-fixtures`

## Problem

`bluetape-testcontainers` currently owns a production-quality Redis 8 test-server
boundary, but issue #15 also requires PostgreSQL and AWS-compatible fixture
families. Downstream SQL toolkit and audit-outbox work need a stable PostgreSQL
endpoint without owning Docker lifecycle code, while future AWS adapters need a
LocalStack endpoint without coupling test infrastructure to a production AWS SDK
client lifecycle.

Direct use of Testcontainers Python would repeat image authority, mapped-port,
readiness, error-redaction, cleanup, and pytest ownership rules in each consumer.
Conversely, a generic container framework inside Bluetape would duplicate the
chosen provider and make its internals part of the public contract.

## Approved Outcome

Complete issue #15 as one delivery unit:

1. Preserve the existing `RedisServer` public behavior.
2. Add an ecosystem-owned `PostgresServer` using PostgreSQL 18.
3. Add an ecosystem-owned `LocalStackServer` for caller-selected AWS-compatible
   services.
4. Add focused package extras named `postgres`, `aws`, and `all`.
5. Keep the default `bluetape` installation provider-free and keep automatic
   pytest plugin registration out of scope.
6. Document explicit fixture scope, image, endpoint, credential, readiness,
   cleanup, and CI ownership in English and Korean.
7. Deliver an issue-linked PR to `develop`; merge, release, tag, and publish remain
   separate gates.

## Current Evidence

### Repository

- `packages/bluetape-testcontainers` already exposes `RedisServer`, immutable
  connection details, validated pinned images, stable startup categories,
  retryable cleanup, and caller-owned context-manager lifecycle.
- The package currently depends on `testcontainers>=4.14.2,<4.15`; the lockfile
  resolves `4.14.2`.
- Root `bluetape[testcontainers]` is opt-in. The default meta install still
  depends only on `bluetape-core`.
- Issue #14 disposable evidence used PostgreSQL `18.4` through
  `postgres:18-alpine`; its durable recommendation assigns container lifecycle
  and sanitized connection coordinates to this package while leaving engines,
  pools, schema, transactions, and seed data caller-owned.
- The fresh worktree baseline passes `2304` normal tests with the focused
  `observability_sdk` group excluded and passes the `8` SDK tests after installing
  the package's `test` dependency group.

### Provider and image authority

- Testcontainers Python 4.14.2 provides official `PostgresContainer` and
  `LocalStackContainer` modules.
- `PostgresContainer` can return a driver-neutral URL when `driver=None`; its
  default driver name must not leak into the Bluetape contract.
- `LocalStackContainer` imports `boto3`, so the public Bluetape module must remain
  importable when the `aws` extra is absent and defer provider loading until
  startup.
- The current official LocalStack GitHub release is `v4.14.0`; the wrapper pins
  `localstack/localstack:4.14.0` rather than the provider's stale default or a
  floating `latest` tag.

Primary references:

- [Testcontainers Python repository](https://github.com/testcontainers/testcontainers-python)
- [Testcontainers Python PostgreSQL module](https://testcontainers-python.readthedocs.io/en/latest/modules/postgres/README.html)
- [LocalStack v4.14.0](https://github.com/localstack/localstack/releases/tag/v4.14.0)
- [LocalStack Testcontainers documentation](https://docs.localstack.cloud/aws/integrations/containers/testcontainers/)

## Approaches Considered

### 1. Thin Bluetape adapters over official provider modules - selected

`PostgresServer` and `LocalStackServer` own a small, stable lifecycle and details
surface while official Testcontainers modules own container construction and
service-specific readiness. Provider objects and Docker clients remain private.
This follows issue #15's reuse requirement and avoids duplicating database or AWS
container configuration.

### 2. Generic lifecycle base plus Redis refactor - rejected

A shared abstract server could remove some state-machine repetition, but it would
also rewrite the already-delivered Redis lifecycle and couple three providers to
one inheritance hierarchy before their failure behavior is proven identical.
Private pure validation and error helpers may be shared; a generic public or
private server base is not introduced.

### 3. Re-export provider container classes - rejected

This is the smallest implementation, but it exposes provider image defaults,
mutable provider objects, raw exceptions, and client factories. It does not give
downstream Bluetape packages stable endpoint, redaction, cleanup, or ownership
contracts.

## Package Boundary

The existing distribution and namespace remain authoritative:

```text
packages/bluetape-testcontainers/
├── pyproject.toml
├── README.md
├── README.ko.md
├── src/bluetape/testcontainers/
│   ├── __init__.py
│   ├── _support.py
│   ├── redis.py
│   ├── postgres.py
│   └── localstack.py
└── tests/bluetape_testcontainers_tests/
    ├── test_packaging.py
    ├── test_postgres_server.py
    ├── test_postgres_server_integration.py
    ├── test_localstack_server.py
    └── test_localstack_server_integration.py
```

Runtime dependency and extras:

```toml
dependencies = ["testcontainers>=4.14.2,<4.15"]

[project.optional-dependencies]
postgres = ["testcontainers[postgres]>=4.14.2,<4.15"]
aws = ["testcontainers[localstack]>=4.14.2,<4.15"]
all = [
  "testcontainers[postgres]>=4.14.2,<4.15",
  "testcontainers[localstack]>=4.14.2,<4.15",
]

[dependency-groups]
test = [
  "boto3>=1,<2",
  "psycopg[binary]>=3.2,<4",
  "pytest>=8.4.0",
]
```

`testcontainers[postgres]` is explicit even though version 4.14.2 currently adds
no driver dependency. The wrapper does not require SQLAlchemy, Psycopg, asyncpg,
or a production AWS SDK client. Integration-only dependencies belong in the
package `test` group, which is the authoritative source for integration-test
clients and is not published as a runtime extra. Root `bluetape[testcontainers]`
continues forwarding the focused package without installing its AWS extra.

## Public API

Ellipses in the signature sketches omit implementation bodies; they are not
unresolved requirements or placeholders.

### Shared startup contract

`StartFailureKind` gains one additive value:

```python
class StartFailureKind(StrEnum):
    DEPENDENCY_MISSING = "dependency-missing"
    RUNTIME_UNAVAILABLE = "runtime-unavailable"
    IMAGE_PULL = "image-pull"
    READINESS_TIMEOUT = "readiness-timeout"
    WRAPPER_FAILURE = "wrapper-failure"
```

`TestcontainerStartError` uses the exact compatible constructor
`__init__(kind: StartFailureKind, image: str, *, service: str = "Redis")`.
The existing two-argument Redis call retains the exact Redis message and symbol
identity. `StartFailureKind` and `TestcontainerStartError` remain importable from
both `bluetape.testcontainers` and `bluetape.testcontainers.redis` even when their
implementation moves to `_support.py`. Provider exceptions are suppressed from
the public cause chain.

The package root explicitly exports the existing Redis symbols plus
`DEFAULT_POSTGRES_IMAGE`, `PostgresConnectionDetails`, `PostgresServer`,
`DEFAULT_LOCALSTACK_IMAGE`, `LocalStackConnectionDetails`, and
`LocalStackServer`. Importing every root export succeeds from a base-only wheel
without Psycopg, boto3, or SQLAlchemy; service providers load only inside the
corresponding `start()` call.

### PostgreSQL

```python
DEFAULT_POSTGRES_IMAGE = "postgres:18-alpine"

@dataclass(frozen=True, slots=True)
class PostgresConnectionDetails:
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)

    @property
    def url(self) -> str: ...

    def connection_url(self, *, driver: str | None = None) -> str: ...


class PostgresServer:
    def __init__(
        self,
        *,
        image: str = DEFAULT_POSTGRES_IMAGE,
        database: str = "test",
        username: str = "test",
        password: str = "test",
    ) -> None: ...

    @property
    def running(self) -> bool: ...
    @property
    def details(self) -> PostgresConnectionDetails: ...
    def start(self) -> Self: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(...) -> None: ...
```

`url` is driver-neutral `postgresql://...`; `connection_url(driver=None)` is
exactly equal to `url`. `connection_url(driver="psycopg")`
returns a SQLAlchemy-compatible `postgresql+psycopg://...` string without
importing SQLAlchemy. User, password, database, driver, IPv6 host, and reserved
URL characters are encoded safely. The wrapper does not create engines,
connections, pools, schemas, transactions, migrations, or seed data.
Driver names use lowercase ASCII `[a-z][a-z0-9_]*`; blank, uppercase, plus-prefixed,
or otherwise invalid names raise `ValueError` before Docker access. Both URL
accessors return secret-bearing strings: examples, errors, assertions, and object
representations never log or render their values.

### LocalStack

```python
DEFAULT_LOCALSTACK_IMAGE = "localstack/localstack:4.14.0"

@dataclass(frozen=True, slots=True)
class LocalStackConnectionDetails:
    endpoint_url: str
    region_name: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    services: tuple[str, ...]


class LocalStackServer:
    def __init__(
        self,
        *,
        services: Iterable[str],
        image: str = DEFAULT_LOCALSTACK_IMAGE,
        region_name: str = "us-east-1",
        startup_timeout: float = 60.0,
    ) -> None: ...

    @property
    def running(self) -> bool: ...
    @property
    def details(self) -> LocalStackConnectionDetails: ...
    def start(self) -> Self: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(...) -> None: ...
```

At least one explicit service is required. A bare `str` or `bytes` value raises
`TypeError`; other iterables are normalized once, deduplicated without reordering,
and validated as lowercase ASCII identifiers containing letters, digits, and
hyphens. Before startup, the wrapper calls
`LocalStackContainer.with_services(*normalized_services)` exactly once and never
uses the provider's default-all-services path.

The wrapper exposes endpoint and fixed synthetic credentials only. Both access
key and secret are `testcontainers-localstack`, matching the provider-owned
container environment. They are never read from environment variables, shared
AWS configuration, metadata services, or provider credential discovery. Callers
create and close boto3 or other SDK clients. The wrapper does not configure real
AWS credentials, accounts, IAM policy, production endpoints, or application
shutdown.

The public module remains importable without the `aws` extra. `start()` reports
`dependency-missing` with the exact sanitized installation hint
`pip install "bluetape-testcontainers[aws]"` when the official LocalStack
provider cannot load because `boto3` is absent.

## Lifecycle and Ownership

Both new servers are synchronous, single-use, and caller-owned. Their complete
transition contract is:

| Current state | Operation/outcome | Next state | Contract |
| --- | --- | --- | --- |
| `NEW` | `start()` | `STARTING` | Provider construction begins. |
| `NEW` | `close()` | `CLOSED` | No Docker call is made. |
| `STARTING` | readiness succeeds | `RUNNING` | Immutable details become visible. |
| `STARTING` | startup fails, cleanup succeeds | `CLOSED` | Details and provider reference are cleared. |
| `STARTING` | startup and cleanup fail | `CLEANUP_FAILED` | Details are cleared; provider reference is retained. |
| `RUNNING` | `start()` | `RUNNING` | Returns the same wrapper without provider work. |
| `RUNNING` | `close()` succeeds | `CLOSED` | Details and provider reference are cleared. |
| `RUNNING` | `close()` fails | `CLEANUP_FAILED` | Details are cleared; provider reference is retained. |
| `CLEANUP_FAILED` | `start()` | unchanged | Raises `RuntimeError`; cleanup must finish first. |
| `CLEANUP_FAILED` | `close()` succeeds | `CLOSED` | Retries the retained provider exactly once. |
| `CLEANUP_FAILED` | `close()` fails | `CLEANUP_FAILED` | Remains retryable. |
| `CLOSED` | `start()` | unchanged | Raises `RuntimeError`; the instance is single-use. |
| `CLOSED` | `close()` | `CLOSED` | Idempotent no-op with no provider or Docker call. |

- Construction performs no Docker access.
- Details exist only during `RUNNING` and are immutable snapshots.
- Details are cleared before every cleanup attempt. A failed `close()` raises
  `RuntimeError("<Service> test container cleanup failed") from None`, retains
  the provider reference, and remains `CLEANUP_FAILED`; a successful retry clears
  the reference and enters `CLOSED`.
- `__exit__` returns `None`. When the body raised, cleanup failure is not raised;
  one fixed sanitized note with the `close()` retry instruction is appended to
  the primary exception and state remains `CLEANUP_FAILED`. Without a body
  exception, the sanitized cleanup `RuntimeError` is raised.
- `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` remain primary and are
  never converted to a category error.
- Published service ports use dynamic host ports bound to loopback only
  (`127.0.0.1` or `::1`). Startup fails with a sanitized `wrapper-failure` when
  the Docker provider/runtime cannot guarantee a loopback binding.
- No singleton, background task, thread, scheduler, global registry, fixed host
  port, Docker network, reuse flag, migration, or data reset is owned.
- Instances are not thread-safe and must belong to one fixture or caller.

Unlike the existing Redis wrapper, the new adapters intentionally use official
service modules and their provider lifecycle. `PostgresServer` exposes no
wrapper timeout because the selected provider owns PostgreSQL readiness and does
not accept a public timeout. `LocalStackServer.startup_timeout` is passed to the
provider's public `start(timeout=...)` readiness-log wait. Neither value is a
total wall-clock deadline: provider-owned Docker client creation, image pull,
container creation, and setup may outlive it. Unit tests prove the LocalStack
timeout propagation and prove that PostgreSQL does not advertise an unsupported
timeout.

The wrappers do not mutate global Testcontainers/Ryuk configuration. When the
provider enables Ryuk, it is provider-owned, may be initialized on first service
startup, and may remain process-wide after a wrapper closes. `close()` removes
only the wrapper-owned PostgreSQL or LocalStack service container. This differs
from Redis's existing no-Ryuk lifecycle and must be included in CI capacity and
cleanup documentation.

## Validation and Error Contract

- Non-string scalar inputs raise `TypeError`.
- Blank, surrounding-whitespace, control-character, floating `latest`, invalid
  region/service/driver, non-finite timeout, or invalid port-related values raise
  `ValueError` before Docker access.
- Image input rejects URI schemes and embedded user information. Registry
  authentication belongs only in Docker credential configuration, and public
  errors never include the rejected raw image value.
- Passwords and secret keys use `repr=False`; raw provider exceptions, daemon
  paths, registry responses, environment values, and container logs are not
  included in public errors.
- Missing details outside the live interval raise `RuntimeError`.
- Missing optional AWS dependencies map to `dependency-missing`.
- Docker/socket errors map to `runtime-unavailable`; image acquisition failures
  map to `image-pull`; provider readiness expiry maps to `readiness-timeout`;
  detail or wrapper failures map to `wrapper-failure`.

## Pytest and CI Contract

The distribution does not register a pytest plugin or automatic fixture.
Consumers choose function, module, or session scope explicitly and own database
reset, AWS resource cleanup, and client closure.

Docker-free tests cover:

- success and public details construction;
- invalid image, timeout, credential, region, service, and driver values;
- detail access before start and after close;
- repeated start, single-use enforcement, and cleanup retry;
- primary-exception preservation and provider error redaction;
- complete state transitions, idempotent close, LocalStack timeout propagation,
  and selected-service forwarding with provider spies;
- import and wheel isolation with no AWS extra;
- missing AWS dependency behavior;
- sentinel ambient AWS credentials proving the wrapper neither uses nor returns
  caller environment values;
- URL encoding, IPv4/IPv6, and caller-owned value preservation.

Docker-backed tests run serially and cover:

1. PostgreSQL 18 startup, dynamic endpoint, a real Psycopg query, and cleanup.
2. Driver-neutral and `postgresql+psycopg` URL compatibility.
3. LocalStack startup with only `services=("s3",)`, mapped endpoint, fixed
   synthetic credentials, an S3 create/list round trip, and cleanup.
4. The published PostgreSQL and LocalStack service bindings are dynamic and
   loopback-only rather than wildcard-addressed.
5. No wrapper-owned service container remains after each normal integration-test
   path. Provider-owned process-wide Ryuk is explicitly excluded from this
   assertion.

The implementation sequence runs focused unit tests before real containers.
The existing `testcontainers-redis` CI job becomes a serialized
`testcontainers-services` job. It installs the package's `all` extra plus `test`
group, runs `docker info` as an environment preflight, and then runs the one
marked integration command. A preflight failure identifies runner/runtime
configuration; a later typed startup failure remains a semantic test failure and
is not converted to a skip or retry. Full workspace validation keeps the
caller-owned observability SDK suite separate:

```bash
uv sync --package bluetape-testcontainers --extra all --group test --python 3.13.14 --locked
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m "not testcontainers" packages/bluetape-testcontainers -q
docker info
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m testcontainers packages/bluetape-testcontainers -q
uv sync --all-packages --all-extras --python 3.13.14 --locked
uv run pytest -m "not observability_sdk"
uv sync --package bluetape-observability --group test --python 3.13.14 --locked
uv run pytest -m observability_sdk packages/bluetape-observability -q
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
git diff --check
```

Package changes additionally require wheel metadata/import smoke tests for the
base, `postgres`, `aws`, and `all` install shapes.

## Documentation and Compatibility

- Update package and root `README.md`/`README.ko.md` together.
- Document Redis, PostgreSQL, and LocalStack in one supported-service matrix.
- Publish this exact installation matrix in both languages:
  - Redis/base: `pip install "bluetape[testcontainers]"` or
    `pip install bluetape-testcontainers`;
  - PostgreSQL: `pip install "bluetape-testcontainers[postgres]"`;
  - LocalStack: `pip install "bluetape-testcontainers[aws]"`;
  - both new families: `pip install "bluetape-testcontainers[all]"`.
  Root `bluetape[testcontainers]` remains base-only.
- Provide one copy-paste pytest fixture per new family in both languages.
  PostgreSQL examples show a caller-owned Psycopg connection being closed.
  LocalStack examples use `services=("s3",)`, close the caller-owned SDK client,
  explain AWS resource cleanup between tests, and show fixture scope explicitly.
- Add an error-handling example using `TestcontainerStartError.kind` and a table
  mapping dependency, runtime, image, readiness, wrapper, and cleanup-pending
  states to caller actions. Errors and examples never render secret-bearing
  PostgreSQL URLs, credentials, or rejected image inputs.
- Document `docker info`, trusted explicit image pulls, service-container cleanup
  verification, and the provider-owned Ryuk prerequisite/overhead.
- Update `WIP.md` and `CHANGELOG.md` when the behavior is delivered.
- Existing Redis names, default image, exception strings, dependency isolation,
  and tests remain compatible.
- Add paired “Upgrading from Redis-only usage” notes: existing code and
  dependencies need no change, the root extra remains base-only, and all new
  provider extras are opt-in.
- This is source-workspace delivery only; version, release, tag, and PyPI
  publication are unchanged.

## Failure Modes and Recovery

1. **Provider dependency absent:** base import still succeeds; LocalStack startup
   fails with `dependency-missing` and the exact focused-package `aws` install
   command.
2. **Docker runtime/image/readiness failure:** a stable sanitized category is
   returned, created resources are cleaned when possible, and retry requires a
   new wrapper unless cleanup itself is pending.
3. **Cleanup failure:** details are invalidated, the provider reference remains,
   and repeated `close()` retries termination rather than declaring success.
4. **Credential leakage:** secret fields and secret-bearing URLs are excluded
   from repr/errors/examples, ambient AWS credentials are ignored, and raw
   provider diagnostics are not chained or rendered publicly.
5. **Fixture misuse:** details outside `RUNNING`, restart after close, empty AWS
   service selection, and fixed-port assumptions fail explicitly.
6. **Integration environment unavailable:** serial Docker tests report the typed
   startup failure; CI does not convert semantic failures into skips or parallel
   retries.

## Acceptance Criteria

- Existing Redis public and lifecycle contracts remain green.
- PostgreSQL and LocalStack wrappers use official Testcontainers modules and do
  not expose provider objects.
- LocalStack forwards the normalized selected services exactly once and never
  starts the provider's default-all-services mode.
- Endpoint and credential details are immutable, safely encoded, and redacted in
  representations.
- Dynamic published service ports are loopback-only, and LocalStack uses only
  wrapper-owned synthetic credentials regardless of ambient AWS configuration.
- Base package import succeeds without PostgreSQL drivers, boto3, SQLAlchemy, or
  an AWS SDK client lifecycle owned by Bluetape.
- `postgres`, `aws`, and `all` extras resolve correctly without changing the
  default `bluetape` install.
- Normal, invalid, boundary, failure, cleanup, dependency-missing, packaging,
  and real-container paths are tested.
- Package tests are reproducible from the locked `all` extra plus package `test`
  group, and the serialized CI job runs a Docker preflight before all three
  service integration paths.
- English and Korean documentation agree on prerequisites, supported services,
  image defaults, ownership, CI serialization, and examples.
- Targeted and full validation pass, Type A reviews converge at P0=0/P1=0, and
  the mandatory lesson is committed before PR creation.

## Non-Goals

- MySQL, MariaDB, CockroachDB, MongoDB, Kafka/Redpanda, RabbitMQ/NATS, MinIO,
  Elasticsearch/OpenSearch, Neo4j, Vault, or custom `GenericContainer` wrappers
- Production Redis/PostgreSQL/AWS clients or application provider packages
- SQLAlchemy engine/pool/session, Psycopg connection ownership, async database
  abstraction, schema migration, seed data, transaction, or database reset
- boto3 client factory ownership, real AWS credentials, IAM/account emulation,
  LocalStack extension management, or service-specific production adapters
- Automatic pytest plugin/fixture, hidden reuse, fixed host ports, global state,
  background cleanup, or package-owned scheduling
- Release, tag, publish, merge, or auto-merge

## Definition of Done

The issue is implementation-complete when the approved spec and plan are
committed, tests and package checks pass, six spec/plan/code perspectives plus
main integration report P0=0/P1=0, documentation and package metadata are
aligned, the Type A lesson is committed, and the exact-head issue-linked PR is
green and merge-ready. Final completion still requires a fresh user approval for
the reported PR head, verified rebase merge, local `develop` sync, and proven
worktree/branch cleanup.
