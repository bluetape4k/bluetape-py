#!/usr/bin/env python3
"""Generate the bluetape-money ISO 4217 table from an explicit XML file."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_SOURCE_ROWS = 1024
MAX_UNIQUE_CURRENCIES = 512
MIN_CANONICAL_SOURCE_ROWS = 250
MIN_CANONICAL_UNIQUE_CURRENCIES = 150
EXCLUDED_CODES = ("XTS", "XXX")
CANONICAL_SOURCE_URL = (
    "https://www.six-group.com/dam/download/financial-information/"
    "data-center/iso-currrency/lists/list-one.xml"
)
EXPECTED_ROW_TAGS = {"CtryNm", "CcyNm", "Ccy", "CcyNbr", "CcyMnrUnts"}
EXIT_CODES = {
    "size": 10,
    "schema": 11,
    "conflict": 12,
    "bounds": 13,
    "alias": 14,
    "serialization": 15,
    "replace": 16,
}


class GenerationError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True, slots=True)
class CurrencyRow:
    code: str
    numeric_code: str
    name: str
    minor_unit: int | None


@dataclass(frozen=True, slots=True)
class Snapshot:
    published_date: str
    source_row_count: int
    unique_currency_count: int
    rows: tuple[CurrencyRow, ...]


def _single_text(element: ElementTree.Element, tag: str, *, required: bool) -> str:
    children = element.findall(tag)
    if len(children) > 1:
        raise GenerationError("schema", "a currency row contains a duplicate field")
    if not children:
        value = ""
    else:
        child = children[0]
        allowed_attributes = ({"IsFund": "true"}, {}) if tag == "CcyNm" else ({},)
        if child.attrib not in allowed_attributes or list(child):
            raise GenerationError("schema", "a currency field schema changed")
        value = (child.text or "").strip()
    if required and not value:
        raise GenerationError("schema", "a currency row is missing a required field")
    return value


def _require_whitespace(value: str | None, message: str) -> None:
    if value is not None and value.strip():
        raise GenerationError("schema", message)


def _parse_xml(payload: bytes) -> Snapshot:
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise GenerationError("schema", "DTD and entity declarations are not allowed")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise GenerationError("schema", "input is not valid ISO 4217 XML") from error
    if root.tag != "ISO_4217" or set(root.attrib) != {"Pblshd"}:
        raise GenerationError("schema", "the ISO 4217 root schema changed")
    _require_whitespace(root.text, "the ISO 4217 root schema changed")
    published_date = root.attrib["Pblshd"]
    try:
        date.fromisoformat(published_date)
    except ValueError as error:
        raise GenerationError("schema", "the published date is invalid") from error

    tables = root.findall("CcyTbl")
    if len(tables) != 1 or list(root) != tables:
        raise GenerationError("schema", "the ISO 4217 table schema changed")
    table = tables[0]
    if table.attrib:
        raise GenerationError("schema", "the ISO 4217 table schema changed")
    _require_whitespace(table.text, "the ISO 4217 table schema changed")
    _require_whitespace(table.tail, "the ISO 4217 root schema changed")
    entries = list(table)
    if any(entry.tag != "CcyNtry" for entry in entries):
        raise GenerationError("schema", "the ISO 4217 row schema changed")
    if not entries:
        raise GenerationError("schema", "the ISO 4217 table is empty")
    if len(entries) > MAX_SOURCE_ROWS:
        raise GenerationError("bounds", "the source row limit was exceeded")

    currencies: dict[str, CurrencyRow] = {}
    numeric_to_code: dict[str, str] = {}
    for entry in entries:
        if entry.attrib:
            raise GenerationError("schema", "the ISO 4217 row schema changed")
        _require_whitespace(entry.text, "the ISO 4217 row schema changed")
        _require_whitespace(entry.tail, "the ISO 4217 table schema changed")
        tags = [child.tag for child in entry]
        if set(tags) - EXPECTED_ROW_TAGS or len(tags) != len(set(tags)):
            raise GenerationError("schema", "the ISO 4217 row schema changed")
        for child in entry:
            _require_whitespace(child.tail, "the ISO 4217 row schema changed")
        _single_text(entry, "CtryNm", required=True)
        code = _single_text(entry, "Ccy", required=False)
        if not code:
            if set(tags) != {"CtryNm", "CcyNm"}:
                raise GenerationError("schema", "an empty-currency row is incomplete")
            _single_text(entry, "CcyNm", required=True)
            continue
        if set(tags) != EXPECTED_ROW_TAGS:
            raise GenerationError("schema", "a currency row is incomplete")
        name = _single_text(entry, "CcyNm", required=True)
        numeric_code = _single_text(entry, "CcyNbr", required=True)
        minor_text = _single_text(entry, "CcyMnrUnts", required=True)
        if re.fullmatch(r"[A-Z]{3}", code, re.ASCII) is None:
            raise GenerationError("schema", "a currency code is invalid")
        if re.fullmatch(r"[0-9]{3}", numeric_code, re.ASCII) is None:
            raise GenerationError("schema", "a numeric currency code is invalid")
        if minor_text == "N.A.":
            minor_unit = None
        elif re.fullmatch(r"[0-9]", minor_text, re.ASCII):
            minor_unit = int(minor_text)
        else:
            raise GenerationError("schema", "a minor-unit value is invalid")
        row = CurrencyRow(code, numeric_code, name, minor_unit)
        previous = currencies.get(code)
        if previous is not None and previous != row:
            raise GenerationError("conflict", "duplicate currency metadata conflicts")
        previous_code = numeric_to_code.get(numeric_code)
        if previous_code is not None and previous_code != code:
            raise GenerationError("conflict", "numeric currency codes conflict")
        currencies[code] = row
        numeric_to_code[numeric_code] = code
        if len(currencies) > MAX_UNIQUE_CURRENCIES:
            raise GenerationError("bounds", "the unique currency limit was exceeded")

    rows = tuple(currencies[code] for code in sorted(currencies) if code not in EXCLUDED_CODES)
    return Snapshot(published_date, len(entries), len(currencies), rows)


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render(snapshot: Snapshot, source_url: str, retrieved_date: str, digest: str) -> str:
    lines = [
        '"""Generated ISO 4217 current-currency data. Do not edit manually."""',
        "",
        f"SOURCE_URL = {_quoted(source_url)}",
        f"RETRIEVED_DATE = {_quoted(retrieved_date)}",
        f"SOURCE_SHA256 = {_quoted(digest)}",
        f"PUBLISHED_DATE = {_quoted(snapshot.published_date)}",
        f"SOURCE_ROW_COUNT = {snapshot.source_row_count}",
        f"SOURCE_UNIQUE_CURRENCY_COUNT = {snapshot.unique_currency_count}",
        'EXCLUDED_CODES = ("XTS", "XXX")',
        "",
        "CURRENCY_ROWS: tuple[tuple[str, str, str, int | None], ...] = (",
    ]
    for row in snapshot.rows:
        lines.append(
            "    ("
            f"{_quoted(row.code)}, {_quoted(row.numeric_code)}, {_quoted(row.name)}, "
            f"{row.minor_unit!r}),"
        )
    lines.extend((")", ""))
    return "\n".join(lines)


def _atomic_write(output_path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary_path, output_path)
        except OSError as error:
            raise GenerationError("replace", "could not replace the generated output") from error
        temporary_path = None
    except GenerationError:
        raise
    except (OSError, UnicodeError) as error:
        raise GenerationError("serialization", "could not serialize generated output") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def generate(
    input_path: Path,
    output_path: Path,
    source_url: str,
    retrieved_date: str,
) -> Snapshot:
    if input_path.resolve() == output_path.resolve():
        raise GenerationError("alias", "input and output paths must differ")
    if not source_url.startswith("https://"):
        raise GenerationError("schema", "source URL must use HTTPS")
    try:
        date.fromisoformat(retrieved_date)
    except ValueError as error:
        raise GenerationError("schema", "retrieved date must use YYYY-MM-DD") from error
    try:
        with input_path.open("rb") as stream:
            payload = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise GenerationError("schema", "could not read the XML input") from error
    if len(payload) > MAX_INPUT_BYTES:
        raise GenerationError("size", "the XML input exceeds 2 MiB")
    snapshot = _parse_xml(payload)
    if source_url == CANONICAL_SOURCE_URL and (
        snapshot.source_row_count < MIN_CANONICAL_SOURCE_ROWS
        or snapshot.unique_currency_count < MIN_CANONICAL_UNIQUE_CURRENCIES
    ):
        raise GenerationError("bounds", "the canonical ISO 4217 snapshot is incomplete")
    digest = hashlib.sha256(payload).hexdigest()
    content = _render(snapshot, source_url, retrieved_date, digest)
    _atomic_write(output_path, content)
    return snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--retrieved-date", required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        snapshot = generate(
            arguments.input,
            arguments.output,
            arguments.source_url,
            arguments.retrieved_date,
        )
    except GenerationError as error:
        print(f"iso4217:{error.category}: {error}", file=sys.stderr)
        return EXIT_CODES[error.category]
    print(
        json.dumps(
            {
                "excluded_codes": list(EXCLUDED_CODES),
                "output": str(arguments.output),
                "source_rows": snapshot.source_row_count,
                "unique_currencies": snapshot.unique_currency_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
