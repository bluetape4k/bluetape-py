# bluetape-testcontainers

English | [한국어](README.ko.md)

`bluetape-testcontainers` owns reusable Docker-backed test server boundaries for
the bluetape Python ecosystem. It is test infrastructure, not a production
Redis client package.

## Install

PyPI publication is currently on hold. The intended install shape is:

```bash
pip install "bluetape[testcontainers]"
# or
pip install bluetape-testcontainers
```

The default `bluetape` install remains provider-free. Testcontainers and the
Docker SDK are installed only through the explicit extra or focused package.
The wrapper does not depend on redis-py.

## Redis

```python
from bluetape.testcontainers import RedisServer

with RedisServer() as server:
    print(server.url)
```

- Default image: `redis:8`
- Dynamic host port only
- Explicit `start()`/`close()` or context-manager ownership
- Cached image lookup, missing-image pull, and `redis-cli ping` readiness
  bounded per operation by `startup_timeout`
- Docker-backed suites run serially
- Explicit tagged or digest image overrides are allowed; `latest` is rejected

`RedisServer` does not initialize Testcontainers Ryuk. It uses the provider's
core container and Docker client while owning bounded image acquisition,
startup, readiness, and cleanup itself. Managed containers carry the
`com.bluetape.testcontainers.redis=true` label. An abnormal Python process exit
can leave a labeled container behind; inspect it with
`docker ps -a --filter label=com.bluetape.testcontainers.redis=true` and remove
only the confirmed test container.

Image overrides are executable test infrastructure. Accept them only from
trusted configuration, never from untrusted PR or request input. Prefer a
digest reference when CI requires immutable evidence.

Construction does not access Docker. After `start()` succeeds, `host`, `port`,
`url`, and immutable `details` describe the mapped endpoint until `close()`.
A server instance is single-use: repeated `start()` while running is safe, but
starting again after close is rejected. `RedisServer` is not thread-safe; one
fixture or caller must own each instance.

If container termination fails, the wrapper retains the container reference.
Call `close()` again to retry cleanup; it becomes a no-op only after termination
succeeds.

Startup failures raise `TestcontainerStartError` with one stable
`StartFailureKind`: `runtime-unavailable`, `image-pull`, `readiness-timeout`, or
`wrapper-failure`. Raw provider diagnostics are suppressed from both the public
message and traceback because they can contain daemon paths, credentials, or
registry responses.

For sanitized startup troubleshooting, verify runtime reachability with
`docker info` and, when the image is absent, try an explicit trusted
`docker pull redis:8`. These checks keep credentials and raw provider responses
outside the wrapper's public errors.

## Pytest integration

The package does not register a pytest plugin or automatic fixture. Consumers
choose the ownership scope explicitly:

```python
import pytest

from bluetape.testcontainers import RedisServer


@pytest.fixture(scope="session")
def redis_server():
    with RedisServer() as server:
        yield server
```

The consumer owns fixture scope and Redis key cleanup between tests.

Docker-backed tests require a Docker-compatible runtime and must run serially:

```bash
uv run pytest -m testcontainers packages/bluetape-testcontainers -q
```
