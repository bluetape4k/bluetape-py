# bluetape-async

[English](README.md) | 한국어

`bluetape-py`를 위한 표준 라이브러리 전용 bounded asyncio helper입니다.

현재는 source workspace에서 사용할 수 있습니다. project ownership과 trusted publishing을 확인하기 전까지 PyPI publication은 보류합니다.

## 사용법

```python
import asyncio

from bluetape.asyncio import map_bounded


async def fetch_order(order_id: int) -> str:
    await asyncio.sleep(0.01)
    return f"order-{order_id}"


async def main() -> None:
    orders = await map_bounded([1, 2, 3], fetch_order, limit=2, timeout=1.0)
    print(orders)


asyncio.run(main())
```

`map_bounded`는 입력 순서를 유지하면서 한 번에 최대 `limit`개의 mapper 호출을 실행합니다. `limit`은 호출 범위 worker를 만들며 1 이상 1024 이하여야 합니다. mapper와 iterator 작업은 event loop와 협력해야 합니다. `timeout`은 전체 호출에 적용되는 하나의 cooperative deadline입니다.

## Sync, Async, bounded parallelism 선택

각 작업이 로컬 또는 blocking 작업이고 단순한 순차 소유권이 가장 명확하다면 synchronous iteration을 사용합니다.

```python
def fetch_order_sync(order_id: int) -> str:
    return f"order-{order_id}"


orders = [fetch_order_sync(order_id) for order_id in [1, 2, 3]]
```

이미 범위가 제한된 소수의 coroutine 호출에는 `asyncio.gather`를 사용합니다.

```python
orders = await asyncio.gather(*(fetch_order(order_id) for order_id in [1, 2, 3]))
```

입력이 알려진 집합보다 커질 수 있고 caller가 cooperative async 작업에 구체적인 concurrency ceiling을 적용해야 한다면 `map_bounded`를 사용합니다.

```python
orders = await map_bounded([1, 2, 3], fetch_order, limit=2, timeout=1.0)
```

## 실패와 cancellation

- 잘못된 `limit`, `mapper`, `timeout` 값은 입력을 소비하기 전에 `TypeError` 또는 `ValueError`를 발생시킵니다.
- 만료된 timeout은 관리 대상 작업의 cancellation cleanup이 끝난 뒤 `TimeoutError`를 발생시킵니다.
- 외부 cancellation과 mapper 또는 iterator의 직접 cancellation은 `asyncio.CancelledError`를 발생시키고 관리 대상 sibling을 정리합니다.
- mapper의 self-cancellation은 fail closed로 동작하며 부분 결과를 반환하지 않습니다.
- 일반 mapper 또는 iterator 실패는 원래의 `ExceptionGroup` 형태를 유지합니다. 동시 실행 race에서도 의도적으로 native의 단일 예외가 아닌 형태를 유지합니다.
