# bluetape-testcontainers

English | [한국어](README.ko.md)

`bluetape-testcontainers` owns reusable Docker-backed test server boundaries for
the bluetape Python ecosystem. It is test infrastructure, not a production
Redis, PostgreSQL, or AWS client package.

## Install

PyPI publication is currently on hold. The commands below are the intended
post-publication install shapes. For current source-workspace validation, use
`uv sync --package bluetape-testcontainers --extra all --group test --python
3.13.14 --locked` from this repository.

| Need | Command |
| --- | --- |
| Redis/base wrapper | `pip install "bluetape[testcontainers]"` or `pip install bluetape-testcontainers` |
| PostgreSQL | `pip install "bluetape-testcontainers[postgres]"` |
| LocalStack | `pip install "bluetape-testcontainers[aws]"` |
| PostgreSQL and LocalStack | `pip install "bluetape-testcontainers[all]"` |

The root `bluetape[testcontainers]` extra remains base-only. PostgreSQL drivers,
boto3, SQLAlchemy, and production clients are not installed by that root extra.
Callers install and own the client libraries used by their tests.

## Supported services

| Wrapper | Default image | Caller owns |
| --- | --- | --- |
| `RedisServer` | `redis:8` | key/data reset and client lifecycle |
| `PostgresServer` | `postgres:18-alpine` | connections, pools, schema, transactions, migrations, and seed data |
| `LocalStackServer` | `localstack/localstack:4.14.0` | selected services, SDK clients, and AWS resource cleanup |

## Pytest fixtures

The package does not register a pytest plugin or automatic fixture. Use
function-scoped fixtures unless a wider scope has an explicit reset policy:

```python
import boto3
import psycopg
import pytest

from bluetape.testcontainers import LocalStackServer, PostgresServer


@pytest.fixture
def postgres_connection():
    with PostgresServer() as server:
        with psycopg.connect(server.details.url) as connection:
            yield connection


@pytest.fixture
def s3_client():
    with LocalStackServer(services=("s3",)) as server:
        details = server.details
        client = boto3.client(
            "s3",
            endpoint_url=details.endpoint_url,
            region_name=details.region_name,
            aws_access_key_id=details.access_key_id,
            aws_secret_access_key=details.secret_access_key,
        )
        try:
            yield client
        finally:
            client.close()
```

Callers delete database and AWS resources between tests. Secret-bearing
PostgreSQL URLs must not be logged, and wider fixture scopes require an explicit
reset policy. Each server is synchronous, single-use, not thread-safe, and must
belong to exactly one fixture or caller. The CI capability proof covers S3;
other syntactically valid LocalStack service names are forwarded to the pinned
provider and image and must be capability-tested by the caller before adoption.

Construction does not access Docker. Repeated `start()` while a server is
running is safe, but starting it after `close()` is rejected. Published service
ports are dynamic and loopback-only; remote or shared Docker daemons that cannot
prove this contract are rejected. If termination fails, call `close()` again on
the same wrapper until cleanup succeeds.

## Startup and cleanup failures

Startup failures expose a sanitized `TestcontainerStartError` and stable
`StartFailureKind`. Do not log the caught exception, connection URLs,
credentials, rejected image values, or raw provider output.

| State/category | Caller action |
| --- | --- |
| `dependency-missing` | Install `bluetape-testcontainers[aws]` and create a new wrapper. |
| `runtime-unavailable` | Run `docker info`; repair runtime access before retrying. |
| `image-pull` | Pull the trusted pinned image explicitly and create a new wrapper. |
| `readiness-timeout` | Inspect runtime capacity and the selected service set; do not log raw provider output. |
| `wrapper-failure` | Treat it as a contract/configuration failure and inspect sanitized inputs. |
| cleanup pending | Call `close()` again on the same wrapper until cleanup succeeds. |

Handle only the stable category in caller diagnostics:

```python
from bluetape.testcontainers import (
    LocalStackServer,
    StartFailureKind,
    TestcontainerStartError,
)

server = LocalStackServer(services=("s3",))
try:
    with server:
        pass  # create and close caller-owned SDK clients inside this block
except TestcontainerStartError as error:
    if error.kind is StartFailureKind.DEPENDENCY_MISSING:
        raise RuntimeError(
            'Install "bluetape-testcontainers[aws]" before running this test.'
        ) from None
    if error.kind is StartFailureKind.RUNTIME_UNAVAILABLE:
        raise RuntimeError("Verify Docker access with docker info.") from None
    raise RuntimeError(
        f"LocalStack test setup failed in category: {error.kind.value}"
    ) from None
```

## Timeout ownership

| Wrapper | Timeout contract |
| --- | --- |
| `RedisServer` | `startup_timeout` bounds individual image/start/readiness operations; it is not one total deadline. |
| `PostgresServer` | No wrapper timeout is advertised because Testcontainers 4.14.2 exposes no public PostgreSQL readiness-timeout input. |
| `LocalStackServer` | `startup_timeout` is passed only to provider readiness-log waiting; Docker client creation, image acquisition, and container creation are outside it. |
| CI service job | `timeout-minutes: 30` is an outer workflow safety cap, not a wrapper API guarantee. |

## Docker operations and orphan cleanup

Use `docker info` as the runtime preflight. Pull trusted pinned images explicitly
when needed:

```bash
docker pull postgres:18-alpine
docker pull localstack/localstack:4.14.0
```

PostgreSQL and LocalStack use provider-owned Ryuk when Testcontainers enables
it. Ryuk may persist process-wide, while each wrapper removes only its service
container. Managed service containers carry these labels:

- `com.bluetape.testcontainers.postgres=true`
- `com.bluetape.testcontainers.localstack=true`

After an abnormal process exit, inspect the relevant label, confirm both image
and container identity, and remove only that confirmed service container:

```bash
docker ps -a --filter label=com.bluetape.testcontainers.postgres=true
docker ps -a --filter label=com.bluetape.testcontainers.localstack=true
```

Never remove Ryuk through these service-label procedures.

## Redis compatibility

Redis-only callers need no code or dependency change. `RedisServer`, its error
text, and root `bluetape[testcontainers]` behavior remain unchanged. It uses
`redis:8`, owns bounded per-operation image/start/readiness work, publishes a
dynamic loopback port, and does not initialize Ryuk. Its service label remains
`com.bluetape.testcontainers.redis=true`; callers own Redis key cleanup and any
client lifecycle.

Docker-backed tests require a Docker-compatible runtime and run serially:

```bash
uv run --package bluetape-testcontainers --extra all --group test --python 3.13.14 pytest \
  -m testcontainers packages/bluetape-testcontainers -q
```
