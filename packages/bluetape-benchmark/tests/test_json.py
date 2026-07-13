import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from bluetape.benchmark import read_report, write_report
from test_contracts import report

ROOT = Path(__file__).parents[3]
DESIGN = ROOT / "docs/superpowers/specs/2026-07-12-issue-65-redis-coordination-benchmark-design.md"


def test_report_round_trip_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    write_report(path, report())
    first = path.read_bytes()
    assert read_report(path) == report()
    write_report(path, report())
    assert path.read_bytes() == first
    assert first.endswith(b"\n")


def test_writer_uses_restrictive_mode(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    write_report(path, report())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_writer_rejects_symlink_and_preserves_real_target(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text("previous")
    link = tmp_path / "report.json"
    link.symlink_to(real)
    with pytest.raises(ValueError):
        write_report(link, report())
    assert real.read_text() == "previous"


def test_writer_rejects_symlink_parent(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        write_report(link / "report.json", report())


def test_writer_rejects_non_regular_target(tmp_path: Path) -> None:
    directory = tmp_path / "report.json"
    directory.mkdir()
    with pytest.raises(ValueError):
        write_report(directory, report())


def test_concurrent_writers_leave_one_complete_report(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    first = report()
    second = replace(report(), profile="full")
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda value: write_report(path, value), (first, second)))
    assert read_report(path) in {first, second}
    assert not list(tmp_path.glob(".bluetape-benchmark-*.tmp"))


def test_invalid_report_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"schema_version": 1, "unexpected": True}))
    with pytest.raises(ValueError):
        read_report(path)


def test_existing_file_survives_serialization_failure(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "report.json"
    path.write_text("previous")

    def fail(*_args, **_kwargs):
        raise OSError("injected")

    monkeypatch.setattr(os, "fdopen", fail)
    with pytest.raises(OSError):
        write_report(path, report())
    assert path.read_text() == "previous"
    assert not list(tmp_path.glob(".bluetape-benchmark-*.tmp"))


def test_design_json_example_is_a_valid_filtered_smoke_report(tmp_path: Path) -> None:
    text = DESIGN.read_text()
    payload = text.split("```json\n", 1)[1].split("\n```", 1)[0]
    path = tmp_path / "example.json"
    path.write_text(payload)
    parsed = read_report(path)
    assert parsed.profile == "smoke"
    assert parsed.run.mode_order == ("sync",)
    assert len(parsed.scenarios[0].timing.raw_samples_ns) == 5
