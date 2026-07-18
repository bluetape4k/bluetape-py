from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Callable
from datetime import timedelta

import pytest
from bluetape.leader import (
    InvalidLeaderOptionsError,
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderExecutionError,
    LeaderLeaseLostError,
    LeaderReleaseError,
    NotHeld,
    RenewBackendFailure,
    Renewed,
)
from bluetape.leader.redis import RedisDistributedLock
from bluetape.leader.redis._scripts import ACQUIRE_SCRIPT, RECONCILE_SCRIPT, RELEASE_SCRIPT
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


class SequencedClock(FakeClock):
    def __init__(self, samples: list[int]) -> None:
        super().__init__()
        self._samples = iter(samples)

    def monotonic_ns(self) -> int:
        return next(self._samples)

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.sleeps.append(seconds)


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
        self.close_calls = 0

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

    def close(self) -> None:
        self.close_calls += 1

    @staticmethod
    def _next(effects: list[object]) -> object:
        effect = effects.pop(0)
        if isinstance(effect, BlockingEffect):
            return effect.resolve()
        if isinstance(effect, BaseException):
            raise effect
        return effect


class WorkerCrash(BaseException):
    pass


class BlockingEffect:
    def __init__(self, response: object = None) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.response = [b"RENEWED"] if response is None else response

    def resolve(self) -> object:
        self.entered.set()
        if not self.release.wait(2.0):
            raise RuntimeError("test failed to unblock worker")
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


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


def test_repr_is_redacted_and_borrowed_client_is_never_closed() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"DELETED"]])
    lock = new_lock(commands, clock, token="S" * 32)

    handle = lock.try_acquire("secret-lock-name", options())
    assert handle is not None
    handle.release()

    assert repr(lock) == "RedisDistributedLock(<redacted>)"
    assert repr(handle) == "_RedisLockLease(<redacted>)"
    assert "secret-lock-name" not in repr(lock) + repr(handle)
    assert "S" * 32 not in repr(lock) + repr(handle)
    assert commands.close_calls == 0


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


def test_contention_retry_never_sleeps_negative_when_deadline_crosses_samples() -> None:
    clock = SequencedClock([0, 0, 99_999_999, 100_000_001])
    commands = FakeCommands(evalsha_effects=[[b"CONTENDED"]])
    lock = new_lock(commands, clock)

    assert lock.try_acquire("job", options(wait=0.1)) is None

    assert clock.sleeps == [1e-09]
    assert [call[0] for call in commands.calls] == ["evalsha"]


def test_contention_retry_dispatch_uses_the_deadline_check_sample() -> None:
    clock = SequencedClock([0, 0, 50_000_000, 99_999_999, 100_000_001, 100_000_001])
    dispatch_samples: list[int] = []
    commands = FakeCommands(
        evalsha_effects=[[b"CONTENDED"], [b"CONTENDED"]],
        after_call=lambda _: dispatch_samples.append(clock.now),
    )

    original_monotonic_ns = clock.monotonic_ns

    def observed_monotonic_ns() -> int:
        sample = original_monotonic_ns()
        clock.now = sample
        return sample

    lock = RedisDistributedLock._for_test(
        commands,
        TIMING,
        monotonic_ns=observed_monotonic_ns,
        sleep=clock.sleep,
        jitter=lambda: 0.05,
        token_factory=lambda: "A" * 32,
    )

    assert lock.try_acquire("job", options(wait=0.1)) is None

    assert dispatch_samples == [0, 99_999_999]
    assert all(sample < 100_000_000 for sample in dispatch_samples)


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


def test_noscript_acquire_response_loss_reconciles_with_exact_trace() -> None:
    clock = FakeClock()
    commands = FakeCommands(
        evalsha_effects=[NoScriptError()],
        eval_effects=[
            TimeoutError("raw response marker"),
            [b"PRESENT", b"v1:" + b"A" * 32 + b":9"],
        ],
    )

    handle = new_lock(commands, clock).try_acquire("job", options())

    assert handle is not None
    assert handle.lease.fencing_token == 9
    assert [call[0] for call in commands.calls] == ["evalsha", "eval", "eval"]
    assert commands.calls[1][1] == ACQUIRE_SCRIPT.source
    assert commands.calls[2][1] == RECONCILE_SCRIPT.source


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


