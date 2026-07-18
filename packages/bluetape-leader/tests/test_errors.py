import importlib
import inspect

import pytest

PUBLIC_EXPORTS = [
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


def load_leader() -> object:
    return importlib.import_module("bluetape.leader")


def test_public_surface_exports_contracts_in_plan_order() -> None:
    leader = load_leader()

    assert leader.__all__ == PUBLIC_EXPORTS


def test_error_inheritance_is_exact() -> None:
    leader = load_leader()

    assert leader.LeaderError.__bases__ == (Exception,)
    assert leader.InvalidLeaderOptionsError.__bases__ == (leader.LeaderError, ValueError)
    assert leader.InvalidLockNameError.__bases__ == (leader.LeaderError, ValueError)
    assert leader.LeaderBackendError.__bases__ == (leader.LeaderError,)
    assert leader.LeaderLeaseLostError.__bases__ == (leader.LeaderError,)
    assert leader.LeaderReleaseError.__bases__ == (leader.LeaderError,)
    assert leader.LeaderExecutionError.__bases__ == (leader.LeaderError,)


@pytest.mark.parametrize(
    ("error_name", "expected_message"),
    [
        ("InvalidLeaderOptionsError", "leader options are invalid"),
        ("InvalidLockNameError", "lock name is invalid"),
        ("LeaderBackendError", "leader backend operation failed"),
        ("LeaderLeaseLostError", "leader lease was lost"),
        ("LeaderReleaseError", "leader release failed"),
    ],
)
def test_simple_errors_have_fixed_value_free_messages(
    error_name: str,
    expected_message: str,
) -> None:
    leader = load_leader()
    error_type = getattr(leader, error_name)

    assert str(error_type()) == expected_message


def test_backend_error_does_not_accept_or_retain_raw_cause() -> None:
    leader = load_leader()
    marker = "redis://user:secret@127.0.0.1:6379 owner-123"
    error = leader.LeaderBackendError()

    assert str(inspect.signature(leader.LeaderBackendError)) == "() -> None"
    assert str(error) == "leader backend operation failed"
    assert marker not in repr(error)
    assert not hasattr(error, "cause")
    assert error.__cause__ is None
    assert error.__context__ is None
    assert getattr(error, "__notes__", []) == []


def test_composite_preserves_causes_but_redacts_its_representation() -> None:
    leader = load_leader()
    action = RuntimeError("caller-value-canary")
    lifecycle = leader.LeaderBackendError()
    error = leader.LeaderExecutionError(action, lifecycle)

    assert error.action_cause is action
    assert error.lifecycle_cause is lifecycle
    assert str(error) == "leader action and lifecycle both failed"
    assert repr(error) == "LeaderExecutionError(<redacted>)"
    assert "caller-value-canary" not in repr(error)
