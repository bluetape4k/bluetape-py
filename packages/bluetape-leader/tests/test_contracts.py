import ast
import importlib
import inspect
from collections.abc import Awaitable, Callable
from datetime import timedelta
from types import NoneType, TracebackType
from typing import Self, get_args, get_origin

import pytest
from bluetape.leader import FencedLeaderLease, LeaderElectionOptions, LeaderLease

DEFAULT_OPTIONS = LeaderElectionOptions()


def load_leader() -> object:
    return importlib.import_module("bluetape.leader")


def sample_lease() -> FencedLeaderLease:
    return FencedLeaderLease(
        audit_leader_id="21",
        node_id="node-a",
        elected_at=None,
        lease_until=None,
        fencing_token=21,
    )


def assert_options_parameter(callable_object: Callable[..., object]) -> None:
    parameter = inspect.signature(callable_object).parameters["options"]

    assert parameter.annotation is LeaderElectionOptions
    assert parameter.default == LeaderElectionOptions()
    assert type(parameter.default) is LeaderElectionOptions


def assert_optional_generic(annotation: object, origin: object, argument: object) -> None:
    generic, absent = get_args(annotation)

    assert get_origin(generic) is origin
    assert get_args(generic) == (argument,)
    assert absent is NoneType


def assert_lease_protocol_shape(protocol: type[object], *, asynchronous: bool) -> None:
    (lease_t,) = protocol.__type_params__
    lease_property = protocol.lease

    assert lease_t.__bound__ is LeaderLease
    assert isinstance(lease_property, property)
    assert inspect.signature(lease_property.fget).return_annotation is lease_t

    method_names = ("renew", "is_held", "assert_held", "release")
    for method_name in method_names:
        method = getattr(protocol, method_name)
        assert inspect.iscoroutinefunction(method) is asynchronous

    renew_signature = inspect.signature(protocol.renew)
    assert list(renew_signature.parameters) == ["self", "lease_time"]
    assert renew_signature.parameters["lease_time"].annotation == timedelta | None
    assert renew_signature.parameters["lease_time"].default is None
    assert renew_signature.return_annotation is load_leader().RenewOutcome

    for method_name in ("is_held", "assert_held", "release"):
        signature = inspect.signature(getattr(protocol, method_name))
        assert list(signature.parameters) == ["self"]
    assert inspect.signature(protocol.is_held).return_annotation is bool
    assert inspect.signature(protocol.assert_held).return_annotation is None
    assert inspect.signature(protocol.release).return_annotation is None

    enter_name = "__aenter__" if asynchronous else "__enter__"
    exit_name = "__aexit__" if asynchronous else "__exit__"
    enter = getattr(protocol, enter_name)
    exit_method = getattr(protocol, exit_name)
    assert inspect.iscoroutinefunction(enter) is asynchronous
    assert inspect.iscoroutinefunction(exit_method) is asynchronous
    assert inspect.signature(enter).return_annotation is Self

    exit_signature = inspect.signature(exit_method)
    assert list(exit_signature.parameters) == [
        "self",
        "exc_type",
        "exc",
        "traceback",
    ]
    assert exit_signature.parameters["exc_type"].annotation == type[BaseException] | None
    assert exit_signature.parameters["exc"].annotation == BaseException | None
    assert exit_signature.parameters["traceback"].annotation == TracebackType | None
    assert exit_signature.return_annotation is None


def assert_lock_protocol_shape(protocol: type[object], lease_protocol: object) -> None:
    (lease_t,) = protocol.__type_params__
    method = protocol.try_acquire
    signature = inspect.signature(method)

    assert lease_t.__bound__ is LeaderLease
    assert list(signature.parameters) == ["self", "lock_name", "options"]
    assert signature.parameters["lock_name"].annotation is str
    assert_options_parameter(method)
    assert_optional_generic(signature.return_annotation, lease_protocol, lease_t)


