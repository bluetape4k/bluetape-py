"""Asyncio Redis leader-action composition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from bluetape.leader import (
    ActionFailed,
    AsyncLeaderElector,
    Elected,
    FencedLeaderLease,
    LeaderElectionOptions,
    LeaderError,
    LeaderExecutionError,
    LeaderRunResult,
    Skipped,
)

import redis.asyncio as async_redis

from ._async_lock import AsyncRedisDistributedLock

_DEFAULT_PREFIX = "bluetape-leader"


class AsyncRedisLeaderElector(AsyncLeaderElector[FencedLeaderLease]):
    """Run async actions while a Redis fencing lease is proven."""

    __slots__ = ("_lock",)

    def __init__(
        self,
        client: async_redis.Redis,
        *,
        prefix: str = _DEFAULT_PREFIX,
    ) -> None:
        self._lock = AsyncRedisDistributedLock(client, prefix=prefix)

    async def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[FencedLeaderLease], Awaitable[T]],
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> T | None:
        result = await self.run_if_leader_result(lock_name, action, options)
        if isinstance(result, Skipped):
            return None
        if isinstance(result, ActionFailed):
            raise result.cause
        return result.value

    async def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[FencedLeaderLease], Awaitable[T]],
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> LeaderRunResult[T, FencedLeaderLease]:
        handle = await self._lock.try_acquire(lock_name, options)
        if handle is None:
            return Skipped()
        result_lease: FencedLeaderLease | None = None
        action_value: T | None = None
        action_error: Exception | None = None
        try:
            async with handle as held:
                result_lease = held.lease
                try:
                    action_value = await action(result_lease)
                except Exception as caught:
                    action_error = caught
        except LeaderError as lifecycle_error:
            if action_error is not None:
                raise LeaderExecutionError(action_error, lifecycle_error) from None
            raise
        assert result_lease is not None
        if action_error is not None:
            return ActionFailed(action_error, result_lease)
        return Elected(cast(T, action_value), result_lease)

    def __repr__(self) -> str:
        return "AsyncRedisLeaderElector(<redacted>)"


__all__: list[str] = []
