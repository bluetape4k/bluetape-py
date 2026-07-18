"""Backend-neutral leader contracts for bluetape-py."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

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
]
