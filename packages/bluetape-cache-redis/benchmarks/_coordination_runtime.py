"""Bounded process and task containment for coordination benchmarks."""

import asyncio
import multiprocessing
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any

from _coordination_matrix import FULL, SMOKE, BenchmarkProfile, ScenarioCase
from _coordination_scenarios import (
    BenchmarkScenarioError,
    run_async_case,
    run_sync_case,
)
from bluetape.benchmark import BenchmarkScenarioResult


@dataclass(frozen=True, slots=True, kw_only=True)
class ChildConfig:
    """Minimal immutable data allowed across the sync child boundary."""

    redis_url: str
    profile_id: str
    scenario_id: str
    case_id: str
    seed: int

    def __post_init__(self) -> None:
        for field in ("redis_url", "profile_id", "scenario_id", "case_id"):
            if type(getattr(self, field)) is not str:
                raise TypeError(f"{field} must be an exact str")
        if type(self.seed) is not int:
            raise TypeError("seed must be an exact int")


class ChildExecutionError(RuntimeError):
    """Redacted failure returned by a contained sync child."""

    def __init__(self, category: str, events: tuple[str, ...] = ()) -> None:
        super().__init__(category)
        self.category = category
        self.events = events


def _resolve_case(config: ChildConfig) -> tuple[BenchmarkProfile, ScenarioCase]:
    profiles = {"smoke": SMOKE, "full": FULL}
    try:
        profile = profiles[config.profile_id]
    except KeyError:
        raise ChildExecutionError("input-invalid") from None
    matches = tuple(
        case
        for case in profile.cases
        if case.scenario_id == config.scenario_id and case.case_id == config.case_id
    )
    if len(matches) != 1:
        raise ChildExecutionError("input-invalid")
    return profile, matches[0]


def _failure_category(error: BaseException) -> str:
    if isinstance(error, BenchmarkScenarioError):
        return str(error)
    if isinstance(error, TimeoutError):
        return "deadline"
    return "provider-failed"


def _child_main(sender: Connection, config: ChildConfig) -> None:
    try:
        profile, case = _resolve_case(config)
        result = run_sync_case(config.redis_url, profile, case, config.seed)
        sender.send(("success", result))
    except BaseException as error:
        sender.send(("failure", _failure_category(error)))
    finally:
        sender.close()


def _stop_process(
    process: multiprocessing.Process,
    *,
    cleanup_timeout: float,
    terminate_timeout: float,
    kill_timeout: float,
) -> tuple[str, ...]:
    events = ["abort"]
    process.join(cleanup_timeout)
    if process.is_alive():
        process.terminate()
        events.append("terminate")
        process.join(terminate_timeout)
    if process.is_alive():
        process.kill()
        events.append("kill")
        process.join(kill_timeout)
    events.append("join")
    if process.is_alive():
        raise ChildExecutionError("cleanup-failed", tuple(events))
    return tuple(events)


def run_sync_case_in_child(
    config: ChildConfig,
    *,
    wall_timeout_seconds: float | None = None,
    cleanup_timeout: float = 10.0,
    terminate_timeout: float = 5.0,
    kill_timeout: float = 5.0,
    _target: Callable[[Connection, ChildConfig], None] = _child_main,
) -> BenchmarkScenarioResult:
    """Run a sync case in a fresh spawn child and contain blocked threads."""
    profile, _ = _resolve_case(config)
    timeout = float(profile.wall_timeout_seconds)
    if wall_timeout_seconds is not None:
        if wall_timeout_seconds <= 0:
            raise ValueError("wall_timeout_seconds must be positive")
        timeout = wall_timeout_seconds
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_target, args=(sender, config))
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            events = _stop_process(
                process,
                cleanup_timeout=cleanup_timeout,
                terminate_timeout=terminate_timeout,
                kill_timeout=kill_timeout,
            )
            raise ChildExecutionError("live-worker", events)
        status, value = receiver.recv()
        process.join(terminate_timeout)
        if process.is_alive():
            events = _stop_process(
                process,
                cleanup_timeout=0.0,
                terminate_timeout=terminate_timeout,
                kill_timeout=kill_timeout,
            )
            raise ChildExecutionError("cleanup-failed", events)
        if status == "failure":
            raise ChildExecutionError(value)
        if status != "success" or not isinstance(value, BenchmarkScenarioResult):
            raise ChildExecutionError("provider-failed")
        return value
    finally:
        receiver.close()
        if process.is_alive():
            _stop_process(
                process,
                cleanup_timeout=0.0,
                terminate_timeout=terminate_timeout,
                kill_timeout=kill_timeout,
            )
        process.close()


class AsyncConvergenceRuntime[T]:
    """Preserve first cancellation while one shielded cleanup converges."""

    def __init__(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        cleanup: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._operation = operation
        self._cleanup = cleanup
        self._owned: set[asyncio.Task[Any]] = set()
        self._cleanup_task: asyncio.Task[None] | None = None
        self.cleanup_task_creations = 0

    @property
    def pending_owned_tasks(self) -> tuple[asyncio.Task[Any], ...]:
        return tuple(task for task in self._owned if not task.done())

    async def _converge(self) -> None:
        current = asyncio.current_task()
        tasks = tuple(task for task in self._owned if task is not current)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._cleanup is not None:
            await self._cleanup()

    def _ensure_cleanup(self) -> asyncio.Task[None]:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._converge())
            self.cleanup_task_creations += 1
        return self._cleanup_task

    async def run(self) -> T:
        operation = asyncio.create_task(self._operation())
        self._owned.add(operation)
        try:
            return await operation
        except asyncio.CancelledError as first:
            cleanup = self._ensure_cleanup()
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
            await cleanup
            raise first
        finally:
            self._owned.discard(operation)


async def run_async_case_bounded(
    redis_url: str,
    profile: BenchmarkProfile,
    case: ScenarioCase,
    seed: int,
) -> BenchmarkScenarioResult:
    runtime = AsyncConvergenceRuntime(lambda: run_async_case(redis_url, profile, case, seed))
    return await runtime.run()


__all__ = [
    "AsyncConvergenceRuntime",
    "ChildConfig",
    "ChildExecutionError",
    "run_async_case_bounded",
    "run_sync_case_in_child",
]
