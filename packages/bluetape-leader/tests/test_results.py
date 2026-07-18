import importlib
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import TypeAliasType, get_args, get_origin

import pytest
from bluetape.leader import FencedLeaderLease, LeaderBackendError, LeaderLease


def load_leader() -> object:
    return importlib.import_module("bluetape.leader")


def sample_lease() -> FencedLeaderLease:
    return FencedLeaderLease(
        audit_leader_id="17",
        node_id="node-a",
        elected_at=datetime(2026, 7, 18, tzinfo=UTC),
        lease_until=datetime(2026, 7, 18, 0, 1, tzinfo=UTC),
        fencing_token=17,
    )


def test_elected_none_is_distinct_from_skipped() -> None:
    leader = load_leader()
    lease = sample_lease()

    result = leader.Elected(None, lease)

    assert isinstance(result, leader.Elected)
    assert result.value is None
    assert result.lease is lease
    assert not isinstance(result, leader.Skipped)


def test_stateless_outcomes_are_singleton_like_immutable_values() -> None:
    leader = load_leader()

    for outcome_type in (leader.Skipped, leader.NotHeld):
        first = outcome_type()
        second = outcome_type()

        assert first == second
        assert hash(first) == hash(second)
        assert not hasattr(first, "__dict__")
        assert outcome_type.__final__ is True


def test_action_failed_preserves_lease_and_caller_exception_without_repr_leak() -> None:
    leader = load_leader()
    lease = sample_lease()
    cause = RuntimeError("caller-secret-canary")

    result = leader.ActionFailed(cause, lease)

    assert result.cause is cause
    assert result.lease is lease
    assert not hasattr(result, "__dict__")
    assert "caller-secret-canary" not in repr(result)
    assert "FencedLeaderLease(<redacted>)" in repr(result)
    with pytest.raises(FrozenInstanceError):
        result.lease = sample_lease()


class UnsafeBackendError(LeaderBackendError):
    def __init__(self, raw_value: str) -> None:
        super().__init__()
        self.raw_value = raw_value


@pytest.mark.parametrize(
    "unsafe_cause",
    [RuntimeError("redis://user:secret@127.0.0.1"), UnsafeBackendError("secret")],
)
def test_renew_backend_failure_accepts_only_sanitized_exact_error(
    unsafe_cause: Exception,
) -> None:
    leader = load_leader()

    with pytest.raises(TypeError, match="cause must be LeaderBackendError") as captured:
        leader.RenewBackendFailure(unsafe_cause)

    rendered = f"{captured.value!s} {captured.value!r}"
    assert "redis" not in rendered
    assert "secret" not in rendered


def test_renew_backend_failure_preserves_sanitized_error_without_repr_leak() -> None:
    leader = load_leader()
    cause = LeaderBackendError()

    outcome = leader.RenewBackendFailure(cause)

    assert outcome.cause is cause
    assert not hasattr(outcome, "__dict__")
    assert repr(outcome) == "RenewBackendFailure()"
    assert "leader backend operation failed" not in repr(outcome)


def test_stateful_results_and_outcomes_are_frozen_and_slotted() -> None:
    leader = load_leader()
    lease = sample_lease()
    observed_until = datetime(2026, 7, 18, 0, 2, tzinfo=UTC)
    values_and_field = [
        (leader.Elected("value", lease), "value"),
        (leader.ActionFailed(RuntimeError("failure"), lease), "cause"),
        (leader.Renewed(observed_until), "observed_lease_until"),
        (leader.RenewBackendFailure(LeaderBackendError()), "cause"),
    ]

    for value, field_name in values_and_field:
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, field_name, None)


def test_run_result_alias_is_precise_and_fencing_generic() -> None:
    leader = load_leader()
    alias = leader.LeaderRunResult

    assert isinstance(alias, TypeAliasType)
    assert len(alias.__type_params__) == 2
    assert alias.__type_params__[1].__bound__ is LeaderLease
    elected, skipped, action_failed = get_args(alias.__value__)
    assert get_origin(elected) is leader.Elected
    assert get_args(elected) == alias.__type_params__
    assert skipped is leader.Skipped
    assert get_origin(action_failed) is leader.ActionFailed
    assert get_args(action_failed) == (alias.__type_params__[1],)


def test_renew_outcome_alias_lists_only_precise_outcomes() -> None:
    leader = load_leader()
    alias = leader.RenewOutcome

    assert isinstance(alias, TypeAliasType)
    assert alias.__type_params__ == ()
    assert get_args(alias.__value__) == (
        leader.Renewed,
        leader.NotHeld,
        leader.RenewBackendFailure,
    )


def test_renewed_preserves_optional_observation() -> None:
    leader = load_leader()
    observed_until = datetime(2026, 7, 18, tzinfo=UTC) + timedelta(seconds=30)

    observed = leader.Renewed(observed_until)
    absent = leader.Renewed(None)

    assert observed.observed_lease_until is observed_until
    assert absent.observed_lease_until is None
