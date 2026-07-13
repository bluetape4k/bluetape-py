import json
from dataclasses import replace
from pathlib import Path

import pytest
from bluetape.benchmark import (
    BenchmarkRunIdentity,
    compare_reports,
    read_report,
    summarize_timings,
    write_report,
)
from bluetape.benchmark.compare import main
from test_benchmark_contracts import report


def paired_report(role: str, duration_ns: int):
    base = report()
    timing = summarize_timings([duration_ns] * 20)
    scenario = replace(base.scenarios[0], timing=timing)
    environment = replace(base.environment, git_sha=("1" if role == "baseline" else "2") * 40)
    run = BenchmarkRunIdentity(
        mode_order=("sync",),
        role=role,
        runner_id="runner-a",
        pair_id="pair-000",
        pair_index=0,
        candidate_order="baseline-first",
    )
    return replace(base, environment=environment, run=run, scenarios=(scenario,))


def test_comparison_emits_median_and_available_p95_deltas() -> None:
    result = compare_reports(paired_report("baseline", 100), paired_report("candidate", 110))
    assert result.comparable is True
    assert result.reasons == ()
    assert [(item.statistic, item.absolute_delta_ns) for item in result.deltas] == [
        ("median_ns", 10),
        ("p95_ns", 10),
    ]
    assert all(item.relative_delta_percent == 10.0 for item in result.deltas)
    assert all(item.baseline_samples_ns == (100,) * 20 for item in result.deltas)
    assert all(item.candidate_samples_ns == (110,) * 20 for item in result.deltas)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda value: replace(value, profile="other"), "profile-mismatch"),
        (
            lambda value: replace(
                value, environment=replace(value.environment, seed=value.environment.seed + 1)
            ),
            "seed-mismatch",
        ),
        (
            lambda value: replace(
                value,
                environment=replace(value.environment, dependency_lock_digest="c" * 64),
            ),
            "dependency-lock-mismatch",
        ),
        (
            lambda value: replace(
                value,
                scenarios=(
                    replace(
                        value.scenarios[0],
                        parameters=(("case_id", "small"), ("payload_bytes", 2048)),
                    ),
                ),
            ),
            "workload-mismatch",
        ),
    ],
)
def test_comparison_rejects_required_gate(change, reason: str) -> None:
    baseline = paired_report("baseline", 100)
    candidate = change(paired_report("candidate", 110))
    result = compare_reports(baseline, candidate)
    assert result.comparable is False
    assert result.deltas == ()
    assert result.reasons == (reason,)


def test_comparison_rejects_same_git_sha_and_dirty_source() -> None:
    baseline = paired_report("baseline", 100)
    candidate = paired_report("candidate", 110)
    candidate = replace(
        candidate,
        environment=replace(
            candidate.environment,
            git_sha=baseline.environment.git_sha,
            source_dirty=True,
        ),
    )
    result = compare_reports(baseline, candidate)
    assert result.reasons == ("git-sha-match", "source-dirty")


def test_cli_returns_four_and_empty_deltas_for_non_comparable_pair(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    write_report(baseline, paired_report("baseline", 100))
    mismatched = replace(paired_report("candidate", 110), profile="other")
    write_report(candidate, mismatched)
    assert main(["--baseline", str(baseline), "--candidate", str(candidate), "--output", "-"]) == 4
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["comparable"] is False
    assert output["deltas"] == []
    assert output["reasons"] == ["profile-mismatch"]
    diagnostic = json.loads(captured.err.removeprefix("bluetape-benchmark-error "))
    assert diagnostic["category"] == "not-comparable"
    assert diagnostic["code"] == "BTBENCH_NOT_COMPARABLE"
    assert diagnostic["phase"] == "comparison"


def test_cli_parse_failure_emits_exact_diagnostic(capsys) -> None:
    assert main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    prefix = "bluetape-benchmark-error "
    assert json.loads(captured.err.removeprefix(prefix)) == {
        "case_id": None,
        "category": "input-invalid",
        "code": "BTBENCH_INPUT_INVALID",
        "mode": None,
        "phase": "comparison",
        "repetition": None,
        "scenario_id": None,
    }


def test_cli_writes_comparable_result_atomically(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "comparison.json"
    write_report(baseline, paired_report("baseline", 100))
    write_report(candidate, paired_report("candidate", 110))
    assert (
        main(
            [
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["comparable"] is True
    payload = json.loads(output.read_text())
    assert payload["deltas"][0]["baseline_samples_ns"] == [100] * 20
    assert payload["deltas"][0]["candidate_samples_ns"] == [110] * 20
    assert read_report(baseline).run.role == "baseline"


def test_cli_parse_failure_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "comparison.json"
    output.write_text("previous")
    assert (
        main(
            [
                "--baseline",
                str(tmp_path / "missing.json"),
                "--candidate",
                str(tmp_path / "other.json"),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert output.read_text() == "previous"
