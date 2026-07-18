"""Asyncio single-primary Redis distributed lock."""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Self

from bluetape.leader import (
    AsyncDistributedLock,
    AsyncLockLease,
    FencedLeaderLease,
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderExecutionError,
    LeaderLeaseLostError,
    LeaderReleaseError,
    NotHeld,
    RenewBackendFailure,
    Renewed,
    RenewOutcome,
)

import redis.asyncio as async_redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from ._keys import _redis_keys, _validated_prefix
from ._scripts import (
    ACQUIRE_SCRIPT,
    PROBE_SCRIPT,
    RELEASE_SCRIPT,
    RENEW_SCRIPT,
    _parse_acquire_response,
    _parse_reconcile_response,
    _parse_status_response,
    _run_reconcile_async,
    _run_script_async,
    _validated_script_args,
)
from ._support import (
    _duration_milliseconds,
    _LeaseRecord,
    _new_owner_token,
    _Timing,
    _validated_async_client,
)

_DEFAULT_PREFIX = "bluetape-leader"
_UNCERTAIN_ERRORS = (TimeoutError, RedisTimeoutError, RedisConnectionError)


class _AsyncRedisLockLease:
    __slots__ = (
        "_acquired_at",
        "_cleanup_task",
        "_commands",
        "_failure",
        "_lease",
        "_lease_key",
        "_monotonic",
        "_options",
        "_record",
        "_renew_task",
        "_state",
        "_stop_event",
        "_timing",
    )

    def __init__(
        self,
        *,
        commands: Any,
        lease: FencedLeaderLease,
        lease_key: bytes,
        record: _LeaseRecord,
        options: LeaderElectionOptions,
        monotonic: Callable[[], float],
        acquired_at: float,
        timing: _Timing,
    ) -> None:
        self._commands = commands
        self._lease = lease
        self._lease_key = lease_key
        self._record = record
        self._options = options
        self._monotonic = monotonic
        self._acquired_at = acquired_at
        self._state = "ACQUIRED"
        self._failure: LeaderBackendError | LeaderReleaseError | None = None
        self._timing = timing
        self._stop_event = asyncio.Event()
        self._renew_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    @property
    def lease(self) -> FencedLeaderLease:
        return self._lease

    async def renew(self, lease_time: timedelta | None = None) -> RenewOutcome:
        self._raise_if_unknown()
        if self._state in ("LOST", "RELEASED"):
            return NotHeld()
        duration = self._options.lease_time if lease_time is None else lease_time
        backend_failed = False
        try:
            status = _parse_status_response(
                await _run_script_async(
                    self._commands,
                    RENEW_SCRIPT,
                    (self._lease_key,),
                    (
                        self._record.to_bytes(),
                        str(_duration_milliseconds(duration)).encode("ascii"),
                    ),
                ),
                frozenset({"RENEWED", "NOT_HELD", "CORRUPT"}),
            )
        except Exception:
            backend_failed = True
        if backend_failed:
            failure = LeaderBackendError()
            self._state = "UNKNOWN"
            self._failure = failure
            return RenewBackendFailure(failure)
        if status == "RENEWED":
            return Renewed(None)
        if status == "NOT_HELD":
            self._state = "LOST"
            return NotHeld()
        failure = LeaderBackendError()
        self._state = "UNKNOWN"
        self._failure = failure
        return RenewBackendFailure(failure)

    async def is_held(self) -> bool:
        self._raise_if_unknown()
        if self._state in ("LOST", "RELEASED"):
            return False
        backend_failed = False
        try:
            status = _parse_status_response(
                await _run_script_async(
                    self._commands,
                    PROBE_SCRIPT,
                    (self._lease_key,),
                    (self._record.to_bytes(),),
                ),
                frozenset({"HELD", "NOT_HELD", "CORRUPT"}),
            )
        except Exception:
            backend_failed = True
        if backend_failed:
            self._fail_unknown(LeaderBackendError())
        if status == "HELD":
            return True
        if status == "NOT_HELD":
            self._state = "LOST"
            return False
        self._fail_unknown(LeaderBackendError())

    async def assert_held(self) -> None:
        if not await self.is_held():
            raise LeaderLeaseLostError()

    async def release(self) -> None:
        await self._release(scoped=False)

    async def _release(self, *, scoped: bool) -> None:
        self._raise_if_unknown()
        if self._state in ("LOST", "RELEASED"):
            if scoped and self._state == "RELEASED":
                return
            if scoped:
                raise LeaderLeaseLostError()
            raise LeaderReleaseError()
        uncertain = False
        backend_failed = False
        try:
            status = await self._dispatch_release()
        except _UNCERTAIN_ERRORS:
            uncertain = True
        except Exception:
            backend_failed = True
        if uncertain:
            await self._reconcile_release(scoped=scoped)
            return
        if backend_failed:
            self._fail_unknown(LeaderBackendError())
        self._finish_release_status(status, scoped=scoped)

    async def _dispatch_release(self) -> str:
        remaining = self._options.min_lease_time.total_seconds() - (
            self._monotonic() - self._acquired_at
        )
        remaining_ms = 0 if remaining <= 0 else int(remaining * 1000 + 0.999999)
        return _parse_status_response(
            await _run_script_async(
                self._commands,
                RELEASE_SCRIPT,
                (self._lease_key,),
                (self._record.to_bytes(), str(remaining_ms).encode("ascii")),
            ),
            frozenset({"DELETED", "MIN_TTL_APPLIED", "NOT_HELD", "CORRUPT"}),
        )

    async def _reconcile_release(self, *, scoped: bool) -> None:
        reconcile_failed = False
        try:
            status, record = _parse_reconcile_response(
                await _run_reconcile_async(self._commands, self._lease_key)
            )
        except Exception:
            reconcile_failed = True
        if reconcile_failed:
            self._fail_unknown(LeaderBackendError())
        if status == "ABSENT":
            self._fail_unknown(LeaderReleaseError())
        if status != "PRESENT" or record is None:
            self._fail_unknown(LeaderBackendError())
        if not hmac.compare_digest(record.owner_token, self._record.owner_token):
            self._state = "LOST"
            if scoped:
                raise LeaderLeaseLostError()
            raise LeaderReleaseError()
        uncertain = False
        backend_failed = False
        try:
            repeat_status = await self._dispatch_release()
        except _UNCERTAIN_ERRORS:
            uncertain = True
        except Exception:
            backend_failed = True
        if uncertain:
            self._fail_unknown(LeaderReleaseError())
        if backend_failed:
            self._fail_unknown(LeaderBackendError())
        self._finish_release_status(repeat_status, scoped=scoped)

    def _finish_release_status(self, status: str, *, scoped: bool) -> None:
        if status in ("DELETED", "MIN_TTL_APPLIED"):
            self._state = "RELEASED"
            return
        if status == "NOT_HELD":
            self._state = "LOST"
            if scoped:
                raise LeaderLeaseLostError()
            raise LeaderReleaseError()
        self._fail_unknown(LeaderBackendError())

    async def __aenter__(self) -> Self:
        self._raise_if_unknown()
        if self._state != "ACQUIRED":
            raise LeaderLeaseLostError()
        self._state = "ENTERED"
        if self._options.auto_renew:
            outcome = await self.renew()
            if isinstance(outcome, NotHeld):
                raise LeaderLeaseLostError()
            if isinstance(outcome, RenewBackendFailure):
                raise outcome.cause
            self._renew_task = asyncio.create_task(self._renew_loop())
        elif not await self.is_held():
            raise LeaderLeaseLostError()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        first_cancel = exc if isinstance(exc, asyncio.CancelledError) else None
        first_cancel = await self._stop_renew_task(first_cancel)
        self._cleanup_task = asyncio.create_task(self._release(scoped=True))
        completed, first_cancel = await self._wait_task(
            self._cleanup_task, self._timing.release, first_cancel
        )
        if not completed:
            self._fail_unknown(LeaderBackendError())
        lifecycle_failure: BaseException | None = None
        if self._cleanup_task.cancelled():
            failure = LeaderBackendError()
            self._state = "UNKNOWN"
            self._failure = failure
            lifecycle_failure = failure
        else:
            try:
                self._cleanup_task.result()
            except BaseException as error:
                lifecycle_failure = error
        if first_cancel is not None:
            if lifecycle_failure is not None:
                first_cancel.add_note("leader lifecycle cleanup failed")
            raise first_cancel
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            if lifecycle_failure is not None:
                exc.add_note("leader lifecycle cleanup failed")
            return
        if lifecycle_failure is None:
            return
        if isinstance(exc, Exception):
            raise LeaderExecutionError(exc, lifecycle_failure)
        raise lifecycle_failure

    async def _renew_loop(self) -> None:
        interval = self._options.renew_interval
        assert interval is not None
        seconds = interval.total_seconds()
        while not self._stop_event.is_set():
            try:
                async with asyncio.timeout(seconds):
                    await self._stop_event.wait()
                return
            except TimeoutError:
                pass
            outcome = await self.renew()
            if isinstance(outcome, (NotHeld, RenewBackendFailure)):
                self._stop_event.set()
                return

    async def _stop_renew_task(
        self, first_cancel: asyncio.CancelledError | None
    ) -> asyncio.CancelledError | None:
        task = self._renew_task
        if task is None:
            return first_cancel
        self._stop_event.set()
        completed, first_cancel = await self._wait_task(task, self._timing.renew, first_cancel)
        if not completed:
            self._fail_unknown(LeaderBackendError())
        if task.cancelled():
            self._fail_unknown(LeaderBackendError())
        return first_cancel

    @staticmethod
    async def _wait_task(
        task: asyncio.Task[None],
        envelope: float,
        first_cancel: asyncio.CancelledError | None,
    ) -> tuple[bool, asyncio.CancelledError | None]:
        loop = asyncio.get_running_loop()
        owner = asyncio.current_task()
        assert owner is not None
        deadline = loop.time() + envelope
        while not task.done():
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                async with asyncio.timeout(remaining):
                    await asyncio.shield(task)
            except asyncio.CancelledError as caught:
                if task.done():
                    break
                if first_cancel is None and owner.cancelling() > 0:
                    first_cancel = caught
            except TimeoutError:
                break
            except BaseException:
                if task.done():
                    break
                raise
        if task.done():
            return True, first_cancel
        task.cancel()
        terminal_deadline = deadline + 0.1
        while not task.done():
            remaining = terminal_deadline - loop.time()
            if remaining <= 0:
                return False, first_cancel
            try:
                async with asyncio.timeout(remaining):
                    await asyncio.shield(task)
            except asyncio.CancelledError as caught:
                if task.done():
                    break
                if first_cancel is None and owner.cancelling() > 0:
                    first_cancel = caught
            except TimeoutError:
                return task.done(), first_cancel
            except BaseException:
                if task.done():
                    break
                raise
        return True, first_cancel

    def _raise_if_unknown(self) -> None:
        if self._state == "UNKNOWN":
            assert self._failure is not None
            raise self._failure

    def _fail_unknown(self, failure: LeaderBackendError | LeaderReleaseError) -> None:
        self._state = "UNKNOWN"
        self._failure = failure
        raise failure

    def __repr__(self) -> str:
        return "_AsyncRedisLockLease(<redacted>)"


