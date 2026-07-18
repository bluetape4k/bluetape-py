"""Deterministic secret-safe Redis key derivation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from bluetape.leader import InvalidLockNameError

_MAX_LOCK_NAME_BYTES = 1_024
_MAX_PREFIX_BYTES = 64
_PREFIX_PATTERN = re.compile(r"[A-Za-z0-9._-]+", re.ASCII)


@dataclass(frozen=True, slots=True, repr=False)
class _RedisKeys:
    lease: str
    fence: str

    def __repr__(self) -> str:
        return "_RedisKeys(<redacted>)"


def _validated_prefix(prefix: str) -> str:
    if (
        type(prefix) is not str
        or not 1 <= len(prefix) <= _MAX_PREFIX_BYTES
        or _PREFIX_PATTERN.fullmatch(prefix) is None
    ):
        raise ValueError("Redis key prefix is invalid")
    return prefix


def _redis_keys(lock_name: str, prefix: str) -> _RedisKeys:
    safe_prefix = _validated_prefix(prefix)
    if type(lock_name) is not str or not lock_name.strip():
        raise InvalidLockNameError()
    encoded = lock_name.encode("utf-8")
    if len(encoded) > _MAX_LOCK_NAME_BYTES:
        raise InvalidLockNameError()
    digest = hashlib.sha256(encoded).hexdigest()
    hash_tag = f"{safe_prefix}:{{{digest}}}"
    return _RedisKeys(lease=f"{hash_tag}:lease", fence=f"{hash_tag}:fence")


__all__: list[str] = []
