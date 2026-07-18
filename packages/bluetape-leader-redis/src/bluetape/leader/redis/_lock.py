"""Synchronous single-primary Redis distributed lock."""

from __future__ import annotations

import hmac
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Never, Self

from bluetape.leader import (
    DistributedLock,
    FencedLeaderLease,
    LeaderBackendError,
    LeaderElectionOptions,
    LeaderLeaseLostError,
    LeaderReleaseError,
    LockLease,
    NotHeld,
    RenewBackendFailure,
    Renewed,
    RenewOutcome,
)

import redis
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
    _run_reconcile,
    _run_script,
    _validated_script_args,
)
from ._support import (
    _duration_milliseconds,
    _LeaseRecord,
    _new_owner_token,
    _Timing,
    _validated_sync_client,
)

_DEFAULT_PREFIX = "bluetape-leader"
_UNCERTAIN_ERRORS = (TimeoutError, RedisTimeoutError, RedisConnectionError)


class _RedisLockLease:
    __slots__ = (
        "_acquired_ns",
        "_commands",
        "_failure",
        "_lease",
        "_lease_key",
        "_lock",
        "_monotonic_ns",
        "_options",
        "_record",
        "_state",
    )

    def __init__(
        self,
        *,
        commands: Any,
        lease: FencedLeaderLease,
        lease_key: bytes,
        record: _LeaseRecord,
        options: LeaderElectionOptions,
        monotonic_ns: Callable[[], int],
        acquired_ns: int,
    ) -> None:
        self._commands = commands
        self._failure: LeaderBackendError | LeaderReleaseError | None = None
        self._lease = lease
        self._lease_key = lease_key
        self._record = record
        self._options = options
        self._monotonic_ns = monotonic_ns
        self._acquired_ns = acquired_ns
        self._state = "ACQUIRED"
        self._lock = threading.RLock()

    @property
    def lease(self) -> FencedLeaderLease:
        return self._lease

    def renew(self, lease_time: timedelta | None = None) -> RenewOutcome:
        with self._lock:
            self._raise_if_unknown()
            if self._state in ("LOST", "RELEASED"):
                return NotHeld()
            duration = self._options.lease_time if lease_time is None else lease_time
            ttl_ms = _duration_milliseconds(duration)
            try:
                raw = _run_script(
                    self._commands,
                    RENEW_SCRIPT,
                    (self._lease_key,),
                    (self._record.to_bytes(), str(ttl_ms).encode("ascii")),
                )
                status = _parse_status_response(raw, frozenset({"RENEWED", "NOT_HELD", "CORRUPT"}))
            except Exception:
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

    def is_held(self) -> bool:
        with self._lock:
            self._raise_if_unknown()
            if self._state in ("LOST", "RELEASED"):
                return False
            try:
                raw = _run_script(
                    self._commands,
                    PROBE_SCRIPT,
                    (self._lease_key,),
                    (self._record.to_bytes(),),
                )
                status = _parse_status_response(raw, frozenset({"HELD", "NOT_HELD", "CORRUPT"}))
            except Exception:
                self._fail_unknown(LeaderBackendError())
            if status == "HELD":
                return True
            if status == "NOT_HELD":
                self._state = "LOST"
                return False
            self._fail_unknown(LeaderBackendError())

    def assert_held(self) -> None:
        if not self.is_held():
            raise LeaderLeaseLostError()

    def release(self) -> None:
        self._release(scoped=False)

    def _release(self, *, scoped: bool) -> None:
        with self._lock:
            self._raise_if_unknown()
            if self._state in ("LOST", "RELEASED"):
                if scoped and self._state == "RELEASED":
                    return
                if scoped:
                    raise LeaderLeaseLostError()
                raise LeaderReleaseError()
            try:
                status = self._dispatch_release()
            except _UNCERTAIN_ERRORS:
                self._reconcile_release(scoped=scoped)
                return
            except Exception:
                self._fail_unknown(LeaderBackendError())
            self._finish_release_status(status, scoped=scoped)

    def _dispatch_release(self) -> str:
        remaining_ms = self._remaining_minimum_ms()
        raw = _run_script(
            self._commands,
            RELEASE_SCRIPT,
            (self._lease_key,),
            (self._record.to_bytes(), str(remaining_ms).encode("ascii")),
        )
        return _parse_status_response(
            raw, frozenset({"DELETED", "MIN_TTL_APPLIED", "NOT_HELD", "CORRUPT"})
        )

    def _remaining_minimum_ms(self) -> int:
        remaining_ns = _duration_nanoseconds(self._options.min_lease_time) - (
            self._monotonic_ns() - self._acquired_ns
        )
        return 0 if remaining_ns <= 0 else (remaining_ns + 999_999) // 1_000_000

    def _reconcile_release(self, *, scoped: bool) -> None:
        try:
            status, record = _parse_reconcile_response(
                _run_reconcile(self._commands, self._lease_key)
            )
        except Exception:
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
        try:
            repeat_status = self._dispatch_release()
        except _UNCERTAIN_ERRORS:
            self._fail_unknown(LeaderReleaseError())
        except Exception:
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

    def _fail_unknown(self, failure: LeaderBackendError | LeaderReleaseError) -> Never:
        self._state = "UNKNOWN"
        self._failure = failure
        raise failure from None

    def __enter__(self) -> Self:
        with self._lock:
            self._raise_if_unknown()
            if self._state != "ACQUIRED":
                raise LeaderLeaseLostError()
            self._state = "ENTERED"
        if self._options.auto_renew:
            outcome = self.renew()
            if isinstance(outcome, Renewed):
                return self
            if isinstance(outcome, NotHeld):
                raise LeaderLeaseLostError()
            raise outcome.cause
        if not self.is_held():
            raise LeaderLeaseLostError()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._release(scoped=True)

    def __repr__(self) -> str:
        return "_RedisLockLease(<redacted>)"

    def _raise_if_unknown(self) -> None:
        if self._state == "UNKNOWN":
            assert self._failure is not None
            raise self._failure


