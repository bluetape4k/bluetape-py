from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from bluetape.leader import (
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderLeaseLostError,
    LeaderReleaseError,
    NotHeld,
    RenewBackendFailure,
    Renewed,
)
from bluetape.leader.redis import RedisDistributedLock
from bluetape.leader.redis._scripts import RECONCILE_SCRIPT
from bluetape.leader.redis._support import _Timing
from redis.exceptions import NoScriptError


class FakeClock:
    def __init__(self) -> None:
        self.now = 0
        self.sleeps: list[float] = []

    def monotonic_ns(self) -> int:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += int(seconds * 1_000_000_000)


class FakeCommands:
    def __init__(
        self,
        *,
        evalsha_effects: list[object] | None = None,
        eval_effects: list[object] | None = None,
        after_call: Callable[[str], None] | None = None,
    ) -> None:
        self.evalsha_effects = list(evalsha_effects or [])
        self.eval_effects = list(eval_effects or [])
        self.after_call = after_call
        self.calls: list[tuple[object, ...]] = []

    def evalsha(self, sha1: str, numkeys: int, *values: bytes) -> object:
        self.calls.append(("evalsha", sha1, numkeys, *values))
        if self.after_call is not None:
            self.after_call("evalsha")
        return self._next(self.evalsha_effects)

    def eval(self, source: str, numkeys: int, *values: bytes) -> object:
        self.calls.append(("eval", source, numkeys, *values))
        if self.after_call is not None:
            self.after_call("eval")
        return self._next(self.eval_effects)

    @staticmethod
    def _next(effects: list[object]) -> object:
        effect = effects.pop(0)
        if isinstance(effect, BaseException):
            raise effect
        return effect


TIMING = _Timing(0, 0.01, 0.02, 0.04, 0.06, 0.04, 0.04, 0.1)


def options(
    *,
    wait: float = 0.0,
    lease: float = 1.0,
    minimum: float = 0.0,
    auto_renew: bool = False,
    renew_interval: float | None = None,
) -> LeaderElectionOptions:
    return LeaderElectionOptions(
        wait_time=timedelta(seconds=wait),
        lease_time=timedelta(seconds=lease),
        min_lease_time=timedelta(seconds=minimum),
        auto_renew=auto_renew,
        renew_interval=(None if renew_interval is None else timedelta(seconds=renew_interval)),
    )


def new_lock(
    commands: FakeCommands,
    clock: FakeClock,
    *,
    token: str = "A" * 32,
    jitter: float = 0.05,
) -> RedisDistributedLock:
    return RedisDistributedLock._for_test(
        commands,
        TIMING,
        monotonic_ns=clock.monotonic_ns,
        sleep=clock.sleep,
        jitter=lambda: jitter,
        token_factory=lambda: token,
    )


def test_zero_wait_dispatches_exactly_one_acquire_with_monotonic_deadline() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"CONTENDED"]])
    lock = new_lock(commands, clock)

    assert lock.try_acquire("job", options()) is None

    assert [call[0] for call in commands.calls] == ["evalsha"]
    assert clock.sleeps == []


def test_zero_wait_generates_one_owner_token_per_public_call() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"CONTENDED"], [b"CONTENDED"]])
    generated = 0

    def token_factory() -> str:
        nonlocal generated
        generated += 1
        return "A" * 32

    lock = RedisDistributedLock._for_test(
        commands,
        TIMING,
        monotonic_ns=clock.monotonic_ns,
        sleep=clock.sleep,
        jitter=lambda: 0.05,
        token_factory=token_factory,
    )

    assert lock.try_acquire("job", options()) is None
    assert lock.try_acquire("job", options()) is None
    assert generated == 2


def test_contention_retry_caps_jitter_and_never_dispatches_at_deadline() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"CONTENDED"]])
    lock = new_lock(commands, clock, jitter=0.06)

    assert lock.try_acquire("job", options(wait=0.045)) is None

    assert clock.sleeps == [0.045]
    assert [call[0] for call in commands.calls] == ["evalsha"]


def test_contention_retry_uses_jitter_inside_closed_40_to_60ms_range() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"CONTENDED"], [b"CONTENDED"]])
    lock = new_lock(commands, clock, jitter=0.04)

    assert lock.try_acquire("job", options(wait=0.04)) is None

    assert clock.sleeps == [0.04]
    assert [call[0] for call in commands.calls] == ["evalsha"]


def test_uncertain_acquire_recovers_matching_owner_without_redispatch() -> None:
    clock = FakeClock()
    commands = FakeCommands(
        evalsha_effects=[TimeoutError("secret")],
        eval_effects=[[b"PRESENT", b"v1:" + b"A" * 32 + b":9"]],
    )

    handle = new_lock(commands, clock).try_acquire("job", options())

    assert handle is not None
    assert handle.lease.fencing_token == 9
    assert [call[0] for call in commands.calls] == ["evalsha", "eval"]
    assert commands.calls[1][1] == RECONCILE_SCRIPT.source


