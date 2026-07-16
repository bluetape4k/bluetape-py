"""Bounded value objects for storage-neutral audit contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import final

from bluetape.audit._errors import (
    InvalidAuditIdentityError,
    InvalidAuditLimitsError,
    InvalidAuditPayloadError,
)

_MAX_IDENTITY_KIND_CHARS = 64
_MAX_IDENTITY_VALUE_CHARS = 512
_MAX_CONTENT_TYPE_CHARS = 128
_MAX_SCHEMA_VERSION_CHARS = 64
_MAX_PAYLOAD_BYTES = 1_048_576

_LIMIT_CEILINGS = (
    ("max_event_id_chars", 128),
    ("max_action_chars", 128),
    ("max_identity_kind_chars", _MAX_IDENTITY_KIND_CHARS),
    ("max_identity_value_chars", _MAX_IDENTITY_VALUE_CHARS),
    ("max_correlation_id_chars", 128),
    ("max_causation_id_chars", 128),
    ("max_content_type_chars", _MAX_CONTENT_TYPE_CHARS),
    ("max_schema_version_chars", _MAX_SCHEMA_VERSION_CHARS),
    ("max_payload_bytes", _MAX_PAYLOAD_BYTES),
    ("max_metadata_entries", 64),
    ("max_metadata_key_chars", 128),
    ("max_metadata_value_chars", 2_048),
)


def _contains_control(value: str) -> bool:
    return any(ord(character) <= 0x1F or 0x7F <= ord(character) <= 0x9F for character in value)


def _require_string(
    value: object,
    *,
    maximum: int,
    type_message: str,
    error_type: type[InvalidAuditIdentityError] | type[InvalidAuditPayloadError],
    reject_control: bool = False,
) -> str:
    if type(value) is not str:
        raise TypeError(type_message)
    if len(value) > maximum:
        raise error_type()
    if not value or value.isspace():
        raise error_type()
    if reject_control and _contains_control(value):
        raise error_type()
    return value


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class AuditIdentity:
    """A bounded caller-owned identity namespace and value."""

    kind: str = field(repr=False)
    value: str = field(repr=False)

    def __init__(self, kind: str, value: str) -> None:
        checked_kind = _require_string(
            kind,
            maximum=_MAX_IDENTITY_KIND_CHARS,
            type_message="identity kind must be a string",
            error_type=InvalidAuditIdentityError,
        )
        checked_value = _require_string(
            value,
            maximum=_MAX_IDENTITY_VALUE_CHARS,
            type_message="identity value must be a string",
            error_type=InvalidAuditIdentityError,
        )
        object.__setattr__(self, "kind", checked_kind)
        object.__setattr__(self, "value", checked_value)

    def __repr__(self) -> str:
        return "AuditIdentity(<redacted>)"


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class AuditPayload:
    """Opaque bytes with bounded caller-declared format labels."""

    data: bytes = field(repr=False)
    content_type: str = field(repr=False)
    schema_version: str = field(repr=False)

    def __init__(self, data: bytes, content_type: str, schema_version: str) -> None:
        if type(data) is not bytes:
            raise TypeError("payload data must be bytes")
        if not data or len(data) > _MAX_PAYLOAD_BYTES:
            raise InvalidAuditPayloadError()
        checked_content_type = _require_string(
            content_type,
            maximum=_MAX_CONTENT_TYPE_CHARS,
            type_message="payload content type must be a string",
            error_type=InvalidAuditPayloadError,
            reject_control=True,
        )
        checked_schema_version = _require_string(
            schema_version,
            maximum=_MAX_SCHEMA_VERSION_CHARS,
            type_message="payload schema version must be a string",
            error_type=InvalidAuditPayloadError,
            reject_control=True,
        )
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "content_type", checked_content_type)
        object.__setattr__(self, "schema_version", checked_schema_version)

    def __repr__(self) -> str:
        return "AuditPayload(<redacted>)"


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class AuditLimits:
    """Equal-or-stricter validation limits bounded by package ceilings."""

    max_event_id_chars: int = 128
    max_action_chars: int = 128
    max_identity_kind_chars: int = _MAX_IDENTITY_KIND_CHARS
    max_identity_value_chars: int = _MAX_IDENTITY_VALUE_CHARS
    max_correlation_id_chars: int = 128
    max_causation_id_chars: int = 128
    max_content_type_chars: int = _MAX_CONTENT_TYPE_CHARS
    max_schema_version_chars: int = _MAX_SCHEMA_VERSION_CHARS
    max_payload_bytes: int = _MAX_PAYLOAD_BYTES
    max_metadata_entries: int = 64
    max_metadata_key_chars: int = 128
    max_metadata_value_chars: int = 2_048

    def __post_init__(self) -> None:
        for field_name, ceiling in _LIMIT_CEILINGS:
            value = getattr(self, field_name)
            if type(value) is not int or value <= 0 or value > ceiling:
                raise InvalidAuditLimitsError()
