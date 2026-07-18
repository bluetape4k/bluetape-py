from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from bluetape.leader import (
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderExecutionError,
    LeaderLeaseLostError,
    LeaderReleaseError,
    NotHeld,
    RenewBackendFailure,
)
from bluetape.leader.redis._async_lock import AsyncRedisDistributedLock
from bluetape.leader.redis._support import _Timing


class AsyncClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


class AsyncCommands:
    def __init__(
        self,
        *,
        evalsha_effects: list[object] | None = None,
        eval_effects: list[object] | None = None,
    ) -> None:
        self.evalsha_effects = list(evalsha_effects or [])
        self.eval_effects = list(eval_effects or [])
        self.calls: list[tuple[object, ...]] = []

    async def evalsha(self, sha1: str, numkeys: int, *values: bytes) -> object:
        self.calls.append(("evalsha", sha1, numkeys, *values))
        return await self._next(self.evalsha_effects)

    async def eval(self, source: str, numkeys: int, *values: bytes) -> object:
        self.calls.append(("eval", source, numkeys, *values))
        return await self._next(self.eval_effects)

    @staticmethod
    async def _next(effects: list[object]) -> object:
        effect = effects.pop(0)
        if isinstance(effect, AsyncBlockingEffect):
            return await effect.resolve()
        if isinstance(effect, BaseException):
            raise effect
        return effect


class AsyncBlockingEffect:
    def __init__(self, response: object) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.response = response

    async def resolve(self) -> object:
        self.entered.set()
        await self.release.wait()
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


def new_lock(commands: AsyncCommands, clock: AsyncClock) -> AsyncRedisDistributedLock:
    return AsyncRedisDistributedLock._for_test(
        commands,
        TIMING,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        jitter=lambda: 0.05,
        token_factory=lambda: "A" * 32,
    )


@pytest.mark.asyncio
async def test_async_zero_wait_acquires_with_one_awaited_dispatch() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"]])

    handle = await new_lock(commands, clock).try_acquire("job", options())

    assert handle is not None
    assert handle.lease.fencing_token == 7
    assert [call[0] for call in commands.calls] == ["evalsha"]
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_async_zero_wait_contention_dispatches_once_without_sleep() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"CONTENDED"]])

    assert await new_lock(commands, clock).try_acquire("job", options()) is None

    assert [call[0] for call in commands.calls] == ["evalsha"]
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_async_uncertain_acquire_reconciles_matching_owner_once() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(
        evalsha_effects=[TimeoutError("secret")],
        eval_effects=[[b"PRESENT", b"v1:" + b"A" * 32 + b":9"]],
    )

    handle = await new_lock(commands, clock).try_acquire("job", options())

    assert handle is not None
    assert handle.lease.fencing_token == 9
    assert [call[0] for call in commands.calls] == ["evalsha", "eval"]


@pytest.mark.asyncio
async def test_async_uncertain_acquire_absent_fails_without_redispatch() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[TimeoutError("secret")], eval_effects=[[b"ABSENT"]])

    with pytest.raises(LeaderBackendError):
        await new_lock(commands, clock).try_acquire("job", options())

    assert [call[0] for call in commands.calls] == ["evalsha", "eval"]


@pytest.mark.asyncio
async def test_async_state_and_entry_delays_proof_until_scope() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"DELETED"]])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    assert len(commands.calls) == 1
    body_started = False

    async with handle:
        body_started = True

    assert body_started is True
    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "evalsha"]


@pytest.mark.asyncio
async def test_async_state_and_entry_release_is_terminal_without_io() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"DELETED"]])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    await handle.release()
    terminal_calls = len(commands.calls)

    assert await handle.is_held() is False
    assert isinstance(await handle.renew(), NotHeld)
    with pytest.raises(LeaderLeaseLostError):
        await handle.assert_held()
    with pytest.raises(LeaderReleaseError):
        await handle.release()
    assert len(commands.calls) == terminal_calls