@pytest.mark.parametrize("blocked_operation", ["renew", "release"])
def test_local_lock_not_held_across_blocked_redis_io(blocked_operation: str) -> None:
    clock = FakeClock()
    blocked = BlockingEffect([b"RENEWED"] if blocked_operation == "renew" else [b"DELETED"])
    if blocked_operation == "renew":
        effects: list[object] = [[b"ACQUIRED", b"7"], blocked, [b"HELD"], [b"DELETED"]]
    else:
        effects = [[b"ACQUIRED", b"7"], blocked, [b"RENEWED"]]
    commands = FakeCommands(evalsha_effects=effects)
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    blocked_results: list[object] = []
    concurrent_results: list[object] = []
    concurrent_done = threading.Event()

    def run_blocked() -> None:
        operation = handle.renew if blocked_operation == "renew" else handle.release
        try:
            blocked_results.append(operation())
        except BaseException as error:
            blocked_results.append(error)

    def run_concurrent() -> None:
        try:
            operation = handle.is_held if blocked_operation == "renew" else handle.renew
            concurrent_results.append(operation())
        except BaseException as error:
            concurrent_results.append(error)
        finally:
            concurrent_done.set()

    owner = threading.Thread(target=run_blocked)
    contender = threading.Thread(target=run_concurrent)
    owner.start()
    assert blocked.entered.wait(0.5)
    contender.start()
    completed_without_unblocking = concurrent_done.wait(0.1)
    blocked.release.set()
    owner.join(0.5)
    contender.join(0.5)

    assert completed_without_unblocking is True
    assert not owner.is_alive() and not contender.is_alive()
    if blocked_operation == "renew":
        assert isinstance(blocked_results[0], Renewed)
        assert concurrent_results == [True]
        handle.release()
    else:
        assert blocked_results == [None]
        assert isinstance(concurrent_results[0], Renewed)
        assert handle.is_held() is False


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
            LeaderLeaseLostError,
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
            LeaderLeaseLostError,
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
def test_uncertain_release_scoped_cleanup_matrix(
    reconciliation: object,
    repeat: object | None,
    expected_error: type[Exception],
    terminal_kind: str,
    expected_trace: list[str],
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

    with pytest.raises(expected_error) as caught:
        entered.__exit__(None, None, None)
    terminal_calls = len(commands.calls)

    if terminal_kind == "lost":
        assert handle.is_held() is False
    else:
        with pytest.raises(expected_error) as later:
            handle.is_held()
        assert later.value is caught.value
    assert len(commands.calls) == terminal_calls
    assert [call[0] for call in commands.calls[2:]] == expected_trace


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


@pytest.mark.parametrize("scoped", [False, True])
@pytest.mark.parametrize("reconciliation", ["absent", "same_owner"])
def test_uncertain_release_noscript_eval_response_loss_exact_trace(
    scoped: bool,
    reconciliation: str,
) -> None:
    clock = FakeClock()
    evalsha_effects: list[object] = [[b"ACQUIRED", b"7"]]
    if scoped:
        evalsha_effects.append([b"HELD"])
    evalsha_effects.append(NoScriptError())
    if reconciliation == "same_owner":
        evalsha_effects.append([b"DELETED"])
        reconcile_effect: object = [b"PRESENT", b"v1:" + b"A" * 32 + b":7"]
    else:
        reconcile_effect = [b"ABSENT"]
    commands = FakeCommands(
        evalsha_effects=evalsha_effects,
        eval_effects=[TimeoutError("release response marker"), reconcile_effect],
    )
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    entered = handle.__enter__() if scoped else None
    before = len(commands.calls)

    if reconciliation == "absent":
        with pytest.raises(LeaderReleaseError) as caught:
            entered.__exit__(None, None, None) if entered is not None else handle.release()
        expected_trace = ["evalsha", "eval", "eval"]
    else:
        entered.__exit__(None, None, None) if entered is not None else handle.release()
        expected_trace = ["evalsha", "eval", "eval", "evalsha"]

    release_calls = commands.calls[before:]
    assert [call[0] for call in release_calls] == expected_trace
    assert release_calls[1][1] == RELEASE_SCRIPT.source
    assert release_calls[2][1] == RECONCILE_SCRIPT.source
    terminal_calls = len(commands.calls)
    if reconciliation == "same_owner":
        assert handle.is_held() is False
    else:
        with pytest.raises(LeaderReleaseError) as later:
            handle.is_held()
        assert later.value is caught.value
    assert len(commands.calls) == terminal_calls


def test_worker_lifecycle_uses_one_named_non_daemon_thread_and_joins_before_release() -> None:
    clock = FakeClock()
    worker_renewed = threading.Event()

    def observe_call(kind: str) -> None:
        if kind == "evalsha" and len(commands.calls) == 3:
            worker_renewed.set()

    commands = FakeCommands(
        evalsha_effects=[
            [b"ACQUIRED", b"7"],
            [b"RENEWED"],
            [b"RENEWED"],
            [b"DELETED"],
        ],
        after_call=observe_call,
    )
    handle = new_lock(commands, clock).try_acquire(
        "job", options(lease=1.0, auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None

    with handle:
        assert worker_renewed.wait(0.5)
        workers = [
            thread
            for thread in threading.enumerate()
            if thread.name.startswith("bluetape-leader-renew-")
        ]
        assert len(workers) == 1
        assert workers[0].daemon is False

    assert not any(
        thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate()
    )
    assert [call[0] for call in commands.calls] == [
        "evalsha",
        "evalsha",
        "evalsha",
        "evalsha",
    ]


def test_worker_lifecycle_rejects_unprovable_renew_timing_before_io() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"]])

    with pytest.raises(InvalidLeaderOptionsError):
        new_lock(commands, clock).try_acquire(
            "job", options(lease=1.0, auto_renew=True, renew_interval=0.03)
        )

    assert commands.calls == []


def test_worker_start_failure_proves_no_worker_before_owner_checked_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None

    def fail_start(self: threading.Thread) -> None:
        raise RuntimeError("secret start marker")

    monkeypatch.setattr(threading.Thread, "start", fail_start)

    with pytest.raises(LeaderBackendError, match=r"^leader backend operation failed$") as caught:
        handle.__enter__()

    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert "secret start marker" not in "".join(traceback.format_exception(caught.value))
    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "evalsha"]
    assert not any(
        thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate()
    )
    assert handle.is_held() is False


def test_worker_start_cleanup_failure_wins_and_enters_sanitized_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], [b"CORRUPT"]])
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None

    def fail_start(self: threading.Thread) -> None:
        raise RuntimeError("raw worker start marker")

    monkeypatch.setattr(threading.Thread, "start", fail_start)

    with pytest.raises(LeaderBackendError) as caught:
        handle.__enter__()
    terminal_calls = len(commands.calls)

    with pytest.raises(LeaderBackendError) as later:
        handle.is_held()
    assert later.value is caught.value
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert "raw worker start marker" not in "".join(traceback.format_exception(caught.value))
    assert len(commands.calls) == terminal_calls
    assert commands.close_calls == 0
    assert not any(
        thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate()
    )


