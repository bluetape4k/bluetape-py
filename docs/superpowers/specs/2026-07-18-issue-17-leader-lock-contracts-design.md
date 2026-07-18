# Issue #17 Leader Election and Distributed Lock Contracts Design

Date: 2026-07-18 KST
Target issue: #17 - `feat: add leader election and distributed lock contracts`
Target milestone: `0.2.0`
Work type: Type A - Full Feature

## Approved Delivery Shape

Add two focused Python distributions:

1. `bluetape-leader`, a stdlib-only backend-neutral contract package using the
   import path `bluetape.leader`;
2. `bluetape-leader-redis`, a Redis proof adapter using the import path
   `bluetape.leader.redis` and depending only on `bluetape-leader` plus
   `redis==8.0.1`.

This follows the structural boundary of `bluetape4k-leader`: its `leader-core`
module owns common election contracts and lifecycle values, while Lettuce,
Redisson, MongoDB, JDBC, R2DBC, etcd, Kubernetes, and other implementations
remain separate backend modules. Python has one selected Redis client,
`redis-py`, with both synchronous and asyncio clients, so the first Python
Redis adapter is one distribution rather than artificial client-specific
Lettuce/Redisson equivalents.

The user approved this boundary and the initial single-leader scope on
2026-07-18. This specification does not authorize implementation planning,
production-code edits, PR creation, merge, release, tag, or publication. Those
remain later workflow gates.

## Problem

Applications need to ensure that only one contender performs a scheduled or
exclusive operation, but a plain Redis `SET NX PX` call is not a complete
leadership contract. It does not by itself define ownership, safe release,
renewal, loss detection, cancellation cleanup, fencing, caller-owned client
lifecycle, or the distinction between contention and backend failure.

A Redis-shaped API in the core package would also make future SQL, MongoDB,
etcd, Kubernetes Lease, or other backends conform to accidental Redis details.
The first delivery must therefore establish backend-neutral execution and
lease contracts, then prove them with an atomic single-instance Redis adapter.

## Current Evidence

- Live issue #17 requires API contracts, a Redis proof implementation, owner
  tokens, TTL renewal, fencing or slot semantics where applicable, safe
  release, concurrent-contender tests, cancellation cleanup, and documented
  operational caveats.
- `bluetape4k-leader` separates `leader-core` from every backend module. Its
  core contains sync, async, and coroutine electors, election options, lease
  snapshots, explicit run results, active lock handles, renewal outcomes, and
  a scoped auto-extender lifecycle.
- `bluetape4k-leader` distinguishes physical `nodeId` from the audit or fencing
  identity carried by a lease. Its cancellation contracts propagate
  cancellation rather than classifying it as an action failure.
- `bluetape4k-leader` Redis implementations use owner tokens, `SET NX PX`,
  token-checked Lua extension and release, monotonic acquisition deadlines,
  and lifecycle-owned watchdog shutdown.
- `bluetape-go/leader` similarly keeps generic contracts separate from Redis,
  while `bluetape-go/lock/redis` demonstrates the smaller owner-token lock
  primitive. Neither sibling is a mechanical Python API template.
- Existing `bluetape-cache` and `bluetape-cache-redis` prove the repository's
  parent-contract plus nested-adapter namespace pattern. The leader packages
  reuse that packaging structure without depending on cache, serde, or
  compression.
- Redis documents the single-instance safety pattern as a random unique owner
  value written with `SET ... NX PX`, followed by owner-conditional release.
  Lua scripts execute atomically, and fencing counters can be generated with
  an incrementing Redis value.

## Authority References

- sibling architecture and lifecycle authority:
  `../bluetape4k-leader/leader-core` and
  `../bluetape4k-leader/leader-redis-lettuce`;
- additional sibling semantics:
  `../bluetape-go/leader`, `../bluetape-go/leader/redis`, and
  `../bluetape-go/lock/redis`;
- Redis single-instance lock and fencing caveats:
  <https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/>;
- Redis Lua atomicity:
  <https://redis.io/docs/latest/develop/programmability/eval-intro/>;
- Redis `SET` and increment semantics:
  <https://redis.io/docs/latest/commands/set/> and
  <https://redis.io/docs/latest/commands/incr/>.

Sibling sources establish structural similarity; the live Python repository's
packaging, typing, cancellation, and borrowed-client conventions remain the
Python API authority.

## Goals

1. Establish stable sync and asyncio contracts for single-leader execution and
   non-reentrant distributed locking.
2. Keep backend-neutral contracts stdlib-only and open to future independent
   backend distributions.
3. Distinguish contention, action failure, lease loss, invalid ownership, and
   backend failure without treating them as one falsey result.
4. Guarantee owner-checked acquire, renew, and release in the Redis adapter.
5. Issue a strictly increasing Redis fencing token on every successful new
   acquisition while the authoritative counter is not deleted, decreased, or
   restored from an older snapshot; the adapter never resets it.
6. Bound all waiting and renewal lifecycles, use monotonic local deadlines,
   and avoid detached threads, tasks, registries, or package-owned clients.
7. Preserve Python cancellation semantics while performing best-effort,
   awaited cleanup.
8. Document the single-instance availability and split-brain limitations so
   callers do not mistake a lease for a linearizable system-wide guarantee.

## Non-Goals

- Redis Cluster, Redis Sentinel failover safety, Redlock, quorum locks, or
  multi-primary coordination;
- group/slot leadership, strategic candidate election, fairness, priority,
  queues, reentrancy, read/write locks, semaphores, or barriers;
- MongoDB, SQL, etcd, ZooKeeper, Consul, DynamoDB, Kubernetes Lease, Hazelcast,
  or local-process implementations;
- framework decorators, AOP, dependency injection, Spring/Ktor analogues,
  global active-lock context, metrics, tracing, history recording, or logging;
- forcefully interrupting synchronous user actions after lease loss;
- package-owned retry policies for arbitrary backend outages;
- client creation from URLs, credential discovery, connection-pool ownership,
  client shutdown, TLS policy, ACL provisioning, or Redis server lifecycle;
- changing `bluetape-cache-redis` coordination semantics or moving cache code
  into the leader packages;
- release, tag, publication, merge, or unrelated baseline-test repair.

## Structural Mapping From `bluetape4k-leader`

