# bluetape-resilience

English | [한국어](README.ko.md)

Stdlib-only synchronous and asynchronous resilience policies for Python 3.13+.
Install the focused `bluetape-resilience` distribution or the explicit
`bluetape[resilience]` meta extra, then import from `bluetape.resilience`.
The default `bluetape` install remains core-only. PyPI publication is currently
on hold, so these install names describe the intended public shape; use the
source workspace or a locally built wheel today.

## Policies

| Policy | Sync | Async | Contract |
|---|---|---|---|
| Retry | `Retry` | `AsyncRetry` | Bounded attempts with constant or exponential backoff. |
| Circuit breaker | `CircuitBreaker` | `AsyncCircuitBreaker` | `CLOSED`, `OPEN`, and bounded `HALF_OPEN` probes with lazy recovery. |
| Bulkhead | `Bulkhead` | `AsyncBulkhead` | Bounded concurrency and optional bounded waiting; no unbounded queue. |
| Timeout | none | `AsyncTimeout` | Cooperative task timeout using the caller's event loop. |
| Composition | `ResiliencePipeline` | `AsyncResiliencePipeline` | Immutable fluent composition, decorator use, and direct `.call()`. |

All constructors are keyword-only. Reusing a breaker or bulkhead instance shares
its state or capacity across every pipeline that references it; create a new
instance for isolation. Circuit recovery is lazy: no timer or worker changes an
open circuit until a later call attempts admission.

## Synchronous use

<!-- resilience-example:sync:start -->
```python
from bluetape.resilience import CircuitBreaker, ResiliencePipeline, Retry

breaker = CircuitBreaker(
    name="backend-breaker",
    failure_threshold=3,
    open_duration=5,
)
retry = Retry(name="backend-retry", max_attempts=2)
pipeline = (
    ResiliencePipeline()
    .with_circuit_breaker(breaker)
    .with_retry(retry)
)


@pipeline
def load(value: str) -> str:
    return value


assert load("decorated") == "decorated"
assert pipeline.call(lambda: "direct") == "direct"
```
<!-- resilience-example:sync:end -->

Each `.with_*()` returns a new pipeline and retains the supplied policy instance.
The last-added policy is the outermost wrapper. Composition order is behavioral:

```python
# Retry is outermost, so the breaker observes every retry attempt.
per_attempt = ResiliencePipeline().with_circuit_breaker(breaker).with_retry(retry)

# Breaker is outermost, so it observes only the final retry outcome.
final_outcome = ResiliencePipeline().with_retry(retry).with_circuit_breaker(breaker)
```

## Asynchronous use

<!-- resilience-example:async:start -->
```python
import asyncio

from bluetape.resilience import (
    AsyncBulkhead,
    AsyncResiliencePipeline,
    AsyncRetry,
    AsyncTimeout,
)


async def main() -> None:
    pipeline = (
        AsyncResiliencePipeline()
        .with_retry(AsyncRetry(name="backend-retry", max_attempts=2))
        .with_timeout(AsyncTimeout(name="backend-timeout", timeout=1))
        .with_bulkhead(AsyncBulkhead(name="backend-bulkhead", max_concurrency=8))
    )

    @pipeline
    async def load(value: str) -> str:
        await asyncio.sleep(0)
        return value

    assert await load("decorated") == "decorated"
    assert await pipeline.call(asyncio.sleep, 0, result="direct") == "direct"


asyncio.run(main())
```
<!-- resilience-example:async:end -->

`AsyncTimeout` is cooperative: it cancels the current task through
`asyncio.timeout()` and raises `PolicyTimeoutError` only for its own expiry.
External `asyncio.CancelledError` is propagated unchanged. A bulkhead releases its
permit after success, failure, timeout, observer failure, or cancellation; a
rejected or cancelled waiter never releases a permit it did not acquire.

## Events and failures

An optional observer receives a typed `PolicyEvent` inline on the caller's thread
or task. The package does not create a logger, exporter, queue, or background task.
Observer failures propagate only after policy cleanup. Use fixed, low-cardinality
policy names; never put request IDs, tenant IDs, credentials, arguments, results,
or exception text into names. Events intentionally contain no caller values,
exception messages, timestamps, or generated identifiers.

Domain failures are `RetryExhaustedError`, `PolicyTimeoutError`,
`CircuitOpenError`, and `BulkheadRejectedError`. Operation exceptions that do not
reach a policy-owned terminal condition retain their original type.

## Explicit limits

- There is no synchronous timeout: Python cannot safely preempt an in-flight sync
  callable without owning a thread or process whose work may outlive the call.
- Generator and async-generator functions are rejected; policy protection applies
  to callable execution, not deferred iteration.
- There are no HTTP, Redis, framework, telemetry, or sibling-language adapters.
- There are no global registries, reset schedulers, detached tasks, or hidden
  workers.

From this repository, run `uv sync --all-packages --locked` or build the focused
wheel with `uv build --package bluetape-resilience`.
