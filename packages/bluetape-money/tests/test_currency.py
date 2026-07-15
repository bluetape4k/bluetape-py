import inspect
from dataclasses import FrozenInstanceError

import pytest
from bluetape.money import (
    CNY,
    EUR,
    JPY,
    KRW,
    USD,
    Currency,
    ExchangeRate,
    InvalidCurrencyError,
    Money,
    convert,
    get_currency,
    parse_money,
    sum_money,
)


def test_money_public_signatures_are_exact() -> None:
    expected = {
        Currency: (
            "(code: 'str', numeric_code: 'str', name: 'str', minor_unit: 'int | None') -> 'None'"
        ),
        Money: "(amount: 'Decimal', currency: 'Currency') -> 'None'",
        ExchangeRate: "(base: 'Currency', quote: 'Currency', rate: 'Decimal') -> 'None'",
        get_currency: "(code_or_numeric: 'str | int') -> 'Currency'",
        parse_money: "(text: 'str') -> 'Money'",
        sum_money: "(currency: 'Currency', values: 'Iterable[Money]') -> 'Money'",
        convert: "(money: 'Money', rate: 'ExchangeRate') -> 'Money'",
        Money.of: "(value: 'Decimal | int | str', currency: 'Currency') -> 'Money'",
        Money.from_minor: "(units: 'int', currency: 'Currency') -> 'Money'",
        Money.quantize: "(self, *, rounding: 'str' = 'ROUND_HALF_EVEN') -> 'Money'",
        Money.minor_units: "(self, *, rounding: 'str | None' = None) -> 'int'",
        Money.format: (
            "(self, *, quantize: 'bool' = False, rounding: 'str' = 'ROUND_HALF_EVEN') -> 'str'"
        ),
        Money.to_dict: "(self) -> 'dict[str, str]'",
        Money.from_dict: "(value: 'Mapping[str, object]') -> 'Money'",
        ExchangeRate.of: (
            "(base: 'Currency', quote: 'Currency', rate: 'Decimal | int | str') -> 'ExchangeRate'"
        ),
    }
    assert {callable_: str(inspect.signature(callable_)) for callable_ in expected} == expected


def test_currency_lookup_supports_case_insensitive_codes_and_numeric_codes() -> None:
    assert get_currency("usd") is USD
    assert get_currency("USD") is USD
    assert get_currency("840") is USD
    assert get_currency(840) is USD
    assert get_currency("008").code == "ALL"
    assert get_currency(8).code == "ALL"
    assert (EUR.code, KRW.minor_unit, JPY.minor_unit, CNY.numeric_code) == (
        "EUR",
        0,
        0,
        "156",
    )


@pytest.mark.parametrize("value", [" USD", "USD ", "", "US", "USDD", "999", -1, 1000])
def test_currency_lookup_rejects_invalid_or_unknown_values(value: str | int) -> None:
    with pytest.raises(InvalidCurrencyError):
        get_currency(value)


@pytest.mark.parametrize("value", [True, 840.0, None])
def test_currency_lookup_rejects_wrong_types(value: object) -> None:
    with pytest.raises(TypeError):
        get_currency(value)  # type: ignore[arg-type]


def test_currency_requires_exact_generated_row() -> None:
    assert Currency("USD", "840", "US Dollar", 2) == USD
    with pytest.raises(InvalidCurrencyError):
        Currency("USD", "840", "United States Dollar", 2)
    with pytest.raises(InvalidCurrencyError):
        Currency("XXX", "999", "The codes assigned for transactions", None)
    with pytest.raises(InvalidCurrencyError):
        Currency("XTS", "963", "Codes specifically reserved for testing purposes", None)
    with pytest.raises(FrozenInstanceError):
        USD.code = "EUR"  # type: ignore[misc]
    assert Currency.__slots__ == ("code", "numeric_code", "name", "minor_unit")
