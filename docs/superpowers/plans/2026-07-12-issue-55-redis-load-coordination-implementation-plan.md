# Issue #55 Redis Load Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded synchronous and asynchronous Redis load coordinators that
collapse same-key cold loads across application instances while preserving the
existing local-cache, serialization, cancellation, and provider contracts.

**Architecture:** A coordinator enters the borrowed local cache's existing
singleflight before touching Redis. Inside that one local flight it uses a
versioned digest key pair, a short token marker, bounded atomic snapshots, and
token-checked atomic publication. Provider scripts remain fixed and bounded;
sync and async coordinators share immutable contracts and pure state helpers
while keeping I/O and cancellation paths separate.

**Tech Stack:** CPython 3.13; `redis==8.0.1`; `TTLCache`, `AsyncTTLCache`,
`ResultEnvelopeCodec`; dataclasses, `hashlib`, `secrets`, `threading`,
and `asyncio`; pytest, pytest-asyncio, Redis 8 Testcontainers, Ruff, uv,
actionlint, and GitHub Actions.

---

Date: 2026-07-12
Issue: [#55](https://github.com/bluetape4k/bluetape-py/issues/55)
Depends on: #54 and #57 (closed)
Work type: Type A - Full Feature
Approved spec: `docs/superpowers/specs/2026-07-12-issue-55-redis-load-coordination-design.md`

## Execution constraints

- Use `executing-plans` for Inline execution, plus
  `test-driven-development` and `bluetape-py-patterns` for implementation.
- Make every behavior change test-first: observe the named RED failure before
  adding its minimum production code, then rerun the focused GREEN command.
- Add only exact `bluetape-cache==0.1.0` to the focused
  `bluetape-cache-redis` distribution so its public coordinators are usable from
  direct and meta-extra installs. Keep default `bluetape` core-only and make no
  other module, dependency, extra, workflow topology, durable L2 cache, lease
  renewal, fencing, Cluster, Sentinel, Redlock, Pub/Sub, or external-write
  protection change.
- Never issue unbounded Redis reads, hidden retries, dynamic Lua, `KEYS`, or a
  non-atomic publication fallback. RedisServer tests remain serial.
- Never translate `asyncio.CancelledError`; complete at most one required
  owner cleanup, re-raise cancellation unchanged, and leave no coordinator task.
- Never expose namespace, logical key, token, Redis key, payload, URL,
  credentials, exception text, or Redis-controlled metadata in errors/events.
- Preserve `ResultEnvelopeCodec.decode()`; add `decode_matching()`
  without changing existing callers.
- Public signatures, enum and `__all__` order, exact types, stable messages,
  and inclusive bounds come from the approved spec.

## Step 3-P risk prediction

| Risk | Early signal | Mitigation and proof | Rollback or rerun point |
|---|---|---|---|
| Local callers each start a Redis flight | same-cache burst records multiple acquire streams | put distributed closure inside `cache.get_or_load`; barrier test asserts one stream | revert Task 3/4 and rerun burst tests |
| Stale owner overwrites/deletes replacement | stale publication succeeds or replacement TTL shrinks | fixed compare-publish script and token compare-delete race tests | revert Task 2 scripts and block coordinators |
| Polling/artifacts consume unbounded work | raw `GET`, uncapped loop, or over-bound allocation appears | bounded snapshot, exact/+1 tests, command-budget stress assertions | revert Task 2-5 slice and rerun hostile/stress tests |
| Redis retry exceeds deadline | retry configuration still yields a policy | derive policy only from finite no-retry settings; negative construction tests | revert policy and block construction |
| Sync timeout interrupts user code | acquired loader stops at `wait_timeout` | separate coordination/lease deadlines; loader-outlives-wait test | revert Task 3 and rerun deadlines |
| Async cancellation leaks/kills shared flight | pending task or remaining waiter loses result | cache-owned flight, one shielded cleanup, task audit | revert Task 4 and rerun cancellation matrix |
| Decoded `None` becomes mismatch | matching result retries or runs loader | tagged `ResultEnvelopeMatch`; exact `None` tests | revert Task 1 and coordinators |
| Identity/token leaks | hostile sentinel appears in diagnostics | digest keys, static messages, schema/redaction tests | revert affected task and rerun redaction |
| Mixed rollout is incompatible | versions share one namespace | schema-version namespace and quiescent rollback runbook | stop rollout and clean only documented digest prefix |
| Container timing hides race | arbitrary sleeps or intermittent failures | one server, barriers, bounded polling, repetitions | diagnose; rerun Task 5 from start |

This risk gate is mandatory because the change introduces distributed
coordination, polling, untrusted Redis bytes, deadlines, concurrency, and async
cancellation.

## File structure

| Path | Responsibility |
|---|---|
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py` | Policy, snapshot, tagged match, coordination contracts and validation. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_envelope.py` | Compatible `decode` and unambiguous `decode_matching`. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_provider.py` | Sync policy discovery, bounded snapshot, atomic publication, scripts. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_async_provider.py` | Awaited provider parity. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_coordination.py` | Key/marker/backoff helpers and sync coordinator. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/_async_coordination.py` | Async coordinator and cancellation-safe cleanup. |
| `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py` | Ordered additive exports. |
| `packages/bluetape-cache-redis/pyproject.toml`, `uv.lock` | Exact focused cache dependency and resolved workspace metadata. |
| `packages/bluetape-cache-redis/tests/_support.py` | Recording providers, clocks, jitter, codecs, observers, barriers. |
| `packages/bluetape-cache-redis/tests/test_redis_contracts.py` | Public API, values, signatures, validation, policy. |
| `packages/bluetape-cache-redis/tests/test_envelope_codec.py` | Tagged match and legitimate `None`. |
| `packages/bluetape-cache-redis/tests/test_sync_provider.py` | Sync primitives, bounds, policy, response validation, races. |
| `packages/bluetape-cache-redis/tests/test_async_provider.py` | Async provider parity and races. |
| `packages/bluetape-cache-redis/tests/test_sync_coordination.py` | Sync state machine, singleflight, deadlines, failures. |
| `packages/bluetape-cache-redis/tests/test_async_coordination.py` | Async parity, cancellation, cleanup, task convergence. |
| `packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py` | Serial real-Redis multi-instance, outage, ACL, lease/race proof. |
| `packages/bluetape-cache-redis/tests/test_packaging.py` | Default isolation and focused-wheel import smoke. |
| `packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py` | Non-gating latency and command-count evidence. |
| `packages/bluetape-cache-redis/README.md`, `README.ko.md` | API, consistency, security, operations, rollout. |
| `README.md`, `README.ko.md`, `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Workspace/package boundaries and completion. |
| `docs/review/2026-07-12-issue-55-redis-load-coordination-*.md` | TDD, performance/stability, verifier, review evidence. |
| `docs/lessons/2026-07-12-issue-55-redis-load-coordination.md` | Durable lesson before PR. |

## Acceptance traceability

| Approved requirement | Plan tasks |
|---|---|
| Exact additive API, focused cache dependency, exports, tagged `None` | 1, 3, 4 |
| Finite no-retry provider policy | 1, 2, 3, 4 |
| Bounded atomic snapshot and matching publication | 2, 5 |
| Sync cache-first singleflight and lease behavior | 3, 5 |
| Async parity, cancellation, no task leaks | 4, 5 |
| Bounded attempts, polls, jitter, deadlines, TTLs, artifacts | 1-5 |
| Stale-owner safety, hostile artifacts, outage, ACL, redaction | 2-5 |
| Independent coordinators collapse a cold burst | 5 |
| Bilingual docs, rollout/rollback, packaging, validation | 6, 7 |
| Verifier and review convergence | 7 and workflow gates |
| PR metadata, live review, successful CI, merge, local cleanup | 8 |

## Task 1: Lock contracts and tagged envelope matching

**Complexity:** High
**Depends on:** Approved spec
**Pattern skill:** `bluetape-py-patterns`
**Write scope:** contracts, envelope, exports, focused tests

**Files:**

- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_envelope.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/pyproject.toml`
- Modify: `uv.lock`
- Modify: `packages/bluetape-cache-redis/tests/test_redis_contracts.py`
- Modify: `packages/bluetape-cache-redis/tests/test_envelope_codec.py`
- Modify: `packages/bluetape-cache-redis/tests/test_packaging.py`

- [ ] **Step 1: Write RED contract and tagged-`None` tests**

Add exact signature/export/enum/error/event/options tests:

```python
def test_options_require_bounded_polling() -> None:
    options = RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3")
    assert options.lease_ttl == 5.0
    assert options.max_attempts == 3
    with pytest.raises(ValueError):
        replace(options, max_poll_interval=options.result_ttl + 0.001)
    with pytest.raises(TypeError):
        replace(options, max_polls=True)


def test_decode_matching_preserves_legitimate_none(envelope_codec) -> None:
    encoded = envelope_codec.encode("owner-1", None)
    match = envelope_codec.decode_matching(encoded, expected_owner_token="owner-1")
    assert match == ResultEnvelopeMatch(value=None)
    assert envelope_codec.decode_matching(
        encoded, expected_owner_token="owner-2"
    ) is None
```

Parametrize exact/+1 namespace and logical-key UTF-8 limits, all duration
bounds, minimum polling, cross-field relations, int/bool rejection, enum order,
static messages, timeout-code membership, event fields, frozen/slotted values,
and the exact ordered exports for symbols that exist after Task 1. The sync
coordinator export is asserted in Task 3; the async coordinator and final full
ordered `__all__` are asserted only after Task 4 creates both classes. Assert
the focused runtime dependency list contains exact `bluetape-cache==0.1.0`, the
meta `cache-redis` extra remains exactly `bluetape-cache-redis==0.1.0`, and the
default meta dependencies remain exactly `bluetape-core==0.1.0`.
Assert `uv.lock` contains the focused `bluetape-cache-redis -> bluetape-cache`
edge; default, dev, and all memberships remain unchanged. Task 6 inspects the
freshly built wheel's exact `Requires-Dist: bluetape-cache==0.1.0` metadata.

- [ ] **Step 2: Run tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_packaging.py -q
uv run pytest packages/bluetape-cache-redis/tests/test_redis_contracts.py \
  packages/bluetape-cache-redis/tests/test_envelope_codec.py -q
```

Expected: packaging first fails its focused dependency/lock assertions; the
separate contract/envelope run then fails collection/import for new contracts
and `decode_matching`.

- [ ] **Step 3: Implement immutable contracts and shared decode path**

Add every spec enum/value, options, errors, observer, snapshot, policy, and
tagged match. Refactor decoding once:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelopeMatch[T]:
    value: T


def decode_matching(
    self, data: bytes, *, expected_owner_token: str
) -> ResultEnvelopeMatch[T] | None:
    envelope = self._decode_envelope(data)
    if envelope.owner_token != expected_owner_token:
        return None
    return ResultEnvelopeMatch(value=self._decode_payload(envelope))


def decode(self, data: bytes, *, expected_owner_token: str) -> T | None:
    match = self.decode_matching(data, expected_owner_token=expected_owner_token)
    return None if match is None else match.value
```

`RedisCommandPolicy.max_command_time` is the sum of exact finite positive
timeouts and exact `max_retries == 0`. Keep the three option-limit constants
private and export the exact spec list including
`MAX_COORDINATION_MARKER_SIZE`, excluding the not-yet-created coordinator
classes until Tasks 3 and 4. Update focused metadata and run `uv lock`; make no
extra/default membership change.

- [ ] **Step 4: Run GREEN and commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_redis_contracts.py \
  packages/bluetape-cache-redis/tests/test_envelope_codec.py \
  packages/bluetape-cache-redis/tests/test_packaging.py -q
uv lock --check
uv run ruff check packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git diff --check
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests \
  packages/bluetape-cache-redis/pyproject.toml uv.lock
git commit -m "feat: define Redis load coordination contracts"
```

Expected: tests and checks pass. Rollback: revert this additive commit; existing
`decode()` remains compatible.

## Task 2: Add bounded provider primitives and no-retry policy

**Complexity:** High
**Depends on:** Task 1
**Pattern skill:** `bluetape-py-patterns`
**Write scope:** providers and provider tests

**Files:**

- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_provider.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_async_provider.py`
- Modify: `packages/bluetape-cache-redis/tests/test_sync_provider.py`
- Modify: `packages/bluetape-cache-redis/tests/test_async_provider.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED policy, snapshot, publication, race tests**

Use recording clients for one exact `EVAL`, no `GET` fallback, exact
arguments, exact/+1 limits, distinct keys, response shapes, sync/async parity:

```python
def test_stale_owner_cannot_publish(recording_client) -> None:
    recording_client.eval_response = 0
    provider = SyncRedisProvider(recording_client)
    assert provider.publish_if_value(
        "lease",
        b"active:old",
        result_key="result",
        result_value=b"old",
        completion_value=b"completed:old",
        ttl=1.0,
    ) is False


def test_retry_on_error_disables_policy(fake_client) -> None:
    fake_client.connection_pool.connection_kwargs = {
        "socket_connect_timeout": 0.1,
        "socket_timeout": 0.2,
        "retry_on_error": [TimeoutError],
    }
    assert SyncRedisProvider(fake_client).command_policy is None
```

Cover absent/infinite/non-positive timeouts, `retry_on_timeout`, `retry`,
non-empty/empty `retry_on_error`, malformed snapshot shapes, bounded oversize
flags, and invalid script responses.

- [ ] **Step 2: Run provider subset and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_sync_provider.py \
  packages/bluetape-cache-redis/tests/test_async_provider.py \
  -k "command_policy or coordination_snapshot or publish_if_value or stale_owner" -q
```

Expected: missing property/method failures.

- [ ] **Step 3: Implement fixed scripts, bounded decoding, policy discovery**

Publication uses exactly:

```lua
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('set', KEYS[2], ARGV[2], 'PX', ARGV[3])
  redis.call('set', KEYS[1], ARGV[4], 'PX', ARGV[3])
  return 1
end
return 0
```

Snapshot obtains `EXISTS`, `STRLEN`, bounded `GETRANGE` for both keys in
one script. Validate limits and distinct keys before `_execute`; validate the
exact six-field response and never return over-bound bytes. Add the two provider
operations in order. Derive policy only from mapping pool settings with finite
positive connect/socket timeouts, absent/false `retry_on_timeout`,
absent/empty `retry_on_error`, and no `retry`.

- [ ] **Step 4: Run GREEN, repeat races, commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_sync_provider.py \
  packages/bluetape-cache-redis/tests/test_async_provider.py -q
for run in {1..10}; do
  uv run pytest packages/bluetape-cache-redis/tests/test_sync_provider.py \
    packages/bluetape-cache-redis/tests/test_async_provider.py \
    -k "stale_owner or snapshot or publish_if_value" -q || exit 1
done
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: add Redis coordination primitives"
```

Expected: tests and ten repetitions pass. Rollback: revert Task 2 and keep all
coordinators unavailable.

## Task 3: Implement synchronous cache-first coordination

**Complexity:** High
**Depends on:** Tasks 1-2
**Pattern skill:** `bluetape-py-patterns`
**Write scope:** shared helpers, sync coordinator/tests

**Files:**

- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_coordination.py`
- Create: `packages/bluetape-cache-redis/tests/test_sync_coordination.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED sync state-machine tests**

Cover local hit, same-cache burst, independent keys, winner, completed result
including `None`, missing marker reacquire, active poll, malformed/oversized
artifact, attempts/polls/deadline, loader/codec/provider failure, lease loss,
late acquire, cache supersession, cleanup dual failure, redaction, observer
failure, and command budgets:

```python
def test_same_cache_burst_uses_one_distributed_flight(sync_harness) -> None:
    assert sync_harness.run_callers(8, key="order-42") == ["loaded"] * 8
    assert sync_harness.loader_calls == ["order-42"]
    assert sync_harness.provider.acquire_calls == 1


def test_stale_owner_returns_local_without_publish(sync_harness) -> None:
    sync_harness.provider.publish_result = False
    assert sync_harness.coordinator.get_or_load("key", lambda _: "local") == "local"
    assert sync_harness.observer.events[-1].outcome is RedisCoordinationOutcome.LEASE_LOST
```

Assert empty keys, digest-only Redis keys, one token per actual acquire,
full-jitter cap, no wait command after deadline, one owner cleanup maximum, and
no attempt/poll increment for a missing marker. Add constructor tests for a
missing/opaque `command_policy`, absent/infinite/excessive timeouts, every hidden
retry form, and `redis_io_timeout < policy.max_command_time`; each fails before
cache or Redis access with only static diagnostics. Add an owner encode-overflow
test that fails before publication and local insertion, performs exactly one
owned cleanup, and preserves caller-controlled cache state. Add a forged
completed envelope whose Redis metadata violates the caller codec's trust
policy; assert no loader, no cache fill, one explicit envelope/codec failure,
and no metadata/artifact text in errors or events. Add token-mismatch cases:
one stale completed envelope followed by a matching result is ignored within
the existing bounded loop and reuses the matching result; repeated mismatches
reach the exact attempt/poll/deadline terminal bound. Neither case invokes the
loader or fills the cache from the mismatched bytes. Assert exact command
budgets. Test `ttl=None`, explicit local TTL and expiry, invalid TTL before Redis
access, and prove coordinator construction/use/garbage collection never closes
or otherwise owns the borrowed cache/provider.

- [ ] **Step 2: Run tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_sync_coordination.py -q
```

Expected: import failure for `SyncRedisLoadCoordinator`.

- [ ] **Step 3: Implement helpers and coordinator**

Derive keys once per distributed flight:

```python
def _coordination_keys(namespace_id: str, logical_key: str) -> tuple[str, str]:
    key_id = sha256(logical_key.encode("utf-8")).hexdigest()
    slot = f"{{{namespace_id}:{key_id}}}"
    prefix = f"bluetape:cache:coord:{namespace_id}:{slot}"
    return f"{prefix}:lease", f"{prefix}:result"
```

Validate locally, compute deadline, call
`cache.get_or_load(key, distributed_loader, ttl=ttl)`. Loop within attempts,
polls, and deadline. Generate `token_urlsafe(32)` before each actual acquire;
recognize strict markers; decode only completed matching results; use private
injected clock/sleep/jitter for tests; emit one terminal event.

On primary failure run one compare-delete, preserve primary type/cause, add one
static PEP 678 note and `cleanup_failed=True` on dual failure. Issue #64 removed
the never-emitted `CLEANUP_FAILURE`; cleanup never replaces the primary failure.
Cleanup is permitted only after this flight has successfully acquired and still
tracks its active marker: constructor, validation, acquire-loss, and snapshot
failures perform zero cleanups; acquired loader/codec/publication failures
perform at most one. Task 3 tests assert both sides. Export
`SyncRedisLoadCoordinator` here and lock its exact signature/order without yet
asserting the future async export.

- [ ] **Step 4: Run GREEN, repeat races, commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_sync_coordination.py -q
for run in {1..10}; do
  uv run pytest packages/bluetape-cache-redis/tests/test_sync_coordination.py \
    -k "burst or stale_owner or deadline or cleanup" -q || exit 1
done
uv run ruff check packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: coordinate synchronous Redis cache loads"
```

Expected: suite and repetitions pass. Rollback: revert Task 3; primitives stay
additive.

## Task 4: Implement async parity and cancellation-safe cleanup

**Complexity:** High
**Depends on:** Tasks 1-3
**Pattern skills:** `bluetape-py-patterns`, `test-driven-development`
**Write scope:** async coordinator/tests

**Files:**

- Create: `packages/bluetape-cache-redis/src/bluetape/cache/redis/_async_coordination.py`
- Create: `packages/bluetape-cache-redis/tests/test_async_coordination.py`
- Modify: `packages/bluetape-cache-redis/src/bluetape/cache/redis/__init__.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED parity and cancellation tests**

Port sync conformance via awaited adapters. Add cancellation before acquire,
during polling, loader, after expiry, cleanup, repeated cleanup cancellation,
individual waiter with remaining waiter, last waiter, loop mismatch, task audit:

```python
@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_flight(async_harness) -> None:
    first = asyncio.create_task(async_harness.load("key"))
    second = asyncio.create_task(async_harness.load("key"))
    await async_harness.loader_started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    async_harness.release_loader()
    assert await second == "value"
    assert async_harness.loader_calls == 1


@pytest.mark.asyncio
async def test_last_waiter_finishes_one_cleanup(async_harness) -> None:
    baseline = set(asyncio.all_tasks())
    caller = asyncio.create_task(async_harness.load("key"))
    await async_harness.owner_acquired.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    await async_harness.wait_until_quiescent()
    assert async_harness.provider.cleanup_calls == 1
    assert not ({t for t in asyncio.all_tasks() if not t.done()} - baseline)
```

Assert cancellation is not encoded, cached, published, translated, or retried;
original cancellation wins after cleanup failure. Repeat all Task 3 policy,
pre-/post-ownership cleanup, forged-metadata, and owner-encode-overflow cases
through the async surface. Assert failures occur before cache/Redis access where
applicable. After creating the async class, assert both coordinator signatures
and the final exact ordered `__all__`.

- [ ] **Step 2: Run tests and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_async_coordination.py -q
```

Expected: import failure for `AsyncRedisLoadCoordinator`.

- [ ] **Step 3: Implement awaited parity and cleanup**

Mirror sync using awaited calls and `asyncio.sleep`. The cache owns the
distributed flight. The owner exception handler passes the already-caught first
`CancelledError` into a cleanup helper; the helper never initializes that state
to `None`. It drives one cleanup task through repeated cancellation, captures
cleanup failure without calling `result()` before cancellation precedence is
resolved, attaches only a static redacted note, records
`cleanup_failed=True`, and then re-raises the first cancellation:

```python
first_cancelled: asyncio.CancelledError = caught_cancelled
cleanup_failure: Exception | None = None
while not cleanup.done():
    try:
        await asyncio.shield(cleanup)
    except asyncio.CancelledError:
        continue
try:
    cleanup.result()
except Exception as error:
    cleanup_failure = error
if cleanup_failure is not None:
    first_cancelled.add_note("cleanup-failure")
raise first_cancelled
```

Do not catch cancellation under `Exception`, start late wait commands, or
retain a task after terminal cache flight. Issue #64 removed the never-emitted
cleanup-only error code; cleanup never replaces an existing loader, codec,
publication, or cancellation primary.

- [ ] **Step 4: Run GREEN, repeat cancellation, commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_async_coordination.py -q
for run in {1..10}; do
  uv run pytest packages/bluetape-cache-redis/tests/test_async_coordination.py \
    -k "cancel or burst or cleanup or deadline" -q || exit 1
done
git add packages/bluetape-cache-redis/src packages/bluetape-cache-redis/tests
git commit -m "feat: coordinate asynchronous Redis cache loads"
```

Expected: pass without pending-task warnings. Rollback: revert Task 4; sync
remains usable.

## Task 5: Prove real-Redis behavior and stability

**Complexity:** High
**Depends on:** Tasks 1-4
**Pattern skill:** `bluetape-py-patterns`
**Write scope:** integration tests and benchmark

**Files:**

- Create: `packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py`
- Create: `packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py`
- Modify: `packages/bluetape-cache-redis/tests/_support.py`

- [ ] **Step 1: Write RED serial integration tests**

One module-scoped `RedisServer`; close every client/provider. Test independent
sync/async coordinators, one-loader collapse, unrelated keys, active/completed
states, abandoned expiry, stale owner, malformed/oversized result,
loader/codec failure, cancellation, and isolated outage/timeout. Add a separate
blackhole TCP proxy fixture that accepts a connection but never responds; it
must not stop or poison the shared RedisServer and must have explicit teardown.
Sync and async tests start a command immediately before the coordination
deadline and assert monotonic elapsed is at most
`wait_timeout + redis_io_timeout + 0.25` seconds, the loader is never invoked,
the stable timeout/provider error is redacted, no later acquire/snapshot/poll
starts, and all tasks/clients converge.

Add three distinct ACL-negative cases: snapshot denied, publication denied, and
compare-delete cleanup denied. Each proves one explicit redacted provider
failure and no command fallback. A least-privilege success principal is limited
to the derived namespace prefix and exactly `SET`, `GET`, `DEL`, `EXISTS`,
`STRLEN`, `GETRANGE`, and `EVAL` plus required connection commands. Every ACL
test uses a unique principal and a `finally` block that runs `ACL DELUSER` and
closes admin/restricted clients even when the assertion fails.

```python
def test_independent_sync_coordinators_share_one_loader(redis_server) -> None:
    coordinators = make_sync_coordinators(redis_server, count=8)
    results, count = run_sync_burst(coordinators, callers=64, key="shared")
    assert results == [b"value"] * 64
    assert count == 1


@pytest.mark.asyncio
async def test_independent_async_coordinators_share_one_loader(redis_server) -> None:
    coordinators = make_async_coordinators(redis_server, count=8)
    results, count = await run_async_burst(coordinators, callers=64, key="shared")
    assert results == [b"value"] * 64
    assert count == 1
```

Instrument calls for 64 callers across eight coordinators: assert loader count
`1`, distributed flights per coordinator `<= 1`, and per-coordinator acquire
`<= max_attempts`, snapshot `<= max_attempts + max_polls`, publish `<= 1`,
cleanup `<= 1`. Assert each aggregate is at most eight times its corresponding
bound. Outage/blackhole cases use only their isolated fixture.

Add a real-Redis stale completed-envelope token-mismatch case that reaches a
later matching result without calling the waiter loader, plus a bounded
mismatch-to-terminal case. Add two coordinators using different schema-version
namespaces for the same logical key and assert they intentionally do not
coalesce (`loader_count == 2`); link this evidence to the rollout duplicate-load
warning in Task 6.

- [ ] **Step 2: Run and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py \
  -m testcontainers -q
```

Expected: helpers or real-Redis behavior fail before completion.

- [ ] **Step 3: Complete fixtures and benchmark**

Use events/barriers, not timing sleeps. Benchmark runs 100 fixed warm-up local
hits and 10 cold bursts, resets the command recorder before each scenario,
reports median latency, and includes Python/platform, caller/coordinator counts,
options, iteration counts, and workload size. It emits JSON only:

```python
results = {
    "local_hit_median_ns": median(measure_local_hits(repetitions=1_000)),
    "contended_cold_burst_median_ns": median(measure_cold_bursts(repetitions=10)),
    "redis_commands": recorder.total,
    "commands_per_caller": recorder.total / 64,
    "loader_count": loader_count,
    "metadata": workload_metadata(),
}
print(json.dumps(results, sort_keys=True))
```

No production capacity claim.

- [ ] **Step 4: Run GREEN, stress, benchmark, commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py \
  -m testcontainers -q
for run in {1..5}; do
  uv run pytest packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py \
    -m testcontainers -k "independent or stale_owner or cancellation" -q || exit 1
done
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py
git add packages/bluetape-cache-redis/tests packages/bluetape-cache-redis/benchmarks
git commit -m "test: prove Redis load coordination behavior"
```

Expected: serial suite, repetitions, JSON smoke pass. Any flaky failure reopens
Tasks 2-4; retry PASS alone is insufficient.

## Task 6: Document behavior, rollout, rollback, packaging

**Complexity:** Medium
**Depends on:** Tasks 1-5
**Pattern skills:** `bluetape-py-patterns`, `bluetape-writer`
**Write scope:** docs and packaging test

**Files:**

- Modify: `packages/bluetape-cache-redis/README.md`
- Modify: `packages/bluetape-cache-redis/README.ko.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`
- Modify: `packages/bluetape-cache-redis/tests/test_packaging.py`
- Create: `packages/bluetape-cache-redis/tests/test_readme_examples.py`

- [ ] **Step 1: Write RED parity and packaging assertions**

Both focused README locales must contain class names, required namespace
example, local/result TTL distinction, lease loss, bounded polling, TLS/ACL,
rollout overlap, quiescent rollback, no-L2 scope, and exact security guidance:
SHA-256 digests are pseudonyms rather than confidentiality; Redis artifacts are
unauthenticated; caller codecs must validate expected metadata and avoid unsafe
deserialization; TLS must not downgrade; ACLs name the exact commands and
derived prefix. Assertions also require: all dependencies are borrowed and the
coordinator has no close method; local cache mutation is not distributed
invalidation; one cache/one coordinator configuration is required; conflicting
configurations are unsupported; namespace includes application,
environment/tenant, and schema version; all participants use compatible codec
and options; `ttl` affects only the local cache; there is no fencing or external
side-effect guarantee; cold Redis failure has no fallback; sync wait timeout
does not interrupt an acquired loader; individual async cancellation differs
from last-waiter flight cancellation; stable error codes/exceptions are the
caller handling surface.

Both focused README locales show the exact shell-safe commands
`pip install bluetape-cache-redis` and
`pip install "bluetape[cache-redis]"`, state that both install
`bluetape-cache` transitively, and state that plain `pip install bluetape`
remains core-only/Redis-free. The root README pair shows the quoted meta-extra
form and the same default-isolation guarantee.

Operator assertions require local hits emit no coordination event; each
cache-owned distributed flight emits exactly one terminal event; alerts use
stable provider/coordination codes plus attempts, polls, elapsed, and
`cleanup_failed`; applications attach static external route labels; diagnostics
exclude raw namespace/key/token/endpoint/exception/artifact metadata; readiness
must prove quiescence before rollback or re-enable. Wheel smoke proves default
`bluetape` remains Redis-free while cache/serde/cache-redis wheels coexist.

Create two executable example smoke tests using recording provider/cache
fixtures. Tests extract fenced snippets named `sync-coordination-example` and
`async-coordination-example` from both README locales, normalize only comments
and localized prose outside the fences, assert the executable code is identical
between locales, then compile/execute that extracted code rather than a copied
test-only snippet. The sync test compiles and constructs the documented coordinator,
calls `get_or_load(..., ttl=...)`, and closes only the provider. The async test
uses the exact documented imports/keywords/`await`, verifies individual caller
lifecycle, and awaits only provider `aclose()`. Both import public coordinator
classes and prove the README snippets cannot drift from signatures.

- [ ] **Step 2: Run and record RED**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_packaging.py -q
uv run pytest packages/bluetape-cache-redis/tests/test_readme_examples.py -q
```

Expected: documentation marker assertions fail, and executable examples fail
because the documented coordinator examples/exports do not yet exist or drift
from the required signatures.

- [ ] **Step 3: Update bilingual docs and state**

Add spec sync/async examples, consistency/failure tables, limits,
timeout/no-retry construction, security, least-privilege `EVAL`, versioned
namespace migration, quiescent rollback, bounded `SCAN`/`UNLINK`. Remove
future-#55 wording; update changelog/WIP; do not change versions. State all
caller and operator contracts named in Step 1 and link the two-namespace
`loader_count == 2` test to the expected duplicate-load rollout window.
Update `docs/package-layout.md` so the focused dependency list includes exact
`bluetape-cache` while preserving opt-in/core-only language. State that the
milestone release reconciles the exact cache pin, refreshes lock/metadata, and
publishes/verifies the cache artifact before cache-redis.

The rollback runbook order is exact in both locales:

1. stop old participants or switch all traffic to the new namespace;
2. wait at least `max(lease_ttl, result_ttl) + redis_io_timeout`;
3. verify event/readiness quiescence and abort immediately if traffic resumes;
4. scan only the retired namespace-digest prefix in bounded `SCAN` batches;
5. delete batches with `UNLINK` (or bounded `DEL` fallback), never `KEYS` and
   never the active namespace;
6. record scanned, deleted, and remaining counts, then recheck quiescence;
7. on cleanup/recovery failure alert on stable codes and keep traffic disabled;
   re-enable only after readiness and remaining-count checks pass.

- [ ] **Step 4: Run GREEN, build smoke, commit**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_packaging.py -q
uv run pytest packages/bluetape-cache-redis/tests/test_readme_examples.py -q
uv build --all-packages
uv run python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

wheel = next(Path("dist").glob("bluetape_cache_redis-0.1.0-*.whl"))
with ZipFile(wheel) as archive:
    metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
    metadata = archive.read(metadata_name).decode("utf-8")
assert "Requires-Dist: bluetape-cache==0.1.0" in metadata
PY
tmp_default=$(mktemp -d)
tmp_direct=$(mktemp -d)
tmp_focused=$(mktemp -d)
wheelhouse=$(mktemp -d)
trap 'rm -rf "$tmp_default" "$tmp_direct" "$tmp_focused" "$wheelhouse"' EXIT
cp dist/*.whl "$wheelhouse"/
uvx --from pip pip download --dest "$wheelhouse" 'redis==8.0.1'
uv venv "$tmp_default/.venv"
uv pip install --python "$tmp_default/.venv/bin/python" dist/bluetape-0.1.0-py3-none-any.whl \
  --find-links dist --no-index
"$tmp_default/.venv/bin/python" -c 'import importlib.util; assert importlib.util.find_spec("redis") is None; assert importlib.util.find_spec("bluetape.cache") is None'
uv venv "$tmp_direct/.venv"
uv pip install --python "$tmp_direct/.venv/bin/python" \
  "$wheelhouse/bluetape_cache_redis-0.1.0-py3-none-any.whl" \
  --find-links "$wheelhouse" --no-index
"$tmp_direct/.venv/bin/python" -c 'from bluetape.cache import TTLCache, AsyncTTLCache; from bluetape.cache.redis import SyncRedisLoadCoordinator, AsyncRedisLoadCoordinator'
uv venv "$tmp_focused/.venv"
uv pip install --python "$tmp_focused/.venv/bin/python" \
  "bluetape[cache-redis] @ file://$wheelhouse/bluetape-0.1.0-py3-none-any.whl" \
  --find-links "$wheelhouse" --no-index
"$tmp_focused/.venv/bin/python" -c 'from bluetape.cache import TTLCache, AsyncTTLCache; from bluetape.cache.redis import SyncRedisLoadCoordinator, AsyncRedisLoadCoordinator'
rm -rf "$tmp_default" "$tmp_direct" "$tmp_focused" "$wheelhouse"
trap - EXIT
git diff --check
git add README.md README.ko.md docs/package-layout.md WIP.md CHANGELOG.md \
  packages/bluetape-cache-redis/README.md \
  packages/bluetape-cache-redis/README.ko.md \
  packages/bluetape-cache-redis/tests/test_packaging.py \
  packages/bluetape-cache-redis/tests/test_readme_examples.py
git commit -m "docs: document Redis load coordination"
```

Expected: packaging, build, import, diff pass. Rollback docs with public API.

## Task 7: Validate, verify, review, and record learning

**Complexity:** High
**Depends on:** Tasks 1-6
**Required skills:** `verification-before-completion`, `bluetape-workflow`
**Write scope:** evidence and lesson; production fixes return to owning task

**Files:**

- Create: `docs/review/2026-07-12-issue-55-redis-load-coordination-tdd-evidence.md`
- Create: `docs/review/2026-07-12-issue-55-redis-load-coordination-performance-stability.md`
- Create: `docs/review/2026-07-12-issue-55-redis-load-coordination-verifier.md`
- Create: `docs/review/2026-07-12-issue-55-redis-load-coordination-code-review.md`
- Create: `docs/lessons/2026-07-12-issue-55-redis-load-coordination.md`

- [ ] **Step 1: Run focused validation**

```bash
uv run pytest packages/bluetape-cache-redis/tests/test_redis_contracts.py \
  packages/bluetape-cache-redis/tests/test_envelope_codec.py \
  packages/bluetape-cache-redis/tests/test_sync_provider.py \
  packages/bluetape-cache-redis/tests/test_async_provider.py \
  packages/bluetape-cache-redis/tests/test_sync_coordination.py \
  packages/bluetape-cache-redis/tests/test_async_coordination.py -q
uv run pytest packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py \
  -m testcontainers -q
uv run pytest packages/bluetape-cache-redis/tests/test_redis_coordination_integration.py \
  -k "blackhole or acl_denied" -q
```

Expected: pass without warnings, hangs, leaks, unexplained retries.

- [ ] **Step 2: Run full ladder**

```bash
uv sync --all-packages
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv build --all-packages
actionlint
git diff --check
```

Expected: all exit 0. Any failure returns to owning task; rerun entire ladder.

- [ ] **Step 3: Run performance/stability and spec/plan verification**

Inspect final diff for blocking, allocation/copies, round trips, polling,
deadlines/cancellation, cleanup, ownership, redaction, container stability.
Map every spec criterion and plan checkbox to source plus fresh command evidence.
Record exact files/commands; verifier verdict must be `PASS`.

- [ ] **Step 4: Run six pre-PR lenses and integrate**

Review performance, stability, security, Ops, API, caller against complete diff.
Fix P0/P1, rerun affected proof/lenses, and record integrated
`P0=0 P1=0`. Resolve or explicitly defer/file every P2/P3.

- [ ] **Step 5: Commit evidence and durable lesson**

Lesson covers cache-first singleflight, active/completed marker, surprises,
proof, review misses, and future guard against unbounded reads/retries:

```bash
git add docs/review docs/lessons/2026-07-12-issue-55-redis-load-coordination.md
git commit -m "docs: record Redis coordination verification"
git status --short
```

Expected: empty status. Then proceed through authorized PR, live review,
successful CI, explicit merge, ancestry verification, `develop` sync, and
worktree/branch cleanup.

## Task 8: Deliver through PR, successful CI, merge, and local cleanup

**Complexity:** High
**Depends on:** Task 7 clean and committed
**Required skills:** `bluetape-workflow`, `verification-before-completion`
**Side effects:** authorized push, PR creation, merge, and merged local cleanup

- [ ] **Step 1: Push and create the issue-linked PR**

Read issue metadata immediately before creation, then push and create the exact
PR. Its body ends with the workflow-required section:

```bash
gh issue view 55 --json state,labels,milestone,assignees,url
git push -u origin feat/issue-55-redis-load-coordination
gh pr create \
  --base develop \
  --head feat/issue-55-redis-load-coordination \
  --title "feat: add Redis load coordination" \
  --assignee debop \
  --label enhancement \
  --milestone "0.2.0" \
  --body $'Closes #55\n\nAdds bounded sync/async Redis load coordination over the existing local caches and Redis envelope/provider substrate.\n\nValidation includes contract, concurrency, cancellation, RedisServer, packaging, lint, build, and review gates.\n\n## DoD Status\n- Type A gates A-01 through A-09: PASS\n- Pre-PR review: P0=0, P1=0\n- CI and live PR review: PENDING'
gh pr view --json number,url,state,baseRefName,headRefName,title,body,labels,milestone,assignees
```

Expected: open PR targets `develop`, head/metadata mirror issue #55, assignee is
`debop`, and the body finishes with `## DoD Status` content.

- [ ] **Step 2: Review the live PR and resolve all findings**

Run the six review perspectives plus integration against the actual PR diff.
Any P0/P1 or change request returns to the owning implementation task and full
affected validation before push. Query reviews and unresolved threads:

```bash
gh pr view --json reviewDecision,reviews,comments,commits,statusCheckRollup
gh api graphql -f query='query { repository(owner:"bluetape4k", name:"bluetape-py") { pullRequest(number: PR_NUMBER) { reviewThreads(first:100) { nodes { isResolved } } } } }'
```

Replace `PR_NUMBER` with the live number returned in Step 1. Expected: latest
integrated `P0=0 P1=0`, no `CHANGES_REQUESTED`, and unresolved thread count `0`.

- [ ] **Step 3: Wait for every required CI check to succeed**

```bash
gh pr checks --watch --fail-fast
gh pr checks
gh pr view --json mergeStateStatus,reviewDecision,statusCheckRollup
```

Expected: every required check reports `SUCCESS`/`pass`; pending, missing,
failure, cancelled, or unexplained skipped checks block merge and return to
diagnosis. Re-read reviews/threads after CI because new feedback reopens Step 2.

- [ ] **Step 4: Merge only after green CI, verify ancestry, sync, and clean**

The user has explicitly authorized merge after successful CI and cleanup of the
merged worktree/branch. Capture the feature tip, merge with repository policy,
then verify remote ancestry before local deletion:

```bash
feature_sha=$(git rev-parse HEAD)
gh pr merge --rebase --delete-branch=false --match-head-commit "$feature_sha"
gh pr view --json state,mergedAt,mergeCommit
merged_sha=$(gh pr view --json mergeCommit --jq '.mergeCommit.oid')
test -n "$merged_sha"
git fetch origin
git merge-base --is-ancestor "$merged_sha" origin/develop
repo=/Users/debop/work/bluetape4k/bluetape-py
git -C "$repo" switch develop
git -C "$repo" pull --ff-only origin develop
git -C "$repo" merge-base --is-ancestor "$merged_sha" develop
git -C "$repo" worktree remove "$repo/.worktrees/feat-issue-55-redis-load-coordination"
git -C "$repo" branch -D feat/issue-55-redis-load-coordination
git -C "$repo" worktree list
git -C "$repo" status --short --branch
```

Expected: PR is `MERGED` with non-null `mergedAt`; the original feature SHA is
retained only as audit evidence because rebase changes commit IDs. The live
`mergeCommit.oid` is in `origin/develop` and local `develop`,
the #55 worktree and local branch alone are removed, and the main checkout is
clean and synchronized. Do not delete any unrelated worktree or branch.

## Execution stop conditions

- Stop if spec/plan disappears, signatures conflict, finite no-retry I/O cannot
  be proved, a deterministic race fails repeatedly, or required validation
  cannot run.
- Do not create PR until Tasks 1-7, verifier, pre-PR review, evidence, lesson pass.
- Do not merge until all required live CI checks succeed and reviews are clear.
- After merge, verify the live PR `mergeCommit.oid` ancestry in
  `origin/develop` and local `develop`; retain the original feature SHA only as
  audit evidence, then remove only the merged #55 worktree and branch.
