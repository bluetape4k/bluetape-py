from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import pytest
from bluetape.leader import FencedLeaderLease, LeaderLease


class StringSubclass(str):
    def __bool__(self) -> bool:
        raise AssertionError("hostile string truthiness ran")


class DatetimeSubclass(datetime):
    def utcoffset(self) -> timedelta | None:
        raise AssertionError("hostile datetime offset ran")


class IntSubclass(int):
    def __bool__(self) -> bool:
        raise AssertionError("hostile integer truthiness ran")


class HostileTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        raise AssertionError("hostile timezone offset ran")


def make_lease(**changes: object) -> LeaderLease:
    values: dict[str, object] = {
        "audit_leader_id": "audit-node-a",
        "node_id": "node-a",
        "elected_at": datetime(2026, 7, 18, tzinfo=UTC),
        "lease_until": datetime(2026, 7, 18, 0, 1, tzinfo=UTC),
    }
    values.update(changes)
    return LeaderLease(**values)


def test_lease_preserves_accepted_caller_strings_and_datetimes() -> None:
    audit_leader_id = "".join(["audit", "-", "node-a"])
    node_id = "".join(["physical", "-", "node-a"])
    elected_at = datetime(2026, 7, 18, tzinfo=UTC)
    lease_until = datetime(2026, 7, 18, 0, 1, tzinfo=UTC)

    lease = LeaderLease(
        audit_leader_id=audit_leader_id,
        node_id=node_id,
        elected_at=elected_at,
        lease_until=lease_until,
    )

    assert lease.audit_leader_id is audit_leader_id
    assert lease.node_id is node_id
    assert lease.elected_at is elected_at
    assert lease.lease_until is lease_until


def test_lease_allows_absent_physical_identity_and_observations() -> None:
    lease = LeaderLease(
        audit_leader_id="audit-only",
        node_id=None,
        elected_at=None,
        lease_until=None,
    )

    assert lease.node_id is None
    assert lease.elected_at is None
    assert lease.lease_until is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("audit_leader_id", StringSubclass("audit-node-a")),
        ("node_id", StringSubclass("node-a")),
        ("elected_at", DatetimeSubclass(2026, 7, 18, tzinfo=UTC)),
        ("lease_until", DatetimeSubclass(2026, 7, 18, tzinfo=UTC)),
    ],
)
def test_lease_requires_exact_value_types_without_running_hostile_code(
    field: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match=field):
        make_lease(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("elected_at", datetime(2026, 7, 18)),
        ("lease_until", datetime(2026, 7, 18, tzinfo=timezone(timedelta(hours=9)))),
    ],
)
def test_observation_timestamps_must_be_aware_utc(field: str, value: datetime) -> None:
    with pytest.raises(ValueError, match=field):
        make_lease(**{field: value})


@pytest.mark.parametrize(
    "safe_utc",
    [
        datetime(2026, 7, 18, tzinfo=UTC),
        datetime(2026, 7, 18, tzinfo=timezone(timedelta(0), "safe-zero")),
        datetime(2026, 7, 18, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 7, 18, tzinfo=ZoneInfo("Etc/UTC")),
    ],
)
def test_observation_timestamps_accept_safe_exact_stdlib_utc(
    safe_utc: datetime,
) -> None:
    lease = make_lease(elected_at=safe_utc)

    assert lease.elected_at is safe_utc


def test_observation_timestamp_rejects_hostile_timezone_without_invoking_it() -> None:
    hostile = datetime(2026, 7, 18, tzinfo=HostileTimezone())

    with pytest.raises(ValueError, match="elected_at"):
        make_lease(elected_at=hostile)


def test_lease_values_are_frozen_slotted_and_redacted() -> None:
    lease = make_lease()

    assert not hasattr(lease, "__dict__")
    assert repr(lease) == "LeaderLease(<redacted>)"
    assert "node-a" not in repr(lease)
    with pytest.raises(FrozenInstanceError):
        lease.node_id = "node-b"


def test_fenced_lease_keeps_node_and_fence_distinct() -> None:
    lease = FencedLeaderLease(
        audit_leader_id="42",
        node_id="node-a",
        elected_at=datetime(2026, 7, 18, tzinfo=UTC),
        lease_until=datetime(2026, 7, 18, 0, 1, tzinfo=UTC),
        fencing_token=42,
    )

    assert lease.audit_leader_id == "42"
    assert lease.node_id == "node-a"
    assert lease.fencing_token == 42
    assert not hasattr(lease, "__dict__")
    assert repr(lease) == "FencedLeaderLease(<redacted>)"
    assert "42" not in repr(lease)
    assert "node-a" not in repr(lease)
    with pytest.raises(FrozenInstanceError):
        lease.fencing_token = 43


@pytest.mark.parametrize("fencing_token", [True, 0, -1, IntSubclass(1)])
def test_fencing_token_must_be_an_exact_positive_integer(fencing_token: object) -> None:
    with pytest.raises((TypeError, ValueError), match="fencing_token"):
        FencedLeaderLease(
            audit_leader_id="audit-node-a",
            node_id="node-a",
            elected_at=datetime(2026, 7, 18, tzinfo=UTC),
            lease_until=datetime(2026, 7, 18, 0, 1, tzinfo=UTC),
            fencing_token=fencing_token,
        )