| JVM structure | Python first-slice structure | Decision |
|---|---|---|
| `leader-core` | `bluetape-leader` | Same backend-neutral package boundary |
| `LeaderElector` | `LeaderElector` protocol | Sync action execution |
| `SuspendLeaderElector` | `AsyncLeaderElector` protocol | Native asyncio action execution |
| `LeaderElectionOptions` | frozen `LeaderElectionOptions` | Shared wait/lease/lifecycle policy |
| `LeaderLease` | `LeaderLease` and `FencedLeaderLease` | Physical node and fencing identity remain distinct |
| `LeaderRunResult` | `Elected`, `Skipped`, `ActionFailed` | No `None` ambiguity |
| `LeaderLockHandle` | `LockLease` / `AsyncLockLease` | Active ownership and renewal handle |
| `ExtendOutcome` | `Renewed`, `NotHeld`, `RenewBackendFailure` | Explicit renewal classification |
| `LeaderLeaseAutoExtender` | scoped internal renewer | Exists only inside a context/run call |
| Lettuce + Redisson modules | `bluetape-leader-redis` | One selected Python client supports sync and async |
| group/strategic/local/integrations | follow-up issues | No speculative surface in Issue #17 |

The Python design intentionally improves one ambiguity in the JVM lease:
`auditLeaderId` can represent either a node or fencing identity there. Python
uses a base `LeaderLease` for audit and physical node identity and a distinct
`FencedLeaderLease` capability with an integer `fencing_token`. Callers cannot
accidentally compare a physical node ID as though it were a fencing number.

## Package Boundaries

```text
packages/bluetape-leader/
├── pyproject.toml
├── README.md
├── README.ko.md
├── src/bluetape/leader/
│   ├── __init__.py
│   ├── _contracts.py
│   ├── _errors.py
│   ├── _options.py
│   ├── _results.py
│   └── _values.py
└── tests/

packages/bluetape-leader-redis/
├── pyproject.toml
├── README.md
├── README.ko.md
├── src/bluetape/leader/redis/
│   ├── __init__.py
│   ├── _async_lock.py
│   ├── _async_elector.py
│   ├── _keys.py
│   ├── _lock.py
│   ├── _elector.py
│   ├── _scripts.py
│   └── _support.py
└── tests/
```

### `bluetape-leader`

- Distribution: `bluetape-leader`
- Import: `bluetape.leader`
- Python: `>=3.13`
- Runtime dependencies: none
- Root namespace initializer: absent
- `bluetape.leader.__path__`: extended so focused backend wheels can add
  nested modules
- Package-owned background workers or loggers: none

### `bluetape-leader-redis`

- Distribution: `bluetape-leader-redis`
- Import: `bluetape.leader.redis`
- Python: `>=3.13`
- Runtime dependencies: `bluetape-leader==0.1.0`, `redis==8.0.1`
- Test dependencies: `bluetape-testcontainers`, `pytest`, `pytest-asyncio`
- Client ownership: injected sync or asyncio Redis clients are borrowed and
  never closed by this package
- Cache/serde/compression dependency: forbidden

The root workspace registers both packages and their local sources. The thin
meta distribution gains explicit `leader` and `leader-redis` extras. The
default `bluetape` install remains core-only. Existing aggregate-extra policy
must not be widened implicitly; any `all` or `dev` change must follow the live
meta-package convention at implementation time and be tested explicitly.

## Core Public API

`bluetape.leader.__all__` exposes the following categories in a fixed reviewed
order: errors, options, immutable values, run results, renew outcomes, sync
protocols, and async protocols.

### Errors

```python
class LeaderError(Exception): ...
class InvalidLeaderOptionsError(LeaderError, ValueError): ...
class InvalidLockNameError(LeaderError, ValueError): ...
class LeaderBackendError(LeaderError): ...
class LeaderLeaseLostError(LeaderError): ...
class LeaderReleaseError(LeaderError): ...
class LeaderExecutionError(LeaderError): ...
```

- Validation errors identify only the invalid field category and never echo a
  lock name, node ID, owner token, Redis key, URL, credential, or action value.
- `LeaderBackendError` sanitizes an ordinary backend exception and is raised
  `from None`; it does not expose raw cause text, args, credentials, command
  values, or URLs through its message or formatted traceback.
- `LeaderLeaseLostError` means the owner token no longer matches, the lease
  expired, or takeover occurred. It is not a retryable contention result.
- `LeaderReleaseError` means the caller requested explicit release but the
  lease was already lost or ownership could not be proven.
- `LeaderExecutionError` is the redacted composite raised when an ordinary
  action failure and a renewal/release lifecycle failure both occur. Its
  `action_cause: Exception` and `lifecycle_cause: LeaderError` properties are
  excluded from `repr`; the lifecycle property accepts only a sanitized
  package error and never a raw backend exception. Its message contains neither
  cause text nor caller values.
- `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, and
  `asyncio.CancelledError` are never wrapped.

### Options

```python
@final
@dataclass(frozen=True, slots=True, kw_only=True)
class LeaderElectionOptions:
    wait_time: timedelta = timedelta(seconds=5)
    lease_time: timedelta = timedelta(seconds=60)
    node_id: str | None = None
    min_lease_time: timedelta = timedelta(0)
    auto_renew: bool = False
    renew_interval: timedelta | None = None
```

Validation rules:

- `wait_time >= 0`;
- `lease_time > 0`;
- `0 <= min_lease_time <= lease_time`;
- `node_id`, when supplied, is 1 through 256 UTF-8 bytes and contains at least
  one non-whitespace character; the accepted value is preserved without
  trimming or normalization;
- `renew_interval`, when supplied, is positive and strictly less than
  `lease_time`;
- `auto_renew=True` with no interval derives exact `lease_time / 3`;
- exact built-in `timedelta`, `bool`, and `str` inputs are required so custom
comparison or conversion code cannot run during validation.

The core package does not impose Redis millisecond resolution. The Redis
adapter converts durations to whole milliseconds, rejects a positive duration
that converts below one millisecond, and rounds a derived renew interval down
only at that adapter boundary.

Waiting uses `time.monotonic_ns()` or the event loop's monotonic clock. Wall
clock is used only for best-effort observation timestamps.

### Lease Snapshots

```python
@dataclass(frozen=True, slots=True, repr=False)
class LeaderLease:
    audit_leader_id: str = field(repr=False)
    node_id: str | None = field(repr=False)
    elected_at: datetime | None
    lease_until: datetime | None


@final
@dataclass(frozen=True, slots=True, repr=False)
class FencedLeaderLease(LeaderLease):
    fencing_token: int = field(repr=False)
