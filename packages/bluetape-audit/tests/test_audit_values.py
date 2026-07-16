from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from typing import Any

import bluetape.audit as audit
import pytest
from bluetape.audit import (
    InvalidAuditIdentityError,
    InvalidAuditLimitsError,
    InvalidAuditPayloadError,
)

HARD_LIMITS = {
    "max_event_id_chars": 128,
    "max_action_chars": 128,
    "max_identity_kind_chars": 64,
    "max_identity_value_chars": 512,
    "max_correlation_id_chars": 128,
    "max_causation_id_chars": 128,
    "max_content_type_chars": 128,
    "max_schema_version_chars": 64,
    "max_payload_bytes": 1_048_576,
    "max_metadata_entries": 64,
    "max_metadata_key_chars": 128,
    "max_metadata_value_chars": 2_048,
}


class StringSubclass(str):
    pass


class IntegerSubclass(int):
    pass


def _assert_signature(
    value_type: type[object],
    expected: list[tuple[str, inspect._ParameterKind, object]],
) -> None:
    parameters = list(inspect.signature(value_type).parameters.values())
    assert [
        (parameter.name, parameter.kind, parameter.default) for parameter in parameters
    ] == expected


def _assert_fixed_error(
    call: Callable[[], object], error_type: type[Exception], message: str, marker: object
) -> None:
    with pytest.raises(error_type) as captured:
        call()
    assert captured.value.args == (message,)
    assert str(captured.value) == message
    assert repr(marker) not in str(captured.value)
    assert repr(marker) not in repr(captured.value)


def test_value_types_have_exact_public_shape() -> None:
    empty = inspect.Parameter.empty
    positional = inspect.Parameter.POSITIONAL_OR_KEYWORD
    keyword_only = inspect.Parameter.KEYWORD_ONLY

    _assert_signature(
        audit.AuditIdentity, [("kind", positional, empty), ("value", positional, empty)]
    )
    _assert_signature(
        audit.AuditPayload,
        [
            ("data", positional, empty),
            ("content_type", positional, empty),
            ("schema_version", positional, empty),
        ],
    )
    _assert_signature(
        audit.AuditLimits,
        [(name, keyword_only, default) for name, default in HARD_LIMITS.items()],
    )

    assert audit.AuditIdentity.__final__ is True
    assert audit.AuditPayload.__final__ is True
    assert audit.AuditLimits.__final__ is True
    assert audit.AuditIdentity.__slots__ == ("kind", "value")
    assert audit.AuditPayload.__slots__ == ("data", "content_type", "schema_version")
    assert audit.AuditLimits.__slots__ == tuple(HARD_LIMITS)

    assert [field.name for field in dataclasses.fields(audit.AuditIdentity)] == ["kind", "value"]
    assert [field.name for field in dataclasses.fields(audit.AuditPayload)] == [
        "data",
        "content_type",
        "schema_version",
    ]
    assert [field.name for field in dataclasses.fields(audit.AuditLimits)] == list(HARD_LIMITS)
    assert all(not field.repr for field in dataclasses.fields(audit.AuditIdentity))
    assert all(not field.repr for field in dataclasses.fields(audit.AuditPayload))
    identity_params = audit.AuditIdentity.__dataclass_params__
    payload_params = audit.AuditPayload.__dataclass_params__
    limits_params = audit.AuditLimits.__dataclass_params__
    assert (
        identity_params.init,
        identity_params.repr,
        identity_params.eq,
        identity_params.order,
        identity_params.unsafe_hash,
        identity_params.frozen,
        identity_params.kw_only,
        identity_params.slots,
    ) == (
        False,
        False,
        True,
        False,
        False,
        True,
        False,
        True,
    )
    assert (
        payload_params.init,
        payload_params.repr,
        payload_params.eq,
        payload_params.order,
        payload_params.unsafe_hash,
        payload_params.frozen,
        payload_params.kw_only,
        payload_params.slots,
    ) == (
        False,
        False,
        True,
        False,
        False,
        True,
        False,
        True,
    )
    assert (
        limits_params.init,
        limits_params.repr,
        limits_params.eq,
        limits_params.order,
        limits_params.unsafe_hash,
        limits_params.frozen,
        limits_params.kw_only,
        limits_params.slots,
    ) == (
        True,
        True,
        True,
        False,
        False,
        True,
        True,
        True,
    )


