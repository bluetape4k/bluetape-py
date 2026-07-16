from __future__ import annotations

import inspect
from datetime import UTC, datetime

import bluetape.audit as audit
import pytest

validate_audit_event = getattr(audit, "validate_audit_event", None)


def make_event(**overrides: object) -> audit.AuditEvent:
    values: dict[str, object] = {
        "event_id": "evt-test-0001",
        "action": "test.action",
        "occurred_at": datetime(2026, 1, 1, tzinfo=UTC),
        "subject": audit.AuditIdentity("test-subject", "subject-0001"),
        "payload": audit.AuditPayload(b"{}", "application/json", "1"),
        "actor": audit.AuditIdentity("test-actor", "actor-0001"),
        "correlation_id": "corr-test-0001",
        "causation_id": "cause-test-0001",
        "metadata": {"source": "bluetape.audit.testing"},
    }
    values.update(overrides)
    return audit.AuditEvent(**values)  # type: ignore[arg-type]


def validation_case(name: str, size: int) -> tuple[audit.AuditEvent, audit.AuditLimits]:
    text = "가" * size
    match name:
        case "event_id":
            return make_event(event_id=text), audit.AuditLimits(max_event_id_chars=1)
        case "action":
            return make_event(action=text), audit.AuditLimits(max_action_chars=1)
        case "subject.kind":
            return make_event(
                subject=audit.AuditIdentity(text, "v"), actor=None
            ), audit.AuditLimits(max_identity_kind_chars=1)
        case "subject.value":
            return make_event(
                subject=audit.AuditIdentity("k", text), actor=None
            ), audit.AuditLimits(max_identity_value_chars=1)
        case "actor.kind":
            return make_event(
                subject=audit.AuditIdentity("k", "v"),
                actor=audit.AuditIdentity(text, "v"),
            ), audit.AuditLimits(max_identity_kind_chars=1)
        case "actor.value":
            return make_event(
                subject=audit.AuditIdentity("k", "v"),
                actor=audit.AuditIdentity("k", text),
            ), audit.AuditLimits(max_identity_value_chars=1)
        case "correlation_id":
            return make_event(correlation_id=text), audit.AuditLimits(max_correlation_id_chars=1)
        case "causation_id":
            return make_event(causation_id=text), audit.AuditLimits(max_causation_id_chars=1)
        case "payload.content_type":
            return make_event(payload=audit.AuditPayload(b"x", text, "1")), audit.AuditLimits(
                max_content_type_chars=1
            )
        case "payload.schema_version":
            return make_event(payload=audit.AuditPayload(b"x", "x", text)), audit.AuditLimits(
                max_schema_version_chars=1
            )
        case "payload.data":
            return make_event(payload=audit.AuditPayload(b"x" * size, "x", "1")), audit.AuditLimits(
                max_payload_bytes=1
            )
        case "metadata":
            metadata = {str(index): "v" for index in range(size)}
            return make_event(metadata=metadata), audit.AuditLimits(max_metadata_entries=1)
        case "metadata.key":
            return make_event(metadata={text: "v"}), audit.AuditLimits(max_metadata_key_chars=1)
        case "metadata.value":
            return make_event(metadata={"k": text}), audit.AuditLimits(max_metadata_value_chars=1)
        case _:
            raise AssertionError(name)


CASES = [
    ("event_id", "max_event_id_chars"),
    ("action", "max_action_chars"),
    ("subject.kind", "max_identity_kind_chars"),
    ("subject.value", "max_identity_value_chars"),
    ("actor.kind", "max_identity_kind_chars"),
    ("actor.value", "max_identity_value_chars"),
    ("correlation_id", "max_correlation_id_chars"),
    ("causation_id", "max_causation_id_chars"),
    ("payload.content_type", "max_content_type_chars"),
    ("payload.schema_version", "max_schema_version_chars"),
    ("payload.data", "max_payload_bytes"),
    ("metadata", "max_metadata_entries"),
    ("metadata.key", "max_metadata_key_chars"),
    ("metadata.value", "max_metadata_value_chars"),
]


def test_validator_is_not_implemented_before_task_four() -> None:
    assert validate_audit_event is not None, "validate_audit_event is not implemented"


