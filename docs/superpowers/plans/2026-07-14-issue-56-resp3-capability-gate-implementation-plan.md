# Issue #56 RESP3 Public Capability Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that redis-py 8.0.1 can receive, lose, reconnect, and cleanly stop RESP3 `CLIENT TRACKING` invalidation readers in both synchronous and asynchronous modes using public APIs only.

**Architecture:** Keep Gate 0 outside production modules. A Testcontainers integration test acquires a dedicated raw connection from a distinct public `ConnectionPool`, enables `CLIENT TRACKING ON BCAST PREFIX`, and consumes pushes with public `read_response(push_request=True)`. The observed result is recorded in a durable research artifact; PASS authorizes a separate production implementation plan, while either-mode failure records an upstream blocker and stops issue #56 implementation.

**Tech Stack:** Python 3.13.14, redis-py 8.0.1, Redis 8, pytest 9, pytest-asyncio, `bluetape-testcontainers`, `uv`.

---

## Scope Boundary

This plan implements only the all-or-nothing capability gate approved in the
design spec:

- sync idle push consumption through a dedicated RESP3 connection;
- async idle push consumption through a dedicated RESP3 connection;
- key and full-cache invalidation payload shapes;
- connection-loss detection, reconnect, tracking re-enable, and new push
  delivery;
- deterministic thread/task and connection cleanup;
- static proof that no private redis-py hook was used;
- a durable PASS or BLOCKED research result.

This plan does not add public near-cache contracts, marker codecs, facades,
README claims, package exports, or production modules. Those details depend on
the transport shape observed here and belong in a second implementation plan
only after Gate 0 passes.

## Approved Inputs

- Design spec:
  `docs/superpowers/specs/2026-07-13-issue-56-resp3-near-cache-design.md`
- Design self-review:
  `docs/review/2026-07-13-issue-56-resp3-near-cache-design-review.md`
- Issue: <https://github.com/bluetape4k/bluetape-py/issues/56>
- Redis command reference:
  <https://redis.io/docs/latest/commands/client-tracking/>
- redis-py RESP3 reference:
  <https://redis.readthedocs.io/en/stable/resp3_features.html>
- Locked versions: redis-py 8.0.1 and `redis:8`.

## File Map

| Path | Responsibility |
|---|---|
| `packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py` | Disposable-but-committed public-API integration contract for sync, async, reconnect, payloads, and cleanup |
| `docs/superpowers/research/2026-07-14-issue-56-redis-py-resp3-capability.md` | Durable PASS/BLOCKED decision with exact public APIs, versions, commands, and stop/next action |

No file under `packages/bluetape-cache-redis/src/` changes in this plan.

## Gate Decision

Gate 0 is conjunctive:

```text
PASS = sync passes AND async passes AND reconnect passes AND cleanup passes
```

If any required test fails because public redis-py cannot express the behavior,
the executor must:

1. preserve the failing test as reproducible evidence;
2. write the BLOCKED research artifact;
3. run the static private-API audit and `git diff --check`;
4. commit the evidence;
5. stop without creating production files.

Testcontainers runtime unavailability or the known host-port readiness race is
an environment failure, not an API blocker. Re-run the focused container test
once after confirming Docker health. If the environment still cannot run Redis,
report an execution blocker without classifying redis-py capability.

### Task 1: Reconfirm the isolated baseline and public API signatures

**Files:**

- Inspect: `docs/superpowers/specs/2026-07-13-issue-56-resp3-near-cache-design.md`
- Inspect: `.venv/lib/python3.13/site-packages/redis/connection.py`
- Inspect: `.venv/lib/python3.13/site-packages/redis/asyncio/connection.py`
- Modify: none

- [ ] **Step 1: Confirm branch, worktree, and clean state**

Run:

```bash
git branch --show-current
git status --short --branch
git worktree list
```

Expected:

```text
feat/issue-56-resp3-near-cache
## feat/issue-56-resp3-near-cache
```

