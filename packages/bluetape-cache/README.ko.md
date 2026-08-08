# bluetape-cache

[English](README.md) | 한국어

`bluetape-cache`는 동기 및 `asyncio` 애플리케이션을 위한 표준 라이브러리 전용 bounded local TTL loading cache를 제공합니다. entry는 지연 방식으로 만료되고, 살아 있는 entry 수는 LRU eviction으로 제한하며, 동일 key의 동시 miss는 하나의 loader를 공유합니다.

Redis provider와 load coordination은 의도적으로 이 package 밖에 두며 opt-in `bluetape-cache-redis` distribution으로 제공합니다. RESP3 near-cache invalidation은 별도의 upstream-blocked issue #56으로 남아 있습니다.

## 설치

registry publication이 활성화된 후에는 focused distribution 또는 명시적 meta extra를 설치합니다.

```bash
pip install bluetape-cache
pip install "bluetape[cache]"
```

위 registry 명령은 향후 install shape를 설명합니다. 현재 source workspace에서는 locked workspace environment를 사용하고 아래 import smoke를 그대로 실행합니다.

```bash
uv sync --all-packages --locked
uv run --package bluetape-cache python -c "from bluetape.cache import AsyncTTLCache, TTLCache; assert TTLCache and AsyncTTLCache"
```

이 package는 Python standard library 밖의 production dependency를 갖지 않습니다. thin `bluetape` meta distribution은 `cache`, `dev`, `all` extra를 통해서만 전달하며, default meta install은 core-only이고 root `bluetape` import surface를 만들지 않습니다.

## Synchronous cache

operation에서 entry TTL을 지정하지 않으면 `default_ttl`을 사용합니다. 누락되거나 만료된 key에 대해 `get()`은 `KeyError(key)`를 발생시킵니다. `None`은 정상적인 cached value이며 value는 복사하지 않고 identity로 반환합니다.

```pycon
>>> from bluetape.cache import TTLCache
>>> cache = TTLCache[str, object](default_ttl=30, max_size=100)
>>> order = {"order_id": 42}
>>> cache.set("tenant-blue:42", order, ttl=5)
>>> cache.get("tenant-blue:42") is order
True
>>> cache.set("none", None)
>>> cache.get("none") is None
True
>>> cache.invalidate("tenant-blue:42")
True
>>> cache.invalidate("tenant-blue:42")
False
>>> try:
...     cache.get("tenant-blue:42")
... except KeyError as error:
...     assert error.args == ("tenant-blue:42",)

```

miss에서 loader를 호출해야 한다면 `get_or_load()`를 사용합니다. 동일 key caller는 owner caller의 loader와 TTL을 공유하며, coalesced caller의 loader와 TTL은 무시합니다. 서로 다른 key는 `max_inflight` 범위에서 동시에 load할 수 있습니다.

```pycon
>>> calls = []
>>> def load_order(key: str) -> dict[str, str]:
...     calls.append(key)
...     return {"key": key}
>>> cache = TTLCache[str, dict[str, str]](
...     default_ttl=30,
...     max_size=100,
...     max_inflight=8,
... )
>>> loaded = cache.get_or_load("tenant-blue:42", load_order, ttl=5)
>>> cache.get_or_load("tenant-blue:42", load_order) is loaded
True
>>> calls
['tenant-blue:42']

```

## Async cache

`AsyncTTLCache`는 value, TTL, invalidation, loading semantics가 동일합니다. public operation은 async이며 `len()` 대신 `size()`를 사용하고, 하나의 instance는 처음 사용한 event loop에 바인딩됩니다.

```pycon
>>> import asyncio
>>> from bluetape.cache import AsyncTTLCache
>>> async def async_example() -> None:
...     cache = AsyncTTLCache[str, object](
...         default_ttl=30,
...         max_size=100,
...         max_inflight=8,
...     )
...     order = {"order_id": 42}
...     async def load_order(key: str) -> object:
...         assert key == "tenant-blue:42"
...         return order
...     loaded = await cache.get_or_load("tenant-blue:42", load_order, ttl=5)
...     assert loaded is order
...     assert await cache.get("tenant-blue:42") is order
...     await cache.set("none", None)
...     assert await cache.get("none") is None
...     assert await cache.invalidate("tenant-blue:42") is True
...     assert await cache.invalidate("tenant-blue:42") is False
...     try:
...         await cache.get("tenant-blue:42")
...     except KeyError as error:
...         assert error.args == ("tenant-blue:42",)
...     assert await cache.size() == 1
>>> asyncio.run(async_example())

```

한 waiter를 취소해도 다른 waiter가 남아 있는 동일 key load는 취소하지 않습니다. 마지막 waiter가 취소되면 cache는 loader cancellation을 요청하고 느린 cleanup을 기다리지 않은 채 해당 caller에 cancellation을 반환합니다. `CancelledError`를 억제하거나 지연하는 loader는 terminal state에 도달할 때까지 `max_inflight` slot을 소유합니다. cache 호출 바깥에 caller-owned deadline을 두고 loader가 cooperative cancellation을 지원하도록 합니다.

## Mutation과 load 소유권

- `set()`, `invalidate()`, `clear()`는 active loader generation을 supersede합니다. 기존 caller에게는 최종 결과를 반환하지만 stale cache state를 publish할 수는 없습니다. 이후 caller는 새 generation을 시작하거나 합류합니다.
- superseded loader와 cancellation-resistant loader는 terminal state까지 소유되며 `max_inflight`에 포함됩니다. 포화된 cache는 새 loader를 시작하지 않고 `CacheLoadLimitError`를 발생시킵니다.
- recursive same-cache, same-key loading은 deadlock 대신 `RecursiveLoadError`를 발생시킵니다.
- `clear()`는 entry를 제거하지만 lifetime counter를 초기화하지 않습니다.

Cache key에는 value를 바꿀 수 있는 모든 tenant, authorization, locale 또는 기타 context를 포함해야 합니다. cache는 caller context를 검사하지 않습니다. cached mutable object는 identity를 유지하므로 caller가 수정하면 shared cached object도 수정됩니다. 격리가 필요하면 application boundary에서 value를 복사하거나 freeze합니다.

## 통계와 모니터링

`stats()`는 immutable `CacheStats` snapshot을 반환합니다. `hits`, `misses`, `loads`, `load_failures`, `load_rejections`, `coalesced_waiters`, `evictions`, `expirations`, `invalidations`는 lifetime counter이며 `clear()` 이후에도 유지됩니다. `inflight_loads`, `abandoned_loads`, `superseded_loads`는 시점별 gauge입니다.

cache에는 callback 또는 listener API가 없습니다. monitoring code는 `stats()` snapshot을 polling하거나 application boundary에서 public cache operation을 감쌉니다.

## Error와 logging 경계

`KeyError(key)`와 원래 loader exception은 의도적으로 정제하지 않은 caller-visible surface입니다. tenant identifier, authorization context 또는 기타 민감한 caller data를 포함할 수 있습니다. application은 logging 또는 telemetry export 전에 key와 exception content를 redaction해야 합니다. loader failure는 현재 동일 key waiter와 공유하지만 cache에는 저장하지 않습니다.

## 의도적인 제한

이 package는 Redis 또는 distributed coordination, background expiry worker, byte-based sizing, callback/listener, value copying, process-wide cache management를 제공하지 않습니다. capacity는 entry-count 기준입니다. 새로운 public API이므로 migration alias나 compatibility shim이 없습니다. bounded cross-process load coordination이 필요하면 이 stdlib-only 경계를 바꾸지 않고 별도의 opt-in `bluetape-cache-redis` package를 조합할 수 있습니다.
