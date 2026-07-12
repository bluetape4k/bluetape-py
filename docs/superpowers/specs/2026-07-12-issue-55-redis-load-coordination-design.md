# Issue #55 Redis Load Coordination Design

Issue: [#55](https://github.com/bluetape4k/bluetape-py/issues/55)
Milestone: 0.2.0
Date: 2026-07-12
Work type: Type A - Full Feature
Depends on: #54 and #57 (both closed)

## Summary

Add opt-in synchronous and asynchronous Redis load coordinators to
`bluetape-cache-redis`. Each coordinator wraps a caller-owned `TTLCache[str, V]`
or `AsyncTTLCache[str, V]`, uses a single Redis instance to elect one loader for
each namespace/key attempt, and publishes a short-lived owner-token-bound result
envelope so other processes can fill their local caches without calling their
user loaders.

The Redis artifact is coordination state, not a durable L2 value. Mutual
exclusion ends when the lease expires. If a loader finishes after losing its
lease, its caller receives the locally computed value, but the coordinator does
not publish that value to Redis and emits a redacted `lease-lost` observation.

## Problem

The local caches introduced by #50 collapse same-key loads only within one cache
instance. Independent processes can therefore execute the same expensive loader
after a shared cold miss. The provider and envelope substrate from #54 supplies
bounded Redis bytes, owner-safe delete, sync/async parity, and caller-owned value
serialization, but it intentionally does not orchestrate leases, loaders,
polling, or retries.

Issue #55 must compose those existing contracts without changing
`bluetape-cache`, adding Redis to the default install, hiding Redis failures, or
turning transient result envelopes into durable cache entries.

## Approved Requirements

- Add equivalent `SyncRedisLoadCoordinator[V]` and
  `AsyncRedisLoadCoordinator[V]` public APIs under `bluetape.cache.redis`.
- Borrow caller-supplied local caches, Redis providers, envelope codecs, and
  observers; coordinators own no client or cache lifecycle.
- Restrict coordinated keys to exact `str` values so the Redis identity is
  deterministic across processes. Empty strings are valid cache keys.
- Derive Redis keys from SHA-256 namespace and logical-key digests. Raw keys,
  namespaces, tokens, values, provider details, and URLs never appear in events
  or public error messages.
- Acquire an active-marker lease with the existing `SET NX PX` provider
  primitive and a `secrets.token_urlsafe(32)` token containing at least 256 bits
  of CSPRNG entropy.
- Publish a result only through a new atomic provider primitive that verifies the
  current active marker, stores the result with `PX`, and replaces the lease with
  a distinct same-token completion marker with the same result TTL in one Lua
  script.
- Read marker state and bounded result bytes through one atomic snapshot command;
  coordinators never download unbounded Redis-controlled artifacts.
- Release failed or cancelled attempts only through owner-token compare-delete.
  Successful completion markers expire naturally with their result envelopes.
- Bound lease TTL, result TTL, initial/max poll interval, poll count,
  coordination wait timeout, acquire attempts, encoded envelope size, and Redis
  client I/O through explicit caller configuration and substrate checks.
- Propagate loader, codec, and Redis failures explicitly. Never silently fall
  back to an uncoordinated user loader.
- Preserve `asyncio.CancelledError`; owner cancellation performs one shielded,
  awaited compare-delete cleanup with no detached task.
- Use `bluetape-testcontainers.RedisServer` for Docker-backed tests and run all
  Redis integration checks serially.

## Non-Goals

- Durable Redis L2 values or read-through Redis caching.
- Near-cache invalidation or Pub/Sub.
- Redlock, multiple Redis instances, Redis Cluster support, Sentinel, automatic
  lease renewal, fencing tokens, or external-write safety.
- Guaranteed single execution after a loader exceeds its lease.
- Implicit loader deadlines or interruption of synchronous user code.
- Framework-specific adapters or a built-in application payload codec.
- Changes to `TTLCache`, `AsyncTTLCache`, or the default `bluetape` dependency
  set.

## Current Evidence

### Repository anchors

- `TTLCache.get_or_load` and `AsyncTTLCache.get_or_load` already provide local
  same-instance collapse, successful-value caching, recursive-load protection,
  invalidation/supersession rules, and async waiter cancellation cleanup.
- `SyncRedisProvider` and `AsyncRedisProvider` already provide exact-byte
  `get`, `set`, `set_if_absent`, `delete`, and atomic `delete_if_value` with
  borrowed/owned lifecycle and redacted errors.
- `ResultEnvelopeCodec[V]` already binds serialized values to an owner token,
  rejects stale tokens before decompression, enforces encoded-size limits, and
  preserves caller-owned payload and compression policy.
- `RedisServer` is the repository's only permitted Docker-backed Redis boundary.
- `bluetape-cache-redis` is focused and opt-in; the default `bluetape` install
  remains Redis-free.

### Ecosystem anchors

- `bluetape-go/cache/rediscoord` demonstrates that lock-only serialization is
  insufficient: waiters need a token-bound transient result to avoid later
  duplicate loaders.
- The Go design is borrowed for semantic constraints only. Python keeps separate
  sync/async classes, existing Python cache instances, Python exceptions, and
  Python cancellation ownership.

### Redis anchors

- Redis `SET key value NX PX milliseconds` atomically creates a bounded lease.
- Redis single-instance lock guidance requires a unique value per attempt and
  value-matched release rather than unconditional `DEL`.
- Redis Lua scripts execute their command sequence atomically and require
  accessed keys through `KEYS` and non-key inputs through `ARGV`.

## Alternatives

### A. Token marker plus atomic result publication — selected

The owner publishes only if its distinct active marker still matches. The same
script stores the result and replaces the lease with a distinct same-token
completion marker whose TTL equals the result TTL. Waiters decode results only
from a completed snapshot, can reject stale envelopes, and can reuse the result
during the bounded completion window.

This adds one narrow provider primitive but closes the owner-check/publication
TOCTOU and the late-waiter race.

### B. Compose `get`, `set`, and `delete_if_value` only — rejected

Checking the lease with `get` and then publishing with `set` is racy: the lease
can expire and a new owner can acquire it between those commands. The stale owner
could overwrite the new attempt's result. This violates the token-matched
publication criterion.

### C. Publish and immediately delete the lease — rejected

Atomic publish followed by immediate compare-delete is owner-safe, but a waiter
that has not yet observed the token can see neither the completed owner nor a
safe way to associate the envelope with the current attempt. It may acquire a
new lease and execute a duplicate loader while the valid result still exists.

### D. Lock-only coordination — rejected

Lock-only serialization avoids simultaneous execution but cannot let independent
cold local caches reuse the winner's value. It fails the required one-loader
cold-burst semantics.

## Public API

### Options

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class RedisLoadOptions:
    namespace: str
    lease_ttl: float = 5.0
    result_ttl: float = 1.0
    poll_interval: float = 0.01
    max_poll_interval: float = 0.25
    wait_timeout: float = 10.0
    max_attempts: int = 3
    max_polls: int = 100
    redis_io_timeout: float = 1.0
```

Validation is exact and eager:

- `namespace` is required, is a non-blank exact `str`, has no surrounding
  whitespace/control characters, and has a 1..256-byte UTF-8 representation;
- durations are finite positive real numbers and must fit the provider's Redis
  millisecond range;
- every duration is at most `MAX_COORDINATION_DURATION = 3600.0` seconds and
  uses the existing finite-real/type rules; Redis TTLs use the existing
  ceiling-to-milliseconds conversion;
- `poll_interval` is at least `MIN_POLL_INTERVAL = 0.001`,
  `poll_interval <= max_poll_interval`, and both are no greater than
  `wait_timeout`; `max_poll_interval` is also no greater than `result_ttl`;
- `max_attempts` is an exact `int` in `1..100`; `max_polls` is an exact `int` in
  `1..MAX_POLL_BUDGET`, where `MAX_POLL_BUDGET = 10_000`;
- `redis_io_timeout` is finite and positive. The provider must expose finite
  connect/socket command bounds no greater than this value and must not apply
  hidden command retries; otherwise coordinator construction fails;
- logical keys are exact `str` values with a 0..4096-byte UTF-8 representation;
  empty is valid.

Wrong exact types, including booleans passed as numbers, raise `TypeError`.
Invalid values and cross-field relationships raise `ValueError`. Runtime
Redis-controlled artifact failures use the stable coordination error described
below. All boundaries are inclusive unless stated otherwise.

### Coordinators

```python
class SyncRedisLoadCoordinator[V]:
    def __init__(
        self,
        cache: TTLCache[str, V],
        provider: SyncRedisProvider,
        codec: ResultEnvelopeCodec[V],
        *,
        options: RedisLoadOptions,
        observer: RedisCoordinationObserver | None = None,
    ) -> None: ...

    def get_or_load(
        self,
        key: str,
        loader: Callable[[str], V],
        *,
        ttl: float | None = None,
    ) -> V: ...


class AsyncRedisLoadCoordinator[V]:
    def __init__(
        self,
        cache: AsyncTTLCache[str, V],
        provider: AsyncRedisProvider,
        codec: ResultEnvelopeCodec[V],
        *,
        options: RedisLoadOptions,
        observer: RedisCoordinationObserver | None = None,
    ) -> None: ...

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[str], Awaitable[V]],
        *,
        ttl: float | None = None,
    ) -> V: ...
