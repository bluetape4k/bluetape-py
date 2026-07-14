# Issue #12 Resilience Policies Design

Date: 2026-07-14 KST
Target issue: #12 - `feat: add resilience policies package`
Target milestone: `0.2.0`

## Problem

`bluetape-py`에는 재시도, 회로 차단, 동시 실행 격리, 비동기 시간 제한을
일관된 계약으로 조합할 수 있는 Python-native 패키지가 없다. 호출자가 각
기능을 직접 조립하면 취소를 일반 실패로 처리하거나, 실행 중인 sync 작업을
강제로 중단할 수 있다고 오해하거나, permit과 half-open probe를 누수하거나,
관측성 callback이 전역 로깅 상태를 소유하는 문제가 생길 수 있다.

이 이슈는 `bluetape-resilience` 배포와 `bluetape.resilience` import 경계를
추가한다. 첫 버전은 stdlib-only 정책 코어와 명시적인 sync/async pipeline에
집중하며 HTTP, Redis, framework, OpenTelemetry adapter는 포함하지 않는다.

## Current Evidence

- GitHub issue #12는 sync/async callable, retry, timeout, circuit breaker,
  bulkhead, backoff, typed outcome/state, 저카디널리티 관측성, caller-owned
  logging hook을 요구한다. 또한 cancellation/deadline 전파, circuit 전환,
  bulkhead 한도, failure classification, hidden task 부재를 acceptance로 둔다.
- `AGENTS.md`와 `docs/package-layout.md`는 focused distribution, Python 3.13+,
  stdlib 우선, 명시적 extra, 성공/실패/경계/취소 테스트를 요구한다.
- 현재 workspace는 `bluetape-async`, `bluetape-cache`, `bluetape-logging`에서
  call-scoped async ownership, first-loop binding, immutable stats snapshot,
  caller-owned logging을 이미 사용한다.
- Python 3.13 `asyncio.timeout()`은 현재 task를 취소하고 context 바깥에서
  `TimeoutError`로 변환한다. 반면 실행 중인 `concurrent.futures.Future`는
  `cancel()`로 중단할 수 없다. 따라서 async timeout은 cooperative contract로
  제공할 수 있지만 sync 강제 timeout은 hidden worker 누수 없이 제공할 수 없다.
- Tenacity는 sync/async retry와 backoff, callback을 폭넓게 제공하지만 circuit
  breaker와 bulkhead를 같은 상태/관측성 계약으로 제공하지 않는다. PyBreaker와
  aiobreaker는 각각 sync/async 중심 경계가 달라 이 패키지의 통합 public API를
  그대로 위임하기 어렵다.
- `bluetape-go/resilience`의 명시적 policy composition, deterministic clock/sleep,
  lazy circuit recovery, synchronous event hook은 의미론적 참고가 된다. Go의
  `context.Context`, generic interface, HTTP adapter 모양은 Python API로 옮기지
  않는다.
- `bluetape4k-resilience4j`의 핵심 재사용 원칙은 coroutine cancellation을 retry,
  fallback, failure event보다 먼저 전파하는 것이다. Resilience4j decorator API와
  JVM dependency shape는 참고 전용이다.

Primary references:

