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

with RedisServer() as redis:
    configure_test(redis_url=redis.url)
```

- Default image: `redis:8`
- Dynamic host port only
- Explicit `start()`/`close()` or context-manager ownership
- Image pull and `redis-cli ping` readiness bounded by `startup_timeout`
- Docker-backed suites run serially
- Explicit tagged or digest image overrides are allowed; `latest` is rejected

Construction does not access Docker. After `start()` succeeds, `host`, `port`,
`url`, and immutable `details` describe the mapped endpoint until `close()`.
A server instance is single-use: repeated `start()` while running is safe, but
starting again after close is rejected.

If container termination fails, the wrapper retains the container reference.
Call `close()` again to retry cleanup; it becomes a no-op only after termination
succeeds.

Startup failures raise `TestcontainerStartError` with one stable
`StartFailureKind`: `runtime-unavailable`, `image-pull`, `readiness-timeout`, or
`wrapper-failure`. Provider diagnostics stay in the exception cause instead of
the public error text.

Docker-backed tests require a Docker-compatible runtime and must run serially:

```bash
uv run pytest -m testcontainers packages/bluetape-testcontainers -q
```
