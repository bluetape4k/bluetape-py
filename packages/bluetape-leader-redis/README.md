# bluetape-leader-redis

English | [한국어](README.ko.md)

`bluetape-leader-redis` is the opt-in Redis adapter for
`bluetape-leader`. It implements bounded sync and asyncio distributed locks and
leader electors for one authoritative writable Redis primary. The distribution
depends only on `bluetape-leader==0.1.0` and `redis==8.0.1` at runtime.
The tested server compatibility target is Redis Server 8. Other server major
versions are outside this first-slice support contract until separately proven.

PyPI publication is currently on hold. The install commands describe the
public shape after publication.

<!-- leader-scenario:constructor -->
## Install and construct an exact borrowed client

```bash
pip install bluetape-leader-redis
pip install "bluetape[leader-redis]"
```

The adapter accepts an exact redis-py client only before it has opened a
connection. Use a numeric IP address such as `127.0.0.1`, finite positive
connect and command timeouts, zero retry, `health_check_interval=0`, and the
default empty `event_dispatcher`. TLS, a hostname, retrying clients, health
checks, credential callbacks, connection hooks, custom response callbacks,
proxies, subclasses, and pre-used pools are rejected before I/O.

TLS is unsupported. Prefer a local Unix socket whenever possible. If TCP is
required, use plaintext TCP only on a caller-controlled protected network.
Plaintext TCP exposes Redis credentials, owner tokens, and capability-bearing
lock material to network observers.

<!-- sync-constructor-example -->
```python
import redis
from redis.backoff import NoBackoff
from redis.maint_notifications import MaintNotificationsConfig
from redis.retry import Retry

from bluetape.leader.redis import RedisDistributedLock

client = redis.Redis(
    host="127.0.0.1",
    port=6379,
    db=0,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
    health_check_interval=0,
    retry=Retry(NoBackoff(), 0),
    retry_on_error=[],
    maint_notifications_config=MaintNotificationsConfig(
        enabled=False,
        proactive_reconnect=False,
        relaxed_timeout=-1,
    ),
)
lock = RedisDistributedLock(client)
```

<!-- async-constructor-example -->
```python
import asyncio

import redis.asyncio as async_redis
from redis.backoff import NoBackoff
from redis.asyncio.retry import Retry as AsyncRetry

from bluetape.leader.redis import AsyncRedisDistributedLock


async def main(options, value):
    client = async_redis.Redis(
        host="127.0.0.1",
        port=6379,
        db=0,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
        health_check_interval=0,
        retry=AsyncRetry(NoBackoff(), 0),
        retry_on_error=[],
    )
    try:
        lock = AsyncRedisDistributedLock(client)
        handle = await lock.try_acquire("daily-job", options)
        if handle is None:
            return False
        async with handle as held:
            await update_if_newer_async(
                value,
                fencing_token=held.lease.fencing_token,
            )
        return True
    finally:
        await client.aclose()


# asyncio.run(main(options, value))
```

For a local Unix socket, construct the exact sync or async client with
`UnixDomainSocketConnection` via redis-py's `unix_socket_path` option and the
same finite timeout, zero-retry, no-hook rules. Do not also set a host or port.

All four constructors borrow the client:

`RedisDistributedLock(...)`

`AsyncRedisDistributedLock(...)`

`RedisLeaderElector(...)`

`AsyncRedisLeaderElector(...)`

They never close it. Close it exactly once in the caller-owned sync or async
scope after every lock/elector operation is terminal.

<!-- elector-example -->
```python
from bluetape.leader import ActionFailed, Elected, Skipped
from bluetape.leader.redis import AsyncRedisLeaderElector, RedisLeaderElector


def sync_action():
    return "completed"


async def async_action():
    return "completed"


def result_value(result):
    if isinstance(result, Elected):
        return result.value
    if isinstance(result, Skipped):
        return None
    if isinstance(result, ActionFailed):
        raise result.cause
    raise AssertionError("unreachable leader result")


def run_sync(client, options):
    elector = RedisLeaderElector(client)
    result = elector.run_if_leader_result("daily-job", sync_action, options)
    return result_value(result)


async def run_async(client, options):
    elector = AsyncRedisLeaderElector(client)
    result = await elector.run_if_leader_result("daily-job", async_action, options)
    return result_value(result)
```