def test_worker_crash_is_sanitized_unknown_and_never_releases() -> None:
    clock = FakeClock()
    crashed = threading.Event()

    def observe_call(kind: str) -> None:
        if kind == "evalsha" and len(commands.calls) == 3:
            crashed.set()

    commands = FakeCommands(
        evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], WorkerCrash()],
        after_call=observe_call,
    )
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None

    with pytest.raises(LeaderBackendError, match=r"^leader backend operation failed$"):
        with handle:
            assert crashed.wait(0.5)

    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "evalsha"]
    with pytest.raises(LeaderBackendError):
        handle.is_held()


def test_worker_join_deadline_returns_unknown_without_release_and_fixture_joins() -> None:
    clock = FakeClock()
    blocked = BlockingEffect()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], blocked])
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None
    retained: LeaderBackendError | None = None
    worker: threading.Thread | None = None

    try:
        entered = handle.__enter__()
        assert blocked.entered.wait(0.5)
        worker = next(
            thread
            for thread in threading.enumerate()
            if thread.name.startswith("bluetape-leader-renew-")
        )
        started = time.monotonic()
        with pytest.raises(LeaderBackendError) as caught:
            entered.__exit__(None, None, None)
        retained = caught.value
        assert time.monotonic() - started < 0.3
        assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "evalsha"]
    finally:
        blocked.release.set()
        if worker is not None:
            worker.join(0.5)

    assert worker is not None and not worker.is_alive()
    with pytest.raises(LeaderBackendError) as later:
        handle.is_held()
    assert later.value is retained
    assert len(commands.calls) == 3


