from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo

import bluetape.audit as audit
import bluetape.audit._values as values
import pytest

AuditEvent = getattr(audit, "AuditEvent", None)


class StringSubclass(str):
    pass


class DictSubclass(dict[str, str]):
    pass


class CustomTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(0)

    def dst(self, dt: datetime | None) -> timedelta:
        return timedelta(0)


class SecretValue:
    def __repr__(self) -> str:
        return "SECRET-EVENT-MARKER"


def make_event(**overrides: object) -> Any:
    assert AuditEvent is not None
    arguments: dict[str, object] = {
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
    arguments.update(overrides)
    return AuditEvent(**arguments)


def assert_value_safe_error(call: Any, error_type: type[Exception], marker: object) -> None:
    with pytest.raises(error_type) as captured:
        call()
    error = captured.value
    assert error.args == ("audit event is invalid",)
    assert str(error) == "audit event is invalid"
    assert "SECRET-EVENT-MARKER" not in str(error)
    assert "SECRET-EVENT-MARKER" not in repr(error)
    assert repr(marker) not in str(error)


def test_audit_event_is_not_implemented_before_task_three() -> None:
    assert AuditEvent is not None, "AuditEvent is not implemented"


@pytest.mark.skipif(AuditEvent is None, reason="Task 3 production surface is not implemented")
class TestAuditEvent:
    def test_public_shape_is_exact(self) -> None:
        assert AuditEvent is not None
        empty = inspect.Parameter.empty
        positional = inspect.Parameter.POSITIONAL_OR_KEYWORD
        keyword_only = inspect.Parameter.KEYWORD_ONLY
        parameters = list(inspect.signature(AuditEvent).parameters.values())
        assert [
            (parameter.name, parameter.kind, parameter.default) for parameter in parameters
        ] == [
            ("event_id", positional, empty),
            ("action", positional, empty),
            ("occurred_at", positional, empty),
            ("subject", positional, empty),
            ("payload", positional, empty),
            ("actor", keyword_only, None),
            ("correlation_id", keyword_only, None),
            ("causation_id", keyword_only, None),
            ("metadata", keyword_only, None),
        ]
        assert AuditEvent.__final__ is True
        assert AuditEvent.__slots__ == (
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
        assert [field.name for field in dataclasses.fields(AuditEvent)] == list(
            AuditEvent.__slots__
        )
        assert all(not field.repr for field in dataclasses.fields(AuditEvent))
        params = AuditEvent.__dataclass_params__
        assert (
            params.init,
            params.repr,
            params.eq,
            params.order,
            params.unsafe_hash,
            params.frozen,
            params.kw_only,
            params.slots,
        ) == (False, False, False, False, False, True, False, True)
        assert AuditEvent.__hash__ is None

    def test_valid_event_preserves_exact_values_and_redacts_repr(self) -> None:
        occurred_at = datetime(
            2026, 11, 1, 1, 30, 45, 123456, tzinfo=ZoneInfo("America/New_York"), fold=1
        )
        subject = audit.AuditIdentity(" subject-kind ", " subject-value ")
        payload = audit.AuditPayload(b"SECRET-EVENT-MARKER", "application/json", "1")
        actor = audit.AuditIdentity(" actor-kind ", " actor-value ")
        metadata = {" secret-key ": " SECRET-EVENT-MARKER "}

        event = make_event(
            event_id=" evt-secret ",
            action=" action-secret ",
            occurred_at=occurred_at,
            subject=subject,
            payload=payload,
            actor=actor,
            correlation_id=" corr-secret ",
            causation_id=" cause-secret ",
            metadata=metadata,
        )

        assert event.event_id == " evt-secret "
        assert event.action == " action-secret "
        assert event.occurred_at is occurred_at
        assert event.subject is subject
        assert event.payload is payload
        assert event.actor is actor
        assert event.correlation_id == " corr-secret "
        assert event.causation_id == " cause-secret "
        assert dict(event.metadata) == metadata
        assert type(event.metadata) is MappingProxyType
        assert repr(event) == "AuditEvent(<redacted>)"
        assert "SECRET-EVENT-MARKER" not in repr(event)

    def test_event_is_frozen_slotted_unhashable_and_replace_is_unsupported(self) -> None:
        event = make_event()
        assert not hasattr(event, "__dict__")
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.event_id = "changed"
        with pytest.raises(TypeError):
            hash(event)
        with pytest.raises(TypeError):
            dataclasses.replace(event, action="changed")

    @pytest.mark.parametrize(
        ("field", "invalid"),
        [
            ("event_id", SecretValue()),
            ("action", SecretValue()),
            ("occurred_at", SecretValue()),
            ("subject", SecretValue()),
            ("payload", SecretValue()),
            ("actor", SecretValue()),
            ("correlation_id", SecretValue()),
            ("causation_id", SecretValue()),
            ("metadata", SecretValue()),
        ],
    )
    def test_wrong_event_field_types_are_value_safe(self, field: str, invalid: object) -> None:
        with pytest.raises(TypeError) as captured:
            make_event(**{field: invalid})
        assert "SECRET-EVENT-MARKER" not in str(captured.value)
        assert "SECRET-EVENT-MARKER" not in repr(captured.value)
        assert "SECRET-EVENT-MARKER" not in repr(captured.value.args)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("event_id", ""),
            ("event_id", " \t"),
            ("action", ""),
            ("action", " \n"),
            ("correlation_id", ""),
            ("correlation_id", "  "),
            ("causation_id", ""),
            ("causation_id", "\t"),
        ],
    )
    def test_named_strings_reject_blank_values(self, field: str, value: str) -> None:
        assert_value_safe_error(
            lambda: make_event(**{field: value}), audit.InvalidAuditEventError, value
        )

    @pytest.mark.parametrize(
        ("field", "maximum"),
        [
            ("event_id", 128),
            ("action", 128),
            ("correlation_id", 128),
            ("causation_id", 128),
        ],
    )
    def test_named_strings_accept_ceiling_and_reject_first_invalid_value(
        self, field: str, maximum: int
    ) -> None:
        accepted = "x" * maximum
        assert getattr(make_event(**{field: accepted}), field) == accepted
        rejected = "x" * (maximum + 1)
        assert_value_safe_error(
            lambda: make_event(**{field: rejected}),
            audit.InvalidAuditEventError,
            rejected,
        )

    def test_validation_order_is_declaration_order(self) -> None:
        with pytest.raises(TypeError, match="event id"):
            make_event(event_id=SecretValue(), action=SecretValue())
        with pytest.raises(TypeError, match="action"):
            make_event(action=SecretValue(), occurred_at=SecretValue())
        with pytest.raises(TypeError, match="occurrence time"):
            make_event(occurred_at=SecretValue(), subject=SecretValue())

    def test_exact_nested_types_and_optional_none_are_required(self) -> None:
        event = make_event(actor=None, correlation_id=None, causation_id=None, metadata=None)
        assert event.actor is None
        assert event.correlation_id is None
        assert event.causation_id is None
        assert dict(event.metadata) == {}

        class IdentitySubclass(audit.AuditIdentity):
            pass

        class PayloadSubclass(audit.AuditPayload):
            pass

        with pytest.raises(TypeError):
            make_event(subject=IdentitySubclass("kind", "value"))
        with pytest.raises(TypeError):
            make_event(payload=PayloadSubclass(b"x", "text/plain", "1"))

    @pytest.mark.parametrize(
        "occurred_at",
        [
            datetime(2026, 1, 1),
            datetime(2026, 1, 1, tzinfo=CustomTimezone()),
        ],
    )
    def test_occurrence_time_rejects_naive_and_custom_timezones(
        self, occurred_at: datetime
    ) -> None:
        assert_value_safe_error(
            lambda: make_event(occurred_at=occurred_at),
            audit.InvalidAuditEventError,
            occurred_at,
        )

    def test_occurrence_time_requires_exact_datetime(self) -> None:
        class DatetimeSubclass(datetime):
            pass

        with pytest.raises(TypeError, match="occurrence time"):
            make_event(occurred_at=DatetimeSubclass(2026, 1, 1, tzinfo=UTC))

    def test_utcoffset_is_evaluated_once_and_failures_are_value_safe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_datetime = datetime

        class CountingDatetime(datetime):
            calls = 0
            failure: Exception | None = None

            def utcoffset(self) -> timedelta | None:
                type(self).calls += 1
                if type(self).failure is not None:
                    raise type(self).failure
                return super().utcoffset()

        monkeypatch.setattr(values, "datetime", CountingDatetime)
        valid = CountingDatetime(2026, 1, 1, tzinfo=UTC)
        event = make_event(occurred_at=valid)
        assert event.occurred_at is valid
        assert CountingDatetime.calls == 1

        CountingDatetime.calls = 0
        CountingDatetime.failure = RuntimeError("SECRET-EVENT-MARKER")
        failing = CountingDatetime(2026, 1, 1, tzinfo=UTC)
        assert_value_safe_error(
            lambda: make_event(occurred_at=failing),
            audit.InvalidAuditEventError,
            failing,
        )
        assert CountingDatetime.calls == 1
        assert datetime is real_datetime

    def test_timestamp_equality_preserves_wall_offset_and_fold(self) -> None:
        zone = ZoneInfo("America/New_York")
        first = make_event(occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0))
        second = make_event(occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1))
        same = make_event(occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0))
        assert first != second
        assert first == same
        assert first != object()

    @pytest.mark.parametrize(
        ("field", "different"),
        [
            ("event_id", "evt-test-0002"),
            ("action", "test.other-action"),
            ("occurred_at", datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)),
            ("subject", audit.AuditIdentity("test-subject", "subject-0002")),
            ("payload", audit.AuditPayload(b'{"different":true}', "application/json", "1")),
            ("actor", None),
            ("correlation_id", "corr-test-0002"),
            ("causation_id", "cause-test-0002"),
            ("metadata", {"source": "different"}),
        ],
    )
    def test_structural_equality_compares_every_stored_field(
        self, field: str, different: object
    ) -> None:
        assert make_event() != make_event(**{field: different})

    def test_metadata_is_a_private_read_only_snapshot(self) -> None:
        source = {"source": "orders-api"}
        event = make_event(metadata=source)
        source["source"] = "changed"
        assert dict(event.metadata) == {"source": "orders-api"}
        with pytest.raises(TypeError):
            event.metadata["new"] = "value"

    def test_real_metadata_copy_seam_returns_a_distinct_exact_dict(self) -> None:
        source = {"source": "orders-api"}
        copied = values._copy_metadata(source)
        assert type(copied) is dict
        assert copied == source
        assert copied is not source

    @pytest.mark.parametrize("metadata", [DictSubclass(source="x"), MappingProxyType({"x": "y"})])
    def test_metadata_input_requires_exact_dict(self, metadata: Mapping[str, str]) -> None:
        with pytest.raises(TypeError, match="metadata"):
            make_event(metadata=metadata)

    def test_metadata_rechecks_private_length_before_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        private = {str(index): "value" for index in range(65)}
        private[SecretValue()] = SecretValue()  # type: ignore[index]
        monkeypatch.setattr(values, "_copy_metadata", lambda source: private)
        assert_value_safe_error(
            lambda: make_event(metadata={"source": "valid"}),
            audit.InvalidAuditEventError,
            private,
        )

    def test_metadata_validates_only_private_copy_and_publishes_last(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = {"source": "valid"}
        private: dict[object, object] = {SecretValue(): SecretValue()}
        monkeypatch.setattr(values, "_copy_metadata", lambda value: private)
        with pytest.raises(TypeError) as captured:
            make_event(metadata=source)
        assert "SECRET-EVENT-MARKER" not in str(captured.value)
        assert source == {"source": "valid"}

    def test_metadata_accepts_exact_maximum_and_rejects_first_excess_entry(self) -> None:
        maximum = {f"key-{index}": "value" for index in range(64)}
        assert dict(make_event(metadata=maximum).metadata) == maximum
        excess = {f"key-{index}": "value" for index in range(65)}
        assert_value_safe_error(
            lambda: make_event(metadata=excess), audit.InvalidAuditEventError, excess
        )

    @pytest.mark.parametrize(
        ("metadata", "error_type"),
        [
            ({SecretValue(): "value"}, TypeError),
            ({"key": SecretValue()}, TypeError),
            ({"": "value"}, audit.InvalidAuditEventError),
            ({"   ": "value"}, audit.InvalidAuditEventError),
            ({"k" * 129: "value"}, audit.InvalidAuditEventError),
            ({"key": "v" * 2049}, audit.InvalidAuditEventError),
        ],
    )
    def test_metadata_invalid_entries_are_value_safe(
        self, metadata: dict[object, object], error_type: type[Exception]
    ) -> None:
        with pytest.raises(error_type) as captured:
            make_event(metadata=metadata)
        assert "SECRET-EVENT-MARKER" not in str(captured.value)
        assert "SECRET-EVENT-MARKER" not in repr(captured.value)

    def test_metadata_preserves_allowed_empty_whitespace_and_controls(self) -> None:
        metadata = {
            " leading-and-trailing ": "",
            "embedded\x00key": "   ",
            "del\x7fkey": "value\x7f",
            "c1\x85key": "value\x85",
        }
        assert dict(make_event(metadata=metadata).metadata) == metadata

    def test_metadata_key_and_value_exact_ceilings(self) -> None:
        accepted = {"k" * 128: "v" * 2048}
        assert dict(make_event(metadata=accepted).metadata) == accepted

    def test_metadata_equality_is_order_insensitive(self) -> None:
        first = make_event(metadata={"a": "1", "b": "2"})
        second = make_event(metadata={"b": "2", "a": "1"})
        different = make_event(metadata={"a": "1", "b": "3"})
        assert first == second
        assert first != different

    def test_every_nested_caller_value_is_absent_from_event_repr(self) -> None:
        event = make_event(
            event_id="SECRET-EVENT-MARKER",
            action="SECRET-EVENT-MARKER",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=9))),
            subject=audit.AuditIdentity("SECRET-EVENT-MARKER", "SECRET-EVENT-MARKER"),
            payload=audit.AuditPayload(
                b"SECRET-EVENT-MARKER", "SECRET-EVENT-MARKER", "SECRET-EVENT-MARKER"
            ),
            actor=audit.AuditIdentity("SECRET-EVENT-MARKER", "SECRET-EVENT-MARKER"),
            correlation_id="SECRET-EVENT-MARKER",
            causation_id="SECRET-EVENT-MARKER",
            metadata={"SECRET-EVENT-MARKER": "SECRET-EVENT-MARKER"},
        )
        assert repr(event) == "AuditEvent(<redacted>)"
        assert "SECRET-EVENT-MARKER" not in repr(event)