```

The coordinators intentionally expose only `get_or_load`. Callers continue to
use their owned cache instance for `get`, `set`, invalidation, clearing, and
statistics. This avoids implying that local mutation methods provide distributed
invalidation semantics.

All constructor dependencies are borrowed. Closing a coordinator is unnecessary;
callers close an owned Redis provider through its existing lifecycle API.
One cache instance must be paired with one coordinator configuration. Sharing a
cache between coordinators with different namespaces/options is unsupported
because the cache's first same-key local flight intentionally wins for all local
waiters.

The `ttl` argument is only the borrowed local cache entry TTL. `None` delegates
the cache's existing default TTL, and an explicit value is validated and passed
through exactly as `TTLCache.get_or_load` or `AsyncTTLCache.get_or_load` already
defines. It never changes `lease_ttl`, `result_ttl`, polling, or Redis key TTLs.

`namespace` is an application-owned distributed route, not a convenience label.
It must include application, environment/tenant boundary, and value-schema
version, for example `orders:prod:tenant-a:order-v3`. Every participant in one
route must use compatible codec/trust policy, envelope size, coordination
semantics, and options. Reuse across unrelated workloads or tenants is forbidden.

### Failures and observations

The exact public taxonomy is:

```python
class RedisCoordinationOperation(StrEnum):
    GET_OR_LOAD = "get-or-load"