@pytest.mark.parametrize("late_effect", [[b"NOT_HELD"], TimeoutError("late-renew-backend-marker")])
def test_worker_join_deadline_unknown_cannot_be_overwritten_by_late_renew(
    late_effect: object,
) -> None:
    clock = FakeClock()
    blocked = BlockingEffect(late_effect)
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], blocked])
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None
    worker: threading.Thread | None = None
    retained: LeaderBackendError | None = None

    try:
        entered = handle.__enter__()
        assert blocked.entered.wait(0.5)
        worker = next(
            thread
            for thread in threading.enumerate()
            if thread.name.startswith("bluetape-leader-renew-")
        )
        with pytest.raises(LeaderBackendError) as caught:
            entered.__exit__(None, None, None)
        retained = caught.value
    finally:
        blocked.release.set()
        if worker is not None:
            worker.join(0.5)

    assert worker is not None and not worker.is_alive()
    assert retained is not None
    assert retained.__context__ is None
    assert retained.__cause__ is None
    assert "late-renew-backend-marker" not in "".join(traceback.format_exception(retained))
    terminal_calls = len(commands.calls)
    operations = [
        handle.renew,
        handle.is_held,
        handle.assert_held,
        handle.release,
        handle.__enter__,
    ]
    for operation in operations:
        with pytest.raises(LeaderBackendError) as later:
            operation()
        assert later.value is retained
        assert later.value.__context__ is None
        assert later.value.__cause__ is None
        assert "late-renew-backend-marker" not in "".join(traceback.format_exception(later.value))
    assert len(commands.calls) == terminal_calls


@pytest.mark.parametrize("operation", ["acquire", "probe", "release", "uncertain_release"])
def test_exception_graph_sanitized_errors_drop_raw_backend_graph(operation: str) -> None:
    clock = FakeClock()
    secret = "raw" + "-backend-marker"
    if operation == "acquire":
        commands = FakeCommands(evalsha_effects=[TimeoutError(secret)], eval_effects=[[b"ABSENT"]])

        def call() -> object:
            return new_lock(commands, clock).try_acquire("job", options())
    else:
        second: object = TimeoutError(secret)
        eval_effects: list[object] = []
        if operation == "probe":
            effects = [[b"ACQUIRED", b"7"], second]
        elif operation == "release":
            effects = [[b"ACQUIRED", b"7"], ValueError(secret)]
        else:
            effects = [[b"ACQUIRED", b"7"], second]
            eval_effects = [TimeoutError(secret)]
        commands = FakeCommands(evalsha_effects=effects, eval_effects=eval_effects)
        handle = new_lock(commands, clock).try_acquire("job", options())
        assert handle is not None
        call = handle.is_held if operation == "probe" else handle.release

    with pytest.raises(LeaderBackendError) as caught:
        call()

    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert secret not in "".join(traceback.format_exception(caught.value))


