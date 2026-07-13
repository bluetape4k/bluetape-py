from dataclasses import FrozenInstanceError, replace

import pytest
from bluetape.benchmark import (
    BenchmarkComparison,
    BenchmarkDelta,
    BenchmarkEnvironment,
    BenchmarkReport,
    BenchmarkRunIdentity,
    BenchmarkScenarioResult,
    TimingSummary,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def timing(*, samples: tuple[int, ...] = (1, 2, 3)) -> TimingSummary:
    return TimingSummary(
        operations_per_sample=1,
        raw_samples_ns=samples,
        min_ns=min(samples),
        median_ns=samples[(len(samples) - 1) // 2],
        p95_ns=None,
        p99_ns=None,
        max_ns=max(samples),
        throughput_ops_per_sec=len(samples) * 1_000_000_000 / sum(samples),
    )


def environment() -> BenchmarkEnvironment:
    return BenchmarkEnvironment(
        python="3.13.14",
        implementation="CPython",
        platform="darwin-arm64",
        processor="arm",
        cpu_count=10,
        git_sha="1" * 40,
        seed=20260712,
        profile_registry_digest=SHA_A,
        dependency_lock_digest=SHA_B,
        dependencies=(("redis", "8.0.1"),),
        extensions=(("redis_version", "8.0.1"),),
        source_dirty=False,
    )


def scenario(
    *,
    parameters: object = (("payload_bytes", 1024), ("case_id", "small")),
    invariants: object = (("loader_count", True),),
) -> BenchmarkScenarioResult:
    return BenchmarkScenarioResult(
        scenario_id="multi-coordinator",
        mode="sync",
        parameters=parameters,  # type: ignore[arg-type]
        timing=timing(),
        metrics=(("loader_count", 1),),
        invariants=invariants,  # type: ignore[arg-type]
    )


def report() -> BenchmarkReport:
    return BenchmarkReport(
        schema_version=1,
        profile="smoke",
        environment=environment(),
        run=BenchmarkRunIdentity(mode_order=("sync",)),
        scenarios=(scenario(),),
    )


def test_report_copies_and_sorts_caller_owned_fields() -> None:
    values = {"payload_bytes": 1024, "case_id": "small"}
    result = scenario(parameters=values)
    values["payload_bytes"] = 0
    assert result.parameters == (("case_id", "small"), ("payload_bytes", 1024))


def test_contracts_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        report().profile = "full"  # type: ignore[misc]


@pytest.mark.parametrize("value", [True, -1, 1.5])
def test_pair_index_requires_exact_non_negative_int(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        BenchmarkRunIdentity(
            mode_order=("sync",),
            role="baseline",
            runner_id="runner-a",
            pair_id="pair-000",
            pair_index=value,  # type: ignore[arg-type]
            candidate_order="baseline-first",
        )


def test_snapshot_rejects_pairing_fields_and_failed_invariant() -> None:
    with pytest.raises(ValueError):
        BenchmarkRunIdentity(mode_order=("sync",), role="snapshot", pair_id="pair-000")
    with pytest.raises(ValueError):
        scenario(invariants={"loader_count": False})


def test_pair_parity_and_identifier_grammar_are_enforced() -> None:
    with pytest.raises(ValueError):
        BenchmarkRunIdentity(
            mode_order=("sync",),
            role="candidate",
            runner_id="Runner A",
            pair_id="pair-000",
            pair_index=0,
            candidate_order="candidate-first",
        )


def test_report_rejects_duplicate_scenario_identity() -> None:
    with pytest.raises(ValueError):
        replace(report(), scenarios=(scenario(), scenario()))


def test_report_rejects_capacity_claim_and_unknown_schema() -> None:
    with pytest.raises(ValueError):
        replace(report(), production_capacity_claim=True)
    with pytest.raises(ValueError):
        replace(report(), schema_version=2)


def test_environment_rejects_bool_count_and_malformed_digest() -> None:
    with pytest.raises(TypeError):
        replace(environment(), cpu_count=True)
    with pytest.raises(ValueError):
        replace(environment(), profile_registry_digest="not-a-digest")


def test_comparison_requires_empty_deltas_when_not_comparable() -> None:
    delta = BenchmarkDelta(
        mode="sync",
        scenario_id="multi-coordinator",
        case_id="small",
        statistic="median_ns",
        baseline_ns=100,
        candidate_ns=110,
        absolute_delta_ns=10,
        relative_delta_percent=10.0,
    )
    with pytest.raises(ValueError):
        BenchmarkComparison(
            schema_version=1,
            comparable=False,
            reasons=("seed-mismatch",),
            baseline_git_sha="1" * 40,
            candidate_git_sha="2" * 40,
            deltas=(delta,),
        )