The worktree list must associate this branch with
`.worktrees/issue-56-resp3-near-cache`.

- [ ] **Step 2: Reinstall the locked complete baseline environment**

Run:

```bash
uv sync --all-packages --extra fory --extra native --python 3.13.14 --locked
```

Expected: exit 0 with redis-py 8.0.1, pytest, pytest-asyncio,
`bluetape-testcontainers`, `pyfory`, `lz4`, `cramjam`, and `zstandard`
available.

- [ ] **Step 3: Verify the exact public sync/async signatures used by Gate 0**

Run:

```bash
.venv/bin/python - <<'PY'
import inspect
from redis.asyncio.connection import Connection as AsyncConnection
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool
from redis.connection import Connection as SyncConnection
from redis.connection import ConnectionPool as SyncConnectionPool

expected = {
    "SyncConnection.read_response": "push_request=False",
    "AsyncConnection.read_response": "push_request: Optional[bool] = False",
    "SyncConnectionPool.get_connection": "command_name=None",
    "AsyncConnectionPool.get_connection": "command_name=None",
}
actual = {
    "SyncConnection.read_response": str(inspect.signature(SyncConnection.read_response)),
    "AsyncConnection.read_response": str(inspect.signature(AsyncConnection.read_response)),
    "SyncConnectionPool.get_connection": str(
        inspect.signature(SyncConnectionPool.get_connection)
    ),
    "AsyncConnectionPool.get_connection": str(
        inspect.signature(AsyncConnectionPool.get_connection)
    ),
}
for name, fragment in expected.items():
    print(name, actual[name])
    assert fragment in actual[name]
PY
```

Expected: four signatures print and the process exits 0. This is inspection
evidence only; it does not pass Gate 0 without real Redis delivery.

- [ ] **Step 4: Run the complete pre-change baseline**

Run:

```bash
uv run pytest
```

Expected: `1515 passed`. If only
`test_redis_8_server_supports_dynamic_port_and_resp_round_trip` fails once with
host `ConnectionRefusedError`, confirm `docker info`, rerun that exact test, then
rerun the full suite. Do not change RedisServer in this issue.

### Task 2: Add the shared capability-test harness and sync key-push proof

**Files:**

- Create: `packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py`

- [ ] **Step 1: Write the sync capability test before its helpers**

Create this initial file:

```python
from __future__ import annotations

from collections.abc import Iterator

import pytest
import redis
from bluetape.testcontainers import RedisServer
from bluetape.testing import eventually

pytestmark = pytest.mark.testcontainers

_IO_TIMEOUT = 2.0


@pytest.fixture(scope="module")
def redis_url() -> Iterator[str]:
    with RedisServer() as server:
        def host_is_ready() -> bool:
            client = redis.Redis.from_url(
                server.url,
                protocol=3,
                decode_responses=False,
                socket_connect_timeout=_IO_TIMEOUT,
                socket_timeout=_IO_TIMEOUT,
                retry_on_timeout=False,
            )
            try:
                return bool(client.ping())
            except redis.RedisError:
                return False
            finally:
                client.close()

        eventually(host_is_ready, timeout=1.0, interval=0.01)
        yield server.url


def test_sync_public_resp3_reader_receives_peer_marker_push(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLXN5bmM:"
    marker_key = prefix + b"b3JkZXItNDI"
    command = sync_command_client(redis_url)
    try:
        with sync_tracking_reader(redis_url, prefix) as reader:
            assert reader.pool is not command.connection_pool
            assert command.set(marker_key, b"mutation-token", px=60_000) is True
            response = reader.connection.read_response(
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert_key_push(response, marker_key)
    finally:
        command.close()
```

- [ ] **Step 2: Run the sync test to verify RED**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py::test_sync_public_resp3_reader_receives_peer_marker_push -vv
```

Expected: FAIL with `NameError: name 'sync_command_client' is not defined`.
The Redis fixture must reach ready state first, proving the failure is the
missing helper rather than container startup.

- [ ] **Step 3: Add the complete public sync helpers**

Add these imports:

```python
from contextlib import contextmanager
from dataclasses import dataclass

