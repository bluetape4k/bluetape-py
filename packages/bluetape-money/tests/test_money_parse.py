"""Parsing contract tests for bluetape-money."""

from decimal import ROUND_DOWN, Decimal

import pytest
from bluetape.money import USD, InvalidAmountError, InvalidCurrencyError, Money, parse_money


def test_format_and_parse_are_canonical() -> None:
    value = Money.of(Decimal("1234.500"), USD)
    assert value.format() == "USD 1234.500"
    assert value.format(quantize=True, rounding=ROUND_DOWN) == "USD 1234.50"
    assert parse_money("usd 1234.500") == value
    assert parse_money("USD 1e2") == Money.of("1e2", USD)


@pytest.mark.parametrize(
    "text",
    [
        "",
        " USD 1",
        "USD 1 ",
        "USD",
        "USD  1",
        "US 1",
        "840 1",
        "USD \uff11",
        "USD NaN",
        "USD 1_000",
        "USD " + "1" * 513,
    ],
)
def test_parse_money_rejects_noncanonical_or_invalid_text(text: str) -> None:
    with pytest.raises(InvalidAmountError):
        parse_money(text)


def test_parse_money_rejects_unknown_currency() -> None:
    with pytest.raises(InvalidCurrencyError):
        parse_money("XXX 1")
    with pytest.raises(InvalidCurrencyError):
        parse_money("XTS 1")


def test_parse_money_rejects_wrong_type() -> None:
    with pytest.raises(TypeError):
        parse_money(1)  # type: ignore[arg-type]
