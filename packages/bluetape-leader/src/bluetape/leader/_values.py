"""Immutable backend-neutral leader lease snapshots."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import final
from zoneinfo import ZoneInfo


def _require_exact_str(value: object, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be an exact str")


def _require_optional_utc_datetime(value: object, field_name: str) -> None:
    if value is None:
        return
    if type(value) is not datetime:
        raise TypeError(f"{field_name} must be an exact datetime or None")
    timezone_info = value.tzinfo
    if type(timezone_info) is timezone or type(timezone_info) is ZoneInfo:
        offset = timezone_info.utcoffset(value)
    else:
        raise ValueError(f"{field_name} must be an aware UTC datetime")
    if offset != timedelta(0):
        raise ValueError(f"{field_name} must be an aware UTC datetime")


@dataclass(frozen=True, slots=True, repr=False)
class LeaderLease:
    """A safe immutable observation of one acquired leader lease."""

    audit_leader_id: str = field(repr=False)
    node_id: str | None = field(repr=False)
    elected_at: datetime | None
    lease_until: datetime | None

    def __post_init__(self) -> None:
        _require_exact_str(self.audit_leader_id, "audit_leader_id")
        if self.node_id is not None:
            _require_exact_str(self.node_id, "node_id")
        _require_optional_utc_datetime(self.elected_at, "elected_at")
        _require_optional_utc_datetime(self.lease_until, "lease_until")

    def __repr__(self) -> str:
        return "LeaderLease(<redacted>)"


@final
@dataclass(frozen=True, slots=True, repr=False)
class FencedLeaderLease(LeaderLease):
    """A lease observation carrying an independently comparable fence."""

    fencing_token: int = field(repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if type(self.fencing_token) is not int:
            raise TypeError("fencing_token must be an exact int")
        if self.fencing_token < 1:
            raise ValueError("fencing_token must be positive")

    def __repr__(self) -> str:
        return "FencedLeaderLease(<redacted>)"
