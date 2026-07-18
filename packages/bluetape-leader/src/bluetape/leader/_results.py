"""Precise immutable outcomes for backend-neutral leader operations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import final

from ._errors import LeaderBackendError
from ._values import LeaderLease


@dataclass(frozen=True, slots=True)
class Elected[T, LeaseT: LeaderLease]:
    """An action result produced while holding the recorded lease."""

    value: T
    lease: LeaseT


@final
@dataclass(frozen=True, slots=True)
class Skipped:
    """A stateless result indicating that leadership was not acquired."""


@dataclass(frozen=True, slots=True)
class ActionFailed[LeaseT: LeaderLease]:
    """An ordinary caller action failure followed by proven-safe cleanup."""

    cause: Exception = field(repr=False)
    lease: LeaseT


type LeaderRunResult[T, LeaseT: LeaderLease] = Elected[T, LeaseT] | Skipped | ActionFailed[LeaseT]


@dataclass(frozen=True, slots=True)
class Renewed:
    """A successful renewal with an optional diagnostic expiry observation."""

    observed_lease_until: datetime | None


@final
@dataclass(frozen=True, slots=True)
class NotHeld:
    """A stateless renewal result indicating that ownership was not held."""


@dataclass(frozen=True, slots=True)
class RenewBackendFailure:
    """A renewal failure retaining only the sanitized backend error."""

    cause: LeaderBackendError = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.cause) is not LeaderBackendError:
            raise TypeError("cause must be LeaderBackendError")


type RenewOutcome = Renewed | NotHeld | RenewBackendFailure
