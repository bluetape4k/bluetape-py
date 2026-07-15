from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from ._currency import Currency, get_currency
from ._decimal import calculate, parse_decimal, require_rounding, validate_decimal
from ._errors import CurrencyMismatchError, InvalidAmountError, InvalidCurrencyError


def _require_currency(currency: object) -> Currency:
    if not isinstance(currency, Currency):
        raise TypeError("currency must be a Currency")
    return currency


@dataclass(frozen=True, slots=True, init=False)
class Money:
    amount: Decimal
    currency: Currency

    def __init__(self, amount: Decimal, currency: Currency) -> None:
        if not isinstance(amount, Decimal):
            raise TypeError("amount must be a Decimal")
        normalized_currency = _require_currency(currency)
        object.__setattr__(self, "amount", validate_decimal(amount))
        object.__setattr__(self, "currency", normalized_currency)

    @classmethod
    def of(cls, value: Decimal | int | str, currency: Currency) -> Money:
        return cls(parse_decimal(value), _require_currency(currency))

    @classmethod
    def from_minor(cls, units: int, currency: Currency) -> Money:
        normalized_currency = _require_currency(currency)
        if isinstance(units, bool) or not isinstance(units, int):
            raise TypeError("units must be an integer")
        minor_unit = normalized_currency.minor_unit
        if minor_unit is None:
            raise InvalidCurrencyError("currency does not define a minor unit")
        amount = calculate(lambda: Decimal(units).scaleb(-minor_unit))
        return cls(amount, normalized_currency)

    def _same_currency(self, other: object) -> Money:
        if not isinstance(other, Money):
            raise TypeError("operand must be Money")
        if self.currency != other.currency:
            raise CurrencyMismatchError("money currencies must match")
        return other

    def __add__(self, other: Money) -> Money:
        normalized = self._same_currency(other)
        return Money(calculate(lambda: self.amount + normalized.amount), self.currency)

    def __sub__(self, other: Money) -> Money:
        normalized = self._same_currency(other)
        return Money(calculate(lambda: self.amount - normalized.amount), self.currency)

    def __neg__(self) -> Money:
        return Money(calculate(lambda: -self.amount), self.currency)

    def __abs__(self) -> Money:
        return Money(calculate(lambda: abs(self.amount)), self.currency)

    def __mul__(self, scalar: Decimal | int | str) -> Money:
        normalized = parse_decimal(scalar, label="scalar")
        return Money(calculate(lambda: self.amount * normalized), self.currency)

    def __rmul__(self, scalar: Decimal | int | str) -> Money:
        return self * scalar

    def __truediv__(self, scalar: Decimal | int | str) -> Money:
        normalized = parse_decimal(scalar, label="scalar")
        if normalized.is_zero():
            raise ZeroDivisionError("money division by zero")
        return Money(calculate(lambda: self.amount / normalized), self.currency)

    def __lt__(self, other: Money) -> bool:
        return self.amount < self._same_currency(other).amount

    def __le__(self, other: Money) -> bool:
        return self.amount <= self._same_currency(other).amount

    def __gt__(self, other: Money) -> bool:
        return self.amount > self._same_currency(other).amount

    def __ge__(self, other: Money) -> bool:
        return self.amount >= self._same_currency(other).amount

    def _quantum(self) -> Decimal:
        minor_unit = self.currency.minor_unit
        if minor_unit is None:
            raise InvalidCurrencyError("currency does not define a minor unit")
        return Decimal(1).scaleb(-minor_unit)

    def quantize(self, *, rounding: str = ROUND_HALF_EVEN) -> Money:
        normalized_rounding = require_rounding(rounding)
        quantum = self._quantum()
        amount = calculate(lambda: self.amount.quantize(quantum, rounding=normalized_rounding))
        return Money(amount, self.currency)

    def minor_units(self, *, rounding: str | None = None) -> int:
        quantum = self._quantum()
        value = self
        if rounding is not None:
            value = self.quantize(rounding=require_rounding(rounding))
        scaled = calculate(lambda: value.amount / quantum)
        if scaled != scaled.to_integral_value():
            raise InvalidAmountError("amount has fractional minor units")
        return int(scaled)

    def format(
        self,
        *,
        quantize: bool = False,
        rounding: str = ROUND_HALF_EVEN,
    ) -> str:
        if not isinstance(quantize, bool):
            raise TypeError("quantize must be a boolean")
        value = self.quantize(rounding=rounding) if quantize else self
        return f"{value.currency.code} {value.amount:f}"

    def to_dict(self) -> dict[str, str]:
        return {"amount": str(self.amount), "currency": self.currency.code}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Money:
        if not isinstance(value, Mapping):
            raise TypeError("value must be a mapping")
        if set(value) != {"amount", "currency"}:
            raise InvalidAmountError("value must contain exactly amount and currency")
        amount = value["amount"]
        currency = value["currency"]
        if not isinstance(amount, str):
            raise TypeError("amount must be a string")
        if not isinstance(currency, str):
            raise TypeError("currency must be a string")
        return cls.of(amount, get_currency(currency))


def sum_money(currency: Currency, values: Iterable[Money]) -> Money:
    normalized_currency = _require_currency(currency)
    try:
        iterator = iter(values)
    except TypeError as error:
        raise TypeError("values must be an iterable of Money") from error
    total = Money.of(0, normalized_currency)
    for value in iterator:
        if not isinstance(value, Money):
            raise TypeError("values must contain only Money values")
        total += value
    return total