@pytest.mark.parametrize(
    "reconciliation",
    [
        [b"ABSENT"],
        [b"PRESENT", b"v1:" + b"B" * 32 + b":10"],
        [b"CORRUPT"],
        [b"PRESENT", b"bad"],
        TimeoutError("second secret"),
    ],
)
def test_uncertain_acquire_fails_closed_without_redispatch(reconciliation: object) -> None:
    clock = FakeClock()
    commands = FakeCommands(
        evalsha_effects=[TimeoutError("first secret")],
        eval_effects=[reconciliation],
    )

    with pytest.raises(LeaderBackendError, match=r"^leader backend operation failed$") as caught:
        new_lock(commands, clock).try_acquire("job", options())

    assert caught.value.__cause__ is None
    assert [call[0] for call in commands.calls] == ["evalsha", "eval"]


def test_manual_state_supports_acquired_operations_and_release_terminal_no_io() -> None:
    clock = FakeClock()
    commands = FakeCommands(
        evalsha_effects=[
            [b"ACQUIRED", b"7"],
            [b"RENEWED"],
            [b"HELD"],
            [b"HELD"],
            [b"DELETED"],
        ]
    )
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    assert isinstance(handle.renew(), Renewed)
    assert handle.is_held() is True
    handle.assert_held()
    handle.release()
    terminal_call_count = len(commands.calls)

    assert handle.is_held() is False
    assert isinstance(handle.renew(), NotHeld)
    with pytest.raises(LeaderLeaseLostError):
        handle.assert_held()
    with pytest.raises(LeaderReleaseError):
        handle.release()
    assert len(commands.calls) == terminal_call_count


def test_manual_state_probe_mismatch_enters_lost_and_remains_no_io() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"NOT_HELD"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    assert handle.is_held() is False
    terminal_call_count = len(commands.calls)

    assert handle.is_held() is False
    assert isinstance(handle.renew(), NotHeld)
    with pytest.raises(LeaderLeaseLostError):
        handle.assert_held()
    with pytest.raises(LeaderReleaseError):
        handle.release()
    assert len(commands.calls) == terminal_call_count


def test_manual_state_probe_backend_failure_enters_unknown_and_reuses_error() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], TimeoutError("secret")])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    with pytest.raises(LeaderBackendError) as first:
        handle.is_held()
    terminal_calls = len(commands.calls)
    with pytest.raises(LeaderBackendError) as later:
        handle.release()

    assert later.value is first.value
    assert len(commands.calls) == terminal_calls


def test_entry_proof_probes_before_body_and_releases_after_body() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    body_started = False

    with handle:
        body_started = True

    assert body_started is True
    assert len(commands.calls) == 3
    assert handle.is_held() is False


def test_entry_proof_loss_prevents_body_and_never_releases() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"NOT_HELD"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    body_started = False

    with pytest.raises(LeaderLeaseLostError):
        with handle:
            body_started = True

    assert body_started is False
    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha"]


def test_entry_proof_auto_renew_renews_before_body() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.4)
    )
    assert handle is not None

    with handle:
        assert len(commands.calls) == 2

    assert len(commands.calls) == 3


@pytest.mark.parametrize(
    ("renew_effects", "eval_effects", "expected_trace"),
    [
        ([TimeoutError("secret")], [], ["evalsha"]),
        ([NoScriptError()], [TimeoutError("secret")], ["evalsha", "eval"]),
    ],
)
def test_uncertain_renew_enters_unknown_and_reuses_one_no_io_error(
    renew_effects: list[object],
    eval_effects: list[object],
    expected_trace: list[str],
) -> None:
    clock = FakeClock()
    commands = FakeCommands(
        evalsha_effects=[[b"ACQUIRED", b"7"], *renew_effects],
        eval_effects=eval_effects,
    )
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    outcome = handle.renew()
    assert isinstance(outcome, RenewBackendFailure)
    retained = outcome.cause
    terminal_call_count = len(commands.calls)

    operations = [
        handle.renew,
        handle.is_held,
        handle.assert_held,
        handle.release,
        handle.__enter__,
    ]
    for operation in operations:
        with pytest.raises(LeaderBackendError) as caught:
            operation()
        assert caught.value is retained
    assert len(commands.calls) == terminal_call_count
    assert [call[0] for call in commands.calls[1:]] == expected_trace


