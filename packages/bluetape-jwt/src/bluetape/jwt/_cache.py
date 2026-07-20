"""Private bounded cache for fully verified JWT results."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Protocol

from bluetape.cache import TTLCache
from bluetape.jwt._claims import VerifiedToken
from bluetape.jwt._errors import JWTCacheError, JWTConfigurationError
from bluetape.jwt._profiles import ValidationProfile
from bluetape.jwt._repository import KeySnapshot

logger = logging.getLogger(__name__)

_LOG_MESSAGE = "jwt_cache_failure"
type _CacheKey = tuple[bytes, str, int]


@dataclass(frozen=True, slots=True)
class VerifiedTokenCacheOptions:
    """Finite TTL and capacity for opt-in verified-result caching."""

    default_ttl: timedelta
    max_size: int

    def __post_init__(self) -> None:
        if (
            type(self.default_ttl) is not timedelta
            or self.default_ttl <= timedelta(0)
            or type(self.max_size) is not int
            or self.max_size < 1
        ):
            raise JWTConfigurationError() from None


class _CacheBackend(Protocol):
    def get(self, key: _CacheKey) -> VerifiedToken: ...

    def set(
        self,
        key: _CacheKey,
        value: VerifiedToken,
        *,
        ttl: float | None = None,
    ) -> None: ...

    def clear(self) -> None: ...


type _CacheFactory = Callable[..., _CacheBackend]


class _VerifiedTokenCache:
    """Serialize epoch observation around one existing TTLCache instance."""

    __slots__ = ("_cache", "_default_ttl", "_lock", "_observed_epoch")

    def __init__(
        self,
        options: VerifiedTokenCacheOptions,
        *,
        cache_factory: _CacheFactory = TTLCache,
    ) -> None:
        if type(options) is not VerifiedTokenCacheOptions or not callable(cache_factory):
            raise JWTConfigurationError() from None
        default_ttl = options.default_ttl.total_seconds()
        try:
            cache = cache_factory(default_ttl=default_ttl, max_size=options.max_size)
        except Exception:
            raise JWTConfigurationError() from None
        if not all(callable(getattr(cache, name, None)) for name in ("get", "set", "clear")):
            raise JWTConfigurationError() from None
        self._cache = cache
        self._default_ttl = default_ttl
        self._lock = RLock()
        self._observed_epoch: int | None = None

    def get(
        self,
        token: str,
        profile: ValidationProfile,
        snapshot: KeySnapshot,
    ) -> VerifiedToken | None:
        key = self._key(token, profile, snapshot)
        with self._lock:
            self._observe_epoch(snapshot.epoch)
            try:
                value = self._cache.get(key)
            except KeyError:
                return None
            except Exception:
                self._raise_failure("get")
            if type(value) is not VerifiedToken:
                self._raise_failure("get")
            return value

    def set(
        self,
        token: str,
        profile: ValidationProfile,
        snapshot: KeySnapshot,
        value: VerifiedToken,
        *,
        now: datetime,
        live_epoch: int,
    ) -> None:
        key = self._key(token, profile, snapshot)
        with self._lock:
            self._observe_epoch(live_epoch)
            if live_epoch != snapshot.epoch:
                return
            ttl = self._default_ttl
            if value.expires_at is not None:
                try:
                    remaining = (value.expires_at - now).total_seconds()
                except Exception:
                    self._raise_failure("set")
                if remaining <= 0:
                    return
                ttl = min(ttl, remaining)
            try:
                self._cache.set(key, value, ttl=ttl)
            except Exception:
                self._raise_failure("set")

    def _observe_epoch(self, epoch: int) -> None:
        if self._observed_epoch is None:
            self._observed_epoch = epoch
            return
        if self._observed_epoch == epoch:
            return
        try:
            self._cache.clear()
        except Exception:
            self._raise_failure("clear")
        self._observed_epoch = epoch

    @staticmethod
    def _key(
        token: str,
        profile: ValidationProfile,
        snapshot: KeySnapshot,
    ) -> _CacheKey:
        return (
            hashlib.sha256(token.encode("utf-8")).digest(),
            profile.fingerprint,
            snapshot.epoch,
        )

    @staticmethod
    def _raise_failure(operation: str) -> None:
        logger.error(
            _LOG_MESSAGE,
            extra={
                "event": "jwt_cache_failure",
                "operation": operation,
                "outcome": "failure",
                "error_category": "cache",
            },
        )
        raise JWTCacheError() from None
