from decimal import Decimal, getcontext, localcontext

import pytest
from bluetape.money import (
    EUR,
    JPY,
    USD,
    CurrencyMismatchError,
    ExchangeRate,
    InvalidAmountError,
    InvalidExchangeRateError,
    Money,
    convert,
)


def test_exchange_rate_validates_exact_positive_values() -> None:
    rate = ExchangeRate.of(USD, EUR, "0.92")
    assert rate == ExchangeRate(USD, EUR, Decimal("0.92"))
    with pytest.raises(TypeError):
        ExchangeRate(USD, EUR, "0.92")  # type: ignore[arg-type]
    for value in ("0", "-1", "NaN", "Infinity", "1e257"):
        with pytest.raises(InvalidExchangeRateError):
            ExchangeRate.of(USD, EUR, value)
    for value in (True, 1.0):
        with pytest.raises(TypeError):
            ExchangeRate.of(USD, EUR, value)  # type: ignore[arg-type]
    with pytest.raises(InvalidExchangeRateError):
        ExchangeRate.of(USD, USD, "1.01")
    assert ExchangeRate.of(USD, USD, 1).rate == Decimal(1)


def test_exchange_rate_both_directions() -> None:
    rate = ExchangeRate.of(USD, EUR, "0.925")
    dollars = Money.of("12.34", USD)
    euros = convert(dollars, rate)
    assert euros == Money.of("11.41450", EUR)
    assert convert(euros, rate) == dollars
    with pytest.raises(CurrencyMismatchError):
        convert(Money.of(1, JPY), rate)
    with pytest.raises(TypeError):
        convert("USD 1", rate)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        convert(dollars, "USD/EUR")  # type: ignore[arg-type]
    identity = ExchangeRate.of(USD, USD, 1)
    assert convert(dollars, identity) == dollars


def test_exchange_conversion_never_silently_rounds() -> None:
    wide_fraction = "0." + ("1" * 200)
    rate = ExchangeRate.of(USD, EUR, wide_fraction)
    with pytest.raises(InvalidAmountError):
        convert(Money.of(wide_fraction, USD), rate)


def test_exchange_conversion_ignores_ambient_decimal_precision() -> None:
    original_precision = getcontext().prec
    with localcontext() as caller_context:
        caller_context.prec = 3
        result = convert(
            Money.of("1.23456789", USD),
            ExchangeRate.of(USD, EUR, "9.87654321"),
        )
        assert result.amount == Decimal("12.1932631112635269")
        assert caller_context.prec == 3
    assert getcontext().prec == original_precision