@pytest.mark.parametrize(
    (
        "reconciliation",
        "repeat",
        "expected_error",
        "terminal_kind",
        "expected_trace",
    ),
    [
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            [b"NOT_HELD"],
            LeaderReleaseError,
            "lost",
            ["evalsha", "eval", "evalsha"],
        ),
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            [b"CORRUPT"],
            LeaderBackendError,
            "unknown",
            ["evalsha", "eval", "evalsha"],
        ),
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            ValueError("ordinary secret"),
            LeaderBackendError,
            "unknown",
            ["evalsha", "eval", "evalsha"],
        ),
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            TimeoutError("second secret"),
            LeaderReleaseError,
            "unknown",
            ["evalsha", "eval", "evalsha"],
        ),
        ([b"ABSENT"], None, LeaderReleaseError, "unknown", ["evalsha", "eval"]),
        (
            [b"PRESENT", b"v1:" + b"B" * 32 + b":8"],
            None,
            LeaderReleaseError,
            "lost",
            ["evalsha", "eval"],
        ),
        ([b"CORRUPT"], None, LeaderBackendError, "unknown", ["evalsha", "eval"]),
        (
            TimeoutError("reconcile secret"),
            None,
            LeaderBackendError,
            "unknown",
            ["evalsha", "eval"],
        ),
    ],
)
def test_uncertain_release_complete_matrix_never_unconditionally_deletes(
    reconciliation: object,
    repeat: object | None,
    expected_error: type[Exception],
    terminal_kind: str,
    expected_trace: list[str],
) -> None:
    clock = FakeClock()
    evalsha_effects: list[object] = [[b"ACQUIRED", b"7"], TimeoutError("first secret")]
    if repeat is not None:
        evalsha_effects.append(repeat)
    commands = FakeCommands(evalsha_effects=evalsha_effects, eval_effects=[reconciliation])
    handle = new_lock(commands, clock).try_acquire("job", options(minimum=0.5))
    assert handle is not None

    with pytest.raises(expected_error) as caught:
        handle.release()
    terminal_calls = len(commands.calls)

    if terminal_kind == "lost":
        assert handle.is_held() is False
    else:
        with pytest.raises(expected_error) as later:
            handle.is_held()
        assert later.value is caught.value
    assert len(commands.calls) == terminal_calls
    assert [call[0] for call in commands.calls[1:]] == expected_trace


@pytest.mark.parametrize("success", [[b"DELETED"], [b"MIN_TTL_APPLIED"]])
def test_uncertain_release_repeats_same_owner_with_original_instant_remaining_ttl(
    success: object,
) -> None:
    clock = FakeClock()

    def advance_after_reconcile(kind: str) -> None:
        if kind == "eval":
            clock.now += 100_000_000

    commands = FakeCommands(
        evalsha_effects=[[b"ACQUIRED", b"7"], TimeoutError("secret"), success],
        eval_effects=[[b"PRESENT", b"v1:" + b"A" * 32 + b":7"]],
        after_call=advance_after_reconcile,
    )
    handle = new_lock(commands, clock).try_acquire("job", options(minimum=0.5))
    assert handle is not None
    clock.now = 200_000_000

    handle.release()

    release_calls = [call for call in commands.calls if call[0] == "evalsha"][1:]
    assert release_calls[0][-1] == b"300"
    assert release_calls[1][-1] == b"200"
    assert handle.is_held() is False


def test_uncertain_release_minimum_ttl_starts_at_successful_acquire_attempt() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"CONTENDED"], [b"ACQUIRED", b"7"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire("job", options(wait=0.1, minimum=0.5))
    assert handle is not None
    assert clock.now == 50_000_000
    clock.now = 200_000_000

    handle.release()

    assert commands.calls[-1][-1] == b"350"


@pytest.mark.parametrize(
    ("reconciliation", "repeat", "expected_error"),
    [
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            [b"NOT_HELD"],
            LeaderLeaseLostError,
        ),
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            [b"CORRUPT"],
            LeaderBackendError,
        ),
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            TimeoutError("second secret"),
            LeaderReleaseError,
        ),
        ([b"ABSENT"], None, LeaderReleaseError),
        (
            [b"PRESENT", b"v1:" + b"B" * 32 + b":8"],
            None,
            LeaderLeaseLostError,
        ),
        ([b"CORRUPT"], None, LeaderBackendError),
        (TimeoutError("reconcile secret"), None, LeaderBackendError),
    ],
)
def test_uncertain_release_scoped_cleanup_matrix(
    reconciliation: object,
    repeat: object | None,
    expected_error: type[Exception],
) -> None:
    clock = FakeClock()
    effects: list[object] = [
        [b"ACQUIRED", b"7"],
        [b"HELD"],
        TimeoutError("first secret"),
    ]
    if repeat is not None:
        effects.append(repeat)
    commands = FakeCommands(evalsha_effects=effects, eval_effects=[reconciliation])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    entered = handle.__enter__()

    with pytest.raises(expected_error):
        entered.__exit__(None, None, None)


def test_uncertain_release_scoped_same_owner_repeat_success() -> None:
    clock = FakeClock()
    commands = FakeCommands(
        evalsha_effects=[
            [b"ACQUIRED", b"7"],
            [b"HELD"],
            TimeoutError("first secret"),
            [b"DELETED"],
        ],
        eval_effects=[[b"PRESENT", b"v1:" + b"A" * 32 + b":7"]],
    )
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    with handle:
        pass

    assert handle.is_held() is False
