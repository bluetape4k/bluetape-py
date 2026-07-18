from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from bluetape.leader import InvalidLeaderOptionsError, LeaderElectionOptions


class TimedeltaSubclass(timedelta):
    def __lt__(self, other: object) -> bool:
        raise AssertionError("hostile timedelta comparison ran")

    def __truediv__(self, other: object) -> timedelta:
        raise AssertionError("hostile timedelta division ran")


class StringSubclass(str):
    def isspace(self) -> bool:
        raise AssertionError("hostile string whitespace check ran")

    def __bool__(self) -> bool:
        raise AssertionError("hostile string truthiness ran")


class HostileTruthiness:
    def __bool__(self) -> bool:
        raise AssertionError("hostile truthiness ran")


def test_defaults_are_backend_neutral_and_immutable() -> None:
    options = LeaderElectionOptions()

    assert options.wait_time == timedelta(seconds=5)
    assert options.lease_time == timedelta(seconds=60)
    assert options.node_id is None
    assert options.min_lease_time == timedelta(0)
    assert options.auto_renew is False
    assert options.renew_interval is None
    assert not hasattr(options, "__dict__")
    with pytest.raises(FrozenInstanceError):
        options.lease_time = timedelta(seconds=30)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("wait_time", TimedeltaSubclass(seconds=1)),
        ("lease_time", TimedeltaSubclass(seconds=1)),
        ("min_lease_time", TimedeltaSubclass(seconds=1)),
        ("renew_interval", TimedeltaSubclass(seconds=1)),
        ("node_id", StringSubclass("node-a")),
        ("auto_renew", 1),
        ("auto_renew", HostileTruthiness()),
    ],
)
def test_options_require_exact_builtin_types_without_running_hostile_code(
    field: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match=field):
        LeaderElectionOptions(**{field: value})


@pytest.mark.parametrize(
    "values",
    [
        {"wait_time": timedelta(microseconds=-1)},
        {"lease_time": timedelta(0)},
        {"lease_time": timedelta(microseconds=-1)},
        {"min_lease_time": timedelta(microseconds=-1)},
        {"lease_time": timedelta(seconds=1), "min_lease_time": timedelta(seconds=2)},
        {"renew_interval": timedelta(0)},
        {"renew_interval": timedelta(microseconds=-1)},
        {"lease_time": timedelta(seconds=1), "renew_interval": timedelta(seconds=1)},
        {"lease_time": timedelta(seconds=1), "renew_interval": timedelta(seconds=2)},
    ],
)
def test_duration_boundaries_and_ordering_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(InvalidLeaderOptionsError, match="leader options are invalid"):
        LeaderElectionOptions(**values)


@pytest.mark.parametrize("node_id", ["", " ", "\t\n", "x" * 257, "가" * 86])
def test_invalid_node_ids_are_rejected(node_id: str) -> None:
    with pytest.raises(InvalidLeaderOptionsError, match="leader options are invalid"):
        LeaderElectionOptions(node_id=node_id)


def test_accepted_node_id_is_preserved_without_normalization() -> None:
    node_id = "  node-a  "

    options = LeaderElectionOptions(node_id=node_id)

    assert options.node_id is node_id


def test_core_accepts_positive_sub_millisecond_lease() -> None:
    options = LeaderElectionOptions(lease_time=timedelta(microseconds=500))

    assert options.lease_time == timedelta(microseconds=500)


def test_auto_renew_derives_exact_third_only_when_interval_is_absent() -> None:
    lease_time = timedelta(microseconds=10)

    derived = LeaderElectionOptions(lease_time=lease_time, auto_renew=True)
    explicit = LeaderElectionOptions(
        lease_time=lease_time,
        auto_renew=True,
        renew_interval=timedelta(microseconds=2),
    )
    disabled = LeaderElectionOptions(lease_time=lease_time)

    assert derived.renew_interval == lease_time / 3
    assert explicit.renew_interval == timedelta(microseconds=2)
    assert disabled.renew_interval is None


def test_zero_wait_and_minimum_equal_to_lease_are_valid_boundaries() -> None:
    lease_time = timedelta(microseconds=1)

    options = LeaderElectionOptions(
        wait_time=timedelta(0),
        lease_time=lease_time,
        min_lease_time=lease_time,
    )

    assert options.wait_time == timedelta(0)
    assert options.min_lease_time == lease_time
