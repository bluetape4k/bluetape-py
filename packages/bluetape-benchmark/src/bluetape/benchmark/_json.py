"""Strict schema-v1 JSON loading and atomic artifact writing."""

import json
import os
import stat
import tempfile
from pathlib import Path

from ._contracts import (
    BenchmarkComparison,
    BenchmarkEnvironment,
    BenchmarkReport,
    BenchmarkRunIdentity,
    BenchmarkScenarioResult,
    TimingSummary,
)

_REPORT_KEYS = {
    "environment",
    "production_capacity_claim",
    "profile",
    "run",
    "scenarios",
    "schema_version",
}


def _require_mapping(value: object, *, keys: set[str], field: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{field} has invalid fields")
    return value


def _require_list(value: object, *, field: str) -> list[object]:
    if type(value) is not list:
        raise TypeError(f"{field} must be a JSON array")
    return value


def _pairs(value: object, *, field: str) -> tuple[tuple[object, object], ...]:
    result: list[tuple[object, object]] = []
    for item in _require_list(value, field=field):
        if type(item) is not list or len(item) != 2:
            raise TypeError(f"{field} entries must be two-item arrays")
        result.append((item[0], item[1]))
    return tuple(result)


def _timing_to_dict(value: TimingSummary) -> dict[str, object]:
    return {
        "max_ns": value.max_ns,
        "median_ns": value.median_ns,
        "min_ns": value.min_ns,
        "operations_per_sample": value.operations_per_sample,
        "p95_ns": value.p95_ns,
        "p99_ns": value.p99_ns,
        "raw_samples_ns": list(value.raw_samples_ns),
        "throughput_ops_per_sec": value.throughput_ops_per_sec,
    }


def _scenario_to_dict(value: BenchmarkScenarioResult) -> dict[str, object]:
    return {
        "invariants": [list(item) for item in value.invariants],
        "metrics": [list(item) for item in value.metrics],
        "mode": value.mode,
        "parameters": [list(item) for item in value.parameters],
        "scenario_id": value.scenario_id,
        "timing": _timing_to_dict(value.timing),
    }


def report_to_dict(value: BenchmarkReport) -> dict[str, object]:
    """Return the exact schema-v1 JSON object for a validated report."""
    if type(value) is not BenchmarkReport:
        raise TypeError("value must be an exact BenchmarkReport")
    environment = value.environment
    run = value.run
    return {
        "environment": {
            "cpu_count": environment.cpu_count,
            "dependencies": [list(item) for item in environment.dependencies],
            "dependency_lock_digest": environment.dependency_lock_digest,
            "extensions": [list(item) for item in environment.extensions],
            "git_sha": environment.git_sha,
            "implementation": environment.implementation,
            "platform": environment.platform,
            "processor": environment.processor,
            "profile_registry_digest": environment.profile_registry_digest,
            "python": environment.python,
            "seed": environment.seed,
            "source_dirty": environment.source_dirty,
        },
        "production_capacity_claim": value.production_capacity_claim,
        "profile": value.profile,
        "run": {
            "candidate_order": run.candidate_order,
            "mode_order": list(run.mode_order),
            "pair_id": run.pair_id,
            "pair_index": run.pair_index,
            "role": run.role,
            "runner_id": run.runner_id,
        },
        "scenarios": [_scenario_to_dict(item) for item in value.scenarios],
        "schema_version": value.schema_version,
    }


def _timing_from_dict(value: object) -> TimingSummary:
    raw = _require_mapping(
        value,
        keys={
            "max_ns",
            "median_ns",
            "min_ns",
            "operations_per_sample",
            "p95_ns",
            "p99_ns",
            "raw_samples_ns",
            "throughput_ops_per_sec",
        },
        field="timing",
    )
    return TimingSummary(
        operations_per_sample=raw["operations_per_sample"],  # type: ignore[arg-type]
        raw_samples_ns=tuple(_require_list(raw["raw_samples_ns"], field="raw_samples_ns")),  # type: ignore[arg-type]
        min_ns=raw["min_ns"],  # type: ignore[arg-type]
        median_ns=raw["median_ns"],  # type: ignore[arg-type]
        p95_ns=raw["p95_ns"],  # type: ignore[arg-type]
        p99_ns=raw["p99_ns"],  # type: ignore[arg-type]
        max_ns=raw["max_ns"],  # type: ignore[arg-type]
        throughput_ops_per_sec=raw["throughput_ops_per_sec"],  # type: ignore[arg-type]
    )


def _scenario_from_dict(value: object) -> BenchmarkScenarioResult:
    raw = _require_mapping(
        value,
        keys={"invariants", "metrics", "mode", "parameters", "scenario_id", "timing"},
        field="scenario",
    )
    return BenchmarkScenarioResult(
        scenario_id=raw["scenario_id"],  # type: ignore[arg-type]
        mode=raw["mode"],  # type: ignore[arg-type]
        parameters=_pairs(raw["parameters"], field="parameters"),  # type: ignore[arg-type]
        timing=_timing_from_dict(raw["timing"]),
        metrics=_pairs(raw["metrics"], field="metrics"),  # type: ignore[arg-type]
        invariants=_pairs(raw["invariants"], field="invariants"),  # type: ignore[arg-type]
    )


def report_from_dict(value: object) -> BenchmarkReport:
    """Validate and reconstruct a report from an exact schema-v1 object."""
    raw = _require_mapping(value, keys=_REPORT_KEYS, field="report")
    environment = _require_mapping(
        raw["environment"],
        keys={
            "cpu_count",
            "dependencies",
            "dependency_lock_digest",
            "extensions",
            "git_sha",
            "implementation",
            "platform",
            "processor",
            "profile_registry_digest",
            "python",
            "seed",
            "source_dirty",
        },
        field="environment",
    )
    run = _require_mapping(
        raw["run"],
        keys={
            "candidate_order",
            "mode_order",
            "pair_id",
            "pair_index",
            "role",
            "runner_id",
        },
        field="run",
    )
    return BenchmarkReport(
        schema_version=raw["schema_version"],  # type: ignore[arg-type]
        profile=raw["profile"],  # type: ignore[arg-type]
        environment=BenchmarkEnvironment(
            python=environment["python"],  # type: ignore[arg-type]
            implementation=environment["implementation"],  # type: ignore[arg-type]
            platform=environment["platform"],  # type: ignore[arg-type]
            processor=environment["processor"],  # type: ignore[arg-type]
            cpu_count=environment["cpu_count"],  # type: ignore[arg-type]
            git_sha=environment["git_sha"],  # type: ignore[arg-type]
            seed=environment["seed"],  # type: ignore[arg-type]
            profile_registry_digest=environment["profile_registry_digest"],  # type: ignore[arg-type]
            dependency_lock_digest=environment["dependency_lock_digest"],  # type: ignore[arg-type]
            dependencies=_pairs(environment["dependencies"], field="dependencies"),  # type: ignore[arg-type]
            extensions=_pairs(environment["extensions"], field="extensions"),  # type: ignore[arg-type]
            source_dirty=environment["source_dirty"],  # type: ignore[arg-type]
        ),
        run=BenchmarkRunIdentity(
            mode_order=tuple(_require_list(run["mode_order"], field="mode_order")),  # type: ignore[arg-type]
            role=run["role"],  # type: ignore[arg-type]
            runner_id=run["runner_id"],  # type: ignore[arg-type]
            pair_id=run["pair_id"],  # type: ignore[arg-type]
            pair_index=run["pair_index"],  # type: ignore[arg-type]
            candidate_order=run["candidate_order"],  # type: ignore[arg-type]
        ),
        scenarios=tuple(
            _scenario_from_dict(item) for item in _require_list(raw["scenarios"], field="scenarios")
        ),
        production_capacity_claim=raw["production_capacity_claim"],  # type: ignore[arg-type]
    )


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON-compatible data with deterministic compact UTF-8 encoding."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def _pretty_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def _validate_safe_destination(path: Path) -> None:
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    absolute = path.absolute()
    for ancestor in reversed((absolute.parent, *absolute.parent.parents)):
        metadata = ancestor.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("destination ancestors must be real directories")
    if absolute.exists() or absolute.is_symlink():
        metadata = absolute.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("existing destination must be a regular file")


def _fsync_directory_when_supported(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, payload: bytes) -> None:
    _validate_safe_destination(path)
    descriptor, name = tempfile.mkstemp(
        prefix=".bluetape-benchmark-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    descriptor_owned = True
    try:
        os.fchmod(descriptor, 0o600)
        stream = os.fdopen(descriptor, "wb", closefd=True)
        descriptor_owned = False
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory_when_supported(path.parent)
    except BaseException:
        if descriptor_owned:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


def write_report(path: Path, report: BenchmarkReport) -> None:
    """Atomically write a validated benchmark report."""
    _atomic_write(path, _pretty_json_bytes(report_to_dict(report)))


def read_report(path: Path) -> BenchmarkReport:
    """Read and strictly validate a schema-v1 benchmark report."""
    if not isinstance(path, Path):
        raise TypeError("path must be a Path")
    return report_from_dict(json.loads(path.read_text(encoding="utf-8")))


def _comparison_to_dict(value: BenchmarkComparison) -> dict[str, object]:
    return {
        "baseline_git_sha": value.baseline_git_sha,
        "candidate_git_sha": value.candidate_git_sha,
        "comparable": value.comparable,
        "deltas": [
            {
                "absolute_delta_ns": item.absolute_delta_ns,
                "baseline_ns": item.baseline_ns,
                "candidate_ns": item.candidate_ns,
                "case_id": item.case_id,
                "mode": item.mode,
                "relative_delta_percent": item.relative_delta_percent,
                "scenario_id": item.scenario_id,
                "statistic": item.statistic,
            }
            for item in value.deltas
        ],
        "reasons": list(value.reasons),
        "schema_version": value.schema_version,
    }


def write_comparison(path: Path, comparison: BenchmarkComparison) -> None:
    """Atomically write a validated benchmark comparison."""
    if type(comparison) is not BenchmarkComparison:
        raise TypeError("comparison must be an exact BenchmarkComparison")
    _atomic_write(path, _pretty_json_bytes(_comparison_to_dict(comparison)))


__all__ = [
    "canonical_json_bytes",
    "read_report",
    "report_from_dict",
    "report_to_dict",
    "write_comparison",
    "write_report",
]
