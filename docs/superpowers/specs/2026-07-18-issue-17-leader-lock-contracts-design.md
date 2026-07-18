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

## Goals

1. Establish stable sync and asyncio contracts for single-leader execution and
   non-reentrant distributed locking.
2. Keep backend-neutral contracts stdlib-only and open to future independent
   backend distributions.
3. Distinguish contention, action failure, lease loss, invalid ownership, and
   backend failure without treating them as one falsey result.
4. Guarantee owner-checked acquire, renew, and release in the Redis adapter.
5. Issue a strictly increasing Redis fencing token on every successful new
   acquisition and never reuse or reset it.
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
```

- Validation errors identify only the invalid field category and never echo a
  lock name, node ID, owner token, Redis key, URL, credential, or action value.
- `LeaderBackendError` wraps an ordinary backend exception with exception
  chaining but does not retain credentials or command arguments in its own
  message.
- `LeaderLeaseLostError` means the owner token no longer matches, the lease
  expired, or takeover occurred. It is not a retryable contention result.
- `LeaderReleaseError` means the caller requested explicit release but the
  lease was already lost or ownership could not be proven.
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
- `lease_time > 0` and converts to at least one Redis millisecond;
- `0 <= min_lease_time <= lease_time`;
- `node_id`, when supplied, is non-empty without trimming or normalization;
- `renew_interval`, when supplied, is positive and strictly less than
  `lease_time`;
- `auto_renew=True` with no interval derives `lease_time / 3`, rounded down to
  whole milliseconds but never below one millisecond;
- exact built-in `timedelta`, `bool`, and `str` inputs are required so custom
  comparison or conversion code cannot run during validation.

Waiting uses `time.monotonic_ns()` or the event loop's monotonic clock. Wall
clock is used only for best-effort observation timestamps.

### Lease Snapshots

```python
@dataclass(frozen=True, slots=True)
class LeaderLease:
    audit_leader_id: str
    node_id: str | None
    elected_at: datetime | None
    lease_until: datetime | None


@final
@dataclass(frozen=True, slots=True)
class FencedLeaderLease(LeaderLease):
    fencing_token: int
```

- `audit_leader_id` is a safe caller-facing identity, not the secret owner
  token. Redis uses the decimal fencing token rendered as text.
- `node_id` is the physical caller-supplied identity and is never used as a
  fencing value.
- Redis always returns `FencedLeaderLease` with `fencing_token >= 1`.
- timestamps are timezone-aware UTC best-effort observations. They are not
  authorization checks and must not replace `is_held()` or fencing validation.
- owner tokens never appear in immutable snapshots, representations, events,
  errors, or public properties.

### Run Results

```python
@dataclass(frozen=True, slots=True)
class Elected[T]:
    value: T
    lease: LeaderLease


@final
@dataclass(frozen=True, slots=True)
class Skipped:
    pass


@dataclass(frozen=True, slots=True)
class ActionFailed:
    cause: Exception = field(repr=False)
    lease: LeaderLease


type LeaderRunResult[T] = Elected[T] | Skipped | ActionFailed
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
    cause: Exception = field(repr=False)


type RenewOutcome = Renewed | NotHeld | RenewBackendFailure
```

`observed_lease_until` is diagnostic only. Redis expiry is server-owned and
the client observation can include network latency and clock skew.

### Lock Protocols

```python
@runtime_checkable
class LockLease(Protocol):
    @property
    def lease(self) -> LeaderLease: ...
    def renew(self, lease_time: timedelta | None = None) -> RenewOutcome: ...
    def is_held(self) -> bool: ...
    def assert_held(self) -> None: ...
    def release(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...


@runtime_checkable
class DistributedLock(Protocol):
    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LockLease | None: ...
```

Async equivalents use `await renew`, `await is_held`, `await assert_held`,
`await release`, and `async with`. A lease is single-owner, non-reentrant, and
single-release. Releasing twice raises a value-free `LeaderReleaseError`.

### Elector Protocols

```python
@runtime_checkable
class LeaderElector(Protocol):
    def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[LeaderLease], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> T | None: ...

    def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[LeaderLease], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),
    ) -> LeaderRunResult[T]: ...