def assert_elector_protocol_shape(
    protocol: type[object],
    *,
    asynchronous: bool,
) -> None:
    leader = load_leader()
    (lease_t,) = protocol.__type_params__

    assert lease_t.__bound__ is LeaderLease
    for method_name in ("run_if_leader", "run_if_leader_result"):
        method = getattr(protocol, method_name)
        signature = inspect.signature(method)
        (result_t,) = method.__type_params__

        assert inspect.iscoroutinefunction(method) is asynchronous
        assert list(signature.parameters) == ["self", "lock_name", "action", "options"]
        assert signature.parameters["lock_name"].annotation is str
        assert_options_parameter(method)

        action_parameters, action_result = get_args(signature.parameters["action"].annotation)
        assert action_parameters == [lease_t]
        if asynchronous:
            assert get_origin(action_result) is Awaitable
            assert get_args(action_result) == (result_t,)
        else:
            assert action_result is result_t

        if method_name == "run_if_leader":
            assert set(get_args(signature.return_annotation)) == {result_t, NoneType}
        else:
            assert get_origin(signature.return_annotation) is leader.LeaderRunResult
            assert get_args(signature.return_annotation) == (result_t, lease_t)


def test_all_six_protocols_are_runtime_checkable() -> None:
    leader = load_leader()

    for protocol in (
        leader.LockLease,
        leader.AsyncLockLease,
        leader.DistributedLock,
        leader.AsyncDistributedLock,
        leader.LeaderElector,
        leader.AsyncLeaderElector,
    ):
        assert protocol._is_protocol is True
        assert protocol._is_runtime_protocol is True


def test_runtime_protocol_docstrings_state_the_shallow_checking_limit() -> None:
    leader = load_leader()

    for protocol in (
        leader.LockLease,
        leader.AsyncLockLease,
        leader.DistributedLock,
        leader.AsyncDistributedLock,
        leader.LeaderElector,
        leader.AsyncLeaderElector,
    ):
        documentation = inspect.getdoc(protocol)

        assert documentation is not None
        normalized = " ".join(documentation.split())
        assert "shallow member-presence check" in normalized
        assert "does not validate callability, signatures, or generic arguments" in normalized


class NonCallableLockShape:
    lease = 42
    renew = 42
    is_held = 42
    assert_held = 42
    release = 42
    __enter__ = 42
    __exit__ = 42


def test_runtime_protocol_check_can_accept_non_callable_members() -> None:
    leader = load_leader()

    assert isinstance(NonCallableLockShape(), leader.LockLease)


def test_subscripted_runtime_protocol_check_is_rejected() -> None:
    leader = load_leader()

    with pytest.raises(
        TypeError,
        match="Subscripted generics cannot be used with class and instance checks",
    ):
        isinstance(NonCallableLockShape(), leader.LockLease[FencedLeaderLease])


def test_lock_lease_protocols_have_exact_sync_and_async_signatures() -> None:
    leader = load_leader()

    assert_lease_protocol_shape(leader.LockLease, asynchronous=False)
    assert_lease_protocol_shape(leader.AsyncLockLease, asynchronous=True)


def test_distributed_lock_protocols_have_exact_generic_signatures() -> None:
    leader = load_leader()

    assert_lock_protocol_shape(leader.DistributedLock, leader.LockLease)
    assert_lock_protocol_shape(leader.AsyncDistributedLock, leader.AsyncLockLease)
    assert not inspect.iscoroutinefunction(leader.DistributedLock.try_acquire)
    assert inspect.iscoroutinefunction(leader.AsyncDistributedLock.try_acquire)


def test_elector_protocols_propagate_lease_type_through_actions_and_results() -> None:
    leader = load_leader()

    assert_elector_protocol_shape(leader.LeaderElector, asynchronous=False)
    assert_elector_protocol_shape(leader.AsyncLeaderElector, asynchronous=True)


