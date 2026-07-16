"""Value-safe exceptions for audit contracts."""

from __future__ import annotations


class AuditError(ValueError):
    """Base class for invalid audit values and policies."""

    __slots__ = ()


class InvalidAuditIdentityError(AuditError):
    """Raised when an audit identity violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit identity is invalid")

    def __reduce__(self) -> tuple[type[InvalidAuditIdentityError], tuple[()]]:
        return type(self), ()


class InvalidAuditPayloadError(AuditError):
    """Raised when an audit payload violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit payload is invalid")

    def __reduce__(self) -> tuple[type[InvalidAuditPayloadError], tuple[()]]:
        return type(self), ()


class InvalidAuditEventError(AuditError):
    """Raised when an audit event violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit event is invalid")

    def __reduce__(self) -> tuple[type[InvalidAuditEventError], tuple[()]]:
        return type(self), ()


class InvalidAuditLimitsError(AuditError):
    """Raised when audit limits are invalid or exceed hard ceilings."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit limits are invalid")

    def __reduce__(self) -> tuple[type[InvalidAuditLimitsError], tuple[()]]:
        return type(self), ()


class AuditLimitExceededError(AuditError):
    """Raised when an audit event exceeds a configured policy limit."""

    __slots__ = ("field_category", "limit_name")

    field_category: str
    limit_name: str

    def __init__(self, field_category: str, limit_name: str) -> None:
        self.field_category = field_category
        self.limit_name = limit_name
        super().__init__("audit value exceeds configured limit")

    def __reduce__(self) -> tuple[type[AuditLimitExceededError], tuple[str, str]]:
        return type(self), (self.field_category, self.limit_name)