```

`AsyncLeaderElector` accepts `Callable[[LeaderLease], Awaitable[T]]`. The
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

The electors compose the corresponding lock implementation instead of
duplicating acquire, renew, release, token, deadline, and key logic.

## Redis Data Model

For a validated logical lock name, compute a SHA-256 hexadecimal digest over
its UTF-8 bytes. With the default prefix, use:

```text
bluetape:leader:{<digest>}:lease
bluetape:leader:{<digest>}:fence
```

The braces place both keys in the same Redis Cluster hash slot even though
Cluster operation is outside this issue. The raw lock name never becomes a
Redis key and is never logged by package code.

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

1. if the lease key exists, return contention;
2. increment the fence key;
3. reject a non-positive or non-integer-compatible counter result;
4. write the exact `v1:owner:fence` value with `PX ttl`;
5. return the fencing token.

This script makes ownership publication and fencing issuance one atomic Redis
operation. The counter key has no TTL and is never deleted by normal release.
Counter overflow or corruption fails closed as `LeaderBackendError`.

### Renew

One Lua script compares the lease value byte-for-byte with the caller's private
value and applies `PEXPIRE` only on equality. It returns `Renewed` on success
and `NotHeld` on mismatch, expiry, or takeover. It never creates a missing key.

### Release

One Lua script compares the lease value byte-for-byte and then either:

- deletes it when the minimum lease duration has elapsed; or
- applies only the remaining minimum-lease TTL when the action finished early.

It returns a classified status. Mismatch or expiry raises
`LeaderReleaseError` for explicit lock callers. Scoped elector cleanup records
the cleanup failure for propagation rules below but never deletes an unknown
owner's lease.

Scripts use redis-py's registered-script behavior or an equivalent
`EVALSHA`-then-`EVAL` fallback. Every key is passed through `KEYS`; scripts do
not construct dynamic Redis keys internally.

## Acquisition, Deadlines, and Command Uncertainty

- `wait_time=0` performs exactly one acquisition attempt.
- Positive waits use a monotonic deadline and bounded jittered sleeps. Sleep is
  capped by the remaining deadline; asyncio uses `asyncio.sleep`.
- Contention is the only condition that retries automatically.
- Authentication, protocol, parsing, script, connection, and configuration
  failures surface immediately as `LeaderBackendError`.
- A command timeout or disconnect after dispatch can leave the acquire outcome
  unknown. Before failing, the adapter performs one bounded reconciliation
  read using the same owner token. Exact owner-value match recovers the lease;
  absent or different ownership proves no ownership; another uncertain error
  fails closed without sending a new token.
- Renew and release operations are owner-conditional and idempotent with
  respect to another owner's state. Uncertain release is reconciled once; the
  adapter never issues an unconditional delete.
- The package does not promise recovery after process death. Redis TTL is the
  cleanup mechanism for abandoned leases.

## Scoped Auto-Renew Lifecycle

Auto-renew is available only while a lock context or elector action is active.
There is no campaign API that leaves a thread or task running after the scope
returns.

### Synchronous lifecycle

1. acquire lease;
2. start at most one daemon-neutral renewal thread when `auto_renew=True`;
3. run the caller action on the caller's thread;
4. renewal thread sleeps interruptibly for the configured interval;
5. first `NotHeld` marks the handle lost and stops renewal;
6. backend renewal failure is retained and stops renewal;
7. on exit, signal stop and join the worker with a deadline bounded by one
   Redis socket operation plus a small local margin;
8. release only after the worker has stopped;
9. propagate the action or lifecycle result according to the precedence below.

Python cannot safely terminate a synchronous action when another thread
detects lease loss. Callers performing irreversible work must pass the fencing
token downstream and may call `assert_held()` at safe checkpoints.

### Async lifecycle

1. acquire lease;
2. create one child renewal task in the current event loop when enabled;
3. await the action in the caller task;
4. on return, error, or cancellation, signal and await the renew task;
5. perform owner-checked release in an awaited cleanup section;
6. re-raise `asyncio.CancelledError` after cleanup.

Cleanup may use a narrowly scoped shield so a cancellation already in flight
does not abandon the Redis release coroutine. The shielded operation is still
awaited; no task is detached or retained globally.

## Failure Precedence

The implementation preserves the most decision-relevant failure without
silently losing cleanup evidence:

1. cancellation and process-control exceptions remain primary and are
   re-raised after best-effort cleanup;
2. an action exception remains primary; a cleanup failure is attached as a
   note and chained where Python permits;
3. detected lease loss during an otherwise successful action raises
   `LeaderLeaseLostError` instead of reporting success;
4. a renewal backend failure during an otherwise successful action raises
   `LeaderBackendError`;
5. release failure during an otherwise successful action raises
   `LeaderReleaseError` or `LeaderBackendError` by classification;
6. contention returns `None`/`Skipped` and never starts the action or renewer.

`run_if_leader_result()` classifies only application action failures as
`ActionFailed`. Lifecycle and backend failures are raised because the action's
side-effect safety may be unknown.

## Security and Privacy Boundaries

- Redis authentication, authorization, TLS, endpoint selection, and network
  isolation are caller/operator responsibilities.
- The adapter requires permissions for `EVALSHA`/`EVAL`, `GET`, `PTTL`, and the
  commands invoked inside scripts (`EXISTS`, `INCR`, `SET`, `PEXPIRE`, `DEL`).
- Lock names, node IDs, owner tokens, full lease records, Redis URLs, command
  arguments, and credentials never appear in package-generated errors or
  representations.
- SHA-256 key derivation prevents direct key disclosure but is not encryption;
  operators with candidate names and Redis key access can test guesses.
- Fencing protects downstream writes only when the downstream system stores
  and rejects stale tokens. Merely exposing a token does not provide fencing.
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
  leave enough margin before TTL expiry. Documentation recommends socket
  timeout below the renew interval and renew interval at most one third of the
  lease.
- Availability and latency dashboards belong to caller-owned Redis
  instrumentation. This package emits no logs or metrics in Issue #17.
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

Examples must not print lock names, lease internals, credentials, or exception
causes directly. README examples are executed by focused tests.

## Test Design

### Core contract tests

- default and boundary option validation;
- invalid duration types, negative wait, zero/sub-millisecond lease, excessive
  minimum lease, invalid renew interval, and blank node identity;
- immutable lease values and physical-node/fencing separation;
- `Elected(None)` versus `Skipped` distinction;
- action failure classification and process-control/cancellation propagation;
- protocol conformance using deterministic in-memory test doubles only;
- redacted representations and value-free exception messages;
- package export order, namespace extension, metadata, and wheel imports.

### Redis unit tests with controlled fakes

- exact key digest/hash-tag construction;
- owner-token entropy source injection at the private test seam;
- lease record formatting and hostile parse failures;
- wait deadline and bounded sleep behavior;
- contention-only retry classification;
- command-uncertainty reconciliation;
- no raw names, tokens, URLs, or command values in errors/repr;
- borrowed client is never closed.

### Redis Testcontainers integration tests

- sync and async acquire, renew, release, and reacquire;
- owner mismatch cannot renew or release;
- expiry permits a later contender with a greater fencing token;
- two and many concurrent contenders execute exactly one action per lease
  generation;
- fencing tokens strictly increase across release and natural expiry;
- minimum lease time preserves the key only for the remaining duration;
- cancellation and action failure stop/await the renew worker and safely
  release ownership;
- renewal loss prevents successful scoped completion;
- malformed lease/counter state fails closed;
- `NOSCRIPT` fallback succeeds without changing semantics;
- all workers/tasks terminate and no Redis clients are closed;
- long-action auto-renew survives multiple original TTL windows;
- a stale holder cannot delete or renew a successor lease.

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
| Fencing/slot where applicable | Atomic monotonically increasing fencing token; group slots deferred |
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