def test_protocol_methods_contain_only_ellipsis_bodies() -> None:
    contracts = importlib.import_module("bluetape.leader._contracts")
    tree = ast.parse(inspect.getsource(contracts))
    protocol_names = {
        "LockLease",
        "AsyncLockLease",
        "DistributedLock",
        "AsyncDistributedLock",
        "LeaderElector",
        "AsyncLeaderElector",
    }
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in protocol_names
    }

    assert set(classes) == protocol_names
    for class_node in classes.values():
        methods = [
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert methods
        for method in methods:
            assert len(method.body) == 1
            assert isinstance(method.body[0], ast.Expr)
            assert isinstance(method.body[0].value, ast.Constant)
            assert method.body[0].value.value is Ellipsis


class SyncLeaseStub:
    def __init__(self, lease: FencedLeaderLease) -> None:
        self._lease = lease

    @property
    def lease(self) -> FencedLeaderLease:
        return self._lease

    def renew(self, lease_time: timedelta | None = None) -> object:
        del lease_time
        return load_leader().Renewed(self._lease.lease_until)

    def is_held(self) -> bool:
        return True

    def assert_held(self) -> None:
        return None

    def release(self) -> None:
        return None

    def __enter__(self) -> "SyncLeaseStub":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback


class AsyncLeaseStub:
    def __init__(self, lease: FencedLeaderLease) -> None:
        self._lease = lease

    @property
    def lease(self) -> FencedLeaderLease:
        return self._lease

    async def renew(self, lease_time: timedelta | None = None) -> object:
        del lease_time
        return load_leader().Renewed(self._lease.lease_until)

    async def is_held(self) -> bool:
        return True

    async def assert_held(self) -> None:
        return None

    async def release(self) -> None:
        return None

    async def __aenter__(self) -> "AsyncLeaseStub":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback


class SyncLockStub:
    def __init__(self, handle: SyncLeaseStub) -> None:
        self.handle = handle

    def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = DEFAULT_OPTIONS,
    ) -> SyncLeaseStub:
        del lock_name, options
        return self.handle


class AsyncLockStub:
    def __init__(self, handle: AsyncLeaseStub) -> None:
        self.handle = handle

    async def try_acquire(
        self,
        lock_name: str,
        options: LeaderElectionOptions = DEFAULT_OPTIONS,
    ) -> AsyncLeaseStub:
        del lock_name, options
        return self.handle


class SyncElectorStub:
    def __init__(self, lease: FencedLeaderLease) -> None:
        self.lease = lease

    def run_if_leader(
        self,
        lock_name: str,
        action: Callable[[FencedLeaderLease], object],
        options: LeaderElectionOptions = DEFAULT_OPTIONS,
    ) -> object:
        del lock_name, options
        return action(self.lease)

    def run_if_leader_result(
        self,
        lock_name: str,
        action: Callable[[FencedLeaderLease], object],
        options: LeaderElectionOptions = DEFAULT_OPTIONS,
    ) -> object:
        del lock_name, options
        return load_leader().Elected(action(self.lease), self.lease)


class AsyncElectorStub:
    def __init__(self, lease: FencedLeaderLease) -> None:
        self.lease = lease

    async def run_if_leader(
        self,
        lock_name: str,
        action: Callable[[FencedLeaderLease], Awaitable[object]],
        options: LeaderElectionOptions = DEFAULT_OPTIONS,
    ) -> object:
        del lock_name, options
        return await action(self.lease)

    async def run_if_leader_result(
        self,
        lock_name: str,
        action: Callable[[FencedLeaderLease], Awaitable[object]],
        options: LeaderElectionOptions = DEFAULT_OPTIONS,
    ) -> object:
        del lock_name, options
        return load_leader().Elected(await action(self.lease), self.lease)


@pytest.mark.asyncio
async def test_runtime_stubs_preserve_fenced_lease_through_all_protocols() -> None:
    leader = load_leader()
    lease = sample_lease()
    sync_handle = SyncLeaseStub(lease)
    async_handle = AsyncLeaseStub(lease)
    sync_lock = SyncLockStub(sync_handle)
    async_lock = AsyncLockStub(async_handle)
    sync_elector = SyncElectorStub(lease)
    async_elector = AsyncElectorStub(lease)

    assert isinstance(sync_handle, leader.LockLease)
    assert isinstance(async_handle, leader.AsyncLockLease)
    assert isinstance(sync_lock, leader.DistributedLock)
    assert isinstance(async_lock, leader.AsyncDistributedLock)
    assert isinstance(sync_elector, leader.LeaderElector)
    assert isinstance(async_elector, leader.AsyncLeaderElector)
    assert sync_lock.try_acquire("job").lease is lease
    assert (await async_lock.try_acquire("job")).lease is lease
    assert sync_elector.run_if_leader("job", lambda held: held).fencing_token == 21

    async def return_lease(held: FencedLeaderLease) -> FencedLeaderLease:
        return held

    async_result = await async_elector.run_if_leader_result("job", return_lease)
    assert async_result.value is lease
    assert async_result.lease is lease
