from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any

import pytest
from bluetape.leader import (
    ActionFailed,
    Elected,
    FencedLeaderLease,
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderElector,
    LeaderExecutionError,
    LeaderLeaseLostError,
    Skipped,
)


def sample_lease() -> FencedLeaderLease:
    now = datetime.now(UTC)
    return FencedLeaderLease("7", None, now, now + timedelta(seconds=1), 7)


class FakeHandle:
    def __init__(
        self,
        *,
        enter_error: BaseException | None = None,
        exit_error: BaseException | None = None,
    ) -> None:
        self._lease = sample_lease()
        self.enter_error = enter_error
        self.exit_error = exit_error
        self.entered = False
        self.exits = 0

    @property
    def lease(self) -> FencedLeaderLease:
        assert self.entered
        return self._lease

    def __enter__(self) -> FakeHandle:
        if self.enter_error is not None:
            raise self.enter_error
        self.entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.exits += 1
        if self.exit_error is not None:
            raise self.exit_error


class FakeLock:
    def __init__(self, handle: FakeHandle | None) -> None:
        self.handle = handle
        self.calls: list[tuple[str, LeaderElectionOptions]] = []

    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> FakeHandle | None:
        self.calls.append((lock_name, options))
        return self.handle


def elector_with(handle: FakeHandle | None) -> Any:
    from bluetape.leader.redis import RedisLeaderElector

    elector = object.__new__(RedisLeaderElector)
    elector._lock = FakeLock(handle)
    return elector


def test_result_distinguishes_none_from_contention_and_types_callback() -> None:
    handle = FakeHandle()
    elector = elector_with(handle)
    seen: list[FencedLeaderLease] = []

    def action(lease: FencedLeaderLease) -> None:
        assert type(lease) is FencedLeaderLease
        seen.append(lease)

    elected = elector.run_if_leader_result("job", action)
    skipped = elector_with(None).run_if_leader_result("job", action)

    assert isinstance(elected, Elected) and elected.value is None
    assert elected.lease is handle.lease and seen == [handle.lease]
    assert isinstance(skipped, Skipped)
    assert handle.exits == 1


def test_ordinary_action_failure_is_reported_only_after_safe_cleanup() -> None:
    marker = ValueError("action")
    handle = FakeHandle()

    def fail(lease: FencedLeaderLease) -> None:
        del lease
        raise marker

    result = elector_with(handle).run_if_leader_result("job", fail)

    assert isinstance(result, ActionFailed)
    assert result.cause is marker and result.lease is handle.lease
    assert handle.exits == 1


def test_simple_api_reraises_original_action_error_after_safe_cleanup() -> None:
    marker = ValueError("action")
    handle = FakeHandle()

    def fail(lease: FencedLeaderLease) -> None:
        del lease
        raise marker

    with pytest.raises(ValueError) as caught:
        elector_with(handle).run_if_leader("job", fail)

    assert caught.value is marker
    assert handle.exits == 1


@pytest.mark.parametrize(
    "error_type",
    [LeaderLeaseLostError, LeaderBackendError],
    ids=["proof_not_held", "proof_backend_failure"],
)
def test_entry_proof_failure_never_invokes_callback(
    error_type: type[Exception],
) -> None:
    lifecycle_error = error_type()
    handle = FakeHandle(enter_error=lifecycle_error)
    invoked = False

    def action(lease: FencedLeaderLease) -> None:
        nonlocal invoked
        del lease
        invoked = True

    with pytest.raises(error_type) as caught:
        elector_with(handle).run_if_leader_result("job", action)

    assert caught.value is lifecycle_error
    assert invoked is False
    assert handle.entered is False
    assert handle.exits == 0


@pytest.mark.parametrize(
    ("scenario", "error_type"),
    [
        ("renew_loss", LeaderLeaseLostError),
        ("renew_backend_failure", LeaderBackendError),
        ("scoped_release_not_held", LeaderLeaseLostError),
        ("corrupt_release", LeaderBackendError),
        ("uncertain_release", LeaderBackendError),
    ],
)
@pytest.mark.parametrize("action_fails", [False, True], ids=["success_action", "failed_action"])
def test_named_lifecycle_outcomes_apply_elector_failure_matrix(
    scenario: str,
    error_type: type[Exception],
    action_fails: bool,
) -> None:
    lifecycle_error = error_type()
    action_error = ValueError(f"{scenario} action")
    handle = FakeHandle(exit_error=lifecycle_error)

    def action(lease: FencedLeaderLease) -> int:
        if action_fails:
            raise action_error
        return lease.fencing_token

    expected = LeaderExecutionError if action_fails else error_type
    with pytest.raises(expected) as caught:
        elector_with(handle).run_if_leader_result("job", action)

    if action_fails:
        assert caught.value.action_cause is action_error
        assert caught.value.lifecycle_cause is lifecycle_error
    else:
        assert caught.value is lifecycle_error
    assert handle.exits == 1


@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_process_control_identity_survives_handle_cleanup(
    error_type: type[BaseException],
) -> None:
    marker = error_type("control")
    handle = FakeHandle()

    def stop(lease: FencedLeaderLease) -> None:
        del lease
        raise marker

    with pytest.raises(BaseException) as caught:
        elector_with(handle).run_if_leader_result("job", stop)

    assert caught.value is marker
    assert handle.exits == 1


def test_constructor_shape_and_runtime_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.leader.redis import RedisLeaderElector
    from bluetape.leader.redis import _elector as module

    created: list[tuple[object, str]] = []

    class StubLock:
        def __init__(self, client: object, prefix: str) -> None:
            created.append((client, prefix))

        def try_acquire(self, lock_name: str, options: object = None) -> None:
            del lock_name, options

    monkeypatch.setattr(module, "RedisDistributedLock", StubLock)
    client = object()
    elector = RedisLeaderElector(client, prefix="custom")

    assert created == [(client, "custom")]
    assert isinstance(elector, LeaderElector)
    assert str(inspect.signature(RedisLeaderElector)) == (
        "(client: 'redis.Redis', *, prefix: 'str' = 'bluetape-leader') -> 'None'"
    )
