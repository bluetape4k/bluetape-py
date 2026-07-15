import importlib.util
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts/update-iso4217.py"
SAMPLE = Path(__file__).parent / "fixtures/iso4217-list-one-sample.xml"
SOURCE_URL = "https://example.test/list-one.xml"
CANONICAL_SOURCE_URL = (
    "https://www.six-group.com/dam/download/financial-information/"
    "data-center/iso-currrency/lists/list-one.xml"
)


def load_updater():
    specification = importlib.util.spec_from_file_location("update_iso4217", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def run_updater(
    input_path: Path,
    output_path: Path,
    *,
    source_url: str = SOURCE_URL,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--source-url",
            source_url,
            "--retrieved-date",
            "2026-07-15",
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_iso4217_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    assert run_updater(SAMPLE, first).returncode == 0
    assert run_updater(SAMPLE, second).returncode == 0
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text()
    assert "SOURCE_ROW_COUNT = 6" in text
    assert "SOURCE_UNIQUE_CURRENCY_COUNT = 4" in text
    assert 'EXCLUDED_CODES = ("XTS", "XXX")' in text
    assert '("JPY", "392", "Yen", 0)' in text
    assert '("USD", "840", "US Dollar", 2)' in text
    assert text.index('("JPY"') < text.index('("USD"')


def test_iso4217_conflicts_and_schema_drift_fail_closed(tmp_path: Path) -> None:
    output = tmp_path / "output.py"
    output.write_text("sentinel")
    conflict = tmp_path / "conflict.xml"
    conflict.write_text(
        SAMPLE.read_text().replace("<CcyNbr>840</CcyNbr>", "<CcyNbr>841</CcyNbr>", 1)
    )
    completed = run_updater(conflict, output)
    assert completed.returncode != 0
    assert "iso4217:conflict:" in completed.stderr
    assert output.read_text() == "sentinel"

    for payload, category in (
        (b"<!DOCTYPE root><ISO_4217/>", "schema"),
        (b"<changed/>", "schema"),
        (b"x" * ((2 * 1024 * 1024) + 1), "size"),
    ):
        invalid = tmp_path / f"{category}-{len(payload)}.xml"
        invalid.write_bytes(payload)
        completed = run_updater(invalid, output)
        assert completed.returncode != 0
        assert f"iso4217:{category}:" in completed.stderr
        assert output.read_text() == "sentinel"


def test_iso4217_incomplete_or_nested_schema_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "output.py"
    output.write_text("sentinel")
    payloads = {
        "empty": '<ISO_4217 Pblshd="2026-01-01"><CcyTbl/></ISO_4217>',
        "missing-country": SAMPLE.read_text().replace(
            "<CtryNm>UNITED STATES OF AMERICA</CtryNm>", "", 1
        ),
        "nested-name": SAMPLE.read_text().replace(
            "<CcyNm>US Dollar</CcyNm>",
            "<CcyNm>US<Unexpected/> Dollar</CcyNm>",
            1,
        ),
        "field-attribute": SAMPLE.read_text().replace(
            "<Ccy>USD</Ccy>", '<Ccy status="active">USD</Ccy>', 1
        ),
    }
    for name, payload in payloads.items():
        invalid = tmp_path / f"{name}.xml"
        invalid.write_text(payload)
        completed = run_updater(invalid, output)
        assert completed.returncode != 0
        assert "iso4217:schema:" in completed.stderr
        assert output.read_text() == "sentinel"


def test_canonical_iso4217_snapshot_rejects_truncation(tmp_path: Path) -> None:
    output = tmp_path / "output.py"
    output.write_text("sentinel")
    truncated = tmp_path / "truncated.xml"
    truncated.write_text(SAMPLE.read_text())
    completed = run_updater(
        truncated,
        output,
        source_url=CANONICAL_SOURCE_URL,
    )
    assert completed.returncode != 0
    assert "iso4217:bounds:" in completed.stderr
    assert output.read_text() == "sentinel"


def test_iso4217_row_currency_and_alias_bounds_fail_closed(tmp_path: Path) -> None:
    output = tmp_path / "output.py"
    output.write_text("sentinel")
    rows = "".join(
        "<CcyNtry><CtryNm>X</CtryNm><CcyNm>No universal currency</CcyNm></CcyNtry>"
        for _ in range(1025)
    )
    excessive_rows = tmp_path / "rows.xml"
    excessive_rows.write_text(f'<ISO_4217 Pblshd="2026-01-01"><CcyTbl>{rows}</CcyTbl></ISO_4217>')
    completed = run_updater(excessive_rows, output)
    assert completed.returncode != 0
    assert "iso4217:bounds:" in completed.stderr
    assert output.read_text() == "sentinel"

    currencies = []
    for index in range(513):
        first, remainder = divmod(index, 26 * 26)
        second, third = divmod(remainder, 26)
        code = "".join(chr(ord("A") + value) for value in (first, second, third))
        currencies.append(
            "<CcyNtry><CtryNm>X</CtryNm><CcyNm>Name</CcyNm>"
            f"<Ccy>{code}</Ccy><CcyNbr>{index:03d}</CcyNbr>"
            "<CcyMnrUnts>2</CcyMnrUnts></CcyNtry>"
        )
    excessive_currencies = tmp_path / "currencies.xml"
    excessive_currencies.write_text(
        '<ISO_4217 Pblshd="2026-01-01"><CcyTbl>' + "".join(currencies) + "</CcyTbl></ISO_4217>"
    )
    completed = run_updater(excessive_currencies, output)
    assert completed.returncode != 0
    assert "iso4217:bounds:" in completed.stderr
    assert output.read_text() == "sentinel"

    completed = run_updater(SAMPLE, SAMPLE)
    assert completed.returncode != 0
    assert "iso4217:alias:" in completed.stderr


def test_iso4217_atomic_replace_preserves_previous_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    updater = load_updater()
    output = tmp_path / "output.py"
    output.write_text("sentinel")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(updater.os, "replace", fail_replace)
    with pytest.raises(updater.GenerationError) as captured:
        updater.generate(SAMPLE, output, SOURCE_URL, "2026-07-15")
    assert captured.value.category == "replace"
    assert output.read_text() == "sentinel"
    assert list(tmp_path.glob(".output.py.*.tmp")) == []


def test_money_build_and_import_are_network_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts: list[str] = []

    def deny_network(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", deny_network)
    monkeypatch.setattr(urllib.request, "urlopen", deny_network)
    sys.modules.pop("bluetape.money._iso4217", None)
    __import__("bluetape.money._iso4217")
    assert attempts == []

    environment = os.environ.copy()
    environment["UV_OFFLINE"] = "1"
    completed = subprocess.run(
        ["uv", "build", "--package", "bluetape-money", "--out-dir", str(tmp_path / "dist")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    production_paths = [
        *(ROOT / "packages/bluetape-money/src").rglob("*.py"),
        ROOT / "packages/bluetape-money/pyproject.toml",
    ]
    production = "\n".join(path.read_text() for path in production_paths)
    assert "urllib" not in production
    assert "requests" not in production
    assert "socket" not in production
