"""Internal benchmark contracts for source-workspace tooling."""

from ._contracts import (
    BenchmarkComparison,
    BenchmarkDelta,
    BenchmarkEnvironment,
    BenchmarkReport,
    BenchmarkRunIdentity,
    BenchmarkScalar,
    BenchmarkScenarioResult,
    TimingSummary,
)
from ._timing import nearest_rank, summarize_timings

__all__ = [
    "BenchmarkComparison",
    "BenchmarkDelta",
    "BenchmarkEnvironment",
    "BenchmarkReport",
    "BenchmarkRunIdentity",
    "BenchmarkScalar",
    "BenchmarkScenarioResult",
    "TimingSummary",
    "nearest_rank",
    "summarize_timings",
]
