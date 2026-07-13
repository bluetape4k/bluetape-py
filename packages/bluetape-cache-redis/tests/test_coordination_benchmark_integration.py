"""Serial real-Redis proof for the bounded coordination benchmark."""

import subprocess
import sys
from pathlib import Path

import pytest
from bluetape.benchmark import read_report

REPOSITORY = Path(__file__).parents[3]
BENCHMARK = REPOSITORY / "packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py"


@pytest.mark.testcontainers
def test_real_redis_smoke_emits_twelve_valid_results(tmp_path: Path) -> None:
    output = tmp_path / "smoke.json"
    completed = subprocess.run(
        (
            sys.executable,
            str(BENCHMARK),
            "--profile",
            "smoke",
            "--mode",
            "both",
            "--seed",
            "20260712",
            "--output",
            str(output),
        ),
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    report = read_report(output)
    assert len(report.scenarios) == 12
    assert sum(len(item.timing.raw_samples_ns) for item in report.scenarios) == 60
    assert (
        sum(
            item.timing.operations_per_sample * len(item.timing.raw_samples_ns)
            for item in report.scenarios
        )
        == 10_400
    )
    assert all(item.timing.p95_ns is None for item in report.scenarios)
    assert all(item.timing.p99_ns is None for item in report.scenarios)
    assert all(all(passed for _, passed in item.invariants) for item in report.scenarios)


@pytest.mark.testcontainers
def test_real_redis_full_stale_result_observes_active_snapshots(tmp_path: Path) -> None:
    output = tmp_path / "full-multi-coordinator.json"
    completed = subprocess.run(
        (
            sys.executable,
            str(BENCHMARK),
            "--profile",
            "full",
            "--mode",
            "both",
            "--scenario",
            "multi-coordinator",
            "--seed",
            "20260713",
            "--output",
            str(output),
        ),
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    report = read_report(output)
    selected = [
        item for item in report.scenarios if dict(item.parameters)["case_id"] == "high-medium-short"
    ]
    assert [item.mode for item in selected] == ["sync", "async"]
    for item in selected:
        parameters = dict(item.parameters)
        metrics = dict(item.metrics)
        assert parameters["stale_result_bytes"] == 65_536
        assert metrics["correctness_active_snapshot_count"] >= 2
        assert dict(item.invariants)["multiple_active_snapshots"] is True
        assert all(passed for _, passed in item.invariants)
