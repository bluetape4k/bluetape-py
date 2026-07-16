"""Storage-neutral audit event contracts."""

from bluetape.audit._errors import (
    AuditError,
    AuditLimitExceededError,
    InvalidAuditEventError,
    InvalidAuditIdentityError,
    InvalidAuditLimitsError,
    InvalidAuditPayloadError,
)
from bluetape.audit._validation import validate_audit_event
from bluetape.audit._values import AuditEvent, AuditIdentity, AuditLimits, AuditPayload

__all__ = [  # noqa: RUF022 - public order is part of the package contract
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
