# bluetape-leader

English | [한국어](README.ko.md)

`bluetape-leader` provides stdlib-only, backend-neutral contracts for bounded
leader actions and distributed lock leases. A backend adapter supplies the
actual coordination mechanism. The core package owns immutable options,
leases, precise result values, protocols, and sanitized public errors.

PyPI publication is currently on hold. The commands below describe the public
install shape after publication; use the workspace build while the hold is in
place.

<!-- leader-scenario:install -->
## Install

```bash
pip install bluetape-leader
pip install "bluetape[leader]"
```

Both forms install the stdlib-only `bluetape.leader` contract. Redis support is
separate and opt-in. The default `bluetape` install remains core-only.

<!-- leader-scenario:contention -->
## Guard acquisition before entering a context

`try_acquire()`
returns a lease handle or `None` when another contender owns the lock. Never
enter the result before checking it. In particular, do not use either form:

`with lock.try_acquire(...)`

`async with await lock.try_acquire(...)`

```python
from datetime import timedelta

from bluetape.leader import LeaderElectionOptions

options = LeaderElectionOptions(
    wait_time=timedelta(0),
    lease_time=timedelta(seconds=30),
    node_id="worker-a",
    auto_renew=True,
)

handle = lock.try_acquire("daily-job", options)
if handle is not None:
    with handle as held:
        update_if_newer(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

```python
async_handle = await async_lock.try_acquire("daily-job", options)
if async_handle is not None:
    async with async_handle as held:
        await update_if_newer_async(
            value,
            fencing_token=held.lease.fencing_token,
        )
```

`try_acquire()`
itself starts no renewer. With `auto_renew=True`, renewal starts only after
context entry re-proves ownership. The delay between acquisition and context
entry is covered only by the original TTL, so enter promptly or treat a failed
entry as lease loss.

<!-- leader-scenario:precise-result -->
## Prefer precise leader results

`run_if_leader()` returns `None` both when contention skips the action and when
a successful action returns `None`. Use
`run_if_leader_result()`
whenever `T` may be `None`, then exhaustively handle `Elected`, `Skipped`, and
`ActionFailed`.

<!-- precise-result-example -->
```python
from bluetape.leader import ActionFailed, Elected, FencedLeaderLease, Skipped


def classify(result: object) -> str:
    if isinstance(result, Elected):
        return "elected:none" if result.value is None else "elected:value"
    if isinstance(result, Skipped):
        return "skipped"
    if isinstance(result, ActionFailed):
        return "action-failed"
    raise AssertionError("unreachable leader result")


sample_lease = FencedLeaderLease(
    audit_leader_id="example-run",
    node_id="worker-a",
    elected_at=None,
    lease_until=None,
    fencing_token=1,
)
sample_result = Elected(value=None, lease=sample_lease)
```

The precise result preserves an ordinary caller action exception only inside
`ActionFailed.cause`; package-generated representations stay redacted. Lease
loss, release uncertainty, and backend failures remain exceptional lifecycle
failures rather than ordinary action results.

<!-- leader-scenario:manual-lifecycle -->
## Manual and scoped lifecycle

Use a context for the normal case. It performs an entry ownership probe,
optional scoped renewal, and bounded owned cleanup. Manual use is for a caller
that needs explicit checkpoints and accepts responsibility for every release
path.

| Lifecycle | Renewal | Ownership checkpoint | Cleanup |
|---|---|---|---|
| Scoped context | `auto_renew=True` starts after entry proof | `assert_held()` before irreversible work | context exit performs bounded release |
| Manual handle | call `renew()` explicitly | call `assert_held()` at caller-selected boundaries | caller must release in `finally` |

<!-- manual-lifecycle-example -->
```python
from bluetape.leader import LeaderLeaseLostError, NotHeld, RenewBackendFailure


def run_manual(lock, options, value):
    handle = lock.try_acquire("daily-job", options)
    if handle is None:
        return False
    handle.assert_held()
    renewed = handle.renew()
    if isinstance(renewed, NotHeld):
        raise LeaderLeaseLostError()
    if isinstance(renewed, RenewBackendFailure):
        raise renewed.cause
    try:
        update_if_newer(value, fencing_token=handle.lease.fencing_token)
        return True
    finally:
        handle.release()


async def run_manual_async(lock, options, value):
    handle = await lock.try_acquire("daily-job", options)
    if handle is None:
        return False
    await handle.assert_held()
    renewed = await handle.renew()
    if isinstance(renewed, NotHeld):
        raise LeaderLeaseLostError()
    if isinstance(renewed, RenewBackendFailure):
        raise renewed.cause
    try:
        await update_if_newer_async(value, fencing_token=handle.lease.fencing_token)
        return True
    finally:
        await handle.release()
```

Do not call `release()` after `NotHeld` or `RenewBackendFailure`: the handle is
already terminal or uncertain, and explicit release would replace that renewal
outcome with a lifecycle exception. The example raises the corresponding
sanitized lifecycle error before entering the action/release block.

`is_held()` is an observation, not a reservation. Another process can acquire
after the probe, so check-then-write has a TOCTOU race. Use `assert_held()` as a
checkpoint and an atomic downstream fencing transaction as the final stale
write guard.

<!-- leader-scenario:identity -->
## Identity fields

| Field | Meaning | Safety role |
|---|---|---|
| `node_id` | Physical caller identity supplied in `LeaderElectionOptions` | Operator correlation only; never an ownership capability |
| `audit_leader_id` | Per-acquisition correlation text | Audit correlation only; never compare it for exclusion |
| integer `fencing_token` | Monotonically issued capability from a fencing backend | The only identity field used for downstream stale-write rejection |

Do not log or expose any of these values. “Correlation” describes their
semantic purpose, not permission to place them in package-generated messages,
logs, or metric labels.

<!-- leader-scenario:cancellation -->
## Async cancellation

Async lock and elector operations retain their owned cleanup task. If the
caller cancels an operation, the adapter performs bounded cleanup and then
re-raises `CancelledError`; it does not detach background work. The caller still
owns and closes any borrowed backend client in the caller scope.

```python
import asyncio


async def run_once(async_elector, options):
    try:
        return await async_elector.run_if_leader_result(
            "daily-job",
            perform_async_action,
            options,
        )
    except asyncio.CancelledError:
        raise
```

## Error and privacy boundary

Public leader errors deliberately avoid names, IDs, keys, prefixes, clients,
owner records, backend replies, and fence values. `LeaderBackendError` is
intentionally non-diagnostic and does not expose a backend cause kind. Inspect
caller-owned backend health and telemetry outside the exception instead of
guessing its cause from `str`, `repr`, traceback, or notes.

`LeaderExecutionError` means an ordinary caller action and its lifecycle
cleanup both failed. Its `action_cause` retains the caller-owned `Exception`;
its `lifecycle_cause` is a sanitized `LeaderError` and is the ownership-safety
failure. Propagate the composite unless the caller has an explicit policy for
both causes. If handled, classify the two attributes by safe exception type;
do not log their values, parse their text, or discard the lifecycle failure.
