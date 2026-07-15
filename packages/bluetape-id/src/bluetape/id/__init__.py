"""Stdlib-only UUID and ULID values."""

from uuid import UUID as _UUID

from ._errors import IDError, IDOverflowError, InvalidIDError
from ._ulid import MonotonicULIDGenerator, ULIDGenerator, parse_ulid, ulid_timestamp_ms
from ._uuid import UUID7Generator, uuid4, uuid7_timestamp_ms

_UUID7_GENERATOR = UUID7Generator()
_ULID_GENERATOR = ULIDGenerator()


def uuid7() -> _UUID:
    return _UUID7_GENERATOR.new()


def ulid() -> str:
    return _ULID_GENERATOR.new()


__all__ = [  # noqa: RUF022 - public order is part of the package contract
    "IDError",
    "InvalidIDError",
    "IDOverflowError",
    "UUID7Generator",
    "ULIDGenerator",
    "MonotonicULIDGenerator",
    "uuid4",
    "uuid7",
    "uuid7_timestamp_ms",
    "ulid",
    "parse_ulid",
    "ulid_timestamp_ms",
]
