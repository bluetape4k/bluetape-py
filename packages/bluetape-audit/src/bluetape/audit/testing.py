"""Deterministic helpers for caller-owned audit adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bluetape.audit._values import AuditEvent, AuditIdentity, AuditPayload

__all__ = [  # noqa: RUF022 - public order is part of the testing contract
    "make_audit_event",
    "assert_audit_event_preserved",
]


def _timestamp_key(
    value: datetime,
) -> tuple[int, int, int, int, int, int, int, timedelta, int]:
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


def _mismatch(category: str) -> None:
    raise AssertionError(f"audit event field was not preserved: {category}")


def make_audit_event(**overrides: object) -> AuditEvent:
    """Create a fresh deterministic event with optional named field overrides."""

    if any(
        key
        not in (
            "event_id",
            "action",
            "occurred_at",
            "subject",
            "payload",
            "actor",
            "correlation_id",
            "causation_id",
            "metadata",
        )
        for key in overrides
    ):
        raise TypeError("unknown audit event override")

    values: dict[str, object] = {
        "event_id": "evt-test-0001",
        "action": "test.action",
        "occurred_at": datetime(2026, 1, 1, tzinfo=UTC),
        "subject": AuditIdentity("test-subject", "subject-0001"),
        "payload": AuditPayload(b"{}", "application/json", "1"),
        "actor": AuditIdentity("test-actor", "actor-0001"),
        "correlation_id": "corr-test-0001",
        "causation_id": "cause-test-0001",
        "metadata": {"source": "bluetape.audit.testing"},
    }
    values.update(overrides)
    return AuditEvent(**values)  # type: ignore[arg-type]


def assert_audit_event_preserved(actual: AuditEvent, expected: AuditEvent) -> None:
    """Assert an adapter round trip preserved every audit event field."""

    if type(actual) is not AuditEvent:
        raise TypeError("actual must be an AuditEvent")
    if type(expected) is not AuditEvent:
        raise TypeError("expected must be an AuditEvent")
    if actual.event_id != expected.event_id:
        _mismatch("event_id")
    if actual.action != expected.action:
        _mismatch("action")
    if _timestamp_key(actual.occurred_at) != _timestamp_key(expected.occurred_at):
        _mismatch("occurred_at")
    if actual.subject.kind != expected.subject.kind:
        _mismatch("subject.kind")
    if actual.subject.value != expected.subject.value:
        _mismatch("subject.value")
    if (actual.actor is None) != (expected.actor is None):
        _mismatch("actor")
    if actual.actor is not None and expected.actor is not None:
        if actual.actor.kind != expected.actor.kind:
            _mismatch("actor.kind")
        if actual.actor.value != expected.actor.value:
            _mismatch("actor.value")
    if actual.correlation_id != expected.correlation_id:
        _mismatch("correlation_id")
    if actual.causation_id != expected.causation_id:
        _mismatch("causation_id")
    if actual.payload.content_type != expected.payload.content_type:
        _mismatch("payload.content_type")
    if actual.payload.schema_version != expected.payload.schema_version:
        _mismatch("payload.schema_version")
    if actual.payload.data != expected.payload.data:
        _mismatch("payload.data")
    if actual.metadata != expected.metadata:
        _mismatch("metadata")