def test_exception_graph_renew_failure_is_retained_without_raw_graph() -> None:
    clock = FakeClock()
    secret = "raw" + "-renew-marker"
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], TimeoutError(secret)])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    outcome = handle.renew()
    assert isinstance(outcome, RenewBackendFailure)
    with pytest.raises(LeaderBackendError) as caught:
        handle.is_held()

    assert caught.value is outcome.cause
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert secret not in "".join(traceback.format_exception(caught.value))


def test_state_operation_matrix_reentry_is_rejected_without_disturbing_scope() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    entered = handle.__enter__()
    with pytest.raises(LeaderLeaseLostError):
        handle.__enter__()
    entered.__exit__(None, None, None)

    assert len(commands.calls) == 3


def test_state_operation_matrix_concurrent_first_entry_has_one_winner() -> None:
    clock = FakeClock()
    proof = BlockingEffect([b"HELD"])
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], proof, [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    results: list[object] = []

    def enter() -> None:
        try:
            results.append(handle.__enter__())
        except BaseException as error:
            results.append(error)

    first = threading.Thread(target=enter)
    second = threading.Thread(target=enter)
    first.start()
    assert proof.entered.wait(0.5)
    second.start()
    proof.release.set()
    first.join(0.5)
    second.join(0.5)

    assert sum(result is handle for result in results) == 1
    assert sum(isinstance(result, LeaderLeaseLostError) for result in results) == 1
    handle.__exit__(None, None, None)


def test_state_operation_matrix_manual_release_makes_later_exit_idempotent() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    entered = handle.__enter__()
    entered.release()
    terminal_calls = len(commands.calls)
    entered.__exit__(None, None, None)

    assert entered.is_held() is False
    assert len(commands.calls) == terminal_calls


@pytest.mark.parametrize("state", ["ACQUIRED", "ENTERED", "LOST", "RELEASED", "UNKNOWN"])
@pytest.mark.parametrize("operation", ["renew", "probe", "assert", "release", "enter", "exit"])
def test_state_operation_matrix_all_states_and_operations(
    state: str,
    operation: str,
) -> None:
    clock = FakeClock()
    effects: list[object] = [[b"ACQUIRED", b"7"]]
    if state == "ENTERED":
        effects.append([b"HELD"])
    elif state == "LOST":
        effects.append([b"NOT_HELD"])
    elif state == "RELEASED":
        effects.append([b"DELETED"])
    elif state == "UNKNOWN":
        effects.append(TimeoutError("state setup marker"))

    active_state = state in ("ACQUIRED", "ENTERED")
    if active_state and operation == "renew":
        effects.append([b"RENEWED"])
    elif active_state and operation in ("probe", "assert"):
        effects.append([b"HELD"])
    elif active_state and operation in ("release", "exit"):
        effects.append([b"DELETED"])
    elif state == "ACQUIRED" and operation == "enter":
        effects.append([b"HELD"])

    commands = FakeCommands(evalsha_effects=effects)
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    retained: LeaderBackendError | None = None
    if state == "ENTERED":
        handle.__enter__()
    elif state == "LOST":
        assert handle.is_held() is False
    elif state == "RELEASED":
        handle.release()
    elif state == "UNKNOWN":
        with pytest.raises(LeaderBackendError) as setup_failure:
            handle.is_held()
        retained = setup_failure.value
    before = len(commands.calls)

    call: Callable[[], object]
    if operation == "renew":
        call = handle.renew
    elif operation == "probe":
        call = handle.is_held
    elif operation == "assert":
        call = handle.assert_held
    elif operation == "release":
        call = handle.release
    elif operation == "enter":
        call = handle.__enter__
    else:

        def call() -> object:
            return handle.__exit__(None, None, None)

    if state == "UNKNOWN":
        with pytest.raises(LeaderBackendError) as caught:
            call()
        assert caught.value is retained
        expected_state = "UNKNOWN"
        expected_io = 0
    elif state in ("LOST", "RELEASED"):
        if operation == "renew":
            assert isinstance(call(), NotHeld)
        elif operation == "probe":
            assert call() is False
        elif operation in ("assert", "enter") or (operation == "exit" and state == "LOST"):
            with pytest.raises(LeaderLeaseLostError):
                call()
        elif operation == "release":
            with pytest.raises(LeaderReleaseError):
                call()
        else:
            assert call() is None
        expected_state = state
        expected_io = 0
    elif operation == "renew":
        assert isinstance(call(), Renewed)
        expected_state = state
        expected_io = 1
    elif operation == "probe":
        assert call() is True
        expected_state = state
        expected_io = 1
    elif operation == "assert":
        assert call() is None
        expected_state = state
        expected_io = 1
    elif operation == "enter" and state == "ENTERED":
        with pytest.raises(LeaderLeaseLostError):
            call()
        expected_state = "ENTERED"
        expected_io = 0
    else:
        assert call() is handle if operation == "enter" else call() is None
        expected_state = "ENTERED" if operation == "enter" else "RELEASED"
        expected_io = 1

    assert handle._state == expected_state
    assert len(commands.calls) - before == expected_io
    assert not any(
        thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate()
    )


@pytest.mark.parametrize(
    "marker",
    [KeyboardInterrupt("secret"), SystemExit("secret"), GeneratorExit("secret")],
)
@pytest.mark.parametrize("release_status", [[b"DELETED"], [b"NOT_HELD"]])
def test_process_control_exact_object_survives_cleanup(
    marker: BaseException,
    release_status: object,
) -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], release_status])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    caught: BaseException | None = None
    try:
        with handle:
            raise marker
    except BaseException as error:
        caught = error

    assert caught is marker
    assert len(commands.calls) == 3


