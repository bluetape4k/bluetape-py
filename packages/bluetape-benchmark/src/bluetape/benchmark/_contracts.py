"""Immutable validated benchmark report contracts."""

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

BenchmarkScalar: TypeAlias = str | int | float | bool | None
FieldPairs: TypeAlias = tuple[tuple[str, BenchmarkScalar], ...]

_FIELD_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")


def _exact_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if type(value) is not str:
        raise TypeError(f"{field} must be an exact str")
    if not value or len(value) > maximum or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field} is invalid")
    return value


def _identifier(value: object, *, field: str) -> str:
    text = _exact_text(value, field=field, maximum=64)
    if _IDENTIFIER.fullmatch(text) is None:
        raise ValueError(f"{field} is invalid")
    return text


def _validate_scalar(value: object, *, field: str) -> BenchmarkScalar:
    if value is None or type(value) in (bool, int):
        return value  # type: ignore[return-value]
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite")
        return value
    if type(value) is str:
        return _exact_text(value, field=field)
    raise TypeError(f"{field} has an unsupported scalar type")


def _field_pairs(value: object, *, field: str) -> FieldPairs:
    if isinstance(value, Mapping):
        source: Iterable[object] = value.items()
    else:
        try:
            source = tuple(value)  # type: ignore[arg-type]
        except TypeError:
            raise TypeError(f"{field} must be a mapping or pair iterable") from None
    normalized: list[tuple[str, BenchmarkScalar]] = []
    names: set[str] = set()
    for item in source:
        if type(item) not in (tuple, list) or len(item) != 2:  # type: ignore[arg-type]
            raise TypeError(f"{field} entries must be pairs")
        name, raw = item  # type: ignore[misc]
        if type(name) is not str or _FIELD_NAME.fullmatch(name) is None:
            raise ValueError(f"{field} contains an invalid name")
        if name in names:
            raise ValueError(f"{field} contains a duplicate name")
        names.add(name)
        normalized.append((name, _validate_scalar(raw, field=f"{field}.{name}")))
    return tuple(sorted(normalized))


def _bool_pairs(value: object, *, field: str) -> tuple[tuple[str, bool], ...]:
    pairs = _field_pairs(value, field=field)
    if not pairs:
        raise ValueError(f"{field} must not be empty")
    result: list[tuple[str, bool]] = []
    for name, item in pairs:
        if type(item) is not bool:
            raise TypeError(f"{field}.{name} must be an exact bool")
        if not item:
            raise ValueError(f"{field}.{name} must pass")
        result.append((name, item))
    return tuple(result)


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be lowercase SHA-256 hex")
    return value