class RedisCoordinationOutcome(StrEnum):
    LOADED = "loaded"
    RESULT_REUSED = "result-reused"
    LEASE_LOST = "lease-lost"
    TIMEOUT = "timeout"
    FAILURE = "failure"
    CANCELLED = "cancelled"

class RedisCoordinationErrorCode(StrEnum):
    ATTEMPTS_EXHAUSTED = "attempts-exhausted"
    POLLS_EXHAUSTED = "polls-exhausted"
    DEADLINE_EXCEEDED = "deadline-exceeded"
    INVALID_ARTIFACT = "invalid-artifact"
    PROVIDER_FAILURE = "provider-failure"
    ENVELOPE_FAILURE = "envelope-failure"
    LOADER_FAILURE = "loader-failure"
    CLEANUP_FAILURE = "cleanup-failure"

@dataclass(frozen=True, slots=True, kw_only=True)
class RedisCoordinationEvent:
    mode: RedisMode
    operation: RedisCoordinationOperation
    outcome: RedisCoordinationOutcome
    error_code: RedisCoordinationErrorCode | None
    attempts: int
    polls: int
    cleanup_failed: bool
    elapsed_ns: int

class RedisCoordinationObserver(Protocol):
    def on_event(self, event: RedisCoordinationEvent) -> None: ...
```

`RedisCoordinationEvent.__post_init__` requires exact instances of the declared
enum types, permits only `None` or an exact `RedisCoordinationErrorCode` for
`error_code`, requires exact non-negative integers for `attempts`, `polls`, and
`elapsed_ns`, and requires an exact `bool` for `cleanup_failed`. Wrong field
types raise `TypeError`; negative measurements raise `ValueError`.

`RedisCoordinationError(*, code: RedisCoordinationErrorCode)` requires an exact
enum instance (otherwise `TypeError`), has the exact static message
`"Redis load coordination failed"` and a read-only `code`.
`RedisCoordinationTimeoutError(*, code: RedisCoordinationErrorCode)` has the
same exact-type rule, rejects non-timeout codes with `ValueError`, has the exact static message
`"Redis load coordination timed out"`, is its subtype, and uses exactly
`ATTEMPTS_EXHAUSTED`, `POLLS_EXHAUSTED`, or `DEADLINE_EXCEEDED` according to the
first terminal bound. `INVALID_ARTIFACT` reports malformed/oversized snapshot
state. Constructor/options/key/loader validation remains `TypeError` or
`ValueError`; provider, envelope, and loader failures retain their existing
public types and trusted cause chains.

Observer failures are swallowed after the terminal event, matching the existing
provider observer boundary. Events never contain namespace, key, token, payload,
attempt identifier, Redis endpoint, or exception text.
Local hits emit no coordination event. Each cache-owned distributed flight emits
exactly one terminal event. Attempts and polls are bounded numeric measurements,
not metric labels; applications attach their own static route label outside the
library without exposing raw namespace/key data.

The existing provider enums add, in order,
`RedisOperation.COORDINATION_SNAPSHOT = "coordination-snapshot"` and
`RedisOperation.PUBLISH_IF_VALUE = "publish-if-value"`. Snapshot oversize is a
coordination `INVALID_ARTIFACT`; invalid Redis response shape remains provider
`INVALID_RESPONSE`.

The ordered public `__all__` keeps every current item in place and appends:

```text
RedisCommandPolicy, ResultEnvelopeMatch, MAX_COORDINATION_MARKER_SIZE,
RedisCoordinationSnapshot, RedisCoordinationOperation,
RedisCoordinationOutcome, RedisCoordinationErrorCode,
RedisCoordinationEvent, RedisCoordinationObserver, RedisCoordinationError,
RedisCoordinationTimeoutError, RedisLoadOptions, SyncRedisLoadCoordinator,
AsyncRedisLoadCoordinator
```

`MAX_COORDINATION_DURATION`, `MIN_POLL_INTERVAL`, and `MAX_POLL_BUDGET` are
private implementation limits despite their descriptive names: they are not in
`__all__` and are not supported import contracts. Their exact values remain
normative for option validation and tests in this release.

## Provider Command Policy

Providers expose this exact immutable public policy and access API:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class RedisCommandPolicy:
    connect_timeout: float
    socket_timeout: float
    max_retries: int = 0

    @property
    def max_command_time(self) -> float:
        return self.connect_timeout + self.socket_timeout


class SyncRedisProvider:
    @property
    def command_policy(self) -> RedisCommandPolicy | None: ...


class AsyncRedisProvider:
    @property
    def command_policy(self) -> RedisCommandPolicy | None: ...
```

