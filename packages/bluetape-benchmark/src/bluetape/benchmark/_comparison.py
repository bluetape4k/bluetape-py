"""Fail-closed comparison of paired benchmark reports."""

from ._contracts import BenchmarkComparison, BenchmarkDelta, BenchmarkReport


def _scenario_contract(report: BenchmarkReport) -> tuple[object, ...]:
    return tuple(
        (
            item.mode,
            item.scenario_id,
            item.parameters,
            item.timing.operations_per_sample,
            len(item.timing.raw_samples_ns),
            item.timing.p95_ns is not None,
        )
        for item in report.scenarios
    )


def _comparison_reasons(baseline: BenchmarkReport, candidate: BenchmarkReport) -> set[str]:
    reasons: set[str] = set()
    if baseline.schema_version != candidate.schema_version:
        reasons.add("schema-mismatch")
    if baseline.profile != candidate.profile:
        reasons.add("profile-mismatch")
    if (
        baseline.environment.profile_registry_digest
        != candidate.environment.profile_registry_digest
    ):
        reasons.add("registry-mismatch")
    if baseline.environment.seed != candidate.environment.seed:
        reasons.add("seed-mismatch")
    if baseline.environment.dependency_lock_digest != candidate.environment.dependency_lock_digest:
        reasons.add("dependency-lock-mismatch")
    if baseline.environment.dependencies != candidate.environment.dependencies:
        reasons.add("dependencies-mismatch")
    if (
        baseline.environment.python,
        baseline.environment.implementation,
        baseline.environment.platform,
        baseline.environment.processor,
        baseline.environment.cpu_count,
    ) != (
        candidate.environment.python,
        candidate.environment.implementation,
        candidate.environment.platform,
        candidate.environment.processor,
        candidate.environment.cpu_count,
    ):
        reasons.add("runtime-mismatch")
    if baseline.environment.extensions != candidate.environment.extensions:
        reasons.add("environment-mismatch")
    if baseline.environment.source_dirty or candidate.environment.source_dirty:
        reasons.add("source-dirty")
    if baseline.environment.git_sha == candidate.environment.git_sha:
        reasons.add("git-sha-match")
    if baseline.run.role != "baseline" or candidate.run.role != "candidate":
        reasons.add("role-mismatch")
    if baseline.run.mode_order != candidate.run.mode_order:
        reasons.add("mode-order-mismatch")
    if (
        baseline.run.runner_id,
        baseline.run.pair_id,
        baseline.run.pair_index,
        baseline.run.candidate_order,
    ) != (
        candidate.run.runner_id,
        candidate.run.pair_id,
        candidate.run.pair_index,
        candidate.run.candidate_order,
    ):
        reasons.add("pairing-mismatch")
    if _scenario_contract(baseline) != _scenario_contract(candidate):
        reasons.add("workload-mismatch")
    return reasons


def _delta(
    baseline,
    candidate,
    statistic: str,
) -> BenchmarkDelta:
    baseline_ns = getattr(baseline.timing, statistic)
    candidate_ns = getattr(candidate.timing, statistic)
    if type(baseline_ns) is not int or type(candidate_ns) is not int:
        raise ValueError("compared statistic must be available in both reports")
    absolute = candidate_ns - baseline_ns
    return BenchmarkDelta(
        mode=baseline.mode,
        scenario_id=baseline.scenario_id,
        case_id=dict(baseline.parameters)["case_id"],
        statistic=statistic,
        baseline_ns=baseline_ns,
        candidate_ns=candidate_ns,
        baseline_samples_ns=baseline.timing.raw_samples_ns,
        candidate_samples_ns=candidate.timing.raw_samples_ns,
        absolute_delta_ns=absolute,
        relative_delta_percent=float(absolute / baseline_ns * 100),
    )


def compare_reports(baseline: BenchmarkReport, candidate: BenchmarkReport) -> BenchmarkComparison:
    """Compare a validated baseline/candidate pair or return fixed rejection reasons."""
    if type(baseline) is not BenchmarkReport or type(candidate) is not BenchmarkReport:
        raise TypeError("baseline and candidate must be exact BenchmarkReport values")
    reasons = tuple(sorted(_comparison_reasons(baseline, candidate)))
    if reasons:
        return BenchmarkComparison(
            schema_version=1,
            comparable=False,
            reasons=reasons,
            baseline_git_sha=baseline.environment.git_sha,
            candidate_git_sha=candidate.environment.git_sha,
            deltas=(),
        )
    deltas = tuple(
        _delta(base, current, statistic)
        for base, current in zip(baseline.scenarios, candidate.scenarios, strict=True)
        for statistic in ("median_ns", "p95_ns")
        if getattr(base.timing, statistic) is not None
    )
    return BenchmarkComparison(
        schema_version=1,
        comparable=True,
        reasons=(),
        baseline_git_sha=baseline.environment.git_sha,
        candidate_git_sha=candidate.environment.git_sha,
        deltas=deltas,
    )


__all__ = ["compare_reports"]