def test_values_are_frozen_slotted_and_hashable() -> None:
    identity = audit.AuditIdentity("kind", "value")
    payload = audit.AuditPayload(b"data", "application/octet-stream", "1")
    limits = audit.AuditLimits()

    for instance, field_name in [
        (identity, "kind"),
        (payload, "data"),
        (limits, "max_event_id_chars"),
    ]:
        assert not hasattr(instance, "__dict__")
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(instance, field_name, object())

    assert hash(identity) == hash(audit.AuditIdentity("kind", "value"))
    assert hash(payload) == hash(audit.AuditPayload(b"data", "application/octet-stream", "1"))
    assert hash(limits) == hash(audit.AuditLimits())


def test_identity_preserves_values_and_redacts_representation() -> None:
    marker = "  SENSITIVE-Identity-값  "
    identity = audit.AuditIdentity("  User Namespace  ", marker)

    assert identity.kind == "  User Namespace  "
    assert identity.value is marker
    assert repr(identity) == "AuditIdentity(<redacted>)"
    assert marker not in repr(identity)


@pytest.mark.parametrize(("kind", "value"), [("k", "v"), (" " * 2 + "k", "v "), ("종류", "값")])
def test_identity_accepts_nonblank_strings_without_normalization(kind: str, value: str) -> None:
    identity = audit.AuditIdentity(kind, value)
    assert identity.kind is kind
    assert identity.value is value


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("kind", None, "identity kind must be a string"),
        ("kind", 7, "identity kind must be a string"),
        ("kind", True, "identity kind must be a string"),
        ("kind", StringSubclass("secret"), "identity kind must be a string"),
        ("value", None, "identity value must be a string"),
        ("value", b"secret", "identity value must be a string"),
        ("value", 7, "identity value must be a string"),
        ("value", StringSubclass("secret"), "identity value must be a string"),
    ],
)
def test_identity_rejects_non_exact_strings_with_value_free_type_error(
    field_name: str, value: object, message: str
) -> None:
    arguments: dict[str, Any] = {"kind": "kind", "value": "value", field_name: value}
    with pytest.raises(TypeError, match=f"^{message}$") as captured:
        audit.AuditIdentity(**arguments)
    assert repr(value) not in str(captured.value)


def test_identity_validates_fields_in_declaration_order() -> None:
    with pytest.raises(TypeError, match=r"^identity kind must be a string$"):
        audit.AuditIdentity(None, None)  # type: ignore[arg-type]
    with pytest.raises(InvalidAuditIdentityError):
        audit.AuditIdentity("", None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value"), [("kind", ""), ("kind", " \t\n"), ("value", ""), ("value", "\u2003")]
)
def test_identity_rejects_blank_strings_without_disclosure(field_name: str, value: str) -> None:
    arguments = {"kind": "kind", "value": "value", field_name: value}
    _assert_fixed_error(
        lambda: audit.AuditIdentity(**arguments),
        InvalidAuditIdentityError,
        "audit identity is invalid",
        value,
    )


@pytest.mark.parametrize(("field_name", "limit"), [("kind", 64), ("value", 512)])
def test_identity_accepts_hard_limit_and_rejects_one_over(field_name: str, limit: int) -> None:
    at_limit = "x" * limit
    arguments = {"kind": "kind", "value": "value", field_name: at_limit}
    identity = audit.AuditIdentity(**arguments)
    assert getattr(identity, field_name) is at_limit

    over_limit = "x" * (limit + 1)
    arguments[field_name] = over_limit
    _assert_fixed_error(
        lambda: audit.AuditIdentity(**arguments),
        InvalidAuditIdentityError,
        "audit identity is invalid",
        over_limit,
    )


def test_identity_uses_exact_type_structural_equality() -> None:
    class IdentitySubclass(audit.AuditIdentity):
        pass

    left = audit.AuditIdentity("kind", "value")
    assert left == audit.AuditIdentity("kind", "value")
    assert left != audit.AuditIdentity("other", "value")
    assert left != audit.AuditIdentity("kind", "other")
    assert left != IdentitySubclass("kind", "value")
    assert left != ("kind", "value")


