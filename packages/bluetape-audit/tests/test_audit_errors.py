from __future__ import annotations

import copy
import importlib
import pickle

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


@pytest.mark.parametrize(("error_name", "message"), INVALID_ERRORS)
def test_invalid_errors_support_safe_round_trips(error_name: str, message: str) -> None:
    audit = importlib.import_module("bluetape.audit")
    error = getattr(audit, error_name)()

    restored_errors = [pickle.loads(pickle.dumps(error)), copy.copy(error), copy.deepcopy(error)]
    for restored in restored_errors:
        assert type(restored) is type(error)
        assert str(restored) == message
        assert repr(restored) == f"{error_name}({message!r})"
        assert restored.args == (message,)


def test_limit_error_supports_safe_round_trips() -> None:
    audit = importlib.import_module("bluetape.audit")
    error = audit.AuditLimitExceededError("payload.data", "max_payload_bytes")

    restored_errors = [pickle.loads(pickle.dumps(error)), copy.copy(error), copy.deepcopy(error)]
    for restored in restored_errors:
        assert type(restored) is audit.AuditLimitExceededError
        assert str(restored) == "audit value exceeds configured limit"
        assert repr(restored) == "AuditLimitExceededError('audit value exceeds configured limit')"
        assert restored.args == ("audit value exceeds configured limit",)
        assert restored.field_category == "payload.data"
        assert restored.limit_name == "max_payload_bytes"
        assert "payload.data" not in str(restored)
        assert "max_payload_bytes" not in repr(restored)


def test_public_api_preserves_the_ordered_error_prefix() -> None:
    audit = importlib.import_module("bluetape.audit")

    assert audit.__all__[: len(EXPECTED_EXPORTS)] == EXPECTED_EXPORTS