`connect_timeout` and `socket_timeout` accept only exact finite positive real
values (booleans are rejected); `max_retries` must be the exact integer `0`.
Wrong types raise `TypeError`; non-finite, non-positive, or non-zero values raise
`ValueError`. `max_command_time` is the sum of the two bounds.

Construction from a normal redis-py pool derives `command_policy` only when
`connection_kwargs` contains finite `socket_connect_timeout` and
`socket_timeout`, has `retry_on_timeout` absent/false, has `retry_on_error`
absent or empty, and has no `retry` object.
Otherwise `command_policy` is `None`; existing #54 byte operations still work,
but a load coordinator rejects that provider with `ValueError`.

Custom/opaque connection pools cannot claim a production coordination policy and
are rejected by coordinators. Test fakes expose an explicit immutable policy
through the same internal support boundary. `RedisLoadOptions.redis_io_timeout`
must be at least `policy.max_command_time`; it is not a declaration that can
weaken the inspected client. Recommended construction passes both socket bounds
and `retry_on_timeout=False` to `from_url`.

## Tagged Envelope Decode

The current `ResultEnvelopeCodec.decode() -> T | None` remains unchanged for
backward compatibility. Coordinators use a new additive contract:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelopeMatch[T]:
    value: T

def decode_matching(
    self,
    data: bytes,
    *,
    expected_owner_token: str,
) -> ResultEnvelopeMatch[T] | None: ...
```

`None` now unambiguously means token mismatch; a legitimate decoded `None` is
returned as `ResultEnvelopeMatch(value=None)`. All existing validation,
decompression selection, bounds, and error behavior are shared with `decode()`.

## Redis Key Model

For a namespace `N` and logical key `K`:

```text
namespace_id = sha256(utf8(N)).hexdigest()
key_id       = sha256(utf8(K)).hexdigest()
slot_tag     = "{" + namespace_id + ":" + key_id + "}"

bluetape:cache:coord:<namespace_id>:<slot_tag>:lease
bluetape:cache:coord:<namespace_id>:<slot_tag>:result
```

The shared hash tag keeps both keys colocated if a future design adds Cluster
support, but Cluster remains unsupported in this issue. Namespace digests retain
a deterministic operational cleanup prefix without storing raw namespaces or
keys. Digests are pseudonyms, not confidentiality: low-entropy inputs remain
dictionary-guessable, so Redis ACLs, TLS, and deployment isolation protect both
key identity and payloads. The coordinator computes the namespace digest and
prefix once at construction and the key digest/Redis keys once per local flight;
all retries reuse those values.

## Marker and Snapshot Model

Marker bytes have one strict bounded ASCII grammar:

```text
active:<owner-token>
completed:<owner-token>
```

The parser rejects empty, non-ASCII, overlong, unknown-state, malformed, and
invalid-token markers as one redacted `INVALID_ARTIFACT` coordination error.
Only completed markers authorize envelope decoding. An active marker causes the
waiter to ignore any leftover result bytes and continue bounded polling.

Both providers expose one fixed-script `coordination_snapshot` operation. It
atomically returns marker existence, marker length and a bounded marker prefix,
plus result existence, result length and at most `codec.max_encoded_size + 1`
result bytes. The provider validates the complete Redis response shape. Lengths
over their exact limits fail before decode, and coordinator code never calls
unbounded `get()` for marker or result artifacts.

The exact shared return contract is immutable and bounded:

```python
MAX_COORDINATION_MARKER_SIZE = 138

@dataclass(frozen=True, slots=True, kw_only=True)
class RedisCoordinationSnapshot:
    marker: bytes | None
    result: bytes | None
    marker_oversized: bool
    result_oversized: bool


