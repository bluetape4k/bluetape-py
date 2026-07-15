# bluetape-cache

`bluetape-cache` provides stdlib-only, bounded local TTL loading caches for
synchronous and `asyncio` applications. Entries expire lazily, live entries are
bounded by LRU eviction, and concurrent same-key misses share one loader.

Redis provider and load coordination remain deliberately outside this package
and are delivered by the opt-in `bluetape-cache-redis` distribution. RESP3
near-cache invalidation remains the independent upstream-blocked issue #56.

## Install

After registry publication is enabled, install the focused distribution or the
explicit meta extra:

```bash
pip install bluetape-cache
pip install "bluetape[cache]"
```

Those registry commands describe the future install shape. From the current
source workspace, use the locked workspace environment and run the exact import
smoke below:

```bash
uv sync --all-packages --locked
uv run --package bluetape-cache python -c "from bluetape.cache import AsyncTTLCache, TTLCache; assert TTLCache and AsyncTTLCache"
```

The package has no production dependency outside the Python standard library.
The thin `bluetape` meta distribution forwards it only through the `cache`,
`dev`, and `all` extras; the default meta install remains core-only and creates
no root `bluetape` import surface.

## Synchronous cache

`default_ttl` applies when an operation does not supply an entry TTL. `get()`
raises `KeyError(key)` for a missing or expired key. `None` is a normal cached
value, and values are returned by identity rather than copied.

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

Use `get_or_load()` when a miss should call a loader. Same-key callers share
the owner caller's loader and TTL; a coalesced caller's loader and TTL are
ignored. Different keys may load concurrently, subject to `max_inflight`.

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

`AsyncTTLCache` has the same value, TTL, invalidation, and loading semantics.
Its public operations are async, `size()` replaces `len()`, and one instance
binds to the event loop that first uses it.

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

Cancelling one waiter does not cancel a same-key load that still has another
waiter. When the final waiter is cancelled, the cache requests loader
cancellation and returns cancellation to that caller without waiting for slow
cleanup. A loader that suppresses or delays `CancelledError` still owns its
`max_inflight` slot until it reaches a terminal state. Put caller-owned
deadlines around cache calls and make loaders cooperatively cancellable.

## Mutation and load ownership

- `set()`, `invalidate()`, and `clear()` supersede an active loader generation,
  so its eventual result is returned to its existing callers but cannot publish
  stale cache state. A later caller starts or joins the new generation.
- Superseded and cancellation-resistant loaders remain owned and count toward
  `max_inflight` until terminal. A saturated cache raises
  `CacheLoadLimitError` instead of starting another loader.
- Recursive same-cache, same-key loading raises `RecursiveLoadError` rather
  than deadlocking.
- `clear()` removes entries but does not reset lifetime counters.

Cache keys must include every tenant, authorization, locale, or other context
that can change a value. The cache does not inspect caller context. Cached
mutable objects retain identity, so callers that mutate them mutate the shared
cached object; copy or freeze values at the application boundary when isolation
is required.

## Statistics and monitoring

`stats()` returns an immutable `CacheStats` snapshot. `hits`, `misses`,
`loads`, `load_failures`, `load_rejections`, `coalesced_waiters`, `evictions`,
`expirations`, and `invalidations` are lifetime counters and survive `clear()`.
`inflight_loads`, `abandoned_loads`, and `superseded_loads` are point-in-time
gauges.

The cache has no callback or listener API. Monitoring code should poll
`stats()` snapshots or wrap public cache operations at the application
boundary.

## Error and logging boundary

`KeyError(key)` and original loader exceptions are intentionally unsanitized,
caller-visible surfaces. They may contain tenant identifiers, authorization
context, or other sensitive caller data. Applications must redact keys and
exception content before logging or exporting telemetry. Loader failures are
shared with current same-key waiters and are not cached.

## Deliberate limits

This package does not provide Redis or distributed coordination, background
expiry workers, byte-based sizing, callbacks/listeners, value copying, or
process-wide cache management. Capacity is entry-count based. This is a new
public API, so there is no migration alias or compatibility shim. Applications
that need bounded cross-process load coordination can compose the separate
opt-in `bluetape-cache-redis` package without changing this stdlib-only boundary.