from redis.connection import Connection as SyncConnection
from redis.connection import ConnectionPool as SyncConnectionPool
```

Insert before the test:

```python
def sync_command_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
    )


def sync_reader_pool(url: str) -> SyncConnectionPool:
    return SyncConnectionPool.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
        max_connections=1,
    )


@dataclass(frozen=True, slots=True)
class SyncReader:
    pool: SyncConnectionPool
    connection: SyncConnection
    client_id: int


@contextmanager
def sync_tracking_reader(url: str, prefix: bytes) -> Iterator[SyncReader]:
    pool = sync_reader_pool(url)
    connection = pool.get_connection()
    try:
        connection.connect()
        connection.send_command("CLIENT", "TRACKING", "ON", "BCAST", "PREFIX", prefix)
        assert connection.read_response() == b"OK"
        connection.send_command("CLIENT", "ID")
        client_id = connection.read_response()
        assert type(client_id) is int
        yield SyncReader(pool=pool, connection=connection, client_id=client_id)
    finally:
        connection.disconnect()
        pool.release(connection)
        pool.disconnect()


def assert_key_push(response: object, marker_key: bytes) -> None:
    assert response == [b"invalidate", [marker_key]]
```

- [ ] **Step 4: Run the sync test to verify GREEN**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py::test_sync_public_resp3_reader_receives_peer_marker_push -vv
```

Expected on PASS: one test passes and the response is exactly
`[b"invalidate", [marker_key]]`.

If it fails because `push_request=True` cannot receive the push without a
private parser hook, record the exact test name and exception for Task 6's
BLOCKED artifact. A sync failure already means the final decision cannot be
PASS, but run the async proof before classifying the complete public boundary.

- [ ] **Step 5: Commit the sync proof when it passes**

```bash
git add packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
git commit -m "test: prove sync RESP3 tracking push capability"
```

### Task 3: Add the async key-push proof

**Files:**

- Modify: `packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py`

- [ ] **Step 1: Write the failing async key-push test first**

Append this test before adding any async helper:

```python
@pytest.mark.asyncio
async def test_async_public_resp3_reader_receives_peer_marker_push(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLWFzeW5j:"
    marker_key = prefix + b"b3JkZXItNDI"
    command = async_command_client(redis_url)
    try:
        async with async_tracking_reader(redis_url, prefix) as reader:
            assert reader.pool is not command.connection_pool
            assert await command.set(marker_key, b"mutation-token", px=60_000) is True
            response = await reader.connection.read_response(
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert_key_push(response, marker_key)
    finally:
        await command.aclose()
```

- [ ] **Step 2: Run the async test to verify RED**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py::test_async_public_resp3_reader_receives_peer_marker_push -vv
```

Expected: FAIL with `NameError: name 'async_command_client' is not defined`.
This proves the async test is collected and fails for the missing public helper,
not because it was skipped.

- [ ] **Step 3: Add public async imports, client, pool, and reader helpers**

Change the collection/context imports to:

```python
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
```

Add these imports beside the sync redis-py imports:

```python
import redis.asyncio as redis_async
from redis.asyncio.connection import Connection as AsyncConnection
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool
```

Insert after `sync_tracking_reader`:

```python
def async_command_client(url: str) -> redis_async.Redis:
    return redis_async.Redis.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
    )


def async_reader_pool(url: str) -> AsyncConnectionPool:
    return AsyncConnectionPool.from_url(
        url,
        protocol=3,
        decode_responses=False,
        socket_connect_timeout=_IO_TIMEOUT,
        socket_timeout=_IO_TIMEOUT,
        retry_on_timeout=False,
        max_connections=1,
    )