def test_payload_preserves_exact_bytes_without_copy_or_disclosure() -> None:
    marker = b"secret-payload-marker"
    payload = audit.AuditPayload(marker, "application/json", "1")

    assert payload.data is marker
    assert repr(payload) == "AuditPayload(<redacted>)"
    assert marker.decode() not in repr(payload)


def test_payload_accepts_exact_hard_ceiling_without_copy() -> None:
    marker = b"x" * 1_048_576
    payload = audit.AuditPayload(marker, "application/octet-stream", "1")
    assert payload.data is marker


def test_payload_rejects_one_byte_over_without_disclosure() -> None:
    over_limit = b"x" * (1_048_576 + 1)
    with pytest.raises(InvalidAuditPayloadError) as captured:
        audit.AuditPayload(over_limit, "application/octet-stream", "1")
    assert captured.value.args == ("audit payload is invalid",)


def test_payload_type_error_does_not_disclose_short_hostile_marker() -> None:
    marker = bytearray(b"HOSTILE-PAYLOAD-MARKER")
    with pytest.raises(TypeError, match=r"^payload data must be bytes$") as captured:
        audit.AuditPayload(marker, "application/octet-stream", "1")  # type: ignore[arg-type]
    assert marker.decode() not in str(captured.value)
    assert marker.decode() not in repr(captured.value)


@pytest.mark.parametrize(
    "data", [None, "secret", bytearray(b"secret"), memoryview(b"secret"), True]
)
def test_payload_rejects_non_exact_bytes_with_value_free_type_error(data: object) -> None:
    with pytest.raises(TypeError, match=r"^payload data must be bytes$") as captured:
        audit.AuditPayload(data, "application/octet-stream", "1")  # type: ignore[arg-type]
    assert repr(data) not in str(captured.value)


def test_payload_rejects_empty_bytes() -> None:
    _assert_fixed_error(
        lambda: audit.AuditPayload(b"", "application/octet-stream", "1"),
        InvalidAuditPayloadError,
        "audit payload is invalid",
        b"",
    )


def test_payload_validates_fields_in_declaration_order() -> None:
    with pytest.raises(TypeError, match=r"^payload data must be bytes$"):
        audit.AuditPayload(None, None, None)  # type: ignore[arg-type]
    with pytest.raises(InvalidAuditPayloadError):
        audit.AuditPayload(b"", None, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^payload content type must be a string$"):
        audit.AuditPayload(b"data", None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("content_type", None, "payload content type must be a string"),
        ("content_type", b"secret", "payload content type must be a string"),
        ("content_type", StringSubclass("secret"), "payload content type must be a string"),
        ("schema_version", None, "payload schema version must be a string"),
        ("schema_version", 1, "payload schema version must be a string"),
        ("schema_version", StringSubclass("secret"), "payload schema version must be a string"),
    ],
)
def test_payload_labels_reject_non_exact_strings_with_value_free_type_error(
    field_name: str, value: object, message: str
) -> None:
    arguments: dict[str, Any] = {
        "data": b"data",
        "content_type": "application/octet-stream",
        "schema_version": "1",
        field_name: value,
    }
    with pytest.raises(TypeError, match=f"^{message}$") as captured:
        audit.AuditPayload(**arguments)
    assert repr(value) not in str(captured.value)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("content_type", ""),
        ("content_type", " \t\n"),
        ("schema_version", ""),
        ("schema_version", "\u2003"),
    ],
)
def test_payload_labels_reject_blank_strings_without_disclosure(
    field_name: str, value: str
) -> None:
    arguments = {
        "data": b"data",
        "content_type": "application/octet-stream",
        "schema_version": "1",
        field_name: value,
    }
    _assert_fixed_error(
        lambda: audit.AuditPayload(**arguments),
        InvalidAuditPayloadError,
        "audit payload is invalid",
        value,
    )


@pytest.mark.parametrize(("field_name", "limit"), [("content_type", 128), ("schema_version", 64)])
def test_payload_labels_accept_hard_limit_and_reject_one_over(field_name: str, limit: int) -> None:
    at_limit = "x" * limit
    arguments = {
        "data": b"data",
        "content_type": "application/octet-stream",
        "schema_version": "1",
        field_name: at_limit,
    }
    payload = audit.AuditPayload(**arguments)
    assert getattr(payload, field_name) is at_limit

    over_limit = "x" * (limit + 1)
    arguments[field_name] = over_limit
    _assert_fixed_error(
        lambda: audit.AuditPayload(**arguments),
        InvalidAuditPayloadError,
        "audit payload is invalid",
        over_limit,
    )


