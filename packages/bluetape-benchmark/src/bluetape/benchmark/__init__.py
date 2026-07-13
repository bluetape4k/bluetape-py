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
from ._json import read_report, write_comparison, write_report
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
    "read_report",
    "summarize_timings",
    "write_comparison",
    "write_report",
]