The elector also borrows its client. Create, use, and close an async client in
one caller-owned event-loop scope as shown above; never return it from a
temporary `asyncio.run()` loop for later operations.

<!-- leader-scenario:fencing -->
## Fencing is the stale-write guard

A lock prevents simultaneous ownership only while its Redis lease remains
valid. A paused predecessor can resume after expiry, so protected storage must
atomically reject its stale integer `fencing_token`.

```python
handle = lock.try_acquire("daily-job", options)
if handle is not None:
    with handle as held:
        update_if_newer(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

`update_if_newer` must compare the incoming token and commit both the new
high-watermark and business data in one transaction. A check followed by a
separate write is unsupported because another writer can win between them.
Redis counter persistence enables monotonic issuance, while the atomic
downstream transaction is the final stale-write defense.

Owner mismatch or expiry makes renewal return `NotHeld` and causes scoped
entry/exit to report lease loss. `is_held()` remains a TOCTOU observation and
cannot replace downstream fencing.

<!-- leader-scenario:unsupported-topology -->
## Supported topology and explicit exclusions

Mutual exclusion is only against one authoritative writable single-primary.
Asynchronous failover, partitions, promotion, proxy or multi-primary routing,
Sentinel, and Cluster can violate that assumption. This first slice does not
provide Redlock, group/slot locks, strategic election, multi-resource
transactions, or another backend. Clock observations are diagnostic only;
Redis TTL and atomic scripts are authoritative for the lease.

The adapter does not retry ambiguous commands. A response-lost acquire gets
one owner-token reconciliation, while other uncertain lifecycle failures stop
with sanitized errors. Applications must not route the same logical lock to
different writable primaries.

## Minimal ACL

Grant only the coordination prefix key pattern and the documented adapter
commands: `EVALSHA`, `EVAL`, `GET`, plus in-script `TYPE`, `PTTL`, `INCR`,
`SET`, `PEXPIRE`, and `DEL`. Do not grant `SCRIPT LOAD`. RESP negotiation,
non-default DB, authentication, or client name may additionally require the
exact witnessed `HELLO`/`AUTH`/`SELECT`/`CLIENT SETNAME` handshake permissions.
Validate that unrelated commands and keys outside the prefix remain denied.

<!-- leader-scenario:migration -->
## Coordination identity migration and counter restore

Prefix, SHA-256 logical-name digest derivation, the
`lease`/`fence`/`history` suffix set, the persistent `v1` history marker, and
record version `v1` form one coordination identity. A rolling migration can
split contenders, so use this ordered stop-the-world contract:

1. **stop every old and new contender** and prevent any new protected action;
2. **prove the old lease absent** without deleting or printing its value;
3. read and preserve every **downstream resource high-watermark**;
4. restore or seed the authoritative Redis fence counter **strictly above** the
   maximum preserved watermark and set its persistent `v1` history marker;
5. configure every contender with one **identical prefix**, digest derivation,
   suffix set, and record version;
6. **restart all contenders** on that single coordination identity, then
   re-enable protected work.

Backup and restore the counter and history marker together with the protected
data. Acquisition fails closed when the marker exists but the counter is
missing, when the counter exists but the marker is missing, or when either key
has a TTL, wrong type, or malformed value. An active lease whose embedded token
differs from the counter also fails closed. Both keys being absent is accepted
only as a fresh coordination identity with no active lease, so protect and
restore both keys as one unit. If state cannot be proven above all preserved
watermarks, keep writers stopped. Never “repair” it by deleting an active lease
or lowering downstream state.

A deployment created by a pre-marker implementation cannot be upgraded by
rolling migration. Stop every contender and protected writer, prove the lease
absent, seed a persistent counter strictly above every downstream watermark,
set the persistent `v1` history marker, and only then start all contenders on
the marker-aware implementation. There is no automatic legacy-state adoption.

The Redis signed-integer ceiling is `9223372036854775807`. Acquisition fails
closed when the counter reaches that value. If either the counter or a
downstream watermark reaches the ceiling, no integer token can be restored
strictly above it. Keep writers stopped and migrate the protected store to a
new, downstream-recognized coordination epoch with compound epoch/token
ordering; changing only the Redis prefix or resetting the counter is unsafe.

## Lease-loss runbook

When renewal loss, owner mismatch, corruption, or an uncertain release occurs:

1. block new protected work for the affected operation;
2. let atomic downstream fencing reject or abort stale writes;
3. inspect caller-owned Redis health, ACL, pool, command, and server evidence;
4. wait for a proven terminal lease state before resuming.

The runbook never deletes or resets coordination keys and never prints lease
values. Do not turn a sanitized exception into a key scan or a value dump.

<!-- leader-scenario:rollback -->
## Rollback

Stop contenders and protected work, remove adapter usage and the
`leader-redis` extra, and leave counters, history markers, and expired lease
keys intact. Restore
the previous application only if it uses the same coordination identity and
cannot reintroduce a writer whose token is below a preserved downstream
high-watermark. Otherwise keep protected work disabled and complete the ordered
migration procedure before resuming.

<!-- leader-scenario:operator-actions -->
## Structured operator action table

`LeaderBackendError` is intentionally non-diagnostic and exposes no backend
cause kind. Operators must use caller-owned evidence instead of branching on or
guessing from the exception.

| Suspected condition | Caller-owned evidence | Safe action |
|---|---|---|
| Connection or pool timeout | Redis health, pool saturation, configured finite timeouts | Stop protected work if ownership is uncertain; repair capacity or reachability |
| Permission denial | ACL audit and denied-command evidence | Compare the exact ACL command/key allowlist; never broaden to unrelated keys |
| Protocol failure | redis-py/RESP configuration and server logs | Restore the exact supported client shape; do not enable retries or hooks |
| Corrupt lease record | Server-side integrity evidence without rendering the value | Stop writers and investigate ownership; never delete, reset, or print the record |

The exact caller-owned signal set is: acquire outcome/latency, renewal
latency/loss, release failure, pool timeout, command failure, and reconnect.
Safe call-site signals label only the public operation and outcome category.
Lock names, node/audit IDs, owner tokens, Redis keys/prefixes, and fencing
tokens are forbidden as log fields or metric labels, as is any guessed backend
cause.

<!-- leader-scenario:deployment-checklist -->
## Deployment checklist

- [ ] Pin `redis==8.0.1` and construct a fresh exact sync or async client with a
  numeric IP or Unix socket, finite positive timeouts, zero retry, no TLS,
  hostname, health check, callback, event hook, or custom response callback.
- [ ] TLS is unsupported. Prefer a local Unix socket whenever possible. Allow
  plaintext TCP only on a caller-controlled protected network; plaintext TCP
  exposes Redis credentials, owner tokens, and capability-bearing lock material
  to network observers.
- [ ] Deploy against Redis Server 8, the currently tested server major; qualify
  another major with the complete integration suite before declaring support.
- [ ] Route all contenders to one writable standalone primary; reject
  Sentinel, Cluster, proxies, promotion, and multi-primary routing.
- [ ] Apply and test the minimal ACL, including out-of-prefix denial.
- [ ] Persist, back up, and restore the counter and history marker together
  with protected data.
- [ ] Monitor counter headroom below `9223372036854775807`; at exhaustion, keep
  writers stopped until a downstream-recognized epoch migration is complete.
- [ ] Make every protected store atomically compare and commit its
  high-watermark with business data.
- [ ] Exercise contention, cancellation, lease loss, release failure, and
  caller-owned borrowed-client cleanup under finite deadlines.
- [ ] Roll back only to an identical coordination identity while preserving
  counters, history markers, expired leases, and downstream watermarks.

Async cancellation performs bounded owned cleanup and then re-raises
`CancelledError`. Close the borrowed async client only after the cancelled lock
or elector call has reached that terminal boundary.
