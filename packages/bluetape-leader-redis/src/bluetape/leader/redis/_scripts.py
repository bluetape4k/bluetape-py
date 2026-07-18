"""Fixed Lua sources and bounded script dispatch helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol

from redis.exceptions import NoScriptError

from ._support import _is_canonical_fence, _is_owner_token, _LeaseRecord

_FENCE_VALIDATION = """local function valid_fence(fence)
  if not string.match(fence, '^[1-9][0-9]*$') then return false end
  local length = string.len(fence)
  return length < 19 or (length == 19 and fence <= '9223372036854775807')
end
"""


@dataclass(frozen=True, slots=True, repr=False)
class _Script:
    source: str
    sha1: str

    def __init__(self, source: str) -> None:
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "sha1", hashlib.sha1(source.encode("utf-8")).hexdigest())

    def __repr__(self) -> str:
        return "_Script(<fixed-source>)"


ACQUIRE_SCRIPT = _Script(
    _FENCE_VALIDATION
    + """local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type ~= 'none' then
  if lease_type ~= 'string' then return {'CORRUPT'} end
  local current = redis.call('GET', KEYS[1])
  local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
  if not owner or string.len(owner) ~= 32 or not valid_fence(fence) then
    return {'CORRUPT'}
  end
  if redis.call('PTTL', KEYS[1]) <= 0 then
    return {'CORRUPT'}
  end
  return {'CONTENDED'}
end
local fence_type = redis.call('TYPE', KEYS[2]).ok
if fence_type ~= 'none' then
  if fence_type ~= 'string' then return {'CORRUPT'} end
  local previous = redis.call('GET', KEYS[2])
  if not valid_fence(previous) then return {'CORRUPT'} end
  if previous == '9223372036854775807' then return {'CORRUPT'} end
end
redis.call('INCR', KEYS[2])
local fence = redis.call('GET', KEYS[2])
if not valid_fence(fence) then return {'CORRUPT'} end
local record = 'v1:' .. ARGV[1] .. ':' .. fence
redis.call('SET', KEYS[1], record, 'PX', ARGV[2])
return {'ACQUIRED', fence}"""
)

RENEW_SCRIPT = _Script(
    _FENCE_VALIDATION
    + """local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'NOT_HELD'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 or not valid_fence(fence) then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'NOT_HELD'} end
if current ~= ARGV[1] then return {'NOT_HELD'} end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return {'RENEWED'}"""
)

PROBE_SCRIPT = _Script(
    _FENCE_VALIDATION
    + """local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'NOT_HELD'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 or not valid_fence(fence) then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'NOT_HELD'} end
if current ~= ARGV[1] then return {'NOT_HELD'} end
return {'HELD'}"""
)

RECONCILE_SCRIPT = _Script(
    _FENCE_VALIDATION
    + """local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'ABSENT'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 or not valid_fence(fence) then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'ABSENT'} end
return {'PRESENT', current}"""
)

RELEASE_SCRIPT = _Script(
    _FENCE_VALIDATION
    + """local lease_type = redis.call('TYPE', KEYS[1]).ok
if lease_type == 'none' then return {'NOT_HELD'} end
if lease_type ~= 'string' then return {'CORRUPT'} end
local current = redis.call('GET', KEYS[1])
local owner, fence = string.match(current, '^v1:([%w_-]+):([1-9][0-9]*)$')
if not owner or string.len(owner) ~= 32 or not valid_fence(fence) then return {'CORRUPT'} end
local ttl = redis.call('PTTL', KEYS[1])
if ttl == -1 then return {'CORRUPT'} end
if ttl <= 0 then return {'NOT_HELD'} end
if current ~= ARGV[1] then return {'NOT_HELD'} end
if ARGV[2] == '0' then
  redis.call('DEL', KEYS[1])
  return {'DELETED'}
