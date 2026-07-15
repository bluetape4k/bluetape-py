from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ._currency import Currency
from ._decimal import calculate, parse_decimal, validate_decimal
from ._errors import CurrencyMismatchError, InvalidExchangeRateError
from ._money import Money, _require_currency


def _validate_rate(rate: Decimal) -> Decimal:
    normalized = validate_decimal(
        rate,
        error_type=InvalidExchangeRateError,
        label="rate",
    )
    if normalized <= 0:
        raise InvalidExchangeRateError("rate must be positive")
    return normalized


@dataclass(frozen=True, slots=True, init=False)
class ExchangeRate:
    base: Currency
    quote: Currency
    rate: Decimal

    def __init__(self, base: Currency, quote: Currency, rate: Decimal) -> None:
        normalized_base = _require_currency(base)
        normalized_quote = _require_currency(quote)
        if not isinstance(rate, Decimal):
            raise TypeError("rate must be a Decimal")
        normalized_rate = _validate_rate(rate)
        if normalized_base == normalized_quote and normalized_rate != 1:
            raise InvalidExchangeRateError("same-currency rate must equal one")
        object.__setattr__(self, "base", normalized_base)
        object.__setattr__(self, "quote", normalized_quote)
        object.__setattr__(self, "rate", normalized_rate)

    @classmethod
    def of(
        cls,
        base: Currency,
        quote: Currency,
        rate: Decimal | int | str,
    ) -> ExchangeRate:
        parsed = parse_decimal(
            rate,
            error_type=InvalidExchangeRateError,
            label="rate",
        )
        return cls(base, quote, parsed)


def convert(money: Money, rate: ExchangeRate) -> Money:
    if not isinstance(money, Money):
        raise TypeError("money must be Money")
    if not isinstance(rate, ExchangeRate):
        raise TypeError("rate must be an ExchangeRate")
    if money.currency == rate.base:
        amount = calculate(lambda: money.amount * rate.rate)
        return Money(amount, rate.quote)
    if money.currency == rate.quote:
        amount = calculate(lambda: money.amount / rate.rate)
        return Money(amount, rate.base)
    raise CurrencyMismatchError("money currency is unrelated to the exchange rate")
