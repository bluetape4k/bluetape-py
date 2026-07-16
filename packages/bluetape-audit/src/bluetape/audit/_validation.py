"""Explicit equal-or-stricter policy validation for audit events."""

from __future__ import annotations

from bluetape.audit._errors import AuditLimitExceededError
from bluetape.audit._values import AuditEvent, AuditLimits


def _exceeded(field_category: str, limit_name: str) -> None:
    raise AuditLimitExceededError(field_category, limit_name)


def validate_audit_event(event: AuditEvent, limits: AuditLimits) -> AuditEvent:
    """Validate an immutable event against caller-selected bounded limits."""

    if type(event) is not AuditEvent:
        raise TypeError("event must be an AuditEvent")
    if type(limits) is not AuditLimits:
        raise TypeError("limits must be an AuditLimits")

    if len(event.event_id) > limits.max_event_id_chars:
        _exceeded("event_id", "max_event_id_chars")
    if len(event.action) > limits.max_action_chars:
        _exceeded("action", "max_action_chars")
    if len(event.subject.kind) > limits.max_identity_kind_chars:
        _exceeded("subject.kind", "max_identity_kind_chars")
    if len(event.subject.value) > limits.max_identity_value_chars:
        _exceeded("subject.value", "max_identity_value_chars")
    if event.actor is not None:
        if len(event.actor.kind) > limits.max_identity_kind_chars:
            _exceeded("actor.kind", "max_identity_kind_chars")
        if len(event.actor.value) > limits.max_identity_value_chars:
            _exceeded("actor.value", "max_identity_value_chars")
    if (
        event.correlation_id is not None
        and len(event.correlation_id) > limits.max_correlation_id_chars
    ):
        _exceeded("correlation_id", "max_correlation_id_chars")
    if event.causation_id is not None and len(event.causation_id) > limits.max_causation_id_chars:
        _exceeded("causation_id", "max_causation_id_chars")
    if len(event.payload.content_type) > limits.max_content_type_chars:
        _exceeded("payload.content_type", "max_content_type_chars")
    if len(event.payload.schema_version) > limits.max_schema_version_chars:
        _exceeded("payload.schema_version", "max_schema_version_chars")
    if len(event.payload.data) > limits.max_payload_bytes:
        _exceeded("payload.data", "max_payload_bytes")
    if len(event.metadata) > limits.max_metadata_entries:
        _exceeded("metadata", "max_metadata_entries")
    for key, value in event.metadata.items():
        if len(key) > limits.max_metadata_key_chars:
            _exceeded("metadata.key", "max_metadata_key_chars")
        if len(value) > limits.max_metadata_value_chars:
            _exceeded("metadata.value", "max_metadata_value_chars")

    return event
