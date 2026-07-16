"""Value-safe exceptions for audit contracts."""


class AuditError(ValueError):
    """Base class for invalid audit values and policies."""

    __slots__ = ()


class InvalidAuditIdentityError(AuditError):
    """Raised when an audit identity violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit identity is invalid")


class InvalidAuditPayloadError(AuditError):
    """Raised when an audit payload violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit payload is invalid")


class InvalidAuditEventError(AuditError):
    """Raised when an audit event violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit event is invalid")


class InvalidAuditLimitsError(AuditError):
    """Raised when audit limits are invalid or exceed hard ceilings."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("audit limits are invalid")


class AuditLimitExceededError(AuditError):
    """Raised when an audit event exceeds a configured policy limit."""

    __slots__ = ("field_category", "limit_name")

    field_category: str
    limit_name: str

    def __init__(self, field_category: str, limit_name: str) -> None:
        self.field_category = field_category
        self.limit_name = limit_name
        super().__init__("audit value exceeds configured limit")
