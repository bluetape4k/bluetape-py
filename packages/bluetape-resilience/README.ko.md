# bluetape-resilience

[English](README.md) | 한국어

Python 3.13+용 표준 라이브러리 기반 동기·비동기 resilience policy 패키지입니다.
목적별 `bluetape-resilience` 배포 패키지 또는 명시적
`bluetape[resilience]` meta extra를 설치하고 `bluetape.resilience`에서
import합니다. 기본 `bluetape` 설치는 계속 core-only입니다. 현재 PyPI 배포는
보류 중이므로 이 이름은 의도한 공개 설치 형태이며, 지금은 source workspace나
로컬에서 빌드한 wheel을 사용합니다.

## 정책

| 정책 | 동기 | 비동기 | 계약 |
|---|---|---|---|
| Retry | `Retry` | `AsyncRetry` | Constant 또는 exponential backoff를 사용하는 bounded attempt. |
| Circuit breaker | `CircuitBreaker` | `AsyncCircuitBreaker` | `CLOSED`, `OPEN`, bounded `HALF_OPEN` probe와 lazy recovery. |
| Bulkhead | `Bulkhead` | `AsyncBulkhead` | Bounded concurrency와 선택적 bounded wait. 무제한 queue는 없음. |
| Timeout | 없음 | `AsyncTimeout` | Caller event loop에서 동작하는 cooperative task timeout. |
| 조합 | `ResiliencePipeline` | `AsyncResiliencePipeline` | Immutable fluent 조합, decorator, 직접 `.call()`. |

모든 constructor는 keyword-only입니다. 같은 breaker 또는 bulkhead instance를
여러 pipeline에서 재사용하면 state 또는 capacity를 공유합니다. 격리가 필요하면
새 instance를 만듭니다. Circuit recovery는 lazy 방식이며 timer나 worker가
background에서 상태를 바꾸지 않고 다음 admission 시도에서만 회복을 검사합니다.

## 동기 사용

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

각 `.with_*()`는 전달받은 policy instance를 보존한 새 pipeline을 반환합니다.
마지막에 추가한 policy가 가장 바깥쪽 wrapper입니다. 조합 순서는 동작을 바꿉니다.

```python
# Retry가 바깥쪽이므로 breaker가 각 retry attempt를 관찰합니다.
per_attempt = ResiliencePipeline().with_circuit_breaker(breaker).with_retry(retry)

# Breaker가 바깥쪽이므로 최종 retry 결과만 관찰합니다.
final_outcome = ResiliencePipeline().with_retry(retry).with_circuit_breaker(breaker)
```

## 비동기 사용

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

`AsyncTimeout`은 cooperative 방식입니다. `asyncio.timeout()`으로 현재 task를
취소하며 자체 만료만 `PolicyTimeoutError`로 바꿉니다. 외부
`asyncio.CancelledError`는 그대로 전파합니다. Bulkhead permit은 성공, 실패,
timeout, observer 실패, cancellation 뒤에 반환되며 reject되거나 취소된 waiter는
획득하지 않은 permit을 반환하지 않습니다.

## 이벤트와 실패

선택적 observer는 caller의 thread 또는 task에서 typed `PolicyEvent`를 inline으로
받습니다. 패키지는 logger, exporter, queue, background task를 만들지 않습니다.
Observer 실패는 policy cleanup 뒤에 전파합니다. Policy name은 고정된
low-cardinality 값이어야 하며 request ID, tenant ID, credential, argument, result,
exception text를 이름에 넣지 않습니다. Event에는 caller value, exception message,
timestamp, generated identifier가 포함되지 않습니다.

Domain failure는 `RetryExhaustedError`, `PolicyTimeoutError`,
`CircuitOpenError`, `BulkheadRejectedError`입니다. Policy가 소유한 terminal
condition에 도달하지 않은 operation exception은 원래 type을 유지합니다.

## 명시적 제한

- 동기 timeout은 없습니다. 실행 중인 sync callable을 안전하게 선점하려면 호출보다
  오래 살 수 있는 thread 또는 process를 패키지가 소유해야 하기 때문입니다.
- Generator와 async-generator 함수는 지원하지 않습니다. Policy는 deferred
  iteration이 아니라 callable 실행을 보호합니다.
- HTTP, Redis, framework, telemetry, sibling-language adapter는 없습니다.
- Global registry, reset scheduler, detached task, hidden worker는 없습니다.

이 저장소에서는 `uv sync --all-packages --locked`를 실행하거나
`uv build --package bluetape-resilience`로 목적별 wheel을 빌드합니다.