end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return {'MIN_TTL_APPLIED'}"""
)


class _SyncCommands(Protocol):
    def evalsha(self, sha1: str, numkeys: int, *values: bytes) -> Any: ...
    def eval(self, source: str, numkeys: int, *values: bytes) -> Any: ...


class _AsyncCommands(Protocol):
    def evalsha(self, sha1: str, numkeys: int, *values: bytes) -> Awaitable[Any]: ...
    def eval(self, source: str, numkeys: int, *values: bytes) -> Awaitable[Any]: ...


def _run_script(
    commands: _SyncCommands,
    script: _Script,
    keys: tuple[bytes, ...],
    args: tuple[bytes, ...],
) -> object:
    _validate_dispatch(script, keys, args)
    try:
        return commands.evalsha(script.sha1, len(keys), *keys, *args)
    except NoScriptError:
        return commands.eval(script.source, len(keys), *keys, *args)


async def _run_script_async(
    commands: _AsyncCommands,
    script: _Script,
    keys: tuple[bytes, ...],
    args: tuple[bytes, ...],
) -> object:
    _validate_dispatch(script, keys, args)
    try:
        return await commands.evalsha(script.sha1, len(keys), *keys, *args)
    except NoScriptError:
        return await commands.eval(script.source, len(keys), *keys, *args)


def _run_reconcile(commands: _SyncCommands, lease_key: bytes) -> object:
    _validate_bytes(lease_key)
    return commands.eval(RECONCILE_SCRIPT.source, 1, lease_key)


async def _run_reconcile_async(commands: _AsyncCommands, lease_key: bytes) -> object:
    _validate_bytes(lease_key)
    return await commands.eval(RECONCILE_SCRIPT.source, 1, lease_key)


def _validated_script_args(owner_token: str, ttl_ms: int) -> tuple[bytes, bytes]:
    if not _is_owner_token(owner_token):
        raise ValueError("Redis script argument is invalid")
    if type(ttl_ms) is not int or ttl_ms <= 0 or ttl_ms > 9_223_372_036_854_775_807:
        raise ValueError("Redis script argument is invalid")
    return owner_token.encode("ascii"), str(ttl_ms).encode("ascii")


def _parse_acquire_response(value: object) -> tuple[str, int | None]:
    parts = _response_parts(value)
    if parts in ((b"CONTENDED",), (b"CORRUPT",)):
        return parts[0].decode("ascii"), None
    if len(parts) == 2 and parts[0] == b"ACQUIRED":
        fence = parts[1]
        if _canonical_positive_decimal(fence):
            return "ACQUIRED", int(fence)
    raise ValueError("invalid Redis script response")


def _parse_status_response(value: object, allowed: frozenset[str]) -> str:
    parts = _response_parts(value)
    if len(parts) != 1:
        raise ValueError("invalid Redis script response")
    try:
        status = parts[0].decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("invalid Redis script response") from None
    if status not in allowed:
        raise ValueError("invalid Redis script response")
    return status


def _parse_reconcile_response(value: object) -> tuple[str, _LeaseRecord | None]:
    parts = _response_parts(value)
    if parts in ((b"ABSENT",), (b"CORRUPT",)):
        return parts[0].decode("ascii"), None
    if len(parts) == 2 and parts[0] == b"PRESENT":
        try:
            return "PRESENT", _LeaseRecord.parse(parts[1])
        except ValueError:
            pass
    raise ValueError("invalid Redis script response")


def _response_parts(value: object) -> tuple[bytes, ...]:
    if type(value) not in (list, tuple):
        raise ValueError("invalid Redis script response")
    parts = tuple(value)
    if not parts or any(type(part) is not bytes for part in parts):
        raise ValueError("invalid Redis script response")
    return parts


def _canonical_positive_decimal(value: bytes) -> bool:
    if not value.isascii():
        return False
    return _is_canonical_fence(value.decode("ascii"))


def _validate_dispatch(script: _Script, keys: tuple[bytes, ...], args: tuple[bytes, ...]) -> None:
    if type(script) is not _Script or type(keys) is not tuple or type(args) is not tuple:
        raise TypeError("invalid Redis script dispatch")
    for value in (*keys, *args):
        _validate_bytes(value)
    if script is ACQUIRE_SCRIPT:
        if len(keys) != 2 or len(args) != 2 or not _valid_owner_bytes(args[0]):
            raise ValueError("Redis script argument is invalid")
        _validate_milliseconds(args[1], allow_zero=False)
    elif script in (RENEW_SCRIPT, PROBE_SCRIPT, RELEASE_SCRIPT):
        expected_args = 1 if script is PROBE_SCRIPT else 2
        if len(keys) != 1 or len(args) != expected_args:
            raise ValueError("Redis script argument is invalid")
        try:
            _LeaseRecord.parse(args[0])
        except ValueError:
            raise ValueError("Redis script argument is invalid") from None
        if script is not PROBE_SCRIPT:
            _validate_milliseconds(args[1], allow_zero=script is RELEASE_SCRIPT)
    else:
        raise TypeError("invalid Redis script dispatch")


def _valid_owner_bytes(value: bytes) -> bool:
    try:
        owner = value.decode("ascii")
    except UnicodeDecodeError:
        return False
    return _is_owner_token(owner)


def _validate_milliseconds(value: bytes, *, allow_zero: bool) -> None:
    if allow_zero and value == b"0":
        return
    if not _canonical_positive_decimal(value):
        raise ValueError("Redis script argument is invalid")


def _validate_bytes(value: object) -> None:
    if type(value) is not bytes or not value:
        raise TypeError("invalid Redis script dispatch")


__all__: list[str] = []