def coordination_snapshot(
    self,
    marker_key: str,
    result_key: str,
    *,
    max_marker_size: int = MAX_COORDINATION_MARKER_SIZE,
    max_result_size: int,
) -> RedisCoordinationSnapshot: ...
```

The async provider exposes the same arguments and awaited return. Limits are
exact positive integers; booleans, negative/zero values, values above fixed
provider hard caps (`MAX_COORDINATION_MARKER_SIZE = 138` and
`DEFAULT_MAX_ENCODED_SIZE = 16 * 1024 * 1024`), and identical keys fail before
`EVAL`. Returned byte fields can never exceed their requested bound. The script
uses `STRLEN` plus bounded `GETRANGE`; the provider truncates only the diagnostic
prefix and sets the exact oversize boolean. The coordinator, outside the
provider `_execute` wrapper, maps either flag to `INVALID_ARTIFACT`. This keeps
provider response-shape failures as `RedisProviderError(INVALID_RESPONSE)` and
coordination artifact policy as `RedisCoordinationError`.

## Atomic Publication Primitive

Both providers add equivalent `publish_if_value` methods:

```python
def publish_if_value(
    self,
    condition_key: str,
    expected_value: bytes,
    *,
    result_key: str,
    result_value: bytes,
    completion_value: bytes,
    ttl: float,
) -> bool: ...
```

The fixed internal Lua script performs:

```lua
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('set', KEYS[2], ARGV[2], 'PX', ARGV[3])
  redis.call('set', KEYS[1], ARGV[4], 'PX', ARGV[3])
  return 1
