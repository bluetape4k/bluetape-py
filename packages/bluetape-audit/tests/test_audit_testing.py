from __future__ import annotations

import importlib
import importlib.util
import inspect
from datetime import UTC, datetime
from types import ModuleType
from zoneinfo import ZoneInfo

import bluetape.audit as audit
import pytest

TESTING_SPEC = importlib.util.find_spec("bluetape.audit.testing")


def _testing_module() -> ModuleType:
    return importlib.import_module("bluetape.audit.testing")


def expected_event(**overrides: object) -> audit.AuditEvent:
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


def test_testing_module_is_not_implemented_before_task_five() -> None:
    assert TESTING_SPEC is not None, "bluetape.audit.testing is not implemented"


@pytest.mark.skipif(TESTING_SPEC is None, reason="Task 5 testing helpers are not implemented")
class TestAuditTesting:
    def test_testing_exports_and_signatures_are_exact(self) -> None:
        testing = _testing_module()
        assert testing.__all__ == ["make_audit_event", "assert_audit_event_preserved"]
        make_parameters = list(inspect.signature(testing.make_audit_event).parameters.values())
        assert [(item.name, item.kind, item.default) for item in make_parameters] == [
            ("overrides", inspect.Parameter.VAR_KEYWORD, inspect.Parameter.empty)
        ]
        assert [
            (item.name, item.kind, item.default)
            for item in inspect.signature(testing.assert_audit_event_preserved).parameters.values()
        ] == [
            ("actual", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
            ("expected", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ]

    def test_factory_has_complete_literal_defaults(self) -> None:
        event = _testing_module().make_audit_event()
        assert event == expected_event()
        assert event.event_id == "evt-test-0001"
        assert event.action == "test.action"
        assert event.occurred_at == datetime(2026, 1, 1, tzinfo=UTC)
        assert event.subject == audit.AuditIdentity("test-subject", "subject-0001")
        assert event.payload == audit.AuditPayload(b"{}", "application/json", "1")
        assert event.actor == audit.AuditIdentity("test-actor", "actor-0001")
        assert event.correlation_id == "corr-test-0001"
        assert event.causation_id == "cause-test-0001"
        assert dict(event.metadata) == {"source": "bluetape.audit.testing"}

    def test_factory_is_deterministic_without_shared_values(self) -> None:
        make_audit_event = _testing_module().make_audit_event
        first = make_audit_event()
        second = make_audit_event()
        assert first == second
        assert first is not second
        assert first.subject is not second.subject
        assert first.payload is not second.payload
        assert first.actor is not second.actor
        assert first.metadata is not second.metadata

    @pytest.mark.parametrize(
        ("field", "override"),
        [
            ("event_id", "evt-override"),
            ("action", "test.override"),
            ("occurred_at", datetime(2026, 2, 2, tzinfo=UTC)),
            ("subject", audit.AuditIdentity("subject", "override")),
            ("payload", audit.AuditPayload(b"override", "text/plain", "2")),
            ("actor", None),
            ("correlation_id", None),
            ("causation_id", None),
            ("metadata", {"override": "yes"}),
        ],
    )
    def test_factory_accepts_every_event_field_override(self, field: str, override: object) -> None:
        event = _testing_module().make_audit_event(**{field: override})
        assert getattr(event, field) == override

    def test_unknown_override_never_echoes_the_key(self) -> None:
        marker = "secret-override-key"
        with pytest.raises(TypeError) as captured:
            _testing_module().make_audit_event(**{marker: object()})
        assert str(captured.value) == "unknown audit event override"
        assert captured.value.args == ("unknown audit event override",)
        assert marker not in str(captured.value)
        assert marker not in repr(captured.value)

    def test_invalid_known_override_propagates_constructor_error(self) -> None:
        with pytest.raises(audit.InvalidAuditEventError) as captured:
            _testing_module().make_audit_event(action="")
        assert captured.value.args == ("audit event is invalid",)

    def test_comparator_requires_exact_event_types_in_order(self) -> None:
        compare = _testing_module().assert_audit_event_preserved
        event = expected_event()
        with pytest.raises(TypeError, match=r"^actual must be an AuditEvent$"):
            compare(object(), object())
        with pytest.raises(TypeError, match=r"^expected must be an AuditEvent$"):
            compare(event, object())

        class EventSubclass(audit.AuditEvent):
            pass

        subclass = EventSubclass(
            event.event_id,
            event.action,
            event.occurred_at,
            event.subject,
            event.payload,
        )
        with pytest.raises(TypeError, match=r"^actual must be an AuditEvent$"):
            compare(subclass, event)

    @pytest.mark.parametrize(
        ("category", "override"),
        [
            ("event_id", {"event_id": "different"}),
            ("action", {"action": "different"}),
            ("occurred_at", {"occurred_at": datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)}),
            ("subject.kind", {"subject": audit.AuditIdentity("different", "subject-0001")}),
            ("subject.value", {"subject": audit.AuditIdentity("test-subject", "different")}),
            ("actor", {"actor": None}),
            ("actor.kind", {"actor": audit.AuditIdentity("different", "actor-0001")}),
            ("actor.value", {"actor": audit.AuditIdentity("test-actor", "different")}),
            ("correlation_id", {"correlation_id": "different"}),
            ("causation_id", {"causation_id": "different"}),
            (
                "payload.content_type",
                {"payload": audit.AuditPayload(b"{}", "text/plain", "1")},
            ),
            (
                "payload.schema_version",
                {"payload": audit.AuditPayload(b"{}", "application/json", "2")},
            ),
            (
                "payload.data",
                {"payload": audit.AuditPayload(b'{"different":true}', "application/json", "1")},
            ),
            ("metadata", {"metadata": {"source": "different"}}),
        ],
    )
    def test_comparator_uses_every_closed_mismatch_category(
        self, category: str, override: dict[str, object]
    ) -> None:
        with pytest.raises(AssertionError) as captured:
            _testing_module().assert_audit_event_preserved(
                expected_event(**override), expected_event()
            )
        message = f"audit event field was not preserved: {category}"
        assert captured.value.args == (message,)
        assert str(captured.value) == message
        assert "different" not in str(captured.value)

    def test_comparator_uses_total_order_for_multiple_mismatches(self) -> None:
        actual = expected_event(event_id="different", action="different")
        with pytest.raises(AssertionError) as captured:
            _testing_module().assert_audit_event_preserved(actual, expected_event())
        assert captured.value.args == ("audit event field was not preserved: event_id",)

    def test_timestamp_comparison_uses_wall_offset_and_fold(self) -> None:
        zone = ZoneInfo("America/New_York")
        expected = expected_event(occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0))
        different_fold = expected_event(
            occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)
        )
        with pytest.raises(AssertionError, match="occurred_at"):
            _testing_module().assert_audit_event_preserved(different_fold, expected)

        same_instant_different_wall = expected_event(
            occurred_at=expected.occurred_at.astimezone(UTC)
        )
        with pytest.raises(AssertionError, match="occurred_at"):
            _testing_module().assert_audit_event_preserved(same_instant_different_wall, expected)

        utc_expected = expected_event(occurred_at=datetime(2026, 1, 1, tzinfo=UTC))
        zoneinfo_actual = expected_event(occurred_at=datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")))
        _testing_module().assert_audit_event_preserved(zoneinfo_actual, utc_expected)

    def test_metadata_comparison_is_order_insensitive(self) -> None:
        actual = expected_event(metadata={"b": "2", "a": "1"})
        expected = expected_event(metadata={"a": "1", "b": "2"})
        _testing_module().assert_audit_event_preserved(actual, expected)

    def test_helpers_do_not_create_storage_surfaces_or_retain_events(self) -> None:
        testing = _testing_module()
        forbidden = {"repository", "history", "buffer", "outbox", "events", "stored"}
        assert forbidden.isdisjoint(testing.__dict__)
        assert all(
            not isinstance(value, (dict, set, list))
            for name, value in testing.__dict__.items()
            if name not in {"__all__", "__builtins__"}
        )
        assert "make_audit_event" not in audit.__all__
        assert "assert_audit_event_preserved" not in audit.__all__
        assert not hasattr(audit, "make_audit_event")
        assert not hasattr(audit, "assert_audit_event_preserved")
        assert audit.__all__ == [
            "AuditError",
            "InvalidAuditIdentityError",
            "InvalidAuditPayloadError",
            "InvalidAuditEventError",
            "InvalidAuditLimitsError",
            "AuditLimitExceededError",
            "AuditIdentity",
            "AuditPayload",
            "AuditEvent",
            "AuditLimits",
            "validate_audit_event",
        ]
