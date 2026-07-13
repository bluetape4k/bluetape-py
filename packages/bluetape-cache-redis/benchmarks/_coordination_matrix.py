"""Exact bounded Redis coordination benchmark profiles."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace

MAX_RESULTS = 24
MAX_CALLERS = 64
MAX_COORDINATORS = 8
MAX_KEYS = 8
MAX_PAYLOAD_BYTES = 15_728_640
MAX_STALE_RESULT_BYTES = 16_777_216
MAX_AGGREGATE_PAYLOAD_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True, slots=True, kw_only=True)
class ScenarioCase:
    scenario_id: str
    case_id: str
    callers: int
    coordinators: int
    keys: int
    payload_bytes: int
    stale_result_bytes: int
    loader_delay_seconds: float
    operations_per_sample: int
    warmups: int
    repetitions: int

    def __post_init__(self) -> None:
        for field in (
            "callers",
            "coordinators",
            "keys",
            "payload_bytes",
            "stale_result_bytes",
            "operations_per_sample",
            "warmups",
            "repetitions",
        ):
            value = getattr(self, field)
            if type(value) is not int:
                raise TypeError(f"{field} must be an exact int")
            if value < 0:
                raise ValueError(f"{field} must be non-negative")
        if min(self.callers, self.coordinators, self.keys, self.operations_per_sample) < 1:
            raise ValueError("callers, coordinators, keys, and operations must be positive")
        if type(self.loader_delay_seconds) is not float:
            raise TypeError("loader_delay_seconds must be an exact float")
        if not math.isfinite(self.loader_delay_seconds) or self.loader_delay_seconds < 0:
            raise ValueError("loader_delay_seconds must be finite and non-negative")

    @property
    def near_boundary(self) -> bool:
        return self.payload_bytes == MAX_PAYLOAD_BYTES


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkProfile:
    profile_id: str
    cases: tuple[ScenarioCase, ...]
    wall_timeout_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixTotals:
    results: int
    measured_samples: int
    operations: int
    warmups: int


_SMOKE_CASES = (
    ScenarioCase(
        scenario_id="local-only",
        case_id="moderate-small-short",
        callers=8,
        coordinators=4,
        keys=1,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.005,
        operations_per_sample=8,
        warmups=1,
        repetitions=5,
    ),
    ScenarioCase(
        scenario_id="local-hit",
        case_id="steady-small",
        callers=1,
        coordinators=1,
        keys=1,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.0,
        operations_per_sample=1000,
        warmups=1,
        repetitions=5,
    ),
    ScenarioCase(
        scenario_id="single-coordinator",
        case_id="moderate-small-short",
        callers=8,
        coordinators=1,
        keys=1,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.005,
        operations_per_sample=8,
        warmups=1,
        repetitions=5,
    ),
    ScenarioCase(
        scenario_id="multi-coordinator",
        case_id="moderate-small-short",
        callers=8,
        coordinators=4,
        keys=1,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.005,
        operations_per_sample=8,
        warmups=1,
        repetitions=5,
    ),
    ScenarioCase(
        scenario_id="completed-reuse",
        case_id="moderate-small-immediate",
        callers=8,
        coordinators=4,
        keys=1,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.0,
        operations_per_sample=8,
        warmups=1,
        repetitions=5,
    ),
    ScenarioCase(
        scenario_id="unrelated-keys",
        case_id="moderate-small-short",
        callers=8,
        coordinators=4,
        keys=4,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.005,
        operations_per_sample=8,
        warmups=1,
        repetitions=5,
    ),
)

SMOKE = BenchmarkProfile(profile_id="smoke", cases=_SMOKE_CASES, wall_timeout_seconds=120)

_FULL_RETAINED = tuple(
    replace(
        case,
        warmups=3,
        repetitions=20,
        operations_per_sample=(
            10_000 if case.scenario_id == "local-hit" else case.operations_per_sample
        ),
    )
    for case in _SMOKE_CASES
)

_FULL_ADDITIONS = (
    ScenarioCase(
        scenario_id="local-only",
        case_id="high-small-long",
        callers=64,
        coordinators=8,
        keys=1,
        payload_bytes=1024,
        stale_result_bytes=0,
        loader_delay_seconds=0.05,
        operations_per_sample=64,
        warmups=3,
        repetitions=20,
    ),
    ScenarioCase(
        scenario_id="local-hit",
        case_id="single-near-boundary",
        callers=1,
        coordinators=1,
        keys=1,
        payload_bytes=MAX_PAYLOAD_BYTES,
        stale_result_bytes=0,
        loader_delay_seconds=0.0,
        operations_per_sample=3,
        warmups=3,
        repetitions=3,
    ),
    ScenarioCase(
        scenario_id="single-coordinator",
        case_id="moderate-medium-immediate",
        callers=16,
        coordinators=1,
        keys=1,
        payload_bytes=65_536,
        stale_result_bytes=0,
        loader_delay_seconds=0.0,
        operations_per_sample=16,
        warmups=3,
        repetitions=20,
    ),
    ScenarioCase(
        scenario_id="multi-coordinator",
        case_id="high-medium-short",
        callers=64,
        coordinators=8,
        keys=1,
        payload_bytes=65_536,
        stale_result_bytes=65_536,
        loader_delay_seconds=0.005,
        operations_per_sample=64,
        warmups=3,
        repetitions=20,
    ),
    ScenarioCase(
        scenario_id="completed-reuse",
        case_id="single-near-boundary",
        callers=1,
        coordinators=1,
        keys=1,
        payload_bytes=MAX_PAYLOAD_BYTES,
        stale_result_bytes=0,
        loader_delay_seconds=0.0,
        operations_per_sample=1,
        warmups=3,
        repetitions=3,
    ),
    ScenarioCase(
        scenario_id="unrelated-keys",
        case_id="high-empty-immediate",
        callers=64,
        coordinators=8,
        keys=8,
        payload_bytes=0,
        stale_result_bytes=0,
        loader_delay_seconds=0.0,
        operations_per_sample=64,
        warmups=3,
        repetitions=20,
    ),
)

FULL = BenchmarkProfile(
    profile_id="full",
    cases=_FULL_RETAINED + _FULL_ADDITIONS,
    wall_timeout_seconds=900,
)


def matrix_totals(profile: BenchmarkProfile, modes: tuple[str, ...]) -> MatrixTotals:
    multiplier = len(modes)
    return MatrixTotals(
        results=len(profile.cases) * multiplier,
        measured_samples=sum(case.repetitions for case in profile.cases) * multiplier,
        operations=sum(case.operations_per_sample * case.repetitions for case in profile.cases)
        * multiplier,
        warmups=sum(case.warmups for case in profile.cases) * multiplier,
    )


def validate_profile(profile: BenchmarkProfile, modes: tuple[str, ...]) -> None:
    if not modes or len(set(modes)) != len(modes) or not set(modes) <= {"sync", "async"}:
        raise ValueError("modes must contain unique supported values")
    totals = matrix_totals(profile, modes)
    if totals.results > MAX_RESULTS:
        raise ValueError("profile exceeds result ceiling")
    identities: set[tuple[str, str]] = set()
    for case in profile.cases:
        identity = (case.scenario_id, case.case_id)
        if identity in identities:
            raise ValueError("profile case identity must be unique")
        identities.add(identity)
        if case.callers > MAX_CALLERS or case.coordinators > MAX_COORDINATORS:
            raise ValueError("profile exceeds concurrency ceiling")
        if case.keys > MAX_KEYS or case.payload_bytes > MAX_PAYLOAD_BYTES:
            raise ValueError("profile exceeds key or payload ceiling")
        if case.stale_result_bytes > MAX_STALE_RESULT_BYTES:
            raise ValueError("profile exceeds stale result ceiling")
        if case.stale_result_bytes and (
            case.callers < 2 or case.coordinators < 2 or case.scenario_id != "multi-coordinator"
        ):
            raise ValueError("stale result fixture requires multi-coordinator waiters")
        if case.callers * case.payload_bytes > MAX_AGGREGATE_PAYLOAD_BYTES:
            raise ValueError("profile exceeds aggregate payload ceiling")
        deadline = 120 if case.near_boundary else 30
        if deadline > profile.wall_timeout_seconds:
            raise ValueError("case deadline exceeds profile deadline")


def _registry_value(profile: BenchmarkProfile) -> dict[str, object]:
    return {
        "cases": [asdict(case) for case in profile.cases],
        "profile_id": profile.profile_id,
        "wall_timeout_seconds": profile.wall_timeout_seconds,
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def registry_digest(profile: BenchmarkProfile) -> str:
    return hashlib.sha256(_canonical_json(_registry_value(profile))).hexdigest()


def derived_seed(
    root_seed: int,
    profile: str,
    mode: str,
    case: ScenarioCase,
    phase: str,
    repetition: int,
) -> int:
    value = [root_seed, profile, mode, case.scenario_id, case.case_id, phase, repetition]
    return int.from_bytes(hashlib.sha256(_canonical_json(value)).digest()[:8], "big")


validate_profile(SMOKE, ("sync", "async"))
validate_profile(FULL, ("sync", "async"))


__all__ = [
    "FULL",
    "MAX_STALE_RESULT_BYTES",
    "SMOKE",
    "BenchmarkProfile",
    "MatrixTotals",
    "ScenarioCase",
    "derived_seed",
    "matrix_totals",
    "registry_digest",
    "validate_profile",
]
