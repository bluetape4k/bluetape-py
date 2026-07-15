import hashlib
import importlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[3]
SOURCE = ROOT / "docs/research/sources/iso4217/2026-07-15-list-one.xml"
PROVENANCE = ROOT / "docs/research/sources/iso4217/2026-07-15-list-one.provenance.json"


def test_iso4217_provenance_matches_source() -> None:
    generated = importlib.import_module("bluetape.money._iso4217")
    provenance = json.loads(PROVENANCE.read_text())
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert provenance["sha256"] == digest == generated.SOURCE_SHA256
    assert provenance["byte_count"] == SOURCE.stat().st_size
    assert provenance["source_row_count"] == generated.SOURCE_ROW_COUNT
    assert provenance["unique_currency_count"] == generated.SOURCE_UNIQUE_CURRENCY_COUNT
    assert provenance["excluded_codes"] == list(generated.EXCLUDED_CODES) == ["XTS", "XXX"]
    assert provenance["generated_output"] == (
        "packages/bluetape-money/src/bluetape/money/_iso4217.py"
    )
    assert len(generated.CURRENCY_ROWS) == generated.SOURCE_UNIQUE_CURRENCY_COUNT - 2


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