def _git_sha(value: object, *, field: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise ValueError(f"{field} must be lowercase Git SHA-1 hex")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class TimingSummary:
    operations_per_sample: int
    raw_samples_ns: tuple[int, ...]
    min_ns: int
    median_ns: int
    p95_ns: int | None
    p99_ns: int | None
    max_ns: int
    throughput_ops_per_sec: float

    def __post_init__(self) -> None:
        if type(self.operations_per_sample) is not int:
            raise TypeError("operations_per_sample must be an exact int")
        if self.operations_per_sample <= 0:
            raise ValueError("operations_per_sample must be positive")
        samples = tuple(self.raw_samples_ns)
        if not samples:
            raise ValueError("raw_samples_ns must not be empty")
        if any(type(value) is not int for value in samples):
            raise TypeError("raw_samples_ns must contain exact ints")
        if any(value < 0 for value in samples) or sum(samples) <= 0:
            raise ValueError("raw_samples_ns must be non-negative with positive total")
        object.__setattr__(self, "raw_samples_ns", samples)
        for field in ("min_ns", "median_ns", "max_ns"):
            if type(getattr(self, field)) is not int:
                raise TypeError(f"{field} must be an exact int")
        for field in ("p95_ns", "p99_ns"):
            value = getattr(self, field)
            if value is not None and type(value) is not int:
                raise TypeError(f"{field} must be an exact int or None")
        if self.min_ns != min(samples) or self.max_ns != max(samples):
            raise ValueError("min_ns and max_ns must match raw samples")
        if type(self.throughput_ops_per_sec) is not float:
            raise TypeError("throughput_ops_per_sec must be an exact float")
        if not math.isfinite(self.throughput_ops_per_sec) or self.throughput_ops_per_sec <= 0:
            raise ValueError("throughput_ops_per_sec must be finite and positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkEnvironment:
    python: str
    implementation: str
    platform: str
    processor: str
    cpu_count: int | None
    git_sha: str
    seed: int
    profile_registry_digest: str
    dependency_lock_digest: str
    dependencies: FieldPairs
    extensions: FieldPairs = ()
    source_dirty: bool = False

    def __post_init__(self) -> None:
        for field in ("python", "implementation", "platform", "processor"):
            _exact_text(getattr(self, field), field=field)
        if self.cpu_count is not None:
            if type(self.cpu_count) is not int:
                raise TypeError("cpu_count must be an exact int or None")
            if self.cpu_count <= 0:
                raise ValueError("cpu_count must be positive")
        _git_sha(self.git_sha, field="git_sha")
        if type(self.seed) is not int:
            raise TypeError("seed must be an exact int")
        _sha256(self.profile_registry_digest, field="profile_registry_digest")
        _sha256(self.dependency_lock_digest, field="dependency_lock_digest")
        object.__setattr__(self, "dependencies", _field_pairs(self.dependencies, field="dependencies"))
        object.__setattr__(self, "extensions", _field_pairs(self.extensions, field="extensions"))
        if type(self.source_dirty) is not bool:
            raise TypeError("source_dirty must be an exact bool")


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkRunIdentity:
    mode_order: tuple[str, ...]
    role: str = "snapshot"
    runner_id: str | None = None
    pair_id: str | None = None
    pair_index: int | None = None
    candidate_order: str | None = None

    def __post_init__(self) -> None:
        modes = tuple(self.mode_order)
        if not modes or len(set(modes)) != len(modes) or not set(modes) <= {"sync", "async"}:
            raise ValueError("mode_order must contain unique supported modes")
        object.__setattr__(self, "mode_order", modes)
        pairing = (self.runner_id, self.pair_id, self.pair_index, self.candidate_order)
        if self.role == "snapshot":
            if any(value is not None for value in pairing):
                raise ValueError("snapshot runs cannot carry pairing fields")
            return
        if self.role not in {"baseline", "candidate"} or any(value is None for value in pairing):
            raise ValueError("paired roles require every pairing field")
        _identifier(self.runner_id, field="runner_id")
        _identifier(self.pair_id, field="pair_id")
        if type(self.pair_index) is not int:
            raise TypeError("pair_index must be an exact int")
        if self.pair_index < 0:
            raise ValueError("pair_index must be non-negative")
        expected = "baseline-first" if self.pair_index % 2 == 0 else "candidate-first"
        if self.candidate_order != expected:
            raise ValueError("candidate_order does not match pair_index parity")


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkScenarioResult:
    scenario_id: str
    mode: str
    parameters: FieldPairs
    timing: TimingSummary
    metrics: FieldPairs
    invariants: tuple[tuple[str, bool], ...]

    def __post_init__(self) -> None:
        _identifier(self.scenario_id, field="scenario_id")
        if self.mode not in {"sync", "async"}:
            raise ValueError("mode is unsupported")
        parameters = _field_pairs(self.parameters, field="parameters")
        if "case_id" not in dict(parameters):
            raise ValueError("parameters must contain case_id")
        _identifier(dict(parameters)["case_id"], field="case_id")
        object.__setattr__(self, "parameters", parameters)
        if type(self.timing) is not TimingSummary:
            raise TypeError("timing must be an exact TimingSummary")
        object.__setattr__(self, "metrics", _field_pairs(self.metrics, field="metrics"))
        object.__setattr__(self, "invariants", _bool_pairs(self.invariants, field="invariants"))


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkReport:
    schema_version: int
    profile: str
    environment: BenchmarkEnvironment
    run: BenchmarkRunIdentity
    scenarios: tuple[BenchmarkScenarioResult, ...]
    production_capacity_claim: bool = False

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int:
            raise TypeError("schema_version must be an exact int")
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        _identifier(self.profile, field="profile")
        if type(self.environment) is not BenchmarkEnvironment:
            raise TypeError("environment must be an exact BenchmarkEnvironment")
        if type(self.run) is not BenchmarkRunIdentity:
            raise TypeError("run must be an exact BenchmarkRunIdentity")
        scenarios = tuple(self.scenarios)
        if not scenarios or any(type(item) is not BenchmarkScenarioResult for item in scenarios):
            raise ValueError("scenarios must contain benchmark scenario results")
        identities: set[tuple[str, str, object]] = set()
        for item in scenarios:
            identity = (item.mode, item.scenario_id, dict(item.parameters)["case_id"])
            if identity in identities:
                raise ValueError("scenario identity must be unique")
            identities.add(identity)
        if set(self.run.mode_order) != {item.mode for item in scenarios}:
            raise ValueError("mode_order must match scenario modes")
        object.__setattr__(self, "scenarios", scenarios)
        if type(self.production_capacity_claim) is not bool:
            raise TypeError("production_capacity_claim must be an exact bool")
        if self.production_capacity_claim:
            raise ValueError("production capacity claims are forbidden")


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkDelta:
    mode: str
    scenario_id: str
    case_id: str
    statistic: str
    baseline_ns: int
    candidate_ns: int
    absolute_delta_ns: int
    relative_delta_percent: float

    def __post_init__(self) -> None:
        if self.mode not in {"sync", "async"}:
            raise ValueError("mode is unsupported")
        _identifier(self.scenario_id, field="scenario_id")
        _identifier(self.case_id, field="case_id")
        if self.statistic not in {"median_ns", "p95_ns"}:
            raise ValueError("statistic is unsupported")
        for field in ("baseline_ns", "candidate_ns", "absolute_delta_ns"):
            if type(getattr(self, field)) is not int:
                raise TypeError(f"{field} must be an exact int")
        if self.baseline_ns <= 0 or self.candidate_ns <= 0:
            raise ValueError("compared timings must be positive")
        if self.absolute_delta_ns != self.candidate_ns - self.baseline_ns:
            raise ValueError("absolute_delta_ns is inconsistent")
        if type(self.relative_delta_percent) is not float or not math.isfinite(
            self.relative_delta_percent
        ):
            raise ValueError("relative_delta_percent must be finite")


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkComparison:
    schema_version: int
    comparable: bool
    reasons: tuple[str, ...]
    baseline_git_sha: str
    candidate_git_sha: str
    deltas: tuple[BenchmarkDelta, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("schema_version must be exact int 1")
        if type(self.comparable) is not bool:
            raise TypeError("comparable must be an exact bool")
        reasons = tuple(sorted(self.reasons))
        for reason in reasons:
            _identifier(reason, field="reason")
        if len(set(reasons)) != len(reasons):
            raise ValueError("reasons must be unique")
        object.__setattr__(self, "reasons", reasons)
        _git_sha(self.baseline_git_sha, field="baseline_git_sha")
        _git_sha(self.candidate_git_sha, field="candidate_git_sha")
        deltas = tuple(self.deltas)
        if any(type(delta) is not BenchmarkDelta for delta in deltas):
            raise TypeError("deltas must contain exact BenchmarkDelta values")
        object.__setattr__(self, "deltas", deltas)
        if self.comparable and reasons:
            raise ValueError("comparable results cannot have reasons")
        if not self.comparable and (not reasons or deltas):
            raise ValueError("non-comparable results require reasons and no deltas")


__all__ = [
    "BenchmarkComparison",
    "BenchmarkDelta",
    "BenchmarkEnvironment",
    "BenchmarkReport",
    "BenchmarkRunIdentity",
    "BenchmarkScalar",
    "BenchmarkScenarioResult",
    "TimingSummary",
]
