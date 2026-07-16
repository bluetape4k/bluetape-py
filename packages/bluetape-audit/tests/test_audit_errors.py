from __future__ import annotations

import importlib

import pytest

EXPECTED_EXPORTS = [
    "AuditError",
    "InvalidAuditIdentityError",
    "InvalidAuditPayloadError",
    "InvalidAuditEventError",
    "InvalidAuditLimitsError",
    "AuditLimitExceededError",
]

INVALID_ERRORS = [
    ("InvalidAuditIdentityError", "audit identity is invalid"),
    ("InvalidAuditPayloadError", "audit payload is invalid"),
    ("InvalidAuditEventError", "audit event is invalid"),
    ("InvalidAuditLimitsError", "audit limits are invalid"),
]


def test_audit_error_hierarchy_is_value_safe() -> None:
    audit = importlib.import_module("bluetape.audit")

    assert audit.AuditError.__bases__ == (ValueError,)
    assert audit.InvalidAuditIdentityError.__bases__ == (audit.AuditError,)
    assert audit.InvalidAuditPayloadError.__bases__ == (audit.AuditError,)
    assert audit.InvalidAuditEventError.__bases__ == (audit.AuditError,)
    assert audit.InvalidAuditLimitsError.__bases__ == (audit.AuditError,)
    assert audit.AuditLimitExceededError.__bases__ == (audit.AuditError,)

    error = audit.AuditLimitExceededError("payload.data", "max_payload_bytes")
    assert str(error) == "audit value exceeds configured limit"
    assert error.args == ("audit value exceeds configured limit",)
    assert error.field_category == "payload.data"
    assert error.limit_name == "max_payload_bytes"
    assert "payload.data" not in str(error)
    assert "max_payload_bytes" not in str(error)
    assert repr(error) == "AuditLimitExceededError('audit value exceeds configured limit')"


@pytest.mark.parametrize(("error_name", "message"), INVALID_ERRORS)
def test_invalid_errors_have_fixed_non_overridable_messages(error_name: str, message: str) -> None:
    audit = importlib.import_module("bluetape.audit")
    error_type = getattr(audit, error_name)

    error = error_type()
    assert str(error) == message
    assert repr(error) == f"{error_name}({message!r})"
    assert error.args == (message,)

    with pytest.raises(TypeError):
        error_type("caller-secret")


def test_initial_public_api_exports_only_the_error_boundary() -> None:
    audit = importlib.import_module("bluetape.audit")

    assert audit.__all__ == EXPECTED_EXPORTS