```

- `audit_leader_id` is a safe caller-facing identity, not the secret owner
  token. Redis uses the decimal fencing token rendered as text for audit
  correlation only; downstream fencing comparisons use only the integer
  `fencing_token`.
- `node_id` is the physical caller-supplied identity and is never used as a
  fencing value.
- Redis always returns `FencedLeaderLease` with `fencing_token >= 1`.
- timestamps are timezone-aware UTC best-effort observations. They are not
  authorization checks and must not replace `is_held()` or fencing validation.
- owner tokens never appear in immutable snapshots, representations, events,
  errors, or public properties.
- both lease classes use a fixed redacted representation; node IDs, audit IDs,
  timestamps, and fencing tokens do not appear in `repr`.

### Run Results

```python
@dataclass(frozen=True, slots=True)
class Elected[T, LeaseT: LeaderLease]:
    value: T
    lease: LeaseT


@final
@dataclass(frozen=True, slots=True)
class Skipped:
    pass


@dataclass(frozen=True, slots=True)
class ActionFailed[LeaseT: LeaderLease]:
    cause: Exception = field(repr=False)
    lease: LeaseT


type LeaderRunResult[T, LeaseT: LeaderLease] = (
    Elected[T, LeaseT] | Skipped | ActionFailed[LeaseT]
)
```

- `run_if_leader()` returns `T | None` for familiarity with the sibling
  contract and propagates action exceptions. It is documented as ambiguous
  when the action itself returns `None`.
- `run_if_leader_result()` is the preferred precise API. It returns `Elected`
  even when the action returns `None`, returns `Skipped` only for contention
  timeout, and returns `ActionFailed` only after acquisition and an ordinary
  action exception.
- Acquisition, renewal setup, and release failures are infrastructure errors
  and are raised, not classified as `Skipped` or `ActionFailed`.
- Async cancellation is re-raised after awaited cleanup and is never converted
  to `ActionFailed`.

### Renewal Outcomes

```python
@dataclass(frozen=True, slots=True)
class Renewed:
    observed_lease_until: datetime | None


@final
@dataclass(frozen=True, slots=True)
class NotHeld:
    pass


@dataclass(frozen=True, slots=True)
class RenewBackendFailure:
    cause: LeaderBackendError = field(repr=False)