class RedisDistributedLock(DistributedLock[FencedLeaderLease]):
    """Acquire owner-token and fencing leases from a borrowed Redis client."""

    __slots__ = (
        "_commands",
        "_jitter",
        "_monotonic_ns",
        "_prefix",
        "_sleep",
        "_timing",
        "_token_factory",
    )

    def __init__(self, client: redis.Redis, prefix: str = _DEFAULT_PREFIX) -> None:
        self._commands = client
        self._prefix = _validated_prefix(prefix)
        self._timing = _validated_sync_client(client)
        self._monotonic_ns = time.monotonic_ns
        self._sleep = time.sleep
        self._jitter = _random_jitter
        self._token_factory = _new_owner_token

    @classmethod
    def _for_test(
        cls,
        commands: Any,
        timing: _Timing,
        *,
        monotonic_ns: Callable[[], int],
        sleep: Callable[[float], None],
        jitter: Callable[[], float],
        token_factory: Callable[[], str],
        prefix: str = _DEFAULT_PREFIX,
    ) -> Self:
        instance = object.__new__(cls)
        instance._commands = commands
        instance._prefix = _validated_prefix(prefix)
        instance._timing = timing
        instance._monotonic_ns = monotonic_ns
        instance._sleep = sleep
        instance._jitter = jitter
        instance._token_factory = token_factory
        return instance

    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = LeaderElectionOptions(),  # noqa: B008
    ) -> LockLease[FencedLeaderLease] | None:
        keys = _redis_keys(lock_name, self._prefix)
        owner_token = self._token_factory()
        ttl_ms = _duration_milliseconds(options.lease_time)
        started_ns = self._monotonic_ns()
        deadline = started_ns + _duration_nanoseconds(options.wait_time)
        attempted = False
        while True:
            if attempted and self._monotonic_ns() >= deadline:
                return None
            attempted = True
            acquired_ns = self._monotonic_ns()
            try:
                raw = _run_script(
                    self._commands,
                    ACQUIRE_SCRIPT,
                    (keys.lease.encode(), keys.fence.encode()),
                    _validated_script_args(owner_token, ttl_ms),
                )
                status, fencing_token = _parse_acquire_response(raw)
            except _UNCERTAIN_ERRORS:
                return self._reconcile_acquire(
                    keys.lease.encode(), owner_token, options, acquired_ns
                )
            except Exception:
                raise LeaderBackendError() from None
            if status == "ACQUIRED" and fencing_token is not None:
                return self._new_handle(
                    keys.lease.encode(), owner_token, fencing_token, options, acquired_ns
                )
            if status != "CONTENDED":
                raise LeaderBackendError()
            if self._monotonic_ns() >= deadline:
                return None
            remaining = (deadline - self._monotonic_ns()) / 1_000_000_000
            delay = self._jitter()
            if type(delay) not in (int, float) or not 0.04 <= delay <= 0.06:
                raise RuntimeError("Redis acquisition jitter is invalid")
            self._sleep(min(float(delay), remaining))

    def _reconcile_acquire(
        self,
        lease_key: bytes,
        owner_token: str,
        options: LeaderElectionOptions,
        acquired_ns: int,
    ) -> LockLease[FencedLeaderLease]:
        try:
            status, record = _parse_reconcile_response(_run_reconcile(self._commands, lease_key))
        except Exception:
            raise LeaderBackendError() from None
        if (
            status != "PRESENT"
            or record is None
            or not hmac.compare_digest(record.owner_token, owner_token)
        ):
            raise LeaderBackendError()
        return self._new_handle(lease_key, owner_token, record.fencing_token, options, acquired_ns)

    def _new_handle(
        self,
        lease_key: bytes,
        owner_token: str,
        fencing_token: int,
        options: LeaderElectionOptions,
        acquired_ns: int,
    ) -> LockLease[FencedLeaderLease]:
        elected_at = datetime.now(UTC)
        lease = FencedLeaderLease(
            audit_leader_id=str(fencing_token),
            node_id=options.node_id,
            elected_at=elected_at,
            lease_until=elected_at + options.lease_time,
            fencing_token=fencing_token,
        )
        return _RedisLockLease(
            commands=self._commands,
            lease=lease,
            lease_key=lease_key,
            record=_LeaseRecord(owner_token, fencing_token),
            options=options,
            monotonic_ns=self._monotonic_ns,
            acquired_ns=acquired_ns,
        )  # type: ignore[return-value]

    def __repr__(self) -> str:
        return "RedisDistributedLock(<redacted>)"


def _duration_nanoseconds(value: timedelta) -> int:
    return (
        value.days * 86_400_000_000_000 + value.seconds * 1_000_000_000 + value.microseconds * 1_000
    )


def _random_jitter() -> float:
    import random

    return random.uniform(0.04, 0.06)