class AsyncRedisDistributedLock(AsyncDistributedLock[FencedLeaderLease]):
    """Acquire owner-token and fencing leases from a borrowed async Redis client."""

    __slots__ = (
        "_commands",
        "_jitter",
        "_monotonic",
        "_prefix",
        "_sleep",
        "_timing",
        "_token_factory",
    )

    def __init__(self, client: async_redis.Redis, prefix: str = _DEFAULT_PREFIX) -> None:
        self._commands = client
        self._prefix = _validated_prefix(prefix)
        self._timing = _validated_async_client(client)
        self._monotonic = asyncio.get_running_loop().time
        self._sleep = asyncio.sleep
        self._jitter = _random_jitter
        self._token_factory = _new_owner_token

    @classmethod
    def _for_test(
        cls,
        commands: Any,
        timing: _Timing,
        *,
        monotonic: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
        jitter: Callable[[], float],
        token_factory: Callable[[], str],
        prefix: str = _DEFAULT_PREFIX,
    ) -> Self:
        instance = object.__new__(cls)
        instance._commands = commands
        instance._prefix = _validated_prefix(prefix)
        instance._timing = timing
        instance._monotonic = monotonic
        instance._sleep = sleep
        instance._jitter = jitter
        instance._token_factory = token_factory
        return instance

    async def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> AsyncLockLease[FencedLeaderLease] | None:
        keys = _redis_keys(lock_name, self._prefix)
        owner_token = self._token_factory()
        ttl_ms = _duration_milliseconds(options.lease_time)
        deadline = self._monotonic() + options.wait_time.total_seconds()
        attempted = False
        while True:
            acquired_at = self._monotonic()
            if attempted and acquired_at >= deadline:
                return None
            attempted = True
            uncertain = False
            backend_failed = False
            try:
                raw = await _run_script_async(
                    self._commands,
                    ACQUIRE_SCRIPT,
                    (keys.lease.encode(), keys.fence.encode()),
                    _validated_script_args(owner_token, ttl_ms),
                )
                status, fencing_token = _parse_acquire_response(raw)
            except _UNCERTAIN_ERRORS:
                uncertain = True
            except Exception:
                backend_failed = True
            if uncertain:
                return await self._reconcile_acquire(
                    keys.lease.encode(), owner_token, options, acquired_at
                )
            if backend_failed:
                raise LeaderBackendError()
            if status == "ACQUIRED" and fencing_token is not None:
                elected_at = datetime.now(UTC)
                lease = FencedLeaderLease(
                    audit_leader_id=str(fencing_token),
                    node_id=options.node_id,
                    elected_at=elected_at,
                    lease_until=elected_at + options.lease_time,
                    fencing_token=fencing_token,
                )
                return self._new_handle(
                    keys.lease.encode(), owner_token, fencing_token, lease, options, acquired_at
                )
            if status != "CONTENDED":
                raise LeaderBackendError()
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return None
            delay = self._jitter()
            if type(delay) not in (int, float) or not 0.04 <= delay <= 0.06:
                raise RuntimeError("Redis acquisition jitter is invalid")
            await self._sleep(min(float(delay), remaining))

    async def _reconcile_acquire(
        self,
        lease_key: bytes,
        owner_token: str,
        options: LeaderElectionOptions,
        acquired_at: float,
    ) -> AsyncLockLease[FencedLeaderLease]:
        backend_failed = False
        try:
            status, record = _parse_reconcile_response(
                await _run_reconcile_async(self._commands, lease_key)
            )
        except Exception:
            backend_failed = True
        if backend_failed:
            raise LeaderBackendError()
        if (
            status != "PRESENT"
            or record is None
            or not hmac.compare_digest(record.owner_token, owner_token)
        ):
            raise LeaderBackendError()
        elected_at = datetime.now(UTC)
        lease = FencedLeaderLease(
            audit_leader_id=str(record.fencing_token),
            node_id=options.node_id,
            elected_at=elected_at,
            lease_until=elected_at + options.lease_time,
            fencing_token=record.fencing_token,
        )
        return self._new_handle(
            lease_key,
            owner_token,
            record.fencing_token,
            lease,
            options,
            acquired_at,
        )

    def _new_handle(
        self,
        lease_key: bytes,
        owner_token: str,
        fencing_token: int,
        lease: FencedLeaderLease,
        options: LeaderElectionOptions,
        acquired_at: float,
    ) -> AsyncLockLease[FencedLeaderLease]:
        return _AsyncRedisLockLease(
            commands=self._commands,
            lease=lease,
            lease_key=lease_key,
            record=_LeaseRecord(owner_token, fencing_token),
            options=options,
            monotonic=self._monotonic,
            acquired_at=acquired_at,
            timing=self._timing,
        )

    def __repr__(self) -> str:
        return "AsyncRedisDistributedLock(<redacted>)"


def _random_jitter() -> float:
    import random

    return random.uniform(0.04, 0.06)


__all__: list[str] = []