@pytest.mark.parametrize("code_point", [*range(0x00, 0x20), *range(0x7F, 0xA0)])
@pytest.mark.parametrize("field_name", ["content_type", "schema_version"])
def test_payload_labels_reject_all_c0_del_and_c1_controls(field_name: str, code_point: int) -> None:
    marker = f"safe{chr(code_point)}HOSTILE-CONTROL-MARKER"
    arguments = {
        "data": b"data",
        "content_type": "application/octet-stream",
        "schema_version": "1",
        field_name: marker,
    }
    _assert_fixed_error(
        lambda: audit.AuditPayload(**arguments),
        InvalidAuditPayloadError,
        "audit payload is invalid",
        marker,
    )


def test_payload_labels_preserve_whitespace_case_and_unicode() -> None:
    content_type = "  Application/Vnd.Example+Я  "
    schema_version = "  版本-Δ  "
    payload = audit.AuditPayload(b"data", content_type, schema_version)
    assert payload.content_type is content_type
    assert payload.schema_version is schema_version


def test_payload_uses_exact_type_structural_equality() -> None:
    class PayloadSubclass(audit.AuditPayload):
        pass

    left = audit.AuditPayload(b"data", "application/json", "1")
    assert left == audit.AuditPayload(b"data", "application/json", "1")
    assert left != audit.AuditPayload(b"other", "application/json", "1")
    assert left != audit.AuditPayload(b"data", "text/plain", "1")
    assert left != audit.AuditPayload(b"data", "application/json", "2")
    assert left != PayloadSubclass(b"data", "application/json", "1")


def test_limits_defaults_and_field_order_are_exact() -> None:
    limits = audit.AuditLimits()
    assert {
        field.name: getattr(limits, field.name) for field in dataclasses.fields(limits)
    } == HARD_LIMITS


@pytest.mark.parametrize(("field_name", "ceiling"), HARD_LIMITS.items())
def test_limits_accept_equal_and_stricter_positive_policy(field_name: str, ceiling: int) -> None:
    assert getattr(audit.AuditLimits(**{field_name: ceiling}), field_name) == ceiling
    assert getattr(audit.AuditLimits(**{field_name: 1}), field_name) == 1


@pytest.mark.parametrize("field_name", HARD_LIMITS)
@pytest.mark.parametrize("invalid", [True, False, 0, -1, 1.0, "1", None, IntegerSubclass(1)])
def test_limits_reject_non_exact_non_positive_values(field_name: str, invalid: object) -> None:
    _assert_fixed_error(
        lambda: audit.AuditLimits(**{field_name: invalid}),  # type: ignore[arg-type]
        InvalidAuditLimitsError,
        "audit limits are invalid",
        invalid,
    )


@pytest.mark.parametrize(("field_name", "ceiling"), HARD_LIMITS.items())
def test_limits_reject_wider_policy(field_name: str, ceiling: int) -> None:
    invalid = ceiling + 1
    _assert_fixed_error(
        lambda: audit.AuditLimits(**{field_name: invalid}),
        InvalidAuditLimitsError,
        "audit limits are invalid",
        invalid,
    )


def test_limits_use_generated_structural_equality_and_hashing() -> None:
    assert audit.AuditLimits() == audit.AuditLimits()
    assert audit.AuditLimits(max_payload_bytes=1) != audit.AuditLimits()
    assert hash(audit.AuditLimits(max_payload_bytes=1)) == hash(
        audit.AuditLimits(max_payload_bytes=1)
    )


def test_root_exports_errors_then_current_values() -> None:
    import bluetape.audit as audit

    task_two_exports = [
        "AuditError",
        "InvalidAuditIdentityError",
        "InvalidAuditPayloadError",
        "InvalidAuditEventError",
        "InvalidAuditLimitsError",
        "AuditLimitExceededError",
        "AuditIdentity",
        "AuditPayload",
        "AuditLimits",
    ]
    assert [name for name in audit.__all__ if name in task_two_exports] == task_two_exports
