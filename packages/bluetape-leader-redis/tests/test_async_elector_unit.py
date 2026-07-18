from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any

import pytest
from bluetape.leader import (
    ActionFailed,
    AsyncLeaderElector,
    Elected,
    FencedLeaderLease,
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderExecutionError,
    LeaderLeaseLostError,
    LeaderReleaseError,
    Skipped,
)


def sample_lease() -> FencedLeaderLease:
    now = datetime.now(UTC)
    return FencedLeaderLease("7", None, now, now + timedelta(seconds=1), 7)


class FakeHandle:
    def __init__(self, *, exit_error: BaseException | None = None) -> None:
        self._lease = sample_lease()
        self.exit_error = exit_error
        self.entered = False
        self.exits = 0

    @property
    def lease(self) -> FencedLeaderLease:
        assert self.entered
        return self._lease

    async def __aenter__(self) -> FakeHandle:
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.exits += 1
        await asyncio.sleep(0)
        if self.exit_error is not None:
            raise self.exit_error


class FakeLock:
    def __init__(self, handle: FakeHandle | None) -> None:
        self.handle = handle

    async def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> FakeHandle | None:
        del lock_name, options
        return self.handle


def elector_with(handle: FakeHandle | None) -> Any:
    from bluetape.leader.redis import AsyncRedisLeaderElector

    elector = object.__new__(AsyncRedisLeaderElector)
    elector._lock = FakeLock(handle)
    return elector


@pytest.mark.asyncio
async def test_result_distinguishes_none_from_contention_and_types_callback() -> None:
    handle = FakeHandle()
    elector = elector_with(handle)
    seen: list[FencedLeaderLease] = []

    async def action(lease: FencedLeaderLease) -> None:
        assert type(lease) is FencedLeaderLease
        seen.append(lease)

    elected = await elector.run_if_leader_result("job", action)
    skipped = await elector_with(None).run_if_leader_result("job", action)

    assert isinstance(elected, Elected) and elected.value is None
    assert elected.lease is handle.lease and seen == [handle.lease]
    assert isinstance(skipped, Skipped)
    assert handle.exits == 1


@pytest.mark.asyncio
async def test_ordinary_action_failure_is_reported_only_after_safe_cleanup() -> None:
    marker = ValueError("action")
    handle = FakeHandle()

    async def fail(lease: FencedLeaderLease) -> None:
        del lease
        raise marker

    result = await elector_with(handle).run_if_leader_result("job", fail)

    assert isinstance(result, ActionFailed)
    assert result.cause is marker and result.lease is handle.lease
    assert handle.exits == 1


@pytest.mark.asyncio
async def test_simple_api_reraises_original_action_error_after_safe_cleanup() -> None:
    marker = ValueError("action")
    handle = FakeHandle()

    async def fail(lease: FencedLeaderLease) -> None:
        del lease
        raise marker

    with pytest.raises(ValueError) as caught:
        await elector_with(handle).run_if_leader("job", fail)

    assert caught.value is marker
    assert handle.exits == 1


@pytest.mark.parametrize(
    "lifecycle_error",
    [LeaderLeaseLostError(), LeaderBackendError(), LeaderReleaseError()],
)
@pytest.mark.asyncio
async def test_success_never_hides_lifecycle_failure(lifecycle_error: Exception) -> None:
    handle = FakeHandle(exit_error=lifecycle_error)

    async def succeed(lease: FencedLeaderLease) -> int:
        return lease.fencing_token

    with pytest.raises(type(lifecycle_error)) as caught:
        await elector_with(handle).run_if_leader_result("job", succeed)

    assert caught.value is lifecycle_error


@pytest.mark.asyncio
async def test_action_and_lifecycle_failure_raise_sanitized_composite() -> None:
    action_error = ValueError("action")
    lifecycle_error = LeaderBackendError()
    handle = FakeHandle(exit_error=lifecycle_error)

    async def fail(lease: FencedLeaderLease) -> None:
        del lease
        raise action_error

    with pytest.raises(LeaderExecutionError) as caught:
        await elector_with(handle).run_if_leader_result("job", fail)

    assert caught.value.action_cause is action_error
    assert caught.value.lifecycle_cause is lifecycle_error


@pytest.mark.asyncio
async def test_first_cancellation_identity_survives_awaited_handle_cleanup() -> None:
    marker_seen: list[asyncio.CancelledError] = []
    handle = FakeHandle()
    entered = asyncio.Event()

    async def action(lease: FencedLeaderLease) -> None:
        del lease
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError as error:
            marker_seen.append(error)
            raise

    task = asyncio.create_task(elector_with(handle).run_if_leader_result("job", action))
    await asyncio.wait_for(entered.wait(), 0.2)
    task.cancel("first cancel")

    with pytest.raises(asyncio.CancelledError) as caught:
        await task

    assert marker_seen == [caught.value]
    assert caught.value.args == ("first cancel",)
    assert handle.exits == 1


@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
@pytest.mark.asyncio
async def test_process_control_identity_survives_handle_cleanup(
    error_type: type[BaseException],
) -> None:
    marker = error_type("control")
    handle = FakeHandle()

    async def stop(lease: FencedLeaderLease) -> None:
        del lease
        raise marker

    with pytest.raises(BaseException) as caught:
        await elector_with(handle).run_if_leader_result("job", stop)

    assert caught.value is marker
    assert handle.exits == 1


def test_constructor_shape_and_runtime_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.leader.redis import AsyncRedisLeaderElector
    from bluetape.leader.redis import _async_elector as module

    created: list[tuple[object, str]] = []

    class StubLock:
        def __init__(self, client: object, prefix: str) -> None:
            created.append((client, prefix))

        async def try_acquire(self, lock_name: str, options: object = None) -> None:
            del lock_name, options

    monkeypatch.setattr(module, "AsyncRedisDistributedLock", StubLock)
    client = object()
    elector = AsyncRedisLeaderElector(client, prefix="custom")

    assert created == [(client, "custom")]
    assert isinstance(elector, AsyncLeaderElector)
    assert str(inspect.signature(AsyncRedisLeaderElector)) == (
        "(client: 'async_redis.Redis', *, prefix: 'str' = 'bluetape-leader') -> 'None'"
    )
