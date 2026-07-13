"""Generate bounded, non-gating Redis coordination benchmark evidence."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

from _coordination_matrix import (
    FULL,
    SMOKE,
    BenchmarkProfile,
    ScenarioCase,
    registry_digest,
    validate_profile,
)
from _coordination_runtime import (
    ChildConfig,
    ChildExecutionError,
    run_async_case_bounded,
    run_sync_case_in_child,
)
from _coordination_security import (
    POLICY_ID,
    make_sync_client,
    policy_digest,
    validate_redis_report_fields,
)
from bluetape.benchmark import (
    BenchmarkEnvironment,
    BenchmarkReport,
    BenchmarkRunIdentity,
    BenchmarkScenarioResult,
    write_report,
)
from bluetape.benchmark._json import report_to_dict
from bluetape.testcontainers import (
    DEFAULT_REDIS_IMAGE,
    RedisServer,
    StartFailureKind,
    TestcontainerStartError,
)

_EXACT_INTEGER = re.compile(r"-?(0|[1-9][0-9]*)")
_PAIR_FIELDS = ("runner_id", "pair_id", "pair_index", "candidate_order")
_EXIT_CODES = {
    "input-invalid": 2,
    "source-dirty": 2,
    "docker-unavailable": 5,
    "redis-startup": 5,
    "correctness-failed": 3,
    "deadline": 3,
    "live-worker": 3,
    "redis-failed": 3,
    "provider-failed": 3,
    "codec-failed": 3,
    "cancelled": 3,
    "interrupted": 130,
    "cleanup-failed": 3,
    "artifact-write-failed": 6,
}


class BenchmarkCliError(RuntimeError):
    """Low-cardinality CLI failure that never includes underlying details."""

    def __init__(
        self,
        category: str,
        *,
        mode: str | None = None,
        scenario_id: str | None = None,
        case_id: str | None = None,
        phase: str | None = None,
        repetition: int | None = None,
        exit_code: int | None = None,
    ) -> None:
        super().__init__(category)
        self.category = category
        self.mode = mode
        self.scenario_id = scenario_id
        self.case_id = case_id
        self.phase = phase
        self.repetition = repetition
        self.code = "BTBENCH_" + category.upper().replace("-", "_")
        self.exit_code = _EXIT_CODES.get(category, 3) if exit_code is None else exit_code


class _SignalInterrupt(BaseException):
    def __init__(self, signum: int) -> None:
        self.signum = signum


@dataclass(frozen=True, slots=True, kw_only=True)
class RunConfig:
    profile: BenchmarkProfile
    modes: tuple[str, ...]
    cases: tuple[ScenarioCase, ...]
    output: str
    seed: int
    run: BenchmarkRunIdentity
    repository: Path
    git_sha: str


def exact_int(value: str) -> int:
    if _EXACT_INTEGER.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("expected a canonical integer")
    return int(value)


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise BenchmarkCliError("input-invalid")


def parser() -> argparse.ArgumentParser:
    result = _SafeArgumentParser()
    result.add_argument("--profile", choices=("smoke", "full"), required=True)
    result.add_argument("--mode", choices=("sync", "async", "both"), default="both")
    result.add_argument("--scenario", action="append", default=[])
    result.add_argument("--output", required=True)
    result.add_argument("--seed", type=exact_int, required=True)
    result.add_argument("--role", choices=("snapshot", "baseline", "candidate"), default="snapshot")
    result.add_argument("--runner-id")
    result.add_argument("--pair-id")
    result.add_argument("--pair-index", type=exact_int)
    result.add_argument("--candidate-order", choices=("baseline-first", "candidate-first"))
    return result


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _repository() -> Path:
    try:
        return Path(_git(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()
    except (OSError, subprocess.CalledProcessError):
        raise BenchmarkCliError("input-invalid") from None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _worktrees(repository: Path) -> tuple[Path, ...]:
    raw = _git(repository, "worktree", "list", "--porcelain")
    return tuple(
        Path(line.removeprefix("worktree ")).resolve()
        for line in raw.splitlines()
        if line.startswith("worktree ")
    )


def _validate_output(value: str, repository: Path, *, paired: bool) -> None:
    if value == "-":
        if paired:
            raise BenchmarkCliError("input-invalid")
        return
    path = Path(value).expanduser().absolute()
    if not path.parent.exists() or path.parent.is_symlink() or not path.parent.is_dir():
        raise BenchmarkCliError("input-invalid")
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise BenchmarkCliError("input-invalid")
    if paired and any(_is_within(path, worktree) for worktree in _worktrees(repository)):
        raise BenchmarkCliError("input-invalid")


def _source_dirty(repository: Path) -> bool:
    return bool(_git(repository, "status", "--porcelain", "--untracked-files=all"))


def preflight(arguments: argparse.Namespace) -> RunConfig:
    repository = _repository()
    profile = {"smoke": SMOKE, "full": FULL}[arguments.profile]
    modes = ("sync", "async") if arguments.mode == "both" else (arguments.mode,)
    filters = tuple(arguments.scenario)
    if len(filters) != len(set(filters)):
        raise BenchmarkCliError("input-invalid")
    known = {case.scenario_id for case in profile.cases}
    if not set(filters) <= known:
        raise BenchmarkCliError("input-invalid")
    cases = tuple(case for case in profile.cases if not filters or case.scenario_id in filters)
    if not cases:
        raise BenchmarkCliError("input-invalid")
    selected = BenchmarkProfile(
        profile_id=profile.profile_id,
        cases=cases,
        wall_timeout_seconds=profile.wall_timeout_seconds,
    )
    validate_profile(selected, modes)
    pairing = tuple(getattr(arguments, field) for field in _PAIR_FIELDS)
    paired = arguments.role != "snapshot"
    if paired != all(value is not None for value in pairing):
        raise BenchmarkCliError("input-invalid")
    if not paired and any(value is not None for value in pairing):
        raise BenchmarkCliError("input-invalid")
    try:
        run = BenchmarkRunIdentity(
            mode_order=modes,
            role=arguments.role,
            runner_id=arguments.runner_id,
            pair_id=arguments.pair_id,
            pair_index=arguments.pair_index,
            candidate_order=arguments.candidate_order,
        )
    except (TypeError, ValueError):
        raise BenchmarkCliError("input-invalid") from None
    _validate_output(arguments.output, repository, paired=paired)
    if arguments.output != "-" and _source_dirty(repository):
        raise BenchmarkCliError("source-dirty")
    return RunConfig(
        profile=selected,
        modes=modes,
        cases=cases,
        output=arguments.output,
        seed=arguments.seed,
        run=run,
        repository=repository,
        git_sha=_git(repository, "rev-parse", "HEAD"),
    )


def _lock_digest(repository: Path) -> str:
    return hashlib.sha256((repository / "uv.lock").read_bytes()).hexdigest()


def _image_digest() -> str:
    try:
        completed = subprocess.run(
            (
                "docker",
                "image",
                "inspect",
                "--format={{json .RepoDigests}}",
                DEFAULT_REDIS_IMAGE,
            ),
            check=True,
            capture_output=True,
            text=True,
        )
        values = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        raise BenchmarkCliError("redis-startup", phase="startup") from None
    if (
        type(values) is not list
        or not values
        or type(values[0]) is not str
        or "@sha256:" not in values[0]
    ):
        raise BenchmarkCliError("redis-startup")
    return values[0].split("@", 1)[1]


def _redis_extensions(redis_url: str) -> dict[str, object]:
    try:
        client = make_sync_client(redis_url)
        try:
            information = client.info("server")
            version = information.get("redis_version")
        finally:
            client.close()
    except Exception:
        raise BenchmarkCliError("redis-failed", phase="startup") from None
    if type(version) is not str:
        raise BenchmarkCliError("redis-failed")
    return {
        "coordination_policy_digest": policy_digest(),
        "coordination_policy_id": POLICY_ID,
        "redis_configuration_profile": "ephemeral-default",
        "redis_image_digest": _image_digest(),
        "redis_version": version,
    }


def _environment(config: RunConfig, extensions: dict[str, object]) -> BenchmarkEnvironment:
    dependencies = (("redis", importlib.metadata.version("redis")),)
    return BenchmarkEnvironment(
        python=platform.python_version(),
        implementation=platform.python_implementation(),
        platform=platform.system().lower(),
        processor=platform.machine() or "unknown",
        cpu_count=os.cpu_count(),
        git_sha=config.git_sha,
        seed=config.seed,
        profile_registry_digest=registry_digest(config.profile),
        dependency_lock_digest=_lock_digest(config.repository),
        dependencies=dependencies,
        extensions=extensions,
        source_dirty=False,
    )


def _run_results(config: RunConfig, redis_url: str) -> tuple[BenchmarkScenarioResult, ...]:
    results: list[BenchmarkScenarioResult] = []
    for mode in config.modes:
        for case in config.cases:
            try:
                if mode == "sync":
                    result = run_sync_case_in_child(
                        ChildConfig(
                            redis_url=redis_url,
                            profile_id=config.profile.profile_id,
                            scenario_id=case.scenario_id,
                            case_id=case.case_id,
                            seed=config.seed,
                        )
                    )
                else:
                    result = asyncio.run(
                        run_async_case_bounded(redis_url, config.profile, case, config.seed)
                    )
            except ChildExecutionError as error:
                raise BenchmarkCliError(
                    error.category,
                    mode=mode,
                    scenario_id=case.scenario_id,
                    case_id=case.case_id,
                    phase="measurement",
                ) from None
            except asyncio.CancelledError:
                raise BenchmarkCliError(
                    "cancelled",
                    mode=mode,
                    scenario_id=case.scenario_id,
                    case_id=case.case_id,
                    phase="measurement",
                ) from None
            except Exception:
                raise BenchmarkCliError(
                    "provider-failed",
                    mode=mode,
                    scenario_id=case.scenario_id,
                    case_id=case.case_id,
                    phase="measurement",
                ) from None
            results.append(result)
    return tuple(results)


def _write(config: RunConfig, report: BenchmarkReport) -> None:
    try:
        if config.output == "-":
            print(json.dumps(report_to_dict(report), sort_keys=True, indent=2))
        else:
            write_report(Path(config.output).expanduser().absolute(), report)
    except (OSError, TypeError, ValueError):
        raise BenchmarkCliError("artifact-write-failed", phase="write") from None


def _start_server(server: RedisServer) -> None:
    try:
        server.start()
    except TestcontainerStartError as error:
        category = (
            "docker-unavailable"
            if error.kind is StartFailureKind.RUNTIME_UNAVAILABLE
            else "redis-startup"
        )
        raise BenchmarkCliError(category, phase="startup") from None
    except Exception:
        raise BenchmarkCliError("redis-startup", phase="startup") from None


def _close_server(server: RedisServer, primary: BaseException | None) -> None:
    try:
        server.close()
    except Exception:
        if primary is None:
            raise BenchmarkCliError("cleanup-failed", phase="cleanup") from None
        primary.add_note("benchmark cleanup also failed")


def execute(config: RunConfig) -> None:
    server = RedisServer()
    primary: BaseException | None = None
    try:
        _start_server(server)
        extensions = _redis_extensions(server.url)
        results = _run_results(config, server.url)
        for result in results:
            validate_redis_report_fields(
                parameters=dict(result.parameters),
                metrics=dict(result.metrics),
                extensions=extensions,
            )
        report = BenchmarkReport(
            schema_version=1,
            profile=config.profile.profile_id,
            environment=_environment(config, extensions),
            run=config.run,
            scenarios=results,
        )
        _write(config, report)
    except BaseException as error:
        primary = error
        raise
    finally:
        _close_server(server, primary)


def _diagnostic(error: BenchmarkCliError) -> str:
    value = {
        "case_id": error.case_id,
        "category": error.category,
        "code": error.code,
        "mode": error.mode,
        "phase": error.phase,
        "repetition": error.repetition,
        "scenario_id": error.scenario_id,
    }
    return "bluetape-benchmark-error " + json.dumps(value, sort_keys=True, separators=(",", ":"))


def _install_signals() -> dict[int, signal.Handlers]:
    previous: dict[int, signal.Handlers] = {}
    seen = 0

    def handle(signum: int, _frame: FrameType | None) -> None:
        nonlocal seen
        seen += 1
        if seen > 1:
            os._exit(128 + signum)
        raise _SignalInterrupt(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, handle)
    return previous


def _restore_signals(previous: dict[int, signal.Handlers]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    previous = _install_signals()
    try:
        try:
            arguments = parser().parse_args(argv)
            config = preflight(arguments)
            execute(config)
            return 0
        except BenchmarkCliError as error:
            print(_diagnostic(error), file=sys.stderr)
            return error.exit_code
        except Exception:
            error = BenchmarkCliError("provider-failed")
            print(_diagnostic(error), file=sys.stderr)
            return error.exit_code
        except _SignalInterrupt as interrupted:
            code = 128 + interrupted.signum
            error = BenchmarkCliError("interrupted", phase="cleanup", exit_code=code)
            print(_diagnostic(error), file=sys.stderr)
            return code
    finally:
        _restore_signals(previous)


if __name__ == "__main__":
    raise SystemExit(main())
