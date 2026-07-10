# bluetape-async

Stdlib-only bounded asyncio helpers for bluetape-py.

Source-workspace use is available now. PyPI publication remains on hold until
project ownership and trusted publishing are confirmed.

## Usage

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

`map_bounded` preserves input order while running at most `limit` mapper calls
at once. `limit` creates call-scoped workers and must be between 1 and 1024.
Mapper and iterator work must cooperate with the event loop. `timeout` is one
total cooperative deadline for the whole invocation.

## Choosing Sync, Async, or Bounded Parallelism

Use synchronous iteration when each operation is local or blocking and simple
sequential ownership is the clearest choice:

```python
def fetch_order_sync(order_id: int) -> str:
    return f"order-{order_id}"


orders = [fetch_order_sync(order_id) for order_id in [1, 2, 3]]
```

Use `asyncio.gather` for a small, already-bounded set of coroutine calls:

```python
orders = await asyncio.gather(*(fetch_order(order_id) for order_id in [1, 2, 3]))
```

Use `map_bounded` when input can grow beyond that known set and the caller must
put a concrete concurrency ceiling on cooperative async work:

```python
orders = await map_bounded([1, 2, 3], fetch_order, limit=2, timeout=1.0)
```

## Failure and Cancellation

- Invalid `limit`, `mapper`, or `timeout` values raise `TypeError` or
  `ValueError` before input consumption.
- An expired timeout raises `TimeoutError` after managed work has finished
  cancellation cleanup.
- External cancellation and direct mapper or iterator cancellation raise
  `asyncio.CancelledError` and clean up managed siblings.
- Mapper self-cancellation fails closed without returning partial results.
- Ordinary mapper or iterator failures retain native `ExceptionGroup` shapes.
  Concurrent races intentionally retain native, non-single exception shapes.
