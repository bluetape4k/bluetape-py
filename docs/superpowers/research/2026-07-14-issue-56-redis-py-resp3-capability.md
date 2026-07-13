# Issue #56 redis-py RESP3 Public Capability Result

## Decision

**BLOCKED.** redis-py 8.0.1 with Redis 8 does not expose the complete public
sync and async boundary required for RESP3 client-tracking invalidation.

## Runtime Evidence

- Environment: Python 3.13.14, redis-py 8.0.1, and Redis 8.
- Sync: tracking returned `OK`, the peer marker `SET` succeeded, and public
  `read_response(timeout=2.0, push_request=True)` returned `None`; the exact
  invalidation assertion failed.
- Async: tracking returned `OK`, the peer marker `SET` succeeded, and public
  `read_response(timeout=2.0, push_request=True)` returned `None`; the exact
  invalidation assertion failed.

Both focused proofs were real Testcontainers tests. Their intentional failures
are blocker evidence; no overall PASS is claimed.

## Public Surface Tested

- `redis.Redis.from_url` and `redis.asyncio.Redis.from_url`.
- Sync and async `ConnectionPool.from_url`, `get_connection`, `release`, and
  `disconnect`.
- Sync and async `Connection.connect`, `send_command`,
  `read_response(push_request=True)`, and `disconnect`.

## Root Cause Boundary

The connection forwards `push_request` to the RESP3 parser. The parser
dispatches an invalidation push and returns the invalidation handler result;
without a handler, that result is `None`. The handler setter is reachable only
through the private parser, and redis-py's own cache integration reaches it
through private `conn._parser`. No public invalidation-handler registration
route was found on `Connection`, `ConnectionPool`, or `Redis` in either the
sync or async API.

## Reproduction

```bash
uv run pytest \
  packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py::test_sync_public_resp3_reader_receives_peer_marker_push \
  packages/bluetape-cache-redis/tests/test_resp3_tracking_capability.py::test_async_public_resp3_reader_receives_peer_marker_push \
  -vv
```

Result: `2 failed`.

- `test_resp3_tracking_capability.py::test_sync_public_resp3_reader_receives_peer_marker_push`
- `test_resp3_tracking_capability.py::test_async_public_resp3_reader_receives_peer_marker_push`

For both failures, the stable observed fact was `response=None`. Endpoint URLs,
marker keys, credentials, and arbitrary traceback details are intentionally
omitted.

## Boundary Audit

The proof uses no private parser or hook, monkeypatch, Pub/Sub, keyspace
notifications, polling, or sync-only fallback.

## Downstream Proofs Not Run

Task 4 full-flush/reconnect and Task 5 expanded runtime-cleanup proofs were not
run under the conjunctive Gate stop rule. Post-reconnect and full-flush
delivery depend on the already-blocked key-push primitive, so those proofs
cannot change the decision. They did not pass and are not claimed as passing.
On the observed post-setup assertion-failure path, the context managers close
the command client, reader connection, and connection pool. Acquisition and
setup failures were not proven leak-free.

## Stop Decision

Do not add a sync-only facade, private integration, or production code. Revisit
Issue #56 only after redis-py exposes a documented public sync and async
invalidation-handler or invalidation-consumer surface.

This branch and commit are intentionally stopped, non-mergeable evidence. The
two normally collected pytest probes remain deliberately red, so no PR or merge
into `develop` should be created from this state. Any future integration first
requires changed upstream public API support and an approved quarantine or
opt-in strategy for the probes.