end
return 0
```

`expected_value` is the active marker and `completion_value` is the completed
marker for the same validated token. The provider rejects identical condition
and result keys before `EVAL`. `False` means ownership was lost and is not a
provider failure. Invalid Redis responses and script/ACL failures remain
explicit `RedisProviderError`s. There is no non-atomic or unbounded fallback.

## Synchronous Data Flow

1. Validate the key and loader, derive Redis keys, and compute a monotonic
   coordination deadline. This deadline governs acquisition and remote waiting,
   not execution of a user loader after ownership is acquired.
2. Enter the wrapped cache's `get_or_load` immediately, passing one private
   distributed-loader closure. An existing local hit never invokes the closure
   or touches Redis. Same-key local callers join the cache's existing flight, so
   only one distributed flight per cache/key performs Redis acquisition or
   polling.
3. The distributed flight creates one `secrets.token_urlsafe(32)` token per
   actual acquire attempt, validates its shape, builds active/completed marker
   bytes, increments `max_attempts` only when it is about to issue
   `set_if_absent`, and checks the coordination deadline immediately before and
   after every acquisition/wait Redis command. A successful acquisition records
   a separate monotonic lease deadline from the command completion time. If the
   acquire response arrives after the coordination deadline, the caller does not
   start its user loader; it performs one bounded compare-delete and returns the
   coordination-timeout error.
4. If acquired, call the user loader directly inside the cache-owned flight and
   encode its successful result before returning from the private closure. This
   preserves the cache's existing supersession behavior: publication represents
   the successful loader result snapshot, while the borrowed cache independently
   decides whether that result is stored after the closure returns.
5. If the lease deadline has passed after the loader returns, emit `lease-lost`
   and return the locally computed result without encoding or publishing.
   Otherwise atomically publish the encoded loader result and completed marker
   through `publish_if_value`. On `False`, emit `lease-lost` and return the
   locally computed result. On loader, codec, or publication failure, issue at
   most one I/O-bounded compare-delete cleanup even when the lease deadline has
   just passed, then propagate the primary failure.
6. If acquisition loses, fetch one bounded atomic coordination snapshot:
   - missing marker: consume no poll and return to acquisition;
   - active marker: ignore any leftover result, consume one poll, sleep, and
     fetch another snapshot directly without another acquire command;
   - completed marker: require a present in-bound result, decode only for its
     token, and return the decoded value from the private closure; the outer
     cache flight stores it without calling the user loader;
   - malformed/oversized marker or completed result: fail explicitly.
7. Poll with exponential backoff capped by `max_poll_interval` and full jitter,
   additionally bounded by `max_polls` and remaining time. Random jitter is
   generated once per delay and is test-injectable internally. Exhausting time,
   attempts, or polls raises `RedisCoordinationTimeoutError` with a stable code.
   `max_attempts` counts only actual `SET NX` commands; `max_polls` counts only
   active-marker delay/snapshot cycles.

No new acquisition, snapshot, or poll command starts after the coordination
deadline. A command started just before it may overrun by at most the validated
provider I/O bound; the remote-wait wall-clock ceiling is therefore
`wait_timeout + redis_io_timeout` plus scheduler tolerance. The single
owner-cleanup exception may start after either deadline and is separately bounded
by `redis_io_timeout`. Once timely acquisition succeeds, owner publication may
start after the coordination deadline but only before the separately recorded
lease deadline, and it is individually bounded by `redis_io_timeout`. The owner
path has no wall-clock ceiling because user code is unbounded. The wait timeout
does not interrupt a sync user loader or a sync local caller already coalesced
behind that in-process loader; those preserve the existing
`TTLCache.get_or_load` contract.

## Asynchronous Data Flow and Cancellation

The async coordinator follows the same state machine with awaited provider and
cache operations and `asyncio.sleep` for bounded polling.

- Cancellation of the cache-owned distributed flight stops its polling
  immediately and is re-raised unchanged after required owner cleanup.
- An individual local caller cancellation returns `CancelledError` to that
  caller, but if another local waiter remains, the cache-owned distributed flight
  continues and may still poll, load, publish, and fill the shared local cache.
  Only cancellation of the last local waiter triggers the existing
  `AsyncTTLCache` flight cancellation and the coordinator owner-cleanup path.
- The borrowed `AsyncTTLCache` owns the one internal cache-loader task. The
  coordinator's distributed closure owns only its Redis cleanup task. Owner
  cancellation triggers one compare-delete cleanup task; repeated cancellation
  is remembered while a shield/await loop drives that cleanup to terminal
  completion, then the original `CancelledError` is re-raised.
- The coordinator creates no detached task. `AsyncTTLCache` may briefly retain
  its documented internal flight after its last local caller schedules cancellation;
  deterministic tests wait for that cache-owned task to reach terminal state and
  prove convergence even when a hostile loader delays or suppresses its first
  cancellation.
- Cancellation is never translated to timeout, retried, encoded, cached, or
  published.
- The borrowed `AsyncTTLCache` and `AsyncRedisProvider` retain their existing
  event-loop affinity rules.

## Consistency and Failure Semantics

- A local hit is returned even when Redis is unavailable because no coordination
  is needed.
- Any Redis failure after a local miss is explicit; the coordinator does not run
  an uncoordinated loader as fallback.
- User loader failures and cancellations are not encoded or published and the
  matching active marker is released through the explicit provider call. If
  cleanup also fails, the original loader exception or `CancelledError` remains
  the raised primary type and its caller-owned cause chain and notes are not
  replaced. The coordinator adds one static redacted PEP 678 note containing
  only the cleanup stable code and emits `cleanup_failed=True`; it never inserts
  the cleanup error into or overwrites the caller's chain. With no primary
  failure, cleanup failure is raised directly.
- Redis artifacts are untrusted and unauthenticated. Token matching prevents
  attempt mixing, not malicious modification. Payload codecs must independently
  validate expected metadata/trust policy and bounded input and must not elevate
  trust from Redis-controlled metadata or use unsafe deserializers for an
  attacker-writable Redis deployment.
- Matching completed-envelope decode failure is explicit. Token-mismatched
  envelopes are stale coordination artifacts and are ignored within the bounded
  retry loop; active snapshots never decode leftover results.
- Oversized encode fails before a newly loaded value enters the local cache.
- If a loader exceeds `lease_ttl`, a peer may acquire and load. The stale owner
  can still return its own local value, but atomic publication fails and it
  cannot overwrite or release the newer attempt.
- Result and completion-marker TTLs bound key cleanup. Operators may remove one
  rollout namespace by scanning the documented namespace-digest prefix during
  rollback; normal operation never uses `KEYS`.
- This design coordinates cache loads only. It does not fence writes performed
  by user loaders against external systems.

## Failure Modes and Required Proof

1. **Owner crashes or is abandoned:** the lease TTL expires; a distributed flight retries and
   makes bounded progress.
2. **Owner exceeds its lease:** a new owner may load; the stale owner receives
   `publish_if_value == False`, returns locally, and cannot publish or delete the
   new lease.
3. **Loader raises or is cancelled:** no envelope is published; matching cleanup
   runs and the original failure/cancellation remains observable.
4. **Redis becomes unavailable:** local hits still work; every cold-path Redis
   failure is explicit and redacted.
5. **Envelope is stale, malformed, oversized, or undecodable:** mismatched tokens
   are ignored; matching corrupt artifacts fail explicitly; all loops remain
   deadline-bounded.
6. **A local caller is cancelled or a distributed flight times out:** the
   cancelled caller never runs the user loader itself. Other local callers may
   keep the shared cache-owned flight alive and it may later fill the cache. The
   last local cancellation converges the flight and owner cleanup without a task
   leak; no path extends/deletes another owner's marker.
7. **Local cache state is superseded during loading:** the coordinator publishes
   the successful loader snapshot while the cache applies its existing local
   supersession rule after the distributed closure returns. Direct cache
   mutation is local-only and is not a distributed invalidation contract.
8. **Lua is denied or returns an invalid response:** the provider raises an
   explicit redacted failure and never falls back to racy commands.

## Testing Strategy

### Unit and contract tests

- exact ordered exports, signatures, frozen options, enum/error values, observer
  schema, constructor dependency types, and borrowed lifecycle;
- namespace/duration/attempt/key validation, including empty key, exact bounds,
  non-finite durations, booleans, and oversized UTF-8 input;
- deterministic key derivation without raw key/namespace leakage;
- a same-cache burst proves one local distributed flight, one token/acquire
  stream, and no per-caller Redis polling;
- sync/async local hit, winner, distributed result reuse, unrelated-key independence,
  stale marker, marker race, retry exhaustion, timeout, loader failure, codec
  failure, oversized result, lease loss, and Redis failure parity;
- deterministic async cancellation before acquire, while polling, during loader,
  and during repeated owner cleanup cancellation with eventual terminal
  cache-owned and coordinator-owned tasks;
- late-acquire response, loader completion, loader failure, and cancellation
  after the coordination deadline prove that no late user loader or distributed-wait
  command starts, publication obeys the lease deadline, and the single bounded
  owner cleanup remains permitted;
- absent, infinite, excessive, or retry-enabled provider I/O settings fail
  construction, including a non-empty `retry_on_error`; an isolated server/proxy
  that accepts but never responds proves the documented remote-wait ceiling;
- a forged completed envelope cannot elevate caller codec trust through
  Redis-controlled metadata and fails explicitly without leaking artifact text;
- observer failure isolation and hostile-marker redaction.

### Provider tests

- sync/async bounded snapshot and `publish_if_value` command shape, exact return
  validation, active/completed state, exact/+1 artifact limits, distinct-key
  validation, token mismatch, TTL conversion, ACL/script failure, and no
  fallback;
- a deterministic race proving a stale owner cannot publish over a replacement
  lease or shorten/delete it.

### RedisServer integration tests

- independent sync coordinator instances collapse one same-key cold burst to one
  user-loader execution;
- independent async coordinator instances prove the same contract;
- unrelated keys progress independently under contention;
- abandoned owner, lease expiry, stale envelope, stale-owner cleanup, Redis
  outage, timeout, cancellation, oversized payload, and decoding failure are
  deterministic and bounded;
- outage tests use an isolated client/proxy or run last with explicit readiness
  restoration so the module-scoped server cannot poison later tests;
- clients and the single module-scoped `RedisServer` are explicitly closed, and
  Testcontainers tests run serially with event/barrier synchronization rather
  than timing sleeps.

An instrumented-provider stress test uses 64 callers across eight independent
coordinators and asserts loader count `1`, at most one distributed flight per
coordinator, Redis read/poll counts within the option-derived budget, and no new
acquisition/snapshot/poll command after the coordination deadline while allowing
only the specified bounded owner publication/cleanup rules. A non-gating
benchmark records local-hit baseline, contended cold-burst latency, and Redis
commands per caller.

The exact per-coordinator distributed-flight command budget is:

- `SET NX` acquire commands: at most `max_attempts`;
- bounded snapshot commands: at most `max_attempts + max_polls`;
- successful publication commands: at most one;
- owner compare-delete cleanup commands: at most one.

The eight-coordinator stress case asserts eight times each bound, while all 64
same-process callers still share only eight local distributed flights.

### Validation

Run targeted tests first, then:

```bash
uv sync --all-packages
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv build --all-packages
actionlint
git diff --check
```

Packaging-isolation smoke checks must prove the default `bluetape` wheel remains
Redis-free and the focused cache/Redis wheels import together.

## Documentation and Rollout

- Update `packages/bluetape-cache-redis/README.md` and `README.ko.md` together
  with install, sync/async examples, consistency, security, limits, cleanup,
  rollout, rollback, and lease-expiry behavior.
- Update root `README.md`/`README.ko.md`, focused package README locale parity,
  `WIP.md`, and `CHANGELOG.md` as required deliverables. Remove the old wording
  that coordination remains future issue #55 work and record the new public API.
- No dependency, package registration, workflow topology, or default-extra
  change is planned. If implementation proves one necessary, reopen this spec
  and its hazard review before editing metadata or CI.
- Package version changes are deferred to the milestone release PR; this feature
  PR changes unreleased source contracts and validates focused/default wheel
  imports without publishing artifacts.

### Least-privilege Redis deployment

The coordinator requires direct/script access to `SET`, `GET`, `DEL`, `EXISTS`,
`STRLEN`, `GETRANGE`, and `EVAL` only for the derived namespace-prefix
pattern `~bluetape:cache:coord:<namespace_id>:*`. ACLs must permit both script
execution and the commands invoked by the fixed scripts. Integration tests prove
one allowlisted principal succeeds and separately prove denied snapshot,
publication, and cleanup commands fail explicitly without fallback.

Transport security is inherited from the borrowed provider. Production guidance
uses `rediss://` or an SSL-configured redis-py client, validates the peer under
caller policy, and never downgrades or constructs a fallback plaintext client.

