# Issue #56 RESP3 Near-Cache Invalidation Design

**Status:** conversation design approved; document review pending  
**Issue:** [#56](https://github.com/bluetape4k/bluetape-py/issues/56)  
**Parent:** [#51](https://github.com/bluetape4k/bluetape-py/issues/51)  
**Date:** 2026-07-13

## Summary

Add opt-in synchronous and asynchronous near-cache facades to
`bluetape-cache-redis`. Application values remain in the process-local cache.
Redis stores only short-lived marker metadata, and RESP3 `CLIENT TRACKING` push
messages invalidate local entries across processes.

The public facades own their local cache so callers cannot bypass readiness
gating. A dedicated RESP3 reader connection receives
`CLIENT TRACKING ON BCAST PREFIX <namespace>:` invalidations, while a separate
command client writes marker keys after authoritative application data has
changed. Tracking failure is fail-closed: the complete local cache is cleared,
local reads and population stop, and caching resumes only after tracking has
been restored and the cache has been cleared again.

Implementation begins with a strict redis-py public-API capability gate. Both
sync and async push delivery and reconnect must be proven with Testcontainers.
Private parser hooks, private connection attributes, monkey patches, and a
sync-only fallback are prohibited. If public API parity cannot be proven, the
feature stops as an upstream blocker rather than shipping a partial contract.

## Context

Issue #50 established stdlib-only `TTLCache` and `AsyncTTLCache` contracts with
bounded entries, TTL expiry, same-key load coalescing, and generation fencing.
Issues #54 and #55 added the opt-in Redis provider and distributed load
coordination without adding distributed invalidation. Issue #56 is deliberately
separate from both durable Redis caching and load coordination.

Process-local caches become stale when another process changes authoritative
data. Application-level Redis Pub/Sub could distribute invalidation messages,
but it introduces a separate channel protocol, origin envelope, and subscription
contract. Redis client tracking already exposes key invalidation through RESP3
push messages. BCAST mode allows a provider instance to subscribe to one marker
namespace without reading or storing application values in Redis.

The hard part is not marker `SET`; it is proving that redis-py exposes a stable
public push-consumption API for an otherwise idle dedicated connection in both
synchronous and asynchronous modes. The design therefore separates capability
proof from production implementation.

## Goals

- Provide Python-native sync and async near-cache APIs with equivalent behavior.
- Keep `bluetape-cache` stdlib-only and keep Redis optional.
- Invalidate peer local entries through RESP3 client tracking, not Pub/Sub.
- Store only bounded, short-lived marker metadata in Redis.
- Prevent stale in-flight loader results from repopulating invalidated entries.
- Fail closed whenever invalidation coverage is known to be unavailable.
- Make readiness, reconnect, shutdown, cancellation, and client ownership
  explicit and testable.
- Keep observer data low-cardinality and free of raw keys, marker values,
  namespaces, URLs, and provider exception text.

## Non-Goals

- Redis Pub/Sub channels or application-defined invalidation envelopes.
- Durable Redis L2 values or read-through application values in Redis.
- Cross-process load coordination; that remains the responsibility of #55.
- Global ordering, exactly-once delivery, or transactional coupling between the
  authoritative data store and Redis marker writes.
- Redis Cluster or Sentinel support in the first implementation.
- Framework-specific decorators or integrations.
- A general callback/listener surface in `bluetape-cache`.
- Private redis-py parser or connection integration.

## Reference Analysis

### Redis client tracking

`CLIENT TRACKING` is connection-scoped. In RESP3 mode invalidation is delivered
as a push message. `BCAST PREFIX` subscribes the reader connection to all writes
under the marker prefix, avoiding per-key read registration. `NOLOOP` is not
used because marker commands and push consumption occur on different
connections; origin correctness must not depend on connection-local origin
suppression.

Primary references:

- <https://redis.io/docs/latest/commands/client-tracking/>
- <https://redis.readthedocs.io/en/stable/resp3_features.html>

### `bluetape4k-cache-lettuce`

The Lettuce implementation is a behavioral and lifecycle reference, not an API
port. Useful mechanics are:

- a public `PushListener` attached to a stateful RESP3 connection;
- one lifecycle owner for tracking setup and listener removal;
- sync and suspend variants with equivalent invalidation tests;
- key invalidation, null/full-flush payload handling, namespace isolation, and
  idempotent duplicate delivery;
- ordering tracking readiness before relying on local cache contents.

The Python design intentionally differs in these areas:

- Lettuce uses default tracked-key registration and `NOLOOP`; #56 uses
  `BCAST PREFIX` over marker keys and does not use `NOLOOP`.
- Lettuce stores application values in Redis as a back cache; #56 stores only
  marker metadata.
- Lettuce logs tracking startup failure and continues serving the cache; #56
  clears and disables local caching.
- #56 uses a dedicated reader connection and a separate marker command client.
- #56 explicitly fences every in-flight loader and every readiness generation.

Relevant local references:

- `../bluetape4k-projects/cache/cache-lettuce/src/main/kotlin/io/bluetape4k/cache/nearcache/TrackingInvalidationListener.kt`
- `../bluetape4k-projects/cache/cache-lettuce/src/main/kotlin/io/bluetape4k/cache/nearcache/LettuceNearCache.kt`
- `../bluetape4k-projects/cache/cache-lettuce/src/main/kotlin/io/bluetape4k/cache/nearcache/LettuceSuspendNearCache.kt`
- `../bluetape4k-projects/cache/cache-lettuce/src/test/kotlin/io/bluetape4k/cache/nearcache/LettuceNearCacheTrackingTest.kt`
- `../bluetape4k-projects/cache/cache-lettuce/src/test/kotlin/io/bluetape4k/cache/nearcache/TrackingInvalidationListenerPayloadTest.kt`

### Retry and stale-completion compensation

The Lettuce near-cache retry compensation lesson reinforces a general rule:
completion and recovery from older work must not overwrite state installed by a
newer mutation. #56 applies the rule through the existing local cache
epoch/version fencing plus a near-cache readiness generation. A reconnect from
an older reader generation cannot mark a newer lifecycle generation ready, and
a loader started before degradation cannot publish afterward.

Reference:

- `../bluetape4k-projects/docs/lessons/2026-07-10-issue-785-near-cache-retry-compensation.md`

## Gate 0: redis-py Public Capability Proof

Gate 0 runs before production contracts or implementations are added. The spike
uses `bluetape-testcontainers` and the locked redis-py version. It may add a
disposable probe or focused research artifact, but it must not create a public
API that assumes an unproven transport.

### Required proofs

The sync and async proofs must each demonstrate all of the following using only
documented public redis-py APIs:

1. Create a dedicated RESP3 connection and a separate command connection.
2. Enable `CLIENT TRACKING ON BCAST PREFIX <probe-prefix>:` on the reader.
3. Keep the reader idle from the application's perspective while still
   consuming invalidation pushes.
4. Observe a marker `SET` from the command connection.
5. Decode a key invalidation and a full-cache invalidation payload without
   touching parser internals.
6. Detect reader connection loss.
7. Stop the old consumer, reconnect, reinstall public push handling, re-enable
   tracking, and observe a new marker invalidation.
8. Shut down without a reader thread, asyncio task, connection, or callback
   leak.

The proof must record the exact public API entry points and the redis-py version
under test. Source inspection alone is insufficient; real Redis delivery is
required.

### Forbidden techniques

- `connection._parser` or another underscore-prefixed redis-py attribute;
- `set_invalidation_push_handler` reached through a private object;
- monkey patching redis-py classes;
- depending on undocumented callback timing or parser implementation details;
- using redis-py's sync-only client-side value cache as the async design;
- replacing client tracking with Pub/Sub, keyspace notifications, or polling.

### Stop condition

Gate 0 passes only when both modes satisfy every required proof. If either mode
fails, implementation stops. The result is documented as an upstream capability
blocker with the tested version and missing public surface. No sync-only API,
private-hook implementation, or semantic downgrade is shipped under issue #56.

## Package Boundaries

`bluetape-cache` remains unchanged and stdlib-only. The new contracts and
facades belong to `bluetape-cache-redis`, which already owns the optional
redis-py dependency and depends on `bluetape-cache`.

The near-cache facade creates and owns its `TTLCache` or `AsyncTTLCache` rather
than accepting an externally reusable cache instance. This prevents callers
from reading or populating the same local cache behind the readiness gate.

Internal concerns stay separated:

- marker key codec and validation;
- immutable options, status, events, and stable errors;
- sync/async tracking transport adapters proven by Gate 0;
- lifecycle/readiness state machines;
- bounded push dispatch;
- marker command execution;
- public sync/async facades.

No near-cache symbol is re-exported from the root `bluetape` distribution unless
the existing optional-extra packaging rules explicitly install
`bluetape-cache-redis`.

## Public Contracts

Names below are the approved semantic shape. Exact import ordering and typing
syntax may be refined by the implementation plan without weakening the
contract.

### Key codec

```python
class NearCacheKeyCodec[K](Protocol):
    def encode(self, key: K) -> bytes: ...
    def decode(self, payload: bytes) -> K: ...


class StringNearCacheKeyCodec(NearCacheKeyCodec[str]):
    ...
```

The default codec accepts exact `str` values only. UTF-8 output must be 1..1024
bytes. Empty strings, unpaired surrogates, oversized values, and non-`str`
values are rejected. The marker layer base64url-encodes codec bytes without
padding, so separators and Unicode cannot collide with the namespace boundary.

A custom codec must return exact `bytes` of 1..1024 bytes, decode to a hashable
key, and be canonical: encoding the decoded key must reproduce the original
payload. Codec exceptions are wrapped in a stable near-cache error without
including the key or payload.

### Options

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class RedisNearCacheOptions:
    namespace: str
    default_ttl: float
    max_size: int
    max_inflight: int | None = None
    marker_ttl: float = 60.0
    queue_capacity: int = 1024
    marker_max_attempts: int = 3
    reconnect_initial_delay: float = 0.05
    reconnect_max_delay: float = 5.0
    reconnect_multiplier: float = 2.0
```

Namespace validation follows the existing Redis coordination convention: exact
`str`, 1..256 UTF-8 bytes, no surrounding whitespace, and no control
characters. TTLs and reconnect delays are finite and positive. Entry,
in-flight, queue, and attempt bounds are exact positive integers. The initial
delay cannot exceed the maximum delay, and the multiplier is finite and at
least one.

The implementation plan must set finite upper bounds for all numeric options.
Redis command connect/socket deadlines remain caller-owned redis-py
configuration and must be finite for a provider to claim bounded failure.

### State and status

```python
class RedisNearCacheState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisNearCacheStatus:
    mode: RedisMode
    state: RedisNearCacheState
    generation: int
    error_code: RedisNearCacheErrorCode | None
```

`is_ready` is true only in `READY`. Status is a point-in-time snapshot and does
not expose exception text, endpoint details, namespace, key, or marker data.

Stable error codes distinguish invalid input, not started, closed, connection,
timeout, protocol, malformed push, queue overflow, marker failure, codec
failure, and internal provider failure. Raw redis-py exceptions may be attached
as `__cause__`, but callers must not expose them without redaction.

### Facades

```python
class SyncRedisNearCache[K, V]:
    def __init__(
        self,
        command_client: redis.Redis,
        reader_client: redis.Redis,
        *,
        options: RedisNearCacheOptions,
        key_codec: NearCacheKeyCodec[K] | None = None,
        observer: RedisNearCacheObserver | None = None,
    ) -> None: ...

    @classmethod
    def from_url(cls, url: str, *, options: RedisNearCacheOptions, ...) -> Self: ...

    def start(self) -> None: ...
    @property
    def is_ready(self) -> bool: ...
    def status(self) -> RedisNearCacheStatus: ...
    def get(self, key: K) -> V: ...
    def get_or_load(self, key: K, loader: Callable[[K], V], *, ttl: float | None = None) -> V: ...
    def invalidate(self, key: K) -> None: ...
    def clear_local(self) -> None: ...
    def stats(self) -> CacheStats: ...
    def close(self) -> None: ...


class AsyncRedisNearCache[K, V]:
    async def start(self) -> None: ...
    async def get(self, key: K) -> V: ...
    async def get_or_load(
        self,
        key: K,
        loader: Callable[[K], Awaitable[V]],
        *,
        ttl: float | None = None,
    ) -> V: ...
    async def invalidate(self, key: K) -> None: ...
    async def clear_local(self) -> None: ...
    async def stats(self) -> CacheStats: ...
    async def aclose(self) -> None: ...
```

The async facade mirrors constructor, factory, status, observer, and ownership
concepts. It binds to the first running event loop used by `start()` and rejects
use from another loop. The sync facade supports `with`; the async facade
supports `async with`. Context entry starts tracking, and exit performs complete
cleanup.

There is intentionally no public `set()` or direct access to the owned local
cache. Values enter the cache only through a successful loader publication.
Authoritative mutations use `invalidate()` after the authoritative operation
has succeeded.

## Marker Protocol

### Key format

For a validated namespace and canonical codec payload, the marker key is:

```text
<namespace>:<unpadded-base64url(codec.encode(key))>
```

The tracking reader enables:

```text
CLIENT TRACKING ON BCAST PREFIX <namespace>:
```

Base64url keeps the key mapping deterministic and reversible and prevents `:`
inside encoded key bytes from changing the namespace boundary. Encoding is not
encryption: Redis operators can decode marker keys. Applications that consider
cache keys sensitive must provide a reversible codec with an appropriate
security policy or avoid the provider. A one-way digest is insufficient because
the receiver must recover the local key without maintaining an unbounded digest
index.

### Value and lifetime

Each logical invalidation creates one opaque 16-byte mutation token and writes:

```text
SET <marker-key> <token> PX <marker-ttl-ms>
```

The token contains no application value, namespace, key, timestamp, hostname,
or origin identifier. One logical operation reuses its token across bounded
command retries. Tracking invalidation is triggered by the write, not by token
interpretation.

Marker TTL is finite and independently bounds Redis metadata. A later expiry
may produce another invalidation. Key invalidation, retry duplicates, self
delivery, and expiry delivery are all idempotent.

### Write ordering

After the caller has successfully changed authoritative data:

1. `invalidate(key)` validates and encodes the key.
2. The writer's local entry is invalidated immediately. Existing cache
   versioning supersedes an active same-key loader.
3. The separate command client writes the marker with bounded attempts.
4. Each tracking reader decodes the marker key and invalidates its local entry.
5. The writer may receive its own push and invalidates the same key again.

`NOLOOP` is not enabled. Immediate local invalidation provides origin
correctness, while duplicate self delivery keeps the protocol independent of
which connection sent the write.

If every marker attempt fails, the facade enters `DEGRADED`, clears its complete
local cache, and raises a stable consistency failure. The authoritative mutation
has already occurred, so the error cannot be reported as success. This protocol
cannot atomically roll back an external authoritative store; callers must treat
failed invalidation as an explicit consistency incident. If the command path is
isolated while peer readers remain healthy, peers cannot be guaranteed to
observe a marker that Redis never accepted.

## Lifecycle State Machine

### Initial start

`start()` is explicit and idempotent only after a successful start:

1. Under the lifecycle gate, transition `NEW -> STARTING` and increment the
   readiness generation.
2. Disable local reads and population.
3. Clear the complete local cache.
4. Install the public push consumer on the dedicated reader.
5. Connect with RESP3 and enable `CLIENT TRACKING ON BCAST PREFIX`.
6. Clear the local cache again.
7. Publish `READY` for the same generation.

The second clear removes any state that could have existed before tracking was
fully established. A failure during initial start clears and cleans up the
attempt, returns to `NEW`, and raises; no reconnect worker survives a failed
initial `start()`. The caller may correct configuration and retry `start()`.

Concurrent operations while `NEW` or `STARTING` raise a stable not-started/not-
ready error. `CLOSING` and `CLOSED` operations raise a closed error.

### Ready operations

`get()` and `get_or_load()` enter through the lifecycle gate and are admitted
only against the current ready generation. Local cache operations preserve the
existing TTL, capacity, coalescing, and statistics contracts.

The lifecycle gate is not held while a loader executes. A transition away from
`READY` clears the local cache, increments the generation, and supersedes active
flights. A loader may still return its authoritative result to its current
caller, but it cannot publish the result into the local cache.

The guarantee begins when the process detects failure and commits the state
transition. The design does not claim that an undetected network break has zero
detection latency.

### Degradation and reconnect

Reader disconnect, protocol failure, malformed push data, dispatch queue
overflow, or an internal consumer failure performs this order:

1. Atomically leave `READY`, increment the generation, and prevent new local
   reads/population.
2. Clear the complete local cache and supersede active flights.
3. Record a redacted error code and emit a low-cardinality transition event.
4. Tear down the failed reader attempt.
5. Reconnect until success or close, using exponential backoff capped at
   `reconnect_max_delay` and finite connect/socket deadlines.
6. Reinstall the public push consumer and re-enable tracking.
7. Clear the complete local cache again.
8. Transition to `READY` only if the reconnect attempt still owns the current
   lifecycle generation.

Older reconnect completions are ignored and cleaned up. Backoff sleeping must
be interruptible by close. Retry delays are bounded; the number of reader
reconnect attempts is not bounded while the facade remains open, allowing
eventual recovery without silently returning to local caching.

While `DEGRADED` or `RECONNECTING`:

- `get()` behaves as a local miss and raises `KeyError(key)`;
- `get_or_load()` invokes the authoritative loader directly and returns its
  value without local coalescing or population;
- loader failure and async cancellation preserve the original exception;
- `invalidate()` still performs immediate local invalidation and may attempt a
  marker command so healthy peers can be notified;
- `clear_local()` remains idempotent.

### Push handling

Only the exact RESP3 invalidation push shape accepted by the Gate 0 proof is
processed. A list of marker keys is decoded and invalidated one by one. A
documented full invalidation/null payload clears the complete local cache.

Duplicate keys are harmless. A key outside the configured prefix, invalid
base64url, codec failure, unexpected element type, unknown push shape, or an
overflowed bounded handoff is not silently skipped. It degrades the reader and
causes a complete clear because selective invalidation coverage can no longer
be proven.

The sync implementation owns one reader thread. The async implementation owns
one background task. Gate 0 determines the exact public redis-py adapter, but an
implementation must not add unbounded queues or additional hidden worker pools.

### Close

Close is idempotent and has one cleanup owner:

1. Transition to `CLOSING`, increment the generation, and reject new work.
2. Clear the local cache and supersede active flights.
3. Interrupt reconnect backoff or reader waiting.
4. Stop and join/await the owned reader thread or task.
5. Disable tracking and detach public push handling when supported.
6. Close factory-owned Redis clients exactly once.
7. Preserve caller-supplied borrowed clients.
8. Transition to `CLOSED` and wake concurrent closers.

Async cleanup is cancellation-safe: the first `aclose()` establishes one owned
cleanup task, shields it to terminal state, and re-raises cancellation only
after resources are settled. Repeated close observes the same terminal result.

## Redis Client Ownership

The direct constructor requires separate command and reader clients. Both are
borrowed. They must be distinct objects, binary-response compatible, and
configured for finite command bounds. The reader client is contractually
dedicated to the facade even though the caller owns its final close.

The provider stops tracking and detaches its consumer from a borrowed reader but
does not close either borrowed client. Caller code must not use the dedicated
reader for unrelated commands while the facade is started.

`from_url()` creates two binary redis-py clients with RESP3 explicitly enabled
and owns both. It rejects a caller-supplied connection pool because one pool
cannot express the required two-role ownership clearly. Factory close shuts
both clients exactly once.

If Gate 0 shows that redis-py's public API requires a narrower construction
shape, the implementation plan may narrow the constructor but may not permit a
shared command/reader connection or weaken borrowed-versus-owned behavior.

## Concurrency Rules

- Lifecycle state and generation changes are serialized independently from the
  local cache's own lock.
- No Redis I/O or user loader runs while a lifecycle or local-cache lock is
  held.
- A ready operation snapshots its generation before leaving the lifecycle gate.
- Degradation clears through the public local-cache operation, which bumps the
  clear epoch and supersedes active flights.
- Key invalidation uses the public local-cache invalidation operation, which
  bumps the key version and supersedes the same-key flight.
- A reconnect may publish readiness only if its generation and reader ownership
  still match current state.
- Marker retries are idempotent; duplicate pushes never reverse a newer state.
- Async cancellation never cancels shared ready-state loader work for surviving
  waiters, preserving `AsyncTTLCache` behavior. Degraded direct loads have no
  shared flight and are cancelled normally.
- Observer failures are swallowed and cannot alter state or resource cleanup.

## Failure Semantics

| Failure | Local action | Caller-visible action | Recovery |
|---|---|---|---|
| Initial tracking setup | Clear, remain disabled | `start()` raises | Caller may retry start |
| Reader disconnect/protocol failure | Degrade and clear | Reads miss; loads bypass cache | Background reconnect |
| Malformed push | Degrade and clear | Redacted status/event | Background reconnect |
| Queue overflow | Degrade and clear | Redacted status/event | Background reconnect |
| Marker command exhaustion | Degrade and clear | `invalidate()` raises | Reader reconnect if needed; later invalidation may retry |
| Key codec failure on caller input | No Redis command | Operation raises | Caller fixes input/codec |
| Key decode failure from push | Degrade and clear | Redacted status/event | Background reconnect |
| Loader failure | No population | Original exception | Next call may load again |
| Async loader cancellation | No abandoned population | `CancelledError` | Existing ready-state shared-flight rules apply |
| Close during reconnect | Clear and stop | Close waits for cleanup | Terminal `CLOSED` |

There is no silent stale-cache fallback. Degraded direct loading is not a
durable availability cache: it calls the authoritative loader for each request
and deliberately gives up local coalescing until tracking is healthy.

## Observability and Security

An immutable observer event identifies mode, operation, outcome, state
transition, error code, generation, and elapsed time. It must not contain:

- cache keys or encoded marker keys;
- namespace;
- marker token;
- Redis URL, host, credentials, or connection representation;
- redis-py exception text;
- loader values or exceptions.

Expected operations include create/start, tracking-ready, degrade, reconnect,
invalidate, clear-local, and close. State transition events are low-cardinality;
per-key successful push events are not emitted by default because they can
create unbounded telemetry volume.

Marker names are reversible and visible to Redis administrators. Marker values
are random metadata, not authentication tokens. Deployment requires Redis ACL
permission for `CLIENT TRACKING`, `SET`, and connection health commands chosen
by the proven transport. TLS, authentication, endpoint selection, command
timeouts, and Redis availability remain deployment policy.

## Test Strategy

### Gate 0 integration tests

- sync public push receipt from a separate marker command connection;
- async public push receipt from a separate marker command connection;
- BCAST prefix isolation;
- idle reader behavior;
- reader loss detection;
- public-handler reinstall and tracking re-enable after reconnect;
- deterministic shutdown and resource accounting.

### Contract and codec tests

- default exact-`str` success, Unicode, empty, wrong type, unpaired surrogate,
  1024-byte boundary, and oversized input;
- namespace empty, whitespace/control, UTF-8 boundary, and oversized input;
- base64url separator safety and reversible round trip;
- custom codec non-bytes, empty, oversized, unhashable decode, noncanonical
  decode, and raised exception;
- finite numeric bounds and bool rejection for every option;
- immutable status/event/error contracts and public export order.

### Deterministic state-machine tests

Use injected proven transport seams, fake clocks/sleepers, and bounded queues to
test without timing guesses:

- initial start success and every failure point;
- repeated/concurrent start and close;
- `NEW`, `STARTING`, `READY`, `DEGRADED`, `RECONNECTING`, `CLOSING`, and
  `CLOSED` operation behavior;
- stale reconnect completion cannot publish readiness;
- disconnect, protocol failure, malformed push, queue overflow, and internal
  consumer failure all clear and disable;
- reconnect delays cap correctly and close interrupts sleep;
- second clear occurs before readiness recovery;
- observer failure never changes behavior;
- borrowed clients remain open and owned clients close exactly once.

### Cache-race tests

- key invalidation racing a blocked loader prevents stale publication;
- complete degradation racing a blocked loader prevents stale publication;
- clear and reconnect generation changes supersede old flights;
- a ready-state shared loader still returns its result to admitted callers but
  does not populate after degradation;
- degraded `get()` never returns a previously cached value;
- degraded `get_or_load()` calls the loader for every request and never changes
  local size;
- async cancellation and last-waiter behavior preserve existing local-cache
  contracts while ready and direct cancellation semantics while degraded.

### Testcontainers provider tests

- two sync facades invalidate peer entries;
- two async facades invalidate peer entries;
- sync and async cross-mode invalidation;
- self-write invalidation without `NOLOOP`;
- namespace isolation;
- duplicate marker writes and marker expiry are idempotent;
- Redis outage clears and disables local values;
- Redis recovery clears again before readiness;
- marker command retry success and exhaustion;
- context-manager and cancellation cleanup leave no connection, thread, or task
  leak.

Malformed Redis pushes cannot be generated by a conforming Redis server. Those
are tested through the same proven adapter seam used by the Testcontainers
transport, while real delivery, outage, and reconnect remain Testcontainers
coverage. The suite must not pretend that attaching a container to a synthetic
payload test proves server behavior.

### Packaging and documentation tests

- isolated `bluetape-cache` and default `bluetape` wheels do not import or
  require redis-py;
- `bluetape-cache-redis` wheel imports all documented near-cache symbols;
- English and Korean package README examples execute or compile;
- docs distinguish client tracking from Pub/Sub, durable L2 values, and load
  coordination;
- build metadata preserves Python 3.13+ and optional dependency boundaries.

## Verification Gates

Implementation verification escalates in this order:

1. Gate 0 sync/async Testcontainers proof.
2. Targeted codec, contracts, state-machine, and cache-race tests.
3. Targeted Redis near-cache integration tests run serially.
4. `uv run pytest` with required locked optional test extras.
5. `uv run ruff check .`
6. `uv run ruff format --check .`
7. `uv build --all-packages`
8. Isolated wheel/import and metadata smoke checks.
9. `git diff --check`.
10. Independent code and architecture review with P0=0 and P1=0.

The clean baseline for this design worktree is Python 3.13.14 with locked
`fory` and native-compression test extras: 1,515 tests passed on 2026-07-13.

## Documentation

Update both `packages/bluetape-cache-redis/README.md` and `README.ko.md` with:

- sync and async lifecycle examples using context managers;
- the explicit authoritative-mutation-then-`invalidate()` order;
- readiness and degraded direct-load behavior;
- marker key visibility and bounded TTL;
- borrowed versus factory-owned clients;
- no Pub/Sub, durable Redis values, cross-process load coordination, global
  ordering, or exactly-once guarantee;
- Gate 0 redis-py version support and topology limitations;
- rollout, monitoring, failure, and rollback guidance.

Workspace `README.md` and `README.ko.md`, package status tables, package-layout
documentation, `CHANGELOG.md`, and `WIP.md` are updated only where the final
implemented public surface changes their current claims. English and Korean
user-facing descriptions remain aligned.

## Rollout and Rollback

Adoption is explicit and per cache namespace. Applications first deploy the
facade with readiness/status monitoring, bounded local TTL, and authoritative
loader deadlines. A rollout must alert on degraded transitions, reconnect
duration, marker failures, and repeated full clears without recording keys.

Rollback removes the near-cache facade and returns to direct authoritative
loads or an existing process-local cache policy accepted by the application.
Short marker TTL makes Redis metadata self-cleaning. Rollback does not require
deleting application values because none are stored by this feature.

## Acceptance Mapping

| Issue criterion | Design response |
|---|---|
| Sync/async parity | Parallel facades, Gate 0 parity, shared state semantics |
| Peer invalidation without Pub/Sub | BCAST PREFIX marker protocol and Testcontainers tests |
| In-flight race fencing | Existing cache epoch/version plus readiness generation |
| Reconnect/outage/failure coverage | Fail-closed state machine and deterministic/integration tests |
| No reads/population while unhealthy | Owned local cache behind facade gate; degraded direct loading |
| Collision-safe marker encoding | Canonical codec bytes plus reversible base64url framing |
| Optional dependency isolation | All Redis code remains in `bluetape-cache-redis` |
| Documentation distinctions | Bilingual package docs and explicit non-goals |
| P0/P1 review | Final independent review gate |

## Resolved Decisions

- Use the Lettuce module as a behavioral reference, not a Python API template.
- Require redis-py public APIs and stop if either sync or async is blocked.
- Keep `bluetape-cache` unchanged.
- Use owned near-cache facades rather than attaching to caller-accessible local
  cache instances.
- Use `BCAST PREFIX` marker keys, not tracked application values.
- Do not use `NOLOOP`.
- Default to exact `str` keys and require an explicit codec for other types.
- Do not expose public `set()`.
- During degradation, `get()` misses and `get_or_load()` loads directly without
  coalescing or population.
- Reconnect indefinitely with bounded delays until close.
- Treat malformed delivery and queue overflow as loss of coverage and fail
  closed.

## Implementation Planning Boundary

This document approves architecture and behavior, not implementation. After the
document is committed, self-reviewed, and approved by the user, a separate
`writing-plans` pass will define exact files, TDD slices, Gate 0 probe commands,
review checkpoints, packaging changes, and commit boundaries. No production
near-cache implementation begins before that plan is approved.
