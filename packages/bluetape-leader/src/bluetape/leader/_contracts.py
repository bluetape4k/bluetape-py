"""Generic backend-neutral sync and async leader protocols."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from ._options import LeaderElectionOptions
from ._results import LeaderRunResult, RenewOutcome
from ._values import LeaderLease


@runtime_checkable
class LockLease[LeaseT: LeaderLease](Protocol):
    """A synchronous active lease handle.

    Runtime checking performs a shallow member-presence check only; it does not
    validate callability, signatures, or generic arguments.
    """

    @property
    def lease(self) -> LeaseT: ...

    def renew(self, lease_time: timedelta | None = None) -> RenewOutcome: ...

    def is_held(self) -> bool: ...

    def assert_held(self) -> None: ...

    def release(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@runtime_checkable
class AsyncLockLease[LeaseT: LeaderLease](Protocol):
    """An asynchronous active lease handle.

    Runtime checking performs a shallow member-presence check only; it does not
    validate callability, signatures, or generic arguments.
    """

    @property
    def lease(self) -> LeaseT: ...

    async def renew(self, lease_time: timedelta | None = None) -> RenewOutcome: ...

    async def is_held(self) -> bool: ...

    async def assert_held(self) -> None: ...

    async def release(self) -> None: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@runtime_checkable
class DistributedLock[LeaseT: LeaderLease](Protocol):
    """A synchronous distributed-lock acquisition contract.

    Runtime checking performs a shallow member-presence check only; it does not
    validate callability, signatures, or generic arguments.
    """

    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> LockLease[LeaseT] | None: ...


@runtime_checkable
class AsyncDistributedLock[LeaseT: LeaderLease](Protocol):
    """An asynchronous distributed-lock acquisition contract.

    Runtime checking performs a shallow member-presence check only; it does not
    validate callability, signatures, or generic arguments.
    """

    async def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> AsyncLockLease[LeaseT] | None: ...


@runtime_checkable
class LeaderElector[LeaseT: LeaderLease](Protocol):
    """A synchronous scoped leader-action contract.

    Runtime checking performs a shallow member-presence check only; it does not
    validate callability, signatures, or generic arguments.
    """

    def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> T | None: ...

    def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], T],
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> LeaderRunResult[T, LeaseT]: ...


@runtime_checkable
class AsyncLeaderElector[LeaseT: LeaderLease](Protocol):
    """An asynchronous scoped leader-action contract.

    Runtime checking performs a shallow member-presence check only; it does not
    validate callability, signatures, or generic arguments.
    """

    async def run_if_leader[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], Awaitable[T]],
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> T | None: ...

    async def run_if_leader_result[T](
        self,
        lock_name: str,
        action: Callable[[LeaseT], Awaitable[T]],
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> LeaderRunResult[T, LeaseT]: ...