### Rollout and rollback runbook

All participating processes must move to the same stable, versioned namespace to
obtain the single-loader guarantee. During overlap with direct-cache processes or
processes using another namespace, duplicate user loaders are expected and must
be safe. A namespace/schema change therefore uses a coordinated cutover or an
explicit overlap window; it is never presented as continuous mutual exclusion.

Rollback and emergency cleanup are ordered:

1. Stop new coordinator traffic to the old namespace and switch all participants
   to local-only behavior or one replacement namespace.
2. Wait at least `max(lease_ttl, result_ttl) + redis_io_timeout` and verify
   coordination events/readiness show the old route is quiescent. Abort cleanup
   if traffic resumes.
3. Use bounded `SCAN` batches over the namespace-digest prefix and batched
   `UNLINK` or `DEL`; never use `KEYS`, and never delete the active namespace.
4. Record scanned, deleted, and remaining counts and recheck quiescence.

When Redis is unavailable, existing local hits continue, cold calls fail
explicitly, and there is no automatic fallback or circuit breaker. After Redis
readiness recovers, new calls resume normally and bounded stale markers expire;
manual cleanup is normally unnecessary. Operators alert on stable provider and
coordination codes before re-enabling traffic.

### Minimal composition examples

Synchronous callers own every lifecycle dependency:

