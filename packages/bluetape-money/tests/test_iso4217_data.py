import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
SOURCE = ROOT / "docs/research/sources/iso4217/2026-07-15-list-one.xml"
PROVENANCE = ROOT / "docs/research/sources/iso4217/2026-07-15-list-one.provenance.json"
SCRIPT = ROOT / "scripts/update-iso4217.py"


def test_iso4217_provenance_matches_source() -> None:
    generated = importlib.import_module("bluetape.money._iso4217")
    provenance = json.loads(PROVENANCE.read_text())
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert provenance["sha256"] == digest == generated.SOURCE_SHA256
    assert provenance["byte_count"] == SOURCE.stat().st_size
    assert provenance["canonical_url"] == provenance["effective_url"] == generated.SOURCE_URL
    assert provenance["retrieved_at_utc"].startswith(generated.RETRIEVED_DATE)
    assert provenance["published_date"] == generated.PUBLISHED_DATE
    assert provenance["source_row_count"] == generated.SOURCE_ROW_COUNT
    assert provenance["unique_currency_count"] == generated.SOURCE_UNIQUE_CURRENCY_COUNT
    assert provenance["excluded_codes"] == list(generated.EXCLUDED_CODES) == ["XTS", "XXX"]
    assert provenance["excluded_code_count"] == len(generated.EXCLUDED_CODES)
    assert provenance["generated_output"] == (
        "packages/bluetape-money/src/bluetape/money/_iso4217.py"
    )
    assert len(generated.CURRENCY_ROWS) == generated.SOURCE_UNIQUE_CURRENCY_COUNT - 2


def test_iso4217_source_bytes_match_the_git_index() -> None:
    relative_source = SOURCE.relative_to(ROOT)
    attribute = subprocess.run(
        ["git", "check-attr", "text", "--", str(relative_source)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert attribute.stdout.rstrip().endswith(": text: unset")
    indexed = subprocess.run(
        ["git", "show", f":{relative_source}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    assert indexed.stdout == SOURCE.read_bytes()


def test_full_iso4217_source_regenerates_the_committed_table(tmp_path: Path) -> None:
    generated = importlib.import_module("bluetape.money._iso4217")
    output = tmp_path / "_iso4217.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(SOURCE),
            "--output",
            str(output),
            "--source-url",
            generated.SOURCE_URL,
            "--retrieved-date",
            generated.RETRIEVED_DATE,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    committed = ROOT / "packages/bluetape-money/src/bluetape/money/_iso4217.py"
    assert output.read_bytes() == committed.read_bytes()


def test_generated_currency_rows_are_unique_and_current() -> None:
    generated = importlib.import_module("bluetape.money._iso4217")
    codes = [row[0] for row in generated.CURRENCY_ROWS]
    numeric_codes = [row[1] for row in generated.CURRENCY_ROWS]
    assert codes == sorted(codes)
    assert len(codes) == len(set(codes))
    assert len(numeric_codes) == len(set(numeric_codes))
    rows = {row[0]: row[1:] for row in generated.CURRENCY_ROWS}
    assert rows["USD"] == ("840", "US Dollar", 2)
    assert rows["EUR"] == ("978", "Euro", 2)
    assert rows["KRW"] == ("410", "Won", 0)
    assert rows["JPY"] == ("392", "Yen", 0)
    assert rows["CNY"] == ("156", "Yuan Renminbi", 2)