type RenewOutcome = Renewed | NotHeld | RenewBackendFailure
```

`observed_lease_until` is diagnostic only. Redis expiry is server-owned and
the client observation can include network latency and clock skew.
Raw backend exceptions are classified only inside the failing frame, converted
to sanitized `LeaderBackendError`, and never retained in renewal outcomes or
composite lifecycle properties.

### Lock Protocols

```python
@runtime_checkable
class LockLease[LeaseT: LeaderLease](Protocol):
    @property
    def lease(self) -> LeaseT: ...
    def renew(self, lease_time: timedelta | None = None) -> RenewOutcome: ...
    def is_held(self) -> bool: ...
    def assert_held(self) -> None: ...
    def release(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...


@runtime_checkable
class DistributedLock[LeaseT: LeaderLease](Protocol):
    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LockLease[LeaseT] | None: ...
```

Async equivalents use `await renew`, `await is_held`, `await assert_held`,
`await release`, and `async with`. A lease is single-owner, non-reentrant, and
single-release. Releasing twice raises a value-free `LeaderReleaseError`.

`is_held()` returns immediately without Redis I/O for a locally released or
already-lost handle. Otherwise it performs one bounded owner-comparison script
operation. Mismatch, expiry, or takeover returns `False`; malformed state,
missing expiry, and backend failure raise `LeaderBackendError`.
`assert_held()` performs that same single probe and raises
`LeaderLeaseLostError` on `False`. Both are
point-in-time observations with an immediate TOCTOU window, not substitutes
for fencing.

### Elector Protocols

```python
@runtime_checkable
class LeaderElector[LeaseT: LeaderLease](Protocol):
    def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> T | None: ...

    def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LeaderRunResult[T, LeaseT]: ...
```

`AsyncLeaderElector[LeaseT]` accepts `Callable[[LeaseT], Awaitable[T]]`. The
action receives the lease snapshot so callers can forward a fencing token to
downstream state-changing operations. The active handle remains internal to
the scoped execution; callers needing explicit renew/release use the lock API.

## Redis Adapter Public API

`bluetape.leader.redis` exports:

- `RedisDistributedLock`
- `AsyncRedisDistributedLock`
- `RedisLeaderElector`
- `AsyncRedisLeaderElector`

Constructors accept a borrowed exact redis-py client and an optional safe key
prefix. Sync classes accept `redis.Redis`; async classes accept
`redis.asyncio.Redis`. Constructors reject the wrong client family before any
Redis command. They do not accept URLs, passwords, connection options, or
client factories.

“Exact redis-py client” means `type(client) is redis.Redis` for sync and
`type(client) is redis.asyncio.Redis` for async. Subclasses, overridden
`execute_command` paths, blocking instrumentation hooks, duck-typed wrappers,
proxy objects, Redis-compatible clients, and the wrong family are rejected
with a value-free `TypeError` because their execution time cannot be included
in the hard operation envelopes. Instrumentation remains caller-owned outside
the adapter command path. Controlled unit fakes enter only through a private
command-runner seam and are not accepted by public constructors.

The adapter supports only a standalone writable Redis primary. A replica is
rejected by the first write. Sentinel-managed failover, `RedisCluster`, proxy
multi-primary endpoints, and replica-reading clients are explicitly unsafe and
unsupported rather than auto-detected as safe. No preflight API is part of
Issue #17; deployment checks use caller-owned
Redis tooling because a client-side probe cannot prove failover topology
safety.

Before the first acquire, the adapter validates the borrowed client's public
pool configuration:

- `socket_connect_timeout` and `socket_timeout` are finite positive numbers;
- command retry-on-timeout is disabled and the effective redis-py command
  retry count is exactly zero, so a response-lost script is never silently
  redispatched;
- `health_check_interval == 0`, so redis-py cannot insert an implicit `PING`
  into a bounded command operation;
- custom connection callbacks, `redis_connect_func`, dynamic credential
  providers, command hooks, and proactive maintenance/reconnect paths are
  absent; static username/password configuration remains caller-owned and
  redacted;
- TLS/SSL connections are unsupported in the first slice because redis-py's
  configurable TLS handshake does not expose a hard whole-handshake deadline;
  deployments use a protected network with numeric IPs or a Unix-domain socket;
- connection-pool wait is finite and inspectable;
- the endpoint is a numeric IPv4/IPv6 literal or Unix-domain socket path;
  hostnames are rejected because sync DNS resolution is outside redis-py's
  socket connect timeout, and sync/async share the same bounded endpoint rule;
- the connection handshake round-trip count `H` is computed from the exact
  pinned redis-py configuration: static `AUTH`/`HELLO`, `CLIENT SETNAME`, the
  built-in `CLIENT SETINFO` fields, and `SELECT` each contribute their known
  response count;
- the cold connection/reconnect envelope is
  `E = socket_connect_timeout + H * socket_timeout`;
- the primitive command envelope is
  `P = pool_wait + E + socket_timeout`, covering worst-case reconnect plus the
  requested command, with no command retry or retry backoff;
- the script envelope is `S = 2P` for `EVALSHA` plus the one permitted `EVAL`
  fallback;
- acquire uncertainty envelope is `A = S + P` for script plus reconciliation;
- renew envelope is `N = S`;
- release uncertainty envelope is `R = 2S + P` for initial script,
  reconciliation, and the one permitted same-owner repeat;
- when auto-renew is requested, `N < renew_interval` and
  `N + renew_interval < lease_time`.

If the pool is custom or opaque and these invariants cannot be proven, public
adapter construction fails closed for both explicit locking and auto-renew.
The adapter never mutates caller client settings. Infinite or unprovable
timeouts are rejected before attempting acquisition.

The optional prefix is an exact built-in ASCII `str`, 1 through 64 bytes,
matching `[A-Za-z0-9._-]+`. Braces, whitespace, separators, control characters,
Unicode, and secret or credential material are forbidden. The default is
`bluetape-leader`; the fixed separators shown below are package-owned.

The electors compose the corresponding lock implementation instead of
duplicating acquire, renew, release, token, deadline, and key logic.

Concrete typing fixes the generic lease capability:

```python
class RedisDistributedLock(DistributedLock[FencedLeaderLease]): ...
class AsyncRedisDistributedLock(AsyncDistributedLock[FencedLeaderLease]): ...
class RedisLeaderElector(LeaderElector[FencedLeaderLease]): ...
class AsyncRedisLeaderElector(AsyncLeaderElector[FencedLeaderLease]): ...
```

Therefore Redis callbacks and results expose `FencedLeaderLease` directly to
static type checkers; callers do not cast a generic `LeaderLease` to reach the
fencing token.

## Normative Usage Shapes

Manual contention is checked before entering the acquired handle:

```python
handle = lock.try_acquire("daily-job", options)
if handle is None:
    return "skipped"
with handle as held:
    downstream_write(value, fencing_token=held.lease.fencing_token)
```

`with lock.try_acquire(...)` is not a supported shape because contention can
return `None`. Explicit manual use without a context receives no auto-renewer
and must call `release()` in `finally`.

The precise elector result preserves fencing and action classification:

```python
result = elector.run_if_leader_result(
    "daily-job",
    lambda lease: downstream_write(value, fencing_token=lease.fencing_token),
    options,
)
match result:
    case Elected(value=value, lease=lease): ...
    case Skipped(): ...
    case ActionFailed(cause=cause, lease=lease): ...
```

The downstream operation must atomically compare the incoming integer token
with its resource-specific stored high-watermark and commit both the new
high-watermark and business change. A separate check followed by a write is
not fencing.

Async cancellation uses the same result boundary. An externally cancelled
caller receives its original `CancelledError` only after the retained renew
and release tasks reach their bounded terminal states. Renewal loss does not
force-cancel arbitrary application code; the action can finish, but the scope
raises lease loss and cannot report success.

Async manual locking uses the same explicit contention guard:

```python
handle = await async_lock.try_acquire("daily-job", options)
if handle is None:
    return "skipped"
async with handle as held:
    await downstream_write(value, fencing_token=held.lease.fencing_token)
```

Cancellation of an async elector is observed normally by the caller:

```python
try:
    await async_elector.run_if_leader("daily-job", run_job, options)
except asyncio.CancelledError:
    # The elector has already bounded, stopped, and awaited its owned cleanup.
    raise
```

## Redis Data Model

The logical lock name is an exact built-in `str`, contains at least one
non-whitespace character, and is at most 1,024 UTF-8 bytes. It is not trimmed,
case-folded, or Unicode-normalized: NFC and NFD spellings are distinct lock
identities. Compute
a SHA-256 hexadecimal digest over its exact UTF-8 bytes. With the default
prefix, use:

```text
bluetape-leader:{<digest>}:lease
bluetape-leader:{<digest>}:fence
```

The braces place both keys in the same Redis Cluster hash slot even though
Cluster operation is outside this issue. The raw lock name never becomes a
Redis key and is never logged by package code.

Prefix, digest algorithm, key suffixes, and record version together form a
coordination identity and remain immutable for the deployment lifetime. Old
and new identities do not mutually exclude one another. They cannot be changed
by rolling deployment. A migration requires stopping every contender, proving
the old lease absent, reconciling the downstream fencing high-watermark with a
new counter that is strictly greater, and then starting all contenders on one
new identity. Rollback is safe only to the identical prefix, derivation, and
record version.

All Issue #17 `0.1.x` implementations read and write only the exact `v1`
record. An unknown version fails closed as corruption. Any future record change
requires an explicitly compatible reader-first design or the stop-the-world
coordination-identity migration above; mixed writers are not assumed safe.

The lease value is a versioned, strictly parsed ASCII record containing:

```text
v1:<owner-token>:<fencing-token>
```

- owner token: generated once per logical acquisition attempt with
  `secrets.token_urlsafe(24)` and reused across command-uncertainty
  reconciliation;
- fencing token: positive Redis integer returned by `INCR`;
- parsing: exact field count, version, token shape, and canonical positive
  decimal fencing value; malformed records are backend failures, never treated
  as caller ownership.

The owner token and full lease value are secret capability material. They are
stored only in private slotted implementation state with redacted
representations.

## Redis Atomic Operations

### Acquire

One Lua script receives the lease key and fence key in `KEYS`, and the owner
token plus TTL milliseconds in `ARGV`:

1. inspect the lease key type, value, and `PTTL` atomically;
2. return contention only for a canonical `v1` record with a positive TTL;
3. return a corruption status for a wrong type, malformed record, missing TTL,
   or otherwise invalid existing lease;
4. increment the fence key;
5. read the counter back as a bulk decimal string and validate its canonical
   positive form without converting it through a Lua floating-point number;
6. write the exact `v1:owner:fence` value with `PX ttl`;
7. return the fencing token as its canonical decimal string.

This script makes ownership publication and fencing issuance one atomic Redis
operation. The counter key has no TTL and is never deleted by normal release.
Counter overflow or corruption fails closed as `LeaderBackendError`. Gaps are
allowed after a script failure, but a token is never reused. The strict
monotonic guarantee applies only while the authoritative counter is not
deleted, decreased, or restored from an older snapshot.

### Renew

One Lua script compares the lease value byte-for-byte with the caller's private
value and applies `PEXPIRE` only on equality. It returns `Renewed` on success
and `NotHeld` on mismatch, expiry, or takeover. It never creates a missing key.

### Probe

One read-only Lua script atomically inspects type, value, and `PTTL`, strictly
parses the canonical record, and compares the private expected record
byte-for-byte. It returns `HELD`, `NOT_HELD`, or `CORRUPT`. Missing keys,
expired keys, and a different canonical owner return `NOT_HELD`; wrong type,
malformed records, and canonical records without a positive expiry return
`CORRUPT`. It follows the same fixed `EVALSHA` then one `EVAL` fallback path,
so one public probe is one bounded script operation with envelope `S`; it is
not promised as one primitive Redis command round trip.

### Release

One Lua script compares the lease value byte-for-byte and then either:

- deletes it when the minimum lease duration has elapsed; or
- applies only the remaining minimum-lease TTL when the action finished early.

It returns `DELETED`, `MIN_TTL_APPLIED`, `NOT_HELD`, or `CORRUPT`. Both success
statuses are proven logical release and immediately transition the local handle
to `RELEASED`; the latter may leave the owner record visible only until its
shortened TTL. Mismatch, successor ownership, or natural expiry raises
`LeaderReleaseError` for explicit lock callers. Scoped elector cleanup records
the cleanup failure for propagation rules below but never deletes an unknown
owner's lease.

Direct `handle.release()` maps `NOT_HELD` to `LeaderReleaseError` because the
explicit release request could not be fulfilled. Context/elector exit maps the
same proven mismatch or expiry to `LeaderLeaseLostError`, because its primary
semantic is that protected execution outlived ownership. Corruption and
backend uncertainty remain sanitized backend/lifecycle errors in both paths.

Acquire, probe, renew, and release scripts use one fixed execution path: locally
computed SHA-1 with `EVALSHA`, then exactly one full-source `EVAL` fallback on
`NOSCRIPT`. Response-loss reconciliation instead uses exactly one fixed-source,
read-only `EVAL` command that atomically returns a strictly validated canonical
record only when `TYPE` is string and `PTTL` is positive. A value-only `GET`
cannot reject a persisted/no-expiry record, while an `EVALSHA` fallback would
not fit the one-command reconciliation envelope. The adapter does not call
`SCRIPT LOAD`. Every key is passed through `KEYS`; scripts do not construct
dynamic Redis keys internally.

## Acquisition, Deadlines, and Command Uncertainty

- `wait_time=0` dispatches exactly one acquisition attempt.
- `wait_time` is the retry/sleep budget, not a hard wall-clock bound on an
  already dispatched Redis command. No new acquire command is dispatched after
  its monotonic deadline.
- Each contention retry sleeps for deterministic-testable jitter in the closed
  range 40-60 milliseconds, capped by remaining deadline. This caps normal
  contention at 25 acquisition commands per second per contender. Asyncio uses
  `asyncio.sleep`; the production jitter source is process-local and does not
  expose lock identity.
- The maximum acquisition envelope is `wait_time + A`: at most one script
  operation already dispatched at the deadline plus its one-command
  reconciliation. Deterministic clock tests verify no extra acquire dispatch.
- Contention is the only condition that retries automatically.
- Authentication, protocol, parsing, script, connection, and configuration
  failures surface immediately as `LeaderBackendError`.
- A command timeout or disconnect after dispatch can leave the acquire outcome
  unknown. The adapter performs one bounded fixed read-only `EVAL`
  reconciliation over `TYPE`, `GET`, and `PTTL`, strictly parses the returned
  canonical positive-TTL record, and compares only its private owner-token
  field with `hmac.compare_digest`. A match recovers the fencing token from that
  record. An absent record or a different canonical owner proves no current
  ownership but not normal contention because the original backend response was
  lost. Both therefore raise sanitized `LeaderBackendError`; malformed state,
  missing expiry, or a second uncertain error also fails closed. Only an
  explicit `CONTENDED` script status is normal contention. The acquire script is
  never re-executed for the uncertain attempt.
- Renew and release operations are owner-conditional and idempotent with
  respect to another owner's state. After an uncertain release, absence means
  cleanup outcome is uncertain, different ownership means the old lease is no
  longer held, and the same owner triggers exactly one repeat of the identical
  owner-conditional release script with remaining minimum time recomputed from
  the original monotonic acquisition instant. A returned `DELETED` or
  `MIN_TTL_APPLIED` proves logical release; a second lost response remains
  uncertain. A repeat `NOT_HELD` proves loss; a repeat `CORRUPT` or ordinary
  backend failure remains backend uncertainty. Explicit callers receive
  `LeaderReleaseError` for proven loss, absence, or a second lost response and
  `LeaderBackendError` for corruption/backend failure. Scoped cleanup maps
  proven loss to `LeaderLeaseLostError`, absence or a second lost response to
  `LeaderReleaseError`, and corruption/backend failure to
  `LeaderBackendError`, before applying the failure-precedence matrix below.
  The adapter never issues an unconditional delete.
- The package does not promise recovery after process death. Redis TTL is the
  cleanup mechanism for abandoned leases.

## Scoped Auto-Renew Lifecycle

Auto-renew is available only while a lock context or elector action is active.
There is no campaign API that leaves a thread or task running after the scope
returns.

`try_acquire()` itself never starts a worker. It returns an explicit lease for
manual renew/release. On the first successful `with lease` or `async with
lease`, auto-renew starts when requested; re-entry, concurrent entry, and entry
after release are rejected. Electors start renewal after acquisition and
before invoking the action. The acquire-to-enter gap belongs to explicit lock
callers and remains covered only by the original TTL.

The handle state machine is:

```text
ACQUIRED -> ENTERED -> RELEASED
    |          |
    +----------+----> LOST
    |          |
    +----------+----> UNKNOWN
```

- `renew`, `is_held`, `assert_held`, and explicit `release` are valid in
  `ACQUIRED` and `ENTERED`;
- first context entry changes `ACQUIRED` to `ENTERED`; re-entry, concurrent
  entry, and entry after `LOST`/`RELEASED` fail without starting a worker;
- before yielding to caller code, first entry proves current ownership: with
  auto-renew it performs one synchronous/awaited owner-checked renew and
  requires `Renewed`; without auto-renew it performs one bounded probe script;
  proven expiry/takeover enters `LOST`, backend uncertainty enters `UNKNOWN`,
  and the context body never starts;
- proof mismatch enters `LOST` without release; proof/backend uncertainty may
  finish only that probe's already-owned bounded reconciliation before entering
  `UNKNOWN`, then relies on TTL;
- after successful ownership proof, a worker-start failure performs
  owner-checked release before raising; release uncertainty enters `UNKNOWN`;
- explicit release inside a context stops the worker and changes to
  `RELEASED`; the later `__exit__` is an idempotent no-op so it cannot mask the
  action result;
- an explicit second `release()` outside context cleanup raises
  `LeaderReleaseError`;
- successful logical release makes local `is_held()` false immediately even
  when minimum-lease TTL leaves the owner record temporarily present;
- proven mismatch/expiry/takeover changes to `LOST`;
- renewal backend failure, renew-worker join violation, cleanup-task deadline,
  or a second uncertain release changes to `UNKNOWN`;
- `LOST`, `RELEASED`, and `UNKNOWN` are terminal and never renew;
- from `UNKNOWN`, `renew`, `assert_held`, `release`, entry, and exit cleanup
  raise the retained value-free lifecycle error without new Redis I/O;
  `is_held()` also raises rather than falsely reporting proven loss or release;
- only the single bounded reconciliation already owned by the operation that
  created uncertainty may perform I/O before entering `UNKNOWN`.

### Synchronous lifecycle

1. acquire lease;
2. start at most one daemon-neutral renewal thread when `auto_renew=True`;
3. run the caller action on the caller's thread;
4. renewal thread sleeps interruptibly for the configured interval;
5. first `NotHeld` marks the handle lost and stops renewal;
6. backend renewal failure is retained and stops renewal;
7. on exit, signal stop and join the worker within `N + 100ms`;
8. release only after the worker has stopped;
9. propagate the action or lifecycle result according to the precedence below.

The worker is non-daemon and one-thread-per-active-auto-renewed-sync-lease.
The finite client invariant ensures an in-flight renew returns within `N`. If
the worker violates the join envelope, the handle enters a terminal unknown
state, does not race it with release, and raises `LeaderBackendError`; returning
action success is forbidden. Tests treat any remaining worker after the finite
command envelope as a defect.

Python cannot safely terminate a synchronous action when another thread
detects lease loss. Low-level lock callers may use `assert_held()` at safe
checkpoints. Elector callers receive only the snapshot, so irreversible work
must pass its fencing token into each downstream write.

### Async lifecycle

1. acquire lease;
2. create one child renewal task in the current event loop when enabled;
3. await the action in the caller task;
4. renewal loss records terminal loss but does not attempt to force-cancel the
   caller action; the action must use fencing for downstream safety;
5. on return, error, or cancellation, signal and await the renew task within
   `N + 100ms`;
6. create and retain exactly one cleanup task for owner-checked release;
7. record an incoming cancellation, shield the cleanup task, and if shielding
   raises again, re-await that same retained task until its `R + 100ms`
   cleanup deadline;
8. if an in-flight renew/release operation has not completed by its `N`/`R`
   command envelope, cancel that exact retained task once and require terminal
   cancellation by `N + 100ms` / `R + 100ms`; the supported official redis-py
   coroutine path must be cancellation-terminating in the pinned-version stall
   proof or delivery returns to design review;
9. after both retained tasks have completed or reached terminal cancellation,
   re-raise the original `asyncio.CancelledError`.

No cleanup coroutine is launched without a retained task reference. Repeated
cancellation cannot create another release task. Deadline cancellation leaves
TTL as the last-resort cleanup and records a lifecycle failure; pending task
count must be zero before a normal or cancellation return.

## Failure Precedence

The implementation preserves the most decision-relevant failure without
silently losing cleanup evidence:

1. cancellation and process-control exceptions remain primary and are
   re-raised after bounded cleanup; a lifecycle failure is attached as a
   value-free note;
2. action failure plus successful cleanup propagates the action exception from
   `run_if_leader()` and returns `ActionFailed` from the result API;
3. action failure plus any renewal/release uncertainty raises redacted
   `LeaderExecutionError` from both APIs;
4. detected lease loss during an otherwise successful action raises
   `LeaderLeaseLostError` instead of reporting success;
5. a renewal backend failure during an otherwise successful action raises
   `LeaderBackendError`;
6. proven `NOT_HELD` during scoped release raises `LeaderLeaseLostError`;
   corrupt/backend/uncertain release raises a sanitized backend/lifecycle
   error;
7. contention returns `None`/`Skipped` and never starts the action or renewer.

`run_if_leader_result()` classifies only application action failures followed
by proven-safe cleanup as `ActionFailed`. Lifecycle and backend failures are
raised because the action's side-effect safety may be unknown.

| Action | Renewal | Release | Public outcome |
|---|---|---|---|
| not run | n/a | n/a | `Skipped` for contention; otherwise raised backend error |
| success | held | success | `Elected` / action value |
| success | lost | any | raised `LeaderLeaseLostError` |
| success | backend failure | any | raised `LeaderBackendError` |
| success | held | proven `NOT_HELD`/expiry/takeover | raised `LeaderLeaseLostError` |
| success | held | corrupt/backend/uncertain release | raised sanitized backend/lifecycle error |
| ordinary failure | held | success | original exception / `ActionFailed` |
| ordinary failure | lost/backend failure | any | raised `LeaderExecutionError` |
| ordinary failure | held | lost/uncertain release | raised `LeaderExecutionError` |
| cancellation/process control | any | any | original control exception after bounded cleanup |

Manual context managers use the same safety precedence without producing
`ActionFailed`:

| Context body | Exit cleanup | `__exit__` / `__aexit__` outcome |
|---|---|---|
| success | proven release | normal return |
| ordinary exception | proven release | original body exception |
| success | proven loss | `LeaderLeaseLostError` |
| success | backend/uncertain | sanitized lifecycle error |
| ordinary exception | loss/backend/uncertain | `LeaderExecutionError` |
| cancellation/process control | any | original control exception after bounded cleanup |

## Security and Privacy Boundaries

- Redis authentication, authorization, endpoint selection, and network
  isolation are caller/operator responsibilities.
- Issue #17 rejects TLS-enabled client objects to preserve a hard reconnect
  envelope. Numeric-IP deployments therefore require a caller-controlled
  protected network; Unix-domain sockets are preferred when colocated. TLS
  support requires a follow-up design with an enforceable whole-handshake
  deadline.
- The adapter requires permissions for `EVALSHA`, `EVAL`, `GET`, and the
  commands invoked inside scripts (`TYPE`, `GET`, `PTTL`, `INCR`, `SET`,
  `PEXPIRE`, `DEL`). It never requires `SCRIPT LOAD`.
- Lock names, node IDs, owner tokens, full lease records, Redis URLs, command
  arguments, prefixes, keys, borrowed-client representations, and credentials
  never appear in package-generated errors or representations. Public adapter
  and handle classes have fixed redacted `repr` values.
- Backend errors are sanitized and raised `from None`; raw redis-py exception
  text/args are not chained into caller-visible tracebacks. Internal
  classification uses the original exception only within the failing frame.
- SHA-256 key derivation prevents direct key disclosure but is not encryption;
  operators with candidate names and Redis key access can test guesses.
- Fencing protects downstream writes only when the downstream system performs
  `incoming_token > stored_high_watermark` and commits the new high-watermark
  plus business write in the same atomic operation or transaction. Equal
  tokens are rejected as replay. Each independently protected resource needs
  its own high-watermark. A check followed by a separate write is unsafe.
- A Redis lease does not authorize business actions. Authentication and
  application authorization remain outside this package.
- User-provided callbacks are invoked exactly once only after acquisition and
  never while package-internal locks are held.

## Operational Contract and Caveats

- The first adapter targets one authoritative Redis primary. It does not claim
  mutual exclusion across asynchronous failover because a promoted replica may
  not contain the previous lease write.
- TTL expiry uses Redis server wall-clock behavior. Clock discontinuities can
  shorten or lengthen the effective lease.
- Network partitions can leave a former owner executing after its lease
  expires. Fencing-aware downstream storage is required for destructive or
  externally visible operations.
- Auto-renew improves liveness for long actions but does not turn the lease
  into a consensus protocol.
- Renewal interval, Redis socket timeouts, and action checkpoint behavior must
  satisfy `N < renew_interval` and
  `N + renew_interval < lease_time`. The default renew
  interval is one third of the lease; invalid client timing fails before
  acquisition rather than degrading to an unbounded worker.
- Availability and latency dashboards belong to caller-owned Redis
  instrumentation. This package emits no logs or metrics in Issue #17.
- Production Redis ACLs should restrict the adapter principal to the required
  command set and key prefix. Because scripts require mutation commands, ACLs
  alone cannot distinguish adapter-issued `SET`/`DEL` from direct use by the
  same principal; application code must not expose that principal or client to
  arbitrary command paths, and operational mutation uses a separate controlled
  principal. Backups/restores must never resume a counter below the downstream
  high-watermark; restore and manual counter repair require all contenders to
  stop first.
- Rollback is removal of the adapter usage and optional package extras. Existing
  Redis fence counters and expired lease keys may remain; deleting counters is
  unsafe while any consumer can still write with an older token.

## Documentation Contract

English and Korean package READMEs must remain behaviorally aligned and show:

1. focused and meta-extra installation;
2. caller-owned sync and asyncio Redis clients;
3. a single-attempt lock context;
4. precise `run_if_leader_result()` handling;
5. passing `FencedLeaderLease.fencing_token` to a downstream write;
6. cancellation-safe asyncio usage;
7. explicit release/renew/loss behavior;
8. single-primary, failover, partition, TTL-clock, and fencing caveats;
9. unsupported Redlock, group/slot, strategic, reentrant, and backend scopes;
10. borrowed-client shutdown ownership.
11. the first-slice TLS rejection, protected-network/Unix-socket requirement,
    and follow-up boundary;
12. an operator table mapping contention, lease loss, renewal failure, release
    failure, connection/pool timeout, and script permission denial to actions;
13. safe caller-owned signals for acquire outcome/latency, renewal latency and
    loss, release failure, pool timeout, command failure, and reconnect without
    names, IDs, keys, prefixes, or tokens as labels;
14. a deployment checklist for writable-primary role, topology caveat, ACL,
    finite timeouts, persistence/restore policy, and fencing high-watermark;
15. a lease-loss runbook that blocks stale work and verifies downstream atomic
    fencing without printing the lease value.

`LeaderBackendError` is deliberately non-diagnostic: it has no raw cause,
endpoint, command, operation, or failure-kind field. Connection/pool timeout,
permission denial, protocol failure, and corrupt state therefore cannot be
reliably distinguished from the package exception alone. The operator table
must say which caller-owned Redis health, ACL, pool, and server evidence to
inspect for each suspected condition; application code branches only on the
documented leader result/error classes. Safe caller-owned metrics may label the
public operation and outcome observed at the call site, never a guessed backend
cause or caller value.

Examples must not print lock names, lease internals, credentials, or exception
causes directly. README examples are executed by focused tests.

## Test Design

### Core contract tests

- default and boundary option validation;
- invalid duration types, negative wait, zero lease, excessive minimum lease,
  invalid renew interval, blank node identity, and positive sub-millisecond
  lease accepted by the backend-neutral core;
- immutable lease values and physical-node/fencing separation;
- `Elected(None)` versus `Skipped` distinction;
- action failure classification and process-control/cancellation propagation;
- protocol conformance using deterministic in-memory test doubles only;
- redacted representations and value-free exception messages;
- package export order, namespace extension, metadata, and wheel imports.

### Redis unit tests with controlled fakes

- exact key digest/hash-tag construction;
- positive sub-millisecond lease rejected at the Redis adapter boundary;
- owner-token entropy source injection at the private test seam;
- lease record formatting and hostile parse failures;
- wait deadline and bounded sleep behavior;
- exact 40-60ms jitter bounds, no post-deadline dispatch, maximum command count,
  and `wait_time + A` acquisition envelope;
- bounded pool wait/backoff and exact `P`, `S`, `A`, `N`, and `R` envelope
  accounting, including `EVALSHA` fallback paths;
- contention-only retry classification;
- command-uncertainty reconciliation;
- response-loss owner-token recovery, malformed reconciliation state, and no
  acquire-script redispatch;
- infinite/opaque/too-long client timeouts rejected before acquisition;
- retry-enabled clients and hostname endpoints rejected before acquisition,
  including response-loss and stalled-resolution fixtures;
- health-check-enabled clients, connection callbacks, dynamic credential
  providers, and other unbounded command-path hooks rejected at construction;
- TLS clients rejected; cold-connect and forced-reconnect envelope tests cover
  every supported static auth/protocol/client-name/driver-info/database shape;
- wrong-type, malformed, and no-TTL existing leases fail as corruption rather
  than contention;
- fencing counters at `2^53 - 1`, `2^53`, and signed Redis overflow preserve
  canonical decimal behavior or fail closed;
- uncertain minimum-lease release covers absent, different-owner, same-owner
  retry, second uncertainty, and natural expiry;
- action × renewal × release × cancellation failure-matrix coverage;
- first enter, never-entered explicit lease, double/re-entry, and released
  handle lifecycle;
- delayed first entry after expiry, takeover, and backend failure for sync and
  async; no context body starts without a successful entry ownership proof;
- cancellation during renew, `EVALSHA`, fallback `EVAL`, read-only
  reconciliation `EVAL`,
  and repeated release; repeated cancellation, deadline cancellation, and
  pending-task-zero assertions;
- terminal `UNKNOWN` transitions and no-I/O behavior for every public handle
  method;
- fixed redaction canaries across `str`, `repr`, formatted traceback, notes,
  renewal outcome cause access, both composite properties, and composite
  execution failures;
- no raw names, tokens, URLs, or command values in errors/repr;
- borrowed client is never closed.

### Redis Testcontainers integration tests

- sync and async acquire, renew, release, and reacquire;
- owner mismatch cannot renew or release;
- expiry permits a later contender with a greater fencing token;
- 16 concurrent contenders across 10 generations, separately for sync and
  async, execute exactly one action per generation and finish within a
  computed command-time envelope;
- fencing tokens strictly increase across release and natural expiry;
- minimum lease time preserves the key only for the remaining duration;
- cancellation and action failure stop/await the renew worker and safely
  release ownership;
- renewal loss prevents successful scoped completion;
- malformed lease/counter state fails closed;
- `NOSCRIPT` fallback succeeds without changing semantics;
- all workers/tasks terminate and no Redis clients are closed;
- acquisition command count stays below the jitter-derived ceiling; after each
  stress run, worker threads and pending tasks return to baseline;
- 16 simultaneous auto-renewed sync leases never create more than 16 renewal
  threads and return to the baseline thread count after release;
- long-action auto-renew survives multiple original TTL windows;
- a stale holder cannot delete or renew a successor lease.
- atomic downstream fencing rejects both an equal-token replay and an older
  holder after successor acquisition; a deliberately non-atomic example
  demonstrates why check-then-write is unsupported.

Redis integration tests use the existing `bluetape-testcontainers.RedisServer`
boundary and run serially under the repository's `testcontainers` marker.

### Documentation and packaging tests

- English/Korean example execution and semantic parity checklist;
- direct wheel installs for both packages;
- `bluetape[leader]` and `bluetape[leader-redis]` metadata smoke checks;
- default meta install remains `bluetape-core` only;
- Redis is absent from a `bluetape-leader`-only environment;
- core imports without redis-py installed;
- built wheels contain no root `bluetape/__init__.py`;
- `uv build --all-packages` succeeds.

## Baseline Exception

Before design work, the synchronized Python 3.13.14 workspace produced 2,373
passing tests and one reproducible failure in
`test_real_redis_smoke_emits_twelve_valid_results`. The benchmark subprocess
reported its initial Redis startup phase as `redis-failed`, while the targeted
test and repeated direct `RedisServer` start/ping probes passed. The user
approved treating this as a pre-existing Issue #17 baseline exception.

Issue #17 implementation must still run targeted leader tests and the full
suite. It must not claim the baseline failure as caused or repaired without new
evidence, and it must report the known exception separately from new failures.

## Alternatives Considered

### Put leader APIs into `bluetape-cache-redis`

Rejected. That distribution owns cache values, serde/compression integration,
and load coordination. Depending on it would force unrelated cache contracts
and dependencies into every leader backend and block a stdlib-only core.

### Ship only `bluetape-leader-redis`

Rejected. It would leave no stable backend-neutral contract for the multiple
repositories/backends already demonstrated by `bluetape4k-leader` and
`bluetape-go/leader`.

### Split Python Redis sync and asyncio into separate distributions

Rejected. Both are official surfaces of the selected redis-py dependency and
share atomic scripts, key format, failure classification, and lifecycle rules.
Separate wheels would duplicate security-critical semantics.

### Implement Redlock or Redis Cluster in the first slice

Rejected. It substantially changes timing, quorum, partial-failure, and
operational assumptions without being required by Issue #17. The first adapter
states its single-primary boundary honestly.

### Expose the owner token as the leader ID

Rejected. The owner token is a secret release capability, not an audit identity
or fencing value. Redis exposes only the monotonically increasing fence token
and optional caller node identity.

### Run a permanent campaign/watchdog API

Rejected. It creates detached lifecycle ownership, shutdown, recovery, and
global-state obligations. Renewal is scoped to a lock context or action call.

## Acceptance Criteria Mapping

| Issue requirement | Design evidence |
|---|---|
| API contracts plus Redis proof | Separate `bluetape-leader` and `bluetape-leader-redis` distributions |
| Owner tokens | Private high-entropy token per acquisition attempt |
| TTL renewal | Owner-checked Lua renew plus explicit/scoped APIs |
| Fencing/slot where applicable | Atomic increasing token under the authoritative-counter persistence condition; group slots deferred |
| Safe release | Exact owner-value compare and delete/remaining-minimum-TTL script |
| Acquire/renew/release tests | Sync/async unit and Testcontainers matrix |
| Owner mismatch and expiry | Explicit stale-owner and natural-expiry integration tests |
| Cancellation cleanup | Awaited/joined scoped renewer and owner-checked release tests |
| Concurrent contenders | Exactly-one action and increasing-generation stress tests |
| Lua/atomic behavior | Acquire, renew, release scripts with all keys in `KEYS` |
| Operational caveats | Single-primary, failover, partition, clock, fencing, borrowed-client docs |

## Verification and Delivery Gates

Implementation planning must map every contract above to ordered TDD tasks.
After implementation, verification must include:

```bash
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv run pytest <targeted leader test paths>
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
git diff --check
```

Additional delivery gates:

- sync/async public contracts and Redis behavior receive P0/P1 code review;
- lifecycle, security, and concurrency tests include real Redis evidence;
- English/Korean documentation is aligned;
- a committed Type A lesson records reusable decisions and rejected scope;
- PR creation requires separate authority naming repository, base `develop`,
  and the current feature branch;
- merge requires fresh exact-head approval after CI and review/thread evidence;
- release, tag, and publication remain separate gates;
- final PR body ends with `## DoD Status`.

## Open Decisions

None. Group/slot election, strategic election, additional backends, framework
integration, and release scope are explicitly deferred rather than unresolved
inside Issue #17.
