from __future__ import annotations

import importlib

EXPECTED_EXPORTS = [
    "AuditError",
    "InvalidAuditIdentityError",
    "InvalidAuditPayloadError",
    "InvalidAuditEventError",
    "InvalidAuditLimitsError",
    "AuditLimitExceededError",
]


def test_audit_error_hierarchy_is_value_safe() -> None:
    audit = importlib.import_module("bluetape.audit")

    assert issubclass(audit.AuditError, ValueError)
    assert issubclass(audit.InvalidAuditIdentityError, audit.AuditError)
    assert issubclass(audit.InvalidAuditPayloadError, audit.AuditError)
    assert issubclass(audit.InvalidAuditEventError, audit.AuditError)
    assert issubclass(audit.InvalidAuditLimitsError, audit.AuditError)

    error = audit.AuditLimitExceededError("payload.data", "max_payload_bytes")
    assert str(error) == "audit value exceeds configured limit"
    assert error.args == ("audit value exceeds configured limit",)
    assert error.field_category == "payload.data"
    assert error.limit_name == "max_payload_bytes"
    assert "payload.data" not in str(error)
    assert "max_payload_bytes" not in str(error)


def test_initial_public_api_exports_only_the_error_boundary() -> None:
    audit = importlib.import_module("bluetape.audit")

    assert audit.__all__ == EXPECTED_EXPORTS