@pytest.mark.parametrize(
    "marker",
    [KeyboardInterrupt("secret"), SystemExit("secret"), GeneratorExit("secret")],
)
@pytest.mark.parametrize("cleanup", ["backend", "uncertain"])
def test_process_control_exact_object_survives_backend_and_uncertain_cleanup(
    marker: BaseException,
    cleanup: str,
) -> None:
    clock = FakeClock()
    release_effect: object = (
        [b"CORRUPT"] if cleanup == "backend" else TimeoutError("release marker")
    )
    eval_effects: list[object] = [] if cleanup == "backend" else [[b"ABSENT"]]
    commands = FakeCommands(
        evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], release_effect],
        eval_effects=eval_effects,
    )
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    caught: BaseException | None = None
    try:
        with handle:
            raise marker
    except BaseException as error:
        caught = error

    assert caught is marker
    assert [call[0] for call in commands.calls] == (
        ["evalsha", "evalsha", "evalsha"]
        if cleanup == "backend"
        else ["evalsha", "evalsha", "evalsha", "eval"]
    )


@pytest.mark.parametrize(
    "marker",
    [KeyboardInterrupt("secret"), SystemExit("secret"), GeneratorExit("secret")],
)
@pytest.mark.parametrize("worker_result", [[b"NOT_HELD"], TimeoutError("worker marker")])
def test_process_control_exact_object_survives_auto_renew_worker_cleanup(
    marker: BaseException,
    worker_result: object,
) -> None:
    clock = FakeClock()
    worker_terminal = threading.Event()

    def observe_call(kind: str) -> None:
        if kind == "evalsha" and len(commands.calls) == 3:
            worker_terminal.set()

    commands = FakeCommands(
        evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], worker_result],
        after_call=observe_call,
    )
    handle = new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.1)
    )
    assert handle is not None

    caught: BaseException | None = None
    try:
        with handle:
            assert worker_terminal.wait(0.5)
            raise marker
    except BaseException as error:
        caught = error

    assert caught is marker
    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "evalsha"]
    assert not any(
        thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate()
    )


@pytest.mark.parametrize(
    ("release_status", "lifecycle_type"),
    [
        ([b"NOT_HELD"], LeaderLeaseLostError),
        ([b"CORRUPT"], LeaderBackendError),
    ],
)
def test_context_failure_matrix_composes_action_and_lifecycle_without_masking(
    release_status: object,
    lifecycle_type: type[Exception],
) -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], release_status])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    marker = ValueError("caller-owned secret")

    with pytest.raises(LeaderExecutionError) as caught:
        with handle:
            raise marker

    assert caught.value.action_cause is marker
    assert isinstance(caught.value.lifecycle_cause, lifecycle_type)
    assert repr(caught.value) == "LeaderExecutionError(<redacted>)"


