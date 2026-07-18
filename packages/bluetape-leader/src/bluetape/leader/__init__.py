"""Backend-neutral leader contracts for bluetape-py."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

from ._contracts import (
    AsyncDistributedLock,
    AsyncLeaderElector,
    AsyncLockLease,
    DistributedLock,
    LeaderElector,
    LockLease,
)
from ._errors import (
    InvalidLeaderOptionsError,
    InvalidLockNameError,
    LeaderBackendError,
    LeaderError,
    LeaderExecutionError,
    LeaderLeaseLostError,
    LeaderReleaseError,
)
from ._options import LeaderElectionOptions
from ._results import (
    ActionFailed,
    Elected,
    LeaderRunResult,
    NotHeld,
    RenewBackendFailure,
    Renewed,
    RenewOutcome,
    Skipped,
)
from ._values import FencedLeaderLease, LeaderLease

__all__ = [  # noqa: RUF022 - public order is part of the contract
    "LeaderError",
    "InvalidLeaderOptionsError",
    "InvalidLockNameError",
    "LeaderBackendError",
    "LeaderLeaseLostError",
    "LeaderReleaseError",
    "LeaderExecutionError",
    "LeaderElectionOptions",
    "LeaderLease",
    "FencedLeaderLease",
    "Elected",
    "Skipped",
    "ActionFailed",
    "LeaderRunResult",
    "Renewed",
    "NotHeld",
    "RenewBackendFailure",
    "RenewOutcome",
    "LockLease",
    "AsyncLockLease",
    "DistributedLock",
    "AsyncDistributedLock",
    "LeaderElector",
    "AsyncLeaderElector",
]
