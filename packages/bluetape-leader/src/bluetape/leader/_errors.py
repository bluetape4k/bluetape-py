"""Value-safe exceptions for backend-neutral leader contracts."""


class LeaderError(Exception):
    """Base error for backend-neutral leader contracts."""

    __slots__ = ()


class InvalidLeaderOptionsError(LeaderError, ValueError):
    """Raised when leader options violate their contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("leader options are invalid")


class InvalidLockNameError(LeaderError, ValueError):
    """Raised when a logical lock name violates its contract."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("lock name is invalid")


class LeaderBackendError(LeaderError):
    """Raised when a backend operation fails without exposing its raw cause."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("leader backend operation failed")


class LeaderLeaseLostError(LeaderError):
    """Raised when a caller can no longer prove ownership of its lease."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("leader lease was lost")


class LeaderReleaseError(LeaderError):
    """Raised when an explicit release cannot prove safe ownership."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("leader release failed")


class LeaderExecutionError(LeaderError):
    """Preserve action and sanitized lifecycle failures behind a redacted repr."""

    __slots__ = ("action_cause", "lifecycle_cause")

    action_cause: Exception
    lifecycle_cause: LeaderError

    def __init__(self, action_cause: Exception, lifecycle_cause: LeaderError) -> None:
        if not issubclass(type(action_cause), Exception):
            raise TypeError("action_cause must be Exception")
        if not issubclass(type(lifecycle_cause), LeaderError):
            raise TypeError("lifecycle_cause must be LeaderError")
        super().__init__("leader action and lifecycle both failed")
        self.action_cause = action_cause
        self.lifecycle_cause = lifecycle_cause

    def __repr__(self) -> str:
        return "LeaderExecutionError(<redacted>)"