def test_context_failure_matrix_successful_cleanup_preserves_action_object() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"DELETED"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    marker = ValueError("caller-owned secret")

    with pytest.raises(ValueError) as caught:
        with handle:
            raise marker

    assert caught.value is marker


def test_context_failure_matrix_success_with_lost_cleanup_raises_lifecycle() -> None:
    clock = FakeClock()
    commands = FakeCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"NOT_HELD"]])
    handle = new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    with pytest.raises(LeaderLeaseLostError):
        with handle:
            pass


@pytest.mark.parametrize("body_fails", [False, True])
@pytest.mark.parametrize(
    ("cleanup", "lifecycle_type", "expected_trace"),
    [
        ("success", None, ["evalsha", "evalsha", "evalsha"]),
        ("worker_lost", LeaderLeaseLostError, ["evalsha", "evalsha", "evalsha"]),
        ("worker_backend", LeaderBackendError, ["evalsha", "evalsha", "evalsha"]),
        ("release_lost", LeaderLeaseLostError, ["evalsha", "evalsha", "evalsha"]),
        ("release_backend", LeaderBackendError, ["evalsha", "evalsha", "evalsha"]),
        (
            "uncertain_release",
            LeaderReleaseError,
            ["evalsha", "evalsha", "evalsha", "eval"],
        ),
    ],
)
def test_context_failure_matrix_full_body_and_lifecycle_precedence(
    body_fails: bool,
    cleanup: str,
    lifecycle_type: type[Exception] | None,
    expected_trace: list[str],
) -> None:
    clock = FakeClock()
    worker_terminal = threading.Event()

    def observe_call(kind: str) -> None:
        if cleanup.startswith("worker_") and kind == "evalsha" and len(commands.calls) == 3:
            worker_terminal.set()

    eval_effects: list[object] = []
    if cleanup == "worker_lost":
        effects: list[object] = [[b"ACQUIRED", b"7"], [b"RENEWED"], [b"NOT_HELD"]]
    elif cleanup == "worker_backend":
        effects = [[b"ACQUIRED", b"7"], [b"RENEWED"], TimeoutError("worker marker")]
    elif cleanup == "success":
        effects = [[b"ACQUIRED", b"7"], [b"HELD"], [b"DELETED"]]
    elif cleanup == "release_lost":
        effects = [[b"ACQUIRED", b"7"], [b"HELD"], [b"NOT_HELD"]]
    elif cleanup == "release_backend":
        effects = [[b"ACQUIRED", b"7"], [b"HELD"], [b"CORRUPT"]]
    else:
        effects = [[b"ACQUIRED", b"7"], [b"HELD"], TimeoutError("release marker")]
        eval_effects = [[b"ABSENT"]]
    commands = FakeCommands(
        evalsha_effects=effects,
        eval_effects=eval_effects,
        after_call=observe_call,
    )
    auto_renew = cleanup.startswith("worker_")
    handle = new_lock(commands, clock).try_acquire(
        "job",
        options(auto_renew=auto_renew, renew_interval=0.1 if auto_renew else None),
    )
    assert handle is not None
    marker = ValueError("caller-owned marker")
    caught: BaseException | None = None

    try:
        with handle:
            if auto_renew:
                assert worker_terminal.wait(0.5)
            if body_fails:
                raise marker
    except BaseException as error:
        caught = error

    if lifecycle_type is None:
        assert caught is marker if body_fails else caught is None
    elif body_fails:
        assert isinstance(caught, LeaderExecutionError)
        assert caught.action_cause is marker
        assert isinstance(caught.lifecycle_cause, lifecycle_type)
    else:
        assert isinstance(caught, lifecycle_type)
    assert [call[0] for call in commands.calls] == expected_trace
    assert not any(
        thread.name.startswith("bluetape-leader-renew-") for thread in threading.enumerate()
    )