@pytest.mark.asyncio
async def test_async_uncertain_renew_enters_unknown_without_redispatch() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], TimeoutError("renew marker")])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    outcome = await handle.renew()
    assert isinstance(outcome, RenewBackendFailure)
    retained = outcome.cause
    terminal_calls = len(commands.calls)

    for operation in (
        handle.renew,
        handle.is_held,
        handle.assert_held,
        handle.release,
        handle.__aenter__,
    ):
        with pytest.raises(LeaderBackendError) as caught:
            await operation()
        assert caught.value is retained
    assert len(commands.calls) == terminal_calls
    assert [call[0] for call in commands.calls[1:]] == ["evalsha"]


@pytest.mark.parametrize(
    ("reconciliation", "repeat", "expected_error", "terminal_kind", "trace"),
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
            ValueError("ordinary"),
            LeaderBackendError,
            "unknown",
            ["evalsha", "eval", "evalsha"],
        ),
        (
            [b"PRESENT", b"v1:" + b"A" * 32 + b":7"],
            TimeoutError("second"),
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
            TimeoutError("reconcile"),
            None,
            LeaderBackendError,
            "unknown",
            ["evalsha", "eval"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_async_uncertain_release_complete_matrix(
    reconciliation: object,
    repeat: object | None,
    expected_error: type[Exception],
    terminal_kind: str,
    trace: list[str],
) -> None:
    clock = AsyncClock()
    effects: list[object] = [[b"ACQUIRED", b"7"], TimeoutError("first")]
    if repeat is not None:
        effects.append(repeat)
    commands = AsyncCommands(evalsha_effects=effects, eval_effects=[reconciliation])
    handle = await new_lock(commands, clock).try_acquire("job", options(minimum=0.5))
    assert handle is not None

    with pytest.raises(expected_error) as caught:
        await handle.release()
    terminal_calls = len(commands.calls)

    if terminal_kind == "lost":
        assert await handle.is_held() is False
    else:
        with pytest.raises(expected_error) as later:
            await handle.is_held()
        assert later.value is caught.value
    assert len(commands.calls) == terminal_calls
    assert [call[0] for call in commands.calls[1:]] == trace


@pytest.mark.asyncio
async def test_async_uncertain_release_same_owner_repeats_once_with_remaining_ttl() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(
        evalsha_effects=[[b"ACQUIRED", b"7"], TimeoutError("first"), [b"DELETED"]],
        eval_effects=[[b"PRESENT", b"v1:" + b"A" * 32 + b":7"]],
    )
    handle = await new_lock(commands, clock).try_acquire("job", options(minimum=0.5))
    assert handle is not None
    clock.now = 0.2

    await handle.release()

    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "eval", "evalsha"]
    assert commands.calls[1][-1] == b"300"
    assert commands.calls[3][-1] == b"300"
    assert await handle.is_held() is False


@pytest.mark.asyncio
async def test_renew_task_lifecycle_cancels_stall_by_absolute_terminal_deadline() -> None:
    clock = AsyncClock()
    stalled = AsyncBlockingEffect([b"RENEWED"])
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"RENEWED"], stalled])
    handle = await new_lock(commands, clock).try_acquire(
        "job", options(auto_renew=True, renew_interval=0.01)
    )
    assert handle is not None
    entered = await handle.__aenter__()
    await asyncio.wait_for(stalled.entered.wait(), 0.2)
    started = asyncio.get_running_loop().time()

    with pytest.raises(LeaderBackendError):
        await entered.__aexit__(None, None, None)

    assert asyncio.get_running_loop().time() - started < TIMING.renew + 0.15
    assert handle._renew_task is not None and handle._renew_task.done()
    assert handle._cleanup_task is None
    assert [call[0] for call in commands.calls] == ["evalsha", "evalsha", "evalsha"]


