"""Asynchronous cache implementation."""

import asyncio
import time
from collections.abc import Callable, Hashable
from threading import Lock
from typing import Generic, TypeVar

from bluetape.cache._core import _positive_int, _require_callable, _ttl_ns

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class AsyncTTLCache(Generic[K, V]):  # noqa: UP046 - public generics intentionally use TypeVar
    """Bounded asyncio local cache."""

    def __init__(
        self,
        *,
        default_ttl: float,
        max_size: int,
        max_inflight: int | None = None,
        clock: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._default_ttl_ns = _ttl_ns(default_ttl, "default_ttl")
        self._max_size = _positive_int(max_size, "max_size")
        self._max_inflight = (
            self._max_size if max_inflight is None else _positive_int(max_inflight, "max_inflight")
        )
        self._clock = _require_callable(clock, "clock")
        self._loop_guard = Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock: asyncio.Lock | None = None
        self._active_flights: dict[K, object] = {}
        self._owned_flights: set[object] = set()