@pytest.mark.skipif(validate_audit_event is None, reason="Task 4 validator is not implemented")
class TestAuditValidation:
    def test_validator_signature_is_exact(self) -> None:
        assert validate_audit_event is not None
        parameters = list(inspect.signature(validate_audit_event).parameters.values())
        assert [(item.name, item.kind, item.default) for item in parameters] == [
            ("event", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
            ("limits", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ]

    def test_validator_checks_event_before_limits(self) -> None:
        assert validate_audit_event is not None
        with pytest.raises(TypeError, match=r"^event must be an AuditEvent$"):
            validate_audit_event(object(), object())
        with pytest.raises(TypeError, match=r"^limits must be an AuditLimits$"):
            validate_audit_event(make_event(), object())

        class EventSubclass(audit.AuditEvent):
            pass

        class LimitsSubclass(audit.AuditLimits):
            pass

        event = make_event()
        subclass_event = EventSubclass(
            event.event_id,
            event.action,
            event.occurred_at,
            event.subject,
            event.payload,
        )
        with pytest.raises(TypeError, match=r"^event must be an AuditEvent$"):
            validate_audit_event(subclass_event, audit.AuditLimits())
        with pytest.raises(TypeError, match=r"^limits must be an AuditLimits$"):
            validate_audit_event(event, LimitsSubclass())

    def test_success_returns_the_same_event(self) -> None:
        assert validate_audit_event is not None
        event = make_event()
        assert validate_audit_event(event, audit.AuditLimits()) is event

    @pytest.mark.parametrize(("field_category", "limit_name"), CASES)
    def test_every_limit_accepts_boundary_and_rejects_first_excess(
        self, field_category: str, limit_name: str
    ) -> None:
        assert validate_audit_event is not None
        boundary_event, boundary_limits = validation_case(field_category, 1)
        assert validate_audit_event(boundary_event, boundary_limits) is boundary_event

        excess_event, excess_limits = validation_case(field_category, 2)
        with pytest.raises(audit.AuditLimitExceededError) as captured:
            validate_audit_event(excess_event, excess_limits)
        error = captured.value
        assert error.field_category == field_category
        assert error.limit_name == limit_name
        assert error.args == ("audit value exceeds configured limit",)
        assert str(error) == "audit value exceeds configured limit"
        assert "가가" not in str(error)
        assert "가가" not in repr(error)
        assert "가가" not in repr(error.args)
        assert set(vars(error)) <= {"field_category", "limit_name"}

    def test_multi_violation_uses_total_blueprint_order(self) -> None:
        assert validate_audit_event is not None
        event = make_event(
            event_id="11",
            action="22",
            subject=audit.AuditIdentity("33", "44"),
            actor=audit.AuditIdentity("55", "66"),
            correlation_id="77",
            causation_id="88",
            payload=audit.AuditPayload(b"99", "aa", "bb"),
            metadata={"cc": "dd", "ee": "ff"},
        )
        limits = audit.AuditLimits(
            max_event_id_chars=1,
            max_action_chars=1,
            max_identity_kind_chars=1,
            max_identity_value_chars=1,
            max_correlation_id_chars=1,
            max_causation_id_chars=1,
            max_content_type_chars=1,
            max_schema_version_chars=1,
            max_payload_bytes=1,
            max_metadata_entries=1,
            max_metadata_key_chars=1,
            max_metadata_value_chars=1,
        )
        with pytest.raises(audit.AuditLimitExceededError) as captured:
            validate_audit_event(event, limits)
        assert (captured.value.field_category, captured.value.limit_name) == (
            "event_id",
            "max_event_id_chars",
        )

    def test_actor_absence_skips_actor_checks(self) -> None:
        assert validate_audit_event is not None
        event = make_event(actor=None)
        limits = audit.AuditLimits(
            max_identity_kind_chars=1,
            max_identity_value_chars=1,
        )
        with pytest.raises(audit.AuditLimitExceededError) as captured:
            validate_audit_event(event, limits)
        assert captured.value.field_category == "subject.kind"

        short_subject = make_event(subject=audit.AuditIdentity("k", "v"), actor=None)
        assert validate_audit_event(short_subject, limits) is short_subject

    def test_metadata_uses_insertion_order_and_key_before_value(self) -> None:
        assert validate_audit_event is not None
        limits = audit.AuditLimits(max_metadata_key_chars=1, max_metadata_value_chars=1)

        first_value_fails = make_event(metadata={"a": "11", "bb": "2"})
        with pytest.raises(audit.AuditLimitExceededError) as captured:
            validate_audit_event(first_value_fails, limits)
        assert (captured.value.field_category, captured.value.limit_name) == (
            "metadata.value",
            "max_metadata_value_chars",
        )

        first_key_fails = make_event(metadata={"aa": "11"})
        with pytest.raises(audit.AuditLimitExceededError) as captured:
            validate_audit_event(first_key_fails, limits)
        assert (captured.value.field_category, captured.value.limit_name) == (
            "metadata.key",
            "max_metadata_key_chars",
        )

    def test_optional_identifiers_absent_are_skipped(self) -> None:
        assert validate_audit_event is not None
        event = make_event(
            subject=audit.AuditIdentity("k", "v"),
            actor=None,
            correlation_id=None,
            causation_id=None,
            payload=audit.AuditPayload(b"x", "x", "1"),
            metadata={},
        )
        limits = audit.AuditLimits(
            max_event_id_chars=128,
            max_action_chars=128,
            max_identity_kind_chars=1,
            max_identity_value_chars=1,
            max_correlation_id_chars=1,
            max_causation_id_chars=1,
            max_content_type_chars=1,
            max_schema_version_chars=1,
            max_payload_bytes=1,
            max_metadata_entries=1,
            max_metadata_key_chars=1,
            max_metadata_value_chars=1,
        )
        assert validate_audit_event(event, limits) is event

    def test_payload_limit_error_is_safe_and_actionable(self) -> None:
        assert validate_audit_event is not None
        event = make_event(payload=audit.AuditPayload(b"12", "application/json", "1"))
        with pytest.raises(audit.AuditLimitExceededError) as captured:
            validate_audit_event(event, audit.AuditLimits(max_payload_bytes=1))
        assert captured.value.field_category == "payload.data"
        assert captured.value.limit_name == "max_payload_bytes"
        assert captured.value.args == ("audit value exceeds configured limit",)