@pytest.mark.asyncio
async def test_incoming_cancellation_waits_for_retained_cleanup_task() -> None:
    clock = AsyncClock()
    blocked_release = AsyncBlockingEffect([b"DELETED"])
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], blocked_release])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    observed: list[asyncio.CancelledError] = []

    async def owner() -> None:
        try:
            async with handle:
                pass
        except asyncio.CancelledError as error:
            observed.append(error)
            raise

    task = asyncio.create_task(owner())
    await asyncio.wait_for(blocked_release.entered.wait(), 0.2)
    task.cancel("caller marker")
    await asyncio.sleep(0)
    assert task.done() is False
    blocked_release.release.set()

    with pytest.raises(asyncio.CancelledError) as caught:
        await task

    assert observed == [caught.value]
    assert handle._cleanup_task is not None and handle._cleanup_task.done()
    assert await handle.is_held() is False


@pytest.mark.parametrize("same_turn_owned_cancel", [False, True])
@pytest.mark.asyncio
async def test_repeated_cancellation_keeps_first_owner_cancel_and_same_task(
    same_turn_owned_cancel: bool,
) -> None:
    clock = AsyncClock()
    blocked_release = AsyncBlockingEffect([b"DELETED"])
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], blocked_release])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None

    async def owner() -> None:
        async with handle:
            pass

    task = asyncio.create_task(owner())
    await asyncio.wait_for(blocked_release.entered.wait(), 0.2)
    cleanup_task = handle._cleanup_task
    assert cleanup_task is not None
    task.cancel("first owner cancel")
    if same_turn_owned_cancel:
        cleanup_task.cancel("owned cancel")
    await asyncio.sleep(0)
    task.cancel("second owner cancel")
    if not same_turn_owned_cancel:
        assert task.done() is False
        assert handle._cleanup_task is cleanup_task
        blocked_release.release.set()

    with pytest.raises(asyncio.CancelledError) as caught:
        await task

    assert caught.value.args == ("first owner cancel",)
    assert handle._cleanup_task is cleanup_task and cleanup_task.done()
    if same_turn_owned_cancel:
        terminal_calls = len(commands.calls)
        with pytest.raises(LeaderBackendError):
            await handle.is_held()
        assert len(commands.calls) == terminal_calls
    else:
        assert await handle.is_held() is False


@pytest.mark.asyncio
async def test_release_deadline_cancels_retained_task_and_leaves_zero_pending() -> None:
    clock = AsyncClock()
    stalled = AsyncBlockingEffect([b"DELETED"])
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], stalled])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    entered = await handle.__aenter__()
    exit_task = asyncio.create_task(entered.__aexit__(None, None, None))
    await asyncio.wait_for(stalled.entered.wait(), 0.2)
    started = asyncio.get_running_loop().time()

    with pytest.raises(LeaderBackendError) as caught:
        await exit_task

    assert asyncio.get_running_loop().time() - started < TIMING.release + 0.15
    assert handle._cleanup_task is not None and handle._cleanup_task.done()
    terminal_calls = len(commands.calls)
    with pytest.raises(LeaderBackendError) as later:
        await handle.release()
    assert later.value is caught.value
    assert len(commands.calls) == terminal_calls


@pytest.mark.asyncio
async def test_async_context_failure_matrix_composes_action_and_lifecycle() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"NOT_HELD"]])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    marker = ValueError("caller marker")

    with pytest.raises(LeaderExecutionError) as caught:
        async with handle:
            raise marker

    assert caught.value.action_cause is marker
    assert isinstance(caught.value.lifecycle_cause, LeaderLeaseLostError)


@pytest.mark.asyncio
async def test_async_context_failure_matrix_process_control_remains_primary() -> None:
    clock = AsyncClock()
    commands = AsyncCommands(evalsha_effects=[[b"ACQUIRED", b"7"], [b"HELD"], [b"CORRUPT"]])
    handle = await new_lock(commands, clock).try_acquire("job", options())
    assert handle is not None
    marker = KeyboardInterrupt("caller marker")
    caught: BaseException | None = None

    try:
        async with handle:
            raise marker
    except BaseException as error:
        caught = error

    assert caught is marker
    assert marker.__notes__ == ["leader lifecycle cleanup failed"]
