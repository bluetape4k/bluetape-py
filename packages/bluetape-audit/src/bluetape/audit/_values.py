"""Bounded value objects for storage-neutral audit contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import ClassVar, final
from zoneinfo import ZoneInfo

from bluetape.audit._errors import (
    InvalidAuditEventError,
    InvalidAuditIdentityError,
    InvalidAuditLimitsError,
    InvalidAuditPayloadError,
)

_MAX_EVENT_ID_CHARS = 128
_MAX_ACTION_CHARS = 128
_MAX_IDENTITY_KIND_CHARS = 64
_MAX_IDENTITY_VALUE_CHARS = 512
_MAX_CORRELATION_ID_CHARS = 128
_MAX_CAUSATION_ID_CHARS = 128
_MAX_CONTENT_TYPE_CHARS = 128
_MAX_SCHEMA_VERSION_CHARS = 64
_MAX_PAYLOAD_BYTES = 1_048_576
_MAX_METADATA_ENTRIES = 64
_MAX_METADATA_KEY_CHARS = 128
_MAX_METADATA_VALUE_CHARS = 2_048

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
    error_type: (
        type[InvalidAuditIdentityError]
        | type[InvalidAuditPayloadError]
        | type[InvalidAuditEventError]
    ),
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


def _require_optional_string(
    value: object,
    *,
    maximum: int,
    type_message: str,
) -> str | None:
    if value is None:
        return None
    return _require_string(
        value,
        maximum=maximum,
        type_message=type_message,
        error_type=InvalidAuditEventError,
    )


def _copy_metadata(source: dict[str, str]) -> dict[str, str]:
    return dict.copy(source)


def _datetime_key(value: datetime) -> tuple[int, int, int, int, int, int, int, timedelta, int]:
    offset = value.utcoffset()
    assert offset is not None
    return (
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        offset,
        value.fold,
    )


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
@dataclass(frozen=True, slots=True, init=False, repr=False, eq=False)
class AuditEvent:
    """An immutable, storage-neutral snapshot of one caller-owned audit fact."""

    event_id: str = field(repr=False)
    action: str = field(repr=False)
    occurred_at: datetime = field(repr=False)
    subject: AuditIdentity = field(repr=False)
    payload: AuditPayload = field(repr=False)
    actor: AuditIdentity | None = field(default=None, repr=False)
    correlation_id: str | None = field(default=None, repr=False)
    causation_id: str | None = field(default=None, repr=False)
    metadata: Mapping[str, str] = field(default_factory=dict, repr=False)

    __hash__: ClassVar[None] = None

    def __init__(
        self,
        event_id: str,
        action: str,
        occurred_at: datetime,
        subject: AuditIdentity,
        payload: AuditPayload,
        *,
        actor: AuditIdentity | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        checked_event_id = _require_string(
            event_id,
            maximum=_MAX_EVENT_ID_CHARS,
            type_message="event id must be a string",
            error_type=InvalidAuditEventError,
        )
        checked_action = _require_string(
            action,
            maximum=_MAX_ACTION_CHARS,
            type_message="action must be a string",
            error_type=InvalidAuditEventError,
        )
        if type(occurred_at) is not datetime:
            raise TypeError("occurrence time must be a datetime")
        if type(occurred_at.tzinfo) is not timezone and type(occurred_at.tzinfo) is not ZoneInfo:
            raise InvalidAuditEventError()
        try:
            offset = occurred_at.utcoffset()
        except Exception:
            raise InvalidAuditEventError() from None
        if offset is None:
            raise InvalidAuditEventError()
        if type(subject) is not AuditIdentity:
            raise TypeError("subject must be an AuditIdentity")
        if type(payload) is not AuditPayload:
            raise TypeError("payload must be an AuditPayload")
        if actor is not None and type(actor) is not AuditIdentity:
            raise TypeError("actor must be an AuditIdentity or None")
        checked_correlation_id = _require_optional_string(
            correlation_id,
            maximum=_MAX_CORRELATION_ID_CHARS,
            type_message="correlation id must be a string or None",
        )
        checked_causation_id = _require_optional_string(
            causation_id,
            maximum=_MAX_CAUSATION_ID_CHARS,
            type_message="causation id must be a string or None",
        )
        if metadata is None:
            private_metadata: dict[str, str] = {}
        else:
            if type(metadata) is not dict:
                raise TypeError("metadata must be a dict or None")
            if len(metadata) > _MAX_METADATA_ENTRIES:
                raise InvalidAuditEventError()
            private_metadata = _copy_metadata(metadata)
            if type(private_metadata) is not dict:
                raise InvalidAuditEventError()
            if len(private_metadata) > _MAX_METADATA_ENTRIES:
                raise InvalidAuditEventError()
            for key, value in private_metadata.items():
                if type(key) is not str:
                    raise TypeError("metadata keys must be strings")
                if len(key) > _MAX_METADATA_KEY_CHARS or not key or key.isspace():
                    raise InvalidAuditEventError()
                if type(value) is not str:
                    raise TypeError("metadata values must be strings")
                if len(value) > _MAX_METADATA_VALUE_CHARS:
                    raise InvalidAuditEventError()

        object.__setattr__(self, "event_id", checked_event_id)
        object.__setattr__(self, "action", checked_action)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "correlation_id", checked_correlation_id)
        object.__setattr__(self, "causation_id", checked_causation_id)
        object.__setattr__(self, "metadata", MappingProxyType(private_metadata))

    def __eq__(self, other: object) -> bool:
        if type(other) is not AuditEvent:
            return False
        return (
            self.event_id == other.event_id
            and self.action == other.action
            and _datetime_key(self.occurred_at) == _datetime_key(other.occurred_at)
            and self.subject == other.subject
            and self.payload == other.payload
            and self.actor == other.actor
            and self.correlation_id == other.correlation_id
            and self.causation_id == other.causation_id
            and self.metadata == other.metadata
        )

    def __repr__(self) -> str:
        return "AuditEvent(<redacted>)"


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