- [Python 3.13 asyncio timeouts](https://docs.python.org/3.13/library/asyncio-task.html#timeouts)
- [Python 3.13 Future cancellation](https://docs.python.org/3.13/library/concurrent.futures.html#future-objects)
- [Tenacity documentation](https://tenacity.readthedocs.io/en/stable/)
- [PyBreaker project](https://pypi.org/project/pybreaker/)
- [aiobreaker documentation](https://aiobreaker.netlify.app/)

## Goals

1. `bluetape-resilience`를 Python 3.13+ stdlib-only focused distribution으로
   추가하고 `bluetape.resilience`에서 import하게 한다.
2. retry, circuit breaker, bulkhead를 sync와 async에 각각 제공하고 timeout은
   cooperative async callable에만 제공한다.
3. 개별 정책과 immutable fluent pipeline을 제공하며 pipeline과 개별 정책을
   decorator 또는 직접 호출 형태로 사용할 수 있게 한다.
4. original return type과 callable signature를 보존하고 domain rejection/error는
   명시적인 예외로 노출한다.
5. background scheduler, reset worker, detached task, global registry, global logger를
   만들지 않는다.
6. cancellation, timeout, permit, half-open probe, observer 실행의 소유권과 정리
   순서를 문서와 테스트로 고정한다.
7. 저카디널리티 typed event와 immutable state snapshot을 제공하되 caller 입력,
   결과, 원본 예외 메시지를 자동 수집하지 않는다.

## Non-Goals

- sync callable의 실행 중 강제 timeout 또는 thread/process preemption
- HTTP client/server, Redis, database, Ktor/Spring/FastAPI/Django adapter
- OpenTelemetry, Prometheus, logging handler/exporter, global policy registry
- rate limiter, fallback, cache, hedging, distributed circuit state
- generator와 async generator decoration 또는 iteration 중 재시도
- sliding-window failure rate, percentile latency, adaptive concurrency
- cross-language API 또는 wire compatibility
- PyPI publication, release, tag, PR, merge

## Package and Install Boundary

- Distribution: `bluetape-resilience`
- Import path: `bluetape.resilience`
- Runtime dependencies: none
- Python: `>=3.13`
- Meta extra: `bluetape[resilience]`
- The default `bluetape` dependency remains exactly `bluetape-core==0.1.0`.
- The focused package joins the workspace, `dev`, and `all` stdlib package sets.
- Package README and root/package meta README locale pairs describe the same public
  behavior and the repository's current publication hold.

## Public API Shape

The ordered public `__all__` contract is:

```python
[
    "Retry",
    "AsyncRetry",
    "CircuitBreaker",
    "AsyncCircuitBreaker",
    "Bulkhead",
    "AsyncBulkhead",
    "AsyncTimeout",
    "ResiliencePipeline",
    "AsyncResiliencePipeline",
    "Backoff",
    "constant_backoff",
    "exponential_backoff",
    "PolicyEvent",
    "PolicyType",
    "EventKind",
    "PolicyOutcome",
    "FailureCategory",
    "CircuitState",
    "CircuitSnapshot",
    "BulkheadSnapshot",
    "RetryExhaustedError",
    "PolicyTimeoutError",
    "CircuitOpenError",
    "BulkheadRejectedError",
]
```

The public categories are:

| Category | Sync | Async/shared |
|---|---|---|
| Retry | `Retry` | `AsyncRetry` |
| Circuit breaker | `CircuitBreaker` | `AsyncCircuitBreaker`, `CircuitState`, `CircuitSnapshot` |
| Bulkhead | `Bulkhead` | `AsyncBulkhead`, `BulkheadSnapshot` |
| Timeout | N/A | `AsyncTimeout` |
| Composition | `ResiliencePipeline` | `AsyncResiliencePipeline` |
| Backoff | shared | `Backoff`, `constant_backoff`, `exponential_backoff` |
| Events | shared | `PolicyEvent`, `PolicyType`, `EventKind`, `PolicyOutcome`, `FailureCategory` |
| Errors | shared | `RetryExhaustedError`, `PolicyTimeoutError`, `CircuitOpenError`, `BulkheadRejectedError` |

All constructors are keyword-only. Durations are finite non-negative seconds except
policy timeouts and circuit open durations, which must be strictly positive. `bool`
is not accepted as an integer or duration. Invalid configuration raises `TypeError`
or `ValueError` before the operation or caller callback is invoked.

Every named policy requires a non-blank `str` without surrounding whitespace. A
policy name is a caller-owned low-cardinality label and may appear in events and
domain error messages; callers must not use request ids, tenant ids, credentials, or
other sensitive/high-cardinality values as policy names.

Policy objects are intentionally stateful only where the policy requires state.
Reusing one breaker or bulkhead instance shares its state/capacity. Creating a new
instance isolates it. Pipelines retain references to policy instances rather than
cloning them.

### Public value contracts

`Backoff` is a runtime-checkable structural protocol with
`__call__(failed_attempt: int, /) -> float`. The attempt is one-based and refers to
the call that just failed.

The string enum members are fixed as follows:

- `PolicyType`: `RETRY`, `TIMEOUT`, `CIRCUIT_BREAKER`, `BULKHEAD`;
- `EventKind`: `SUCCEEDED`, `FAILED`, `RETRY_SCHEDULED`, `TIMED_OUT`,
  `CIRCUIT_TRANSITIONED`, `ADMITTED`, `REJECTED`;
- `PolicyOutcome`: `SUCCESS`, `FAILURE`, `REJECTION`;
- `FailureCategory`: `NONE`, `FAILURE`, `TIMEOUT`, `RETRY_EXHAUSTED`,
  `CIRCUIT_OPEN`, `BULKHEAD_REJECTED`;
- `CircuitState`: `CLOSED`, `OPEN`, `HALF_OPEN`.

`PolicyEvent` is a frozen, slotted dataclass with this exact field order:

```python
policy_name: str
policy_type: PolicyType
kind: EventKind
outcome: PolicyOutcome | None
failure_category: FailureCategory
attempt: int | None
delay: float | None
timeout: float | None
state: CircuitState | None
previous_state: CircuitState | None
in_flight: int | None
waiters: int | None
```

Unused event fields are `None`; `failure_category` is `NONE` when no failure is
associated with the event. Events do not contain wall-clock timestamps or generated
identifiers.

`CircuitSnapshot` is frozen and slotted with `name`, `state`,
`consecutive_failures`, `recovery_successes`, and `half_open_in_flight` fields in that
order. `BulkheadSnapshot` is frozen and slotted with `name`, `max_concurrency`,
`in_flight`, and `waiters` fields in that order. Counts are non-negative integers.
Private circuit generations and synchronization objects are not exposed.

### Constructor contracts

The public keyword-only configuration is fixed at the design level:

```python
Retry(
    *, name: str, max_attempts: int, backoff: Backoff = constant_backoff(0),
    retry_if: Callable[[Exception], bool] | None = None,
    observer: Callable[[PolicyEvent], None] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
)

AsyncRetry(
    *, name: str, max_attempts: int, backoff: Backoff = constant_backoff(0),
    retry_if: Callable[[Exception], bool] | None = None,
    observer: Callable[[PolicyEvent], None] | None = None,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
)

CircuitBreaker(
    *, name: str, failure_threshold: int, open_duration: float,
    half_open_max_calls: int = 1, recovery_success_threshold: int = 1,
    failure_if: Callable[[Exception], bool] | None = None,
    observer: Callable[[PolicyEvent], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
)

AsyncCircuitBreaker(...)  # same public configuration as CircuitBreaker

Bulkhead(
    *, name: str, max_concurrency: int, max_wait: float = 0,
    observer: Callable[[PolicyEvent], None] | None = None,
)

AsyncBulkhead(...)  # same public configuration as Bulkhead

AsyncTimeout(
    *, name: str, timeout: float,
    observer: Callable[[PolicyEvent], None] | None = None,
)
```

`constant_backoff(delay: float = 0, /) -> Backoff` accepts a finite non-negative
delay. `exponential_backoff(*, initial_delay: float, multiplier: float = 2,
max_delay: float | None = None, jitter: float = 0,
random_source: Callable[[], float] = random.random) -> Backoff` requires a finite
positive initial delay and multiplier, an optional finite positive maximum, and
`jitter` in the inclusive range `0..1`. The random result must be finite in `0..1`.

Callable configuration is validated before protected work. The package does not call
user predicates, clocks, observers, sleepers, or random sources merely to validate a
constructor.

`ResiliencePipeline()` and `AsyncResiliencePipeline()` accept no constructor
arguments. The sync pipeline exposes `with_retry(Retry)`,
`with_circuit_breaker(CircuitBreaker)`, and `with_bulkhead(Bulkhead)`. The async
pipeline exposes the corresponding async policy methods plus
`with_timeout(AsyncTimeout)`. Each method rejects a policy from the other execution
family. All policies and pipelines expose generic `.call(operation, *args, **kwargs)`
and decorator `__call__` signatures preserving `ParamSpec` and the operation return
type.

## Decorator and Fluent Pipeline Contract

The primary composition surface is an immutable pipeline:

```python
pipeline = (
    ResiliencePipeline()
    .with_circuit_breaker(breaker)
    .with_retry(retry)
    .with_bulkhead(bulkhead)
)

@pipeline
def load_catalog() -> Catalog:
    ...
```

The async surface is separate and may include timeout:

```python
pipeline = (
    AsyncResiliencePipeline()
    .with_circuit_breaker(breaker)
    .with_retry(retry)
    .with_timeout(timeout)
    .with_bulkhead(bulkhead)
)

@pipeline
async def load_catalog() -> Catalog:
    ...
```

- Every `.with_*()` returns a new pipeline. The original pipeline is unchanged.
- The last added policy is the outermost wrapper and observes the result of all
  earlier policies. In the async example, bulkhead admission wraps timeout, retry,
  circuit breaker, and the operation.
- `functools.wraps`, `ParamSpec`, and the original return type preserve function and
  bound-method signatures for static typing and introspection.
- A sync pipeline rejects coroutine functions. An async pipeline rejects ordinary
  sync functions before invoking them. A callable that violates the declared
  awaitable contract fails without being adapted through a hidden thread.
- Decorating generator or async-generator functions raises `TypeError` at decoration
  time because retrying function creation would not protect iteration.
- Each individual policy can also decorate a compatible callable. Direct invocation
  remains explicit through `policy.call(operation, *args, **kwargs)` and
  `pipeline.call(operation, *args, **kwargs)`; async variants are awaited.
- Empty pipelines act as signature-preserving pass-through wrappers.

Composition order is behavioral, not cosmetic. For example, retry outside a circuit
breaker lets the breaker observe each attempt; circuit breaker outside retry observes
only the final retry outcome. Documentation includes both forms and does not declare
one universal service-call order.

## Retry and Backoff Contract

- `max_attempts` is a finite positive integer and includes the first call.
- `retry_if(error)` is caller-owned and decides whether an ordinary operation
  exception is retryable. The default retries ordinary `Exception` failures except
  package admission rejections and policy-owned cancellation signals.
- `asyncio.CancelledError` is re-raised before retry classification, event emission,
  or backoff. It never consumes another attempt.
- Exhaustion raises `RetryExhaustedError` with the attempt count and last exception
  available as `__cause__`. A non-retryable exception is propagated unchanged.
- Backoff receives the one-based failed attempt number and returns finite
  non-negative seconds. Invalid callback output fails before sleeping.
- Sync delay uses an injectable sleeper with `time.sleep` as the default. Async delay
  uses an injectable async sleeper with `asyncio.sleep` as the default.
- `constant_backoff` and `exponential_backoff` are immutable callables. Exponential
  backoff supports a maximum delay and bounded jitter. A caller-supplied random source
  makes jitter tests deterministic.
- No retry attempt starts after cancellation, timeout, or a terminal classifier
  decision is observed.

## Async Timeout Contract

- `AsyncTimeout` accepts a finite positive duration and uses `asyncio.timeout()` over
  the wrapped awaitable.
- Policy-owned expiry raises `PolicyTimeoutError`, a `TimeoutError` subclass, with the
  original timeout exception chained as its cause.
- A `TimeoutError` raised directly by the protected operation before the policy
  deadline remains that original exception. Only expiry reported by the policy's own
  timeout context is translated to `PolicyTimeoutError`.
- External caller cancellation remains `asyncio.CancelledError` and is never
  translated to timeout or failure.
- Timeout is cooperative. The protected coroutine must yield and must not suppress
  cancellation. Cancellation suppression is outside the supported contract and may
  delay or prevent timeout completion.
- The call returns or raises only after package-owned async cleanup completes. The
  timeout policy creates no detached task.
- There is no sync `Timeout`. Waiting on a worker future and abandoning a running
  thread would violate the no-hidden-work contract.

## Circuit Breaker Contract

- States are `CLOSED`, `OPEN`, and `HALF_OPEN`.
- Configuration includes a positive consecutive failure threshold, positive open
  duration, positive half-open concurrent probe limit, positive recovery success
  threshold, caller-owned failure predicate, monotonic clock, and optional observer.
- `CLOSED` resets the consecutive failure count on success and opens after the
  configured number of classified failures.
- `OPEN` rejects calls with `CircuitOpenError`. No background timer changes state.
  The first later admission after the open deadline lazily transitions to
  `HALF_OPEN`.
- `HALF_OPEN` admits at most the configured probe count. A classified failure reopens
  the circuit; enough successful probes close it. Excess probes receive
  `CircuitOpenError`.
- Every admission carries a private generation token. A completion from an older
  generation may emit its own call outcome but cannot mutate the current generation's
  counters or state. This prevents late concurrent completions from closing or
  reopening a newer circuit epoch.
- Failure predicates run outside the state lock. If a predicate raises, its exception
  propagates without being classified by that circuit, but any owned half-open slot is
  still released and current circuit counters remain internally consistent.
- Sync state is guarded by a short-held thread lock. Async state is bound to the first
  event loop and uses async-compatible ownership. User operations and observers never
  run while the circuit state lock is held.
- `snapshot()` returns an immutable `CircuitSnapshot`; it does not expose mutable
  internal counters or a registry.

## Bulkhead Contract

- Configuration includes positive `max_concurrency`, finite non-negative `max_wait`,
  monotonic timing where required, and an optional observer.
- `max_wait=0` performs immediate admission or raises `BulkheadRejectedError`.
  A positive value allows bounded waiting. Unbounded waiting is not supported.
- Sync and async implementations use their native synchronization ownership and do
  not share one semaphore instance. Async bulkheads bind to their first event loop.
- Admission ordering and waiter fairness are not guaranteed.
- A permit is released in `finally` after success, ordinary failure, observer failure,
  cancellation, and timeout. A rejected or cancelled waiter never releases a permit
  it did not acquire.
- `snapshot()` returns an immutable `BulkheadSnapshot` with configured capacity,
  in-flight count, and waiter count.

## Failure Classification and Errors

The public operation result remains the callable's original return type. "Typed
outcome" means typed event outcomes, state snapshots, and domain errors; it does not
introduce a `Result[T, E]` wrapper around successful calls.

- `RetryExhaustedError`: terminal retry exhaustion; chains the last operation error.
- `PolicyTimeoutError`: this package's async timeout expiry; subclasses
  `TimeoutError`.
- `CircuitOpenError`: circuit admission rejection with policy name and current state.
- `BulkheadRejectedError`: capacity or bounded-wait admission rejection.
- `FailureCategory` is a closed, low-cardinality enum for `NONE`, `FAILURE`,
  `TIMEOUT`, `RETRY_EXHAUSTED`, `CIRCUIT_OPEN`, and `BULKHEAD_REJECTED`.
- Cancellation is a control signal, not an ordinary failure category. Policies
  propagate `asyncio.CancelledError` before invoking observers, so observer failures
  cannot mask caller cancellation. Cancellation never changes retry/circuit failure
  counters and does not emit a policy event in this first version.
- Caller predicates can narrow retry and circuit failure decisions. Predicate errors
  propagate and are not recursively classified by the same policy.

## Observability Contract

`PolicyEvent` is a frozen, slotted dataclass containing only stable fields such as:

- policy name and `PolicyType`;
- `EventKind`, `PolicyOutcome`, and `FailureCategory`;
- attempt, delay, configured timeout;
- current/previous circuit state;
- in-flight and waiter counts.

The event sequence is part of the public contract:

| Policy | Events |
|---|---|
| Retry | `RETRY_SCHEDULED` after a retry decision and before delay; one terminal `SUCCEEDED` or `FAILED` |
| Async timeout | `SUCCEEDED` on completion, `TIMED_OUT` only for policy-owned expiry, `FAILED` for an ordinary operation error |
| Circuit breaker | `ADMITTED` before an accepted call; `REJECTED` for open/excess probes; `CIRCUIT_TRANSITIONED` after each state change; terminal `SUCCEEDED` or `FAILED` for admitted calls |
| Bulkhead | `ADMITTED` after permit acquisition; `REJECTED` after immediate/bounded-wait failure; terminal `SUCCEEDED` or `FAILED` for admitted calls |

Within one policy, an admission event precedes operation invocation, a transition is
emitted after the state mutation, and a terminal event is emitted after owned state
and permits are reconciled. Wrapper nesting determines cross-policy event order. No
event is emitted after an observer error stops that policy path.

It never contains callable arguments, return values, cache/tenant keys, raw exception
objects, exception messages, tracebacks, or logger instances. Applications correlate
and redact richer context outside the package. Policy names are the sole
caller-provided labels and remain subject to the stable, non-sensitive naming contract
above.

Observers are caller-owned synchronous callbacks and run inline on the protected call
path. They are invoked outside internal state locks. The package does not configure
`logging`, create an exporter, enqueue background work, or suppress observer errors.
If an observer raises, that exception propagates after the emitting policy has restored
its owned permit/probe/state invariants. An outer policy may observe that exception
according to normal composition order. Observers must therefore be fast,
non-blocking, non-raising, and safe for concurrent calls.

## Concurrency and Ownership

- Sync policy instances are thread-safe for concurrent calls.
- Async stateful policy instances bind to the first running event loop; later use from
  another loop raises `RuntimeError` before admission.
- Pipeline objects are immutable and safe to reuse, but they intentionally share the
  referenced policy instances.
- No policy creates a global executor, thread, scheduler, timer task, registry, or
  detached coroutine.
- Every acquired permit and half-open slot has exactly one owner and one `finally`
  release path.
- Clock, sleeper, and jitter injection are package-local testability boundaries, not
  global mutable configuration.

## Alternatives

### Option A - Separate sync/async policies plus fluent decorator pipeline (selected)

This option exposes native synchronization and cancellation semantics while sharing
names, event vocabulary, error types, backoff, and immutable composition behavior.

Pros:

- Explicit sync/async ownership and misuse rejection.
- Supports `@pipeline`, individual policy decorators, and one-shot `.call()`.
- Keeps state sharing and wrapper order visible.
- Requires no runtime dependency.

Cons:

- Parallel sync/async class names and tests create more public surface.
- Callers must intentionally construct the matching policy family.

### Option B - One policy object with `call()` and `call_async()`

Pros:

- Fewer public names.

Cons:

- Mixes thread locks, event-loop binding, sync sleeping, async sleeping, and bulkhead
  capacity in one object.
- Makes cross-mode state sharing ambiguous and easy to misuse.

Decision: reject.

### Option C - Decorator functions backed by Tenacity/PyBreaker/aiobreaker

Pros:

- Less initial retry or circuit implementation code.
- Familiar third-party behavior.

Cons:

- No single dependency provides the complete sync/async policy set and ownership
  contract.
- Public errors, state, events, cancellation, and composition would inherit multiple
  upstream semantics and dependency lifecycles.
- Bulkhead and timeout gaps would still require first-party code.

Decision: reject dependencies for the first package; retain them as behavioral
comparison references.

### Option D - Decorator-only API

Pros:

- Small examples.

Cons:

- Hides state sharing and makes dynamic/one-shot composition awkward.
- Wrapper order and policy inspection are harder to explain and test.

Decision: reject as the sole API. Keep decorator use as one surface of public policy
objects and pipelines.

## Failure Modes and Mitigations

| Failure mode | Severity | Mitigation |
|---|---:|---|
| Sync timeout abandons a running worker thread. | P0 | Do not expose sync timeout or hidden executors. |
| Async cancellation is retried, counted, or translated incorrectly. | P1 | Re-raise `CancelledError` before classifiers/events and test cleanup/count preservation. |
| Bulkhead permit or half-open probe leaks after failure/cancellation/hook error. | P0 | Single-owner `finally` release plus stress and cancellation tests. |
| Late completion from an old circuit epoch corrupts a new state. | P1 | Generation-tag admissions and stale-completion tests. |
| Observer runs under a lock, deadlocks reentrantly, or exports secrets. | P1 | Invoke outside locks; events exclude caller values/raw errors; document inline behavior. |
| Pipeline order is misunderstood and changes retry/circuit semantics. | P1 | Last-added-outermost contract plus trace-based composition tests and contrasting examples. |
| Async policy is reused across event loops. | P1 | First-use loop binding and deterministic rejection before admission. |
| Backoff or duration accepts NaN/infinity/bool and creates hangs. | P1 | Eager finite-value validation and injected deterministic sleepers. |
| Stateful decorator is assumed to create per-call isolation. | P2 | Document instance sharing and test reuse versus separate instances. |
| Operation `TimeoutError` is mistaken for policy-owned expiry. | P1 | Translate only the owned timeout context's expiry and test nested/original timeout errors. |
| Failure predicate raises while a half-open probe is owned. | P1 | Release the generation-tagged slot without recording success/failure, then propagate the predicate error. |

## Compatibility and Migration

This is a new public package, so no compatibility alias or migration shim is needed.
Cross-language siblings are semantic references only. The package does not promise
equivalent default thresholds, wrapper order, error classes, or shared state with Go
or Kotlin implementations.

Future HTTP/framework/telemetry adapters must depend on this focused package rather
than expand its stdlib-only core. Adding sliding-window breakers, unbounded queues,
rate limiting, fallback, generator retry, or distributed state requires a follow-up
design and cannot silently change these first-version contracts.

## Acceptance Criteria

1. `bluetape-resilience` builds and imports from `bluetape.resilience` without runtime
   dependencies; the default meta install stays core-only.
2. Sync and async retry preserve return types, stop at configured attempts, use
   deterministic backoff, propagate non-retryable errors, and expose exhaustion cause.
3. `AsyncTimeout` distinguishes policy expiry from external cancellation and leaves no
   package-owned task; no sync timeout API exists.
4. Sync and async circuit breakers deterministically cover closed/open/half-open
   transitions, bounded probes, lazy recovery, concurrent stale completions, snapshots,
   and caller failure classification.
5. Sync and async bulkheads never exceed capacity, bound waiting, reject explicitly,
   and release every acquired permit on all terminal paths.
6. `CancelledError` is never retried or counted as circuit failure and every async
   cancellation path completes package-owned cleanup.
7. Pipelines are immutable, last-added-outermost, preserve function/method metadata and
   type shape, support decorator and direct-call use, and reject sync/async/generator
   misuse before protected work.
8. Events and snapshots are typed, immutable, low-cardinality, contain no caller-owned
   values or raw errors, and observers run inline outside internal locks.
9. Examples show small Pythonic sync and async composition, including how order changes
   whether a breaker sees individual retry attempts or only the final outcome.
10. Package/root README locale pairs, package layout, WIP, changelog, workspace/meta
    metadata, lockfile, and build/import smoke tests agree with the implemented surface.

## Verification and DoD

- Targeted tests cover success, invalid input, empty/zero boundaries, non-retryable and
  exhausted failures, deterministic constant/exponential jitter, wrapper order,
  signature preservation, method decoration, generator rejection, state sharing, and
  observer errors.
- Concurrency tests cover sync threads and async tasks, maximum in-flight counts,
  immediate and bounded-wait rejection, waiter cancellation, permit cleanup, circuit
  generation races, half-open bounds, and event-loop misuse.
- Async tests use bounded coordination primitives rather than long sleeps and prove
  timeout/cancellation cleanup plus absence of package-owned orphan tasks.
- Packaging proof runs workspace sync/lock checks, targeted and full pytest, Ruff lint
  and format checks, all-package builds, isolated wheel/import/meta-extra smoke tests,
  and `git diff --check`.
- Spec, plan, implementation, and pre-PR reviews must each converge to `P0=0` and
  `P1=0`. This design approval does not authorize implementation, PR creation, merge,
  publication, or release actions.