```python
cache = TTLCache[str, Order](default_ttl=60.0, max_size=10_000)
codec = ResultEnvelopeCodec(payload_codec=OrderCodec())
options = RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3")

with SyncRedisProvider.from_url(
    redis_url,
    socket_connect_timeout=0.25,
    socket_timeout=0.25,
    retry_on_timeout=False,
) as provider:
    coordinator = SyncRedisLoadCoordinator(cache, provider, codec, options=options)
    order = coordinator.get_or_load(order_id, load_order, ttl=30.0)
```

The async form uses the same policy and explicit owned-provider close:

```python
cache = AsyncTTLCache[str, Order](default_ttl=60.0, max_size=10_000)
codec = ResultEnvelopeCodec(payload_codec=OrderCodec())
options = RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3")

async with AsyncRedisProvider.from_url(
    redis_url,
    socket_connect_timeout=0.25,
    socket_timeout=0.25,
    retry_on_timeout=False,
) as provider:
    coordinator = AsyncRedisLoadCoordinator(cache, provider, codec, options=options)
    order = await coordinator.get_or_load(order_id, load_order, ttl=30.0)
```

Choose `lease_ttl` above the normal worst-case loader duration with operational
margin, `result_ttl` long enough for distributed waiters to observe completion,
and `wait_timeout` plus the inspected I/O ceiling within the caller latency
budget. No setting creates fencing or safe external side effects after lease
expiry.

Conflicting coordinator bindings on one cache are documented rather than tracked
in a process-global registry: a registry would add global ownership, weak-reference
and thread/loop lifecycle hazards to otherwise borrowed objects. Examples and
contract docs require one cache/one coordinator; violating it is unsupported and
the cache's first local flight may apply the wrong namespace/options.

## Acceptance Criteria

- Sync and async public semantics are equivalent and Python-native.
- Same-key cold bursts across independent coordinators execute one user loader
  while the lease remains valid.
- Unrelated keys remain independent.
- Wait, backoff/jitter polling, poll count, retry, lease, result, Redis I/O, and
  envelope sizes are bounded; no new acquisition/snapshot/poll command starts
  after the coordination deadline.
- Only a matching owner atomically publishes or releases; stale owners cannot
  affect newer attempts.
- Waiters reject stale envelopes and never run their user loader when a matching
  result is available.
- Loader failures and cancellations are never reusable values.
- Redis failures remain explicit and redacted.
- Async cancellation and every owned cleanup path leave no pending tasks or
  leaked clients.
- RedisServer tests and the complete repository validation ladder pass.
- Documentation covers consistency, security, operations, rollout, rollback,
  cleanup, and limits.
- Independent spec, plan, pre-PR, and PR reviews converge at P0=0 and P1=0.

## Definition of Done

- The approved behavior is implemented without changing local-cache contracts or
  default-install dependencies.
- Every issue acceptance criterion maps to deterministic unit or serial Redis
  integration evidence.
- Full lint, format, tests, builds, actionlint, packaging isolation, and GitHub
  CI pass.
- The PR targets `develop`, mirrors issue #55 metadata, is assigned to `debop`,
  and ends with `## DoD Status`.
- Merge occurs only after all required CI checks succeed and live reviews have no
  unresolved blockers.
- After merge, local `develop` is synchronized and the merged #55 worktree and
  branch are deleted after ancestry is verified.