@dataclass(frozen=True, slots=True)
class AsyncReader:
    pool: AsyncConnectionPool
    connection: AsyncConnection
    client_id: int


@asynccontextmanager
async def async_tracking_reader(url: str, prefix: bytes) -> AsyncIterator[AsyncReader]:
    pool = async_reader_pool(url)
    connection = await pool.get_connection()
    try:
        await connection.connect()
        await connection.send_command(
            "CLIENT",
            "TRACKING",
            "ON",
            "BCAST",
            "PREFIX",
            prefix,
        )
        assert await connection.read_response() == b"OK"
        await connection.send_command("CLIENT", "ID")
        client_id = await connection.read_response()
        assert type(client_id) is int
        yield AsyncReader(pool=pool, connection=connection, client_id=client_id)
    finally:
        await connection.disconnect()
        await pool.release(connection)
        await pool.disconnect()
```

- [ ] **Step 4: Run the async test to verify GREEN**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py::test_async_public_resp3_reader_receives_peer_marker_push -vv
```

Expected on PASS: one async test passes and receives the exact key push through
`AsyncConnection.read_response(push_request=True)`.

- [ ] **Step 5: Run the complete sync/async key-push proof**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -vv
```

Expected on PASS: two tests pass. If async times out, returns `None`, or requires
an underscore-prefixed redis-py hook, Gate 0 is BLOCKED even if sync passed.

- [ ] **Step 6: Commit the async proof when it passes**

```bash
git add packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
git commit -m "test: prove async RESP3 tracking push capability"
```

### Task 4: Prove full-flush payloads and public reconnect

**Files:**

- Modify: `packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py`

- [ ] **Step 1: Add sync full-flush payload coverage**

Append:

```python
def test_sync_public_reader_receives_full_flush_payload(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLWZsdXNoLXN5bmM:"
    command = sync_command_client(redis_url)
    try:
        with sync_tracking_reader(redis_url, prefix) as reader:
            assert command.flushdb() is True
            response = reader.connection.read_response(
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert response == [b"invalidate", None]
    finally:
        command.close()
```

- [ ] **Step 2: Add async full-flush payload coverage**

Append:

```python
@pytest.mark.asyncio
async def test_async_public_reader_receives_full_flush_payload(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLWZsdXNoLWFzeW5j:"
    command = async_command_client(redis_url)
    try:
        async with async_tracking_reader(redis_url, prefix) as reader:
            assert await command.flushdb() is True
            response = await reader.connection.read_response(
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert response == [b"invalidate", None]
    finally:
        await command.aclose()
```

- [ ] **Step 3: Add the sync loss/reconnect proof**

Add this import:

```python
from concurrent.futures import ThreadPoolExecutor
```

Append:

```python
def test_sync_public_reader_detects_loss_and_reconnects(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLXJlY29ubmVjdC1zeW5j:"
    marker_key = prefix + b"b3JkZXItNDI"
    command = sync_command_client(redis_url)
    pool = sync_reader_pool(redis_url)
    connection = pool.get_connection()
    try:
        connection.connect()
        connection.send_command("CLIENT", "TRACKING", "ON", "BCAST", "PREFIX", prefix)
        assert connection.read_response() == b"OK"
        connection.send_command("CLIENT", "ID")
        client_id = connection.read_response()
        assert type(client_id) is int

        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="resp3-capability") as executor:
            waiting = executor.submit(
                connection.read_response,
                timeout=_IO_TIMEOUT,
                push_request=True,
            )
            assert command.execute_command("CLIENT", "KILL", "ID", client_id) == 1
            with pytest.raises(redis.ConnectionError):
                waiting.result(timeout=_IO_TIMEOUT + 1.0)

        connection.connect()
        connection.send_command("CLIENT", "TRACKING", "ON", "BCAST", "PREFIX", prefix)
        assert connection.read_response() == b"OK"
        assert command.set(marker_key, b"after-reconnect", px=60_000) is True
        assert_key_push(
            connection.read_response(timeout=_IO_TIMEOUT, push_request=True),
            marker_key,
        )
    finally:
        connection.disconnect()
        pool.release(connection)
        pool.disconnect()
        command.close()
```

- [ ] **Step 4: Add the async loss/reconnect proof**

Add this import at the top before appending the test:

```python
import asyncio
```

Append:

```python
@pytest.mark.asyncio
async def test_async_public_reader_detects_loss_and_reconnects(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLXJlY29ubmVjdC1hc3luYw:"
    marker_key = prefix + b"b3JkZXItNDI"
    command = async_command_client(redis_url)
    pool = async_reader_pool(redis_url)
    connection = await pool.get_connection()
    try:
        await connection.connect()
        await connection.send_command(
            "CLIENT",
            "TRACKING",
            "ON",
            "BCAST",
            "PREFIX",
            prefix,
        )
        assert await connection.read_response() == b"OK"
        await connection.send_command("CLIENT", "ID")
        client_id = await connection.read_response()
        assert type(client_id) is int

        waiting = asyncio.create_task(
            connection.read_response(timeout=_IO_TIMEOUT, push_request=True),
            name="resp3-capability-read",
        )
        assert await command.execute_command("CLIENT", "KILL", "ID", client_id) == 1
        with pytest.raises(redis.ConnectionError):
            await waiting

        await connection.connect()
        await connection.send_command(
            "CLIENT",
            "TRACKING",
            "ON",
            "BCAST",
            "PREFIX",
            prefix,
        )
        assert await connection.read_response() == b"OK"
        assert await command.set(marker_key, b"after-reconnect", px=60_000) is True
        assert_key_push(
            await connection.read_response(timeout=_IO_TIMEOUT, push_request=True),
            marker_key,
        )
    finally:
        await connection.disconnect()
        await pool.release(connection)
        await pool.disconnect()
        await command.aclose()
```

- [ ] **Step 5: Run the six capability tests**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -vv
```

Expected on PASS: six tests pass. Both reconnect tests must observe a public
`redis.ConnectionError`, reconnect the same public connection object, re-enable
tracking, and receive a new key push.

- [ ] **Step 6: Commit payload and reconnect evidence when all six pass**

```bash
git add packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
git commit -m "test: prove RESP3 tracking reconnect capability"
```

### Task 5: Prove cleanup and audit the public-only boundary

**Files:**

- Modify: `packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py`

- [ ] **Step 1: Add a public server-side connection lookup helper**

Change the testing-helper import to:

```python
from bluetape.testing import eventually, eventually_async
```

Insert before the tests:

```python
def connected_client_ids(command: redis.Redis) -> set[int]:
    return {
        int(entry["id"])
        for entry in command.client_list()
        if "id" in entry
    }
```

- [ ] **Step 2: Add sync normal-cleanup coverage**

Append:

```python
def test_sync_reader_cleanup_closes_server_connection(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLWNsZWFudXAtc3luYw:"
    command = sync_command_client(redis_url)
    try:
        with sync_tracking_reader(redis_url, prefix) as reader:
            reader_id = reader.client_id
            assert reader_id in connected_client_ids(command)
        assert eventually(
            lambda: reader_id not in connected_client_ids(command),
            timeout=_IO_TIMEOUT,
            interval=0.01,
        ) is True
    finally:
        command.close()
```

- [ ] **Step 3: Add async normal-cleanup coverage**

Append:

```python
@pytest.mark.asyncio
async def test_async_reader_cleanup_closes_server_connection(redis_url: str) -> None:
    prefix = b"bluetape:near:Y2FwLWNsZWFudXAtYXN5bmM:"
    command = async_command_client(redis_url)
    try:
        async with async_tracking_reader(redis_url, prefix) as reader:
            reader_id = reader.client_id
            clients = await command.client_list()
            assert reader_id in {int(entry["id"]) for entry in clients if "id" in entry}

        async def reader_is_gone() -> bool:
            clients = await command.client_list()
            return reader_id not in {
                int(entry["id"])
                for entry in clients
                if "id" in entry
            }

        assert await eventually_async(
            reader_is_gone,
            timeout=_IO_TIMEOUT,
            interval=0.01,
        ) is True
    finally:
        await command.aclose()
```

- [ ] **Step 4: Run focused cleanup and complete capability tests**

Run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -vv
```

Expected on PASS: eight tests pass with no pending asyncio-task warning and no
hanging `resp3-capability` executor thread.

- [ ] **Step 5: Run the static forbidden-technique audit**

Run:

```bash
if rg -n '_parser|set_invalidation_push_handler|monkeypatch|execute_command\("SUBSCRIBE"|PubSub' packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py; then
  exit 1
fi
```

Expected: no matches and exit 0.

Then run:

```bash
rg -n 'ConnectionPool|connect\(|send_command\(|read_response\(|disconnect\(|release\(' packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
```

Expected: only public pool/connection methods appear in the integration proof.

- [ ] **Step 6: Run focused style checks**

```bash
uv run ruff check packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
uv run ruff format packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
uv run ruff format --check packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
git diff --check
```

Expected: Ruff reports no lint findings, formats the test if needed, and the
post-format check plus `git diff --check` exit 0.

- [ ] **Step 7: Commit cleanup and public-only audit evidence**

```bash
git add packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
git commit -m "test: verify RESP3 reader cleanup"
```

### Task 6: Record the PASS or BLOCKED decision

**Files:**

- Create: `docs/superpowers/research/2026-07-14-issue-56-redis-py-resp3-capability.md`

- [ ] **Step 1A: If all eight tests pass, write the PASS artifact**

Create the file with this content:

```markdown
# Issue #56 redis-py RESP3 Public Capability Result

## Decision

PASS. redis-py 8.0.1 and Redis 8 provide sufficient public synchronous and
asynchronous APIs for the issue #56 production design.

## Proven Public Surface

- `redis.connection.ConnectionPool.from_url()`
- `redis.asyncio.connection.ConnectionPool.from_url()`
- `ConnectionPool.get_connection()` and `release()`
- `Connection.connect()` and `disconnect()`
- `Connection.send_command()`
- `Connection.read_response(push_request=True)`
- `Redis.execute_command()` for test-only `CLIENT KILL`
- `Redis.client_list()` for cleanup evidence

No parser object, invalidation handler hook, monkey patch, Pub/Sub channel, or
keyspace notification was used.

## Runtime Evidence

- Python: 3.13.14
- redis-py: 8.0.1
- Redis image: `redis:8`
- Sync key push: passed
- Async key push: passed
- Sync full flush: passed
- Async full flush: passed
- Sync loss and reconnect: passed
- Async loss and reconnect: passed
- Sync connection cleanup: passed
- Async connection cleanup: passed

Command:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -vv
```

Result: 8 passed.

## Production Planning Consequence

The production constructor should accept a borrowed command `Redis` client and
a distinct borrowed reader `ConnectionPool`; `from_url()` should create and own
both pools. The reader worker can consume pushes directly through the public
connection API. A separate production implementation plan may now define the
marker codec, contracts, fail-closed state machine, sync thread, async task,
facades, integration tests, packaging checks, and bilingual documentation.
```

- [ ] **Step 1B: If a required capability test fails, write the BLOCKED artifact instead**

Create the file with this content. After `## Reproduction`, append pytest's
single failing-node summary line verbatim; that executable line identifies the
mode and public exception without copying secrets or arbitrary traceback text.

```markdown
# Issue #56 redis-py RESP3 Public Capability Result

## Decision

BLOCKED. redis-py 8.0.1 and Redis 8 did not provide the complete public
sync/async capability required by issue #56.

## Reproduction

Command:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -vv
```

The focused capability suite exits nonzero at a required public sync or async
boundary. The failing-node summary from pytest follows this paragraph.

## Boundary Audit

The proof did not access `_parser`, `set_invalidation_push_handler`, another
underscore-prefixed redis-py object, monkey patches, Pub/Sub, keyspace
notifications, or polling.

## Stop Decision

Issue #56 production implementation stops here. Do not add a sync-only facade,
private parser integration, or degraded substitute. Revisit after an upstream
redis-py release documents a public API that satisfies the failing capability.
```

Append only the one-line pytest failure summary, for example a line beginning
with `FAILED packages/bluetape-cache-redis/tests/`. Do not include endpoint
URLs, keys, credentials, or arbitrary exception messages.

- [ ] **Step 2: Verify the artifact agrees with executable evidence**

For PASS, run:

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -q
rg -n '^PASS|Result: 8 passed|Connection.read_response' docs/superpowers/research/2026-07-14-issue-56-redis-py-resp3-capability.md
```

Expected: `8 passed`, followed by the PASS decision and public API lines.

For BLOCKED, rerun the exact failing node and confirm it fails in the same
public capability boundary before committing. Do not continue to Task 7's PASS
branch.

- [ ] **Step 3: Commit the durable gate result**

PASS commit:

```bash
git add packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py docs/superpowers/research/2026-07-14-issue-56-redis-py-resp3-capability.md
git commit -m "docs: record issue 56 RESP3 capability pass"
```

BLOCKED commit:

```bash
git add packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py docs/superpowers/research/2026-07-14-issue-56-redis-py-resp3-capability.md
git commit -m "docs: record issue 56 RESP3 capability blocker"
```

### Task 7: Close the Gate 0 phase

**Files:**

- Verify: `packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py`
- Verify: `docs/superpowers/research/2026-07-14-issue-56-redis-py-resp3-capability.md`
- Modify: none

- [ ] **Step 1: Run focused final verification**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py -vv
uv run ruff check packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
uv run ruff format --check packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py
git diff --check develop...HEAD
```

Expected on PASS: eight tests pass and every static command exits 0.

Expected on BLOCKED: the focused failing capability remains reproducible; Ruff
and `git diff --check` still exit 0. A failing capability test is intentional
blocker evidence and must not be reported as a passing branch.

- [ ] **Step 2: Run repository regression verification only on PASS**

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected: `1523 passed`, followed by clean Ruff output. If the existing
RedisServer host-port race occurs once, follow Task 1's diagnostic rule and
rerun the full suite after the focused test passes.

- [ ] **Step 3: Confirm scope and history**

```bash
git status --short --branch
git diff --name-only 6c81930..HEAD
git log --oneline --decorate --max-count=8
```

Expected: the worktree is clean. Gate 0 changes are limited to the capability
test and research artifact, in addition to the already-approved spec, review,
and this plan.

- [ ] **Step 4: Apply the stop or handoff rule**

On PASS: request user approval of the capability result, then run a new
`writing-plans` pass for production contracts, marker protocol, sync/async
tracking workers, fail-closed facades, integration/fault tests, packaging,
bilingual docs, and final P0/P1 review.

On BLOCKED: report the exact missing public capability and stop issue #56 work.
Do not create a production plan unless the user explicitly changes the approved
private-API prohibition or redis-py gains the required public API.

## Completion Checklist

- [ ] Sync idle key invalidation received through public APIs.
- [ ] Async idle key invalidation received through public APIs.
- [ ] Sync and async full-flush payloads observed.
- [ ] Sync and async connection loss detected.
- [ ] Sync and async reconnect, tracking re-enable, and new delivery observed.
- [ ] Normal cleanup removes reader connections from Redis.
- [ ] No private parser/hook, monkey patch, Pub/Sub, notification, or polling.
- [ ] PASS or BLOCKED artifact matches executable evidence.
- [ ] PASS proceeds only to user review and a second production plan.
- [ ] BLOCKED stops without production code.
