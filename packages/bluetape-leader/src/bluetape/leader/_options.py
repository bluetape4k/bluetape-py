"""Backend-neutral options for leader election and distributed locks."""

from dataclasses import dataclass
from datetime import timedelta
from typing import final

from ._errors import InvalidLeaderOptionsError

_ZERO = timedelta(0)
_MAX_NODE_ID_BYTES = 256


def _require_exact_timedelta(value: object, field_name: str) -> None:
    if type(value) is not timedelta:
        raise TypeError(f"{field_name} must be an exact timedelta")


def _require_exact_bool(value: object, field_name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be an exact bool")


def _require_exact_str(value: object, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be an exact str")


def _validate_node_id(node_id: str) -> None:
    try:
        encoded_length = len(node_id.encode())
    except UnicodeEncodeError:
        raise InvalidLeaderOptionsError() from None
    if not node_id or node_id.isspace() or encoded_length > _MAX_NODE_ID_BYTES:
        raise InvalidLeaderOptionsError()


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class LeaderElectionOptions:
    """Immutable backend-neutral timing and identity policy."""

    wait_time: timedelta = timedelta(seconds=5)
    lease_time: timedelta = timedelta(seconds=60)
    node_id: str | None = None
    min_lease_time: timedelta = _ZERO
    auto_renew: bool = False
    renew_interval: timedelta | None = None

    def __post_init__(self) -> None:
        _require_exact_timedelta(self.wait_time, "wait_time")
        _require_exact_timedelta(self.lease_time, "lease_time")
        _require_exact_timedelta(self.min_lease_time, "min_lease_time")
        _require_exact_bool(self.auto_renew, "auto_renew")
        if self.renew_interval is not None:
            _require_exact_timedelta(self.renew_interval, "renew_interval")
        if self.node_id is not None:
            _require_exact_str(self.node_id, "node_id")

        if self.wait_time < _ZERO or self.lease_time <= _ZERO:
            raise InvalidLeaderOptionsError()
        if not _ZERO <= self.min_lease_time <= self.lease_time:
            raise InvalidLeaderOptionsError()
        if self.node_id is not None:
            _validate_node_id(self.node_id)

        interval = self.renew_interval
        if self.auto_renew and interval is None:
            derived_interval = self.lease_time / 3
            if derived_interval <= _ZERO:
                raise InvalidLeaderOptionsError()
            object.__setattr__(self, "renew_interval", derived_interval)
        elif interval is not None and not _ZERO < interval < self.lease_time:
            raise InvalidLeaderOptionsError()
