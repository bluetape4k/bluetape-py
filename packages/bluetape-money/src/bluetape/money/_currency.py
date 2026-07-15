from __future__ import annotations

from dataclasses import dataclass

from ._errors import InvalidCurrencyError
from ._iso4217 import CURRENCY_ROWS

_ROWS_BY_CODE = {row[0]: row for row in CURRENCY_ROWS}
_ROWS_BY_NUMERIC = {row[1]: row for row in CURRENCY_ROWS}


@dataclass(frozen=True, slots=True, init=False)
class Currency:
    code: str
    numeric_code: str
    name: str
    minor_unit: int | None

    def __init__(
        self,
        code: str,
        numeric_code: str,
        name: str,
        minor_unit: int | None,
    ) -> None:
        if not isinstance(code, str):
            raise TypeError("code must be a string")
        if not isinstance(numeric_code, str):
            raise TypeError("numeric_code must be a string")
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if minor_unit is not None and (
            isinstance(minor_unit, bool) or not isinstance(minor_unit, int)
        ):
            raise TypeError("minor_unit must be an integer or None")
        row = (code, numeric_code, name, minor_unit)
        if _ROWS_BY_CODE.get(code) != row:
            raise InvalidCurrencyError("currency must match a current ISO 4217 row")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "numeric_code", numeric_code)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "minor_unit", minor_unit)


_CURRENCIES_BY_CODE = {row[0]: Currency(*row) for row in CURRENCY_ROWS}
_CURRENCIES_BY_NUMERIC = {
    currency.numeric_code: currency for currency in _CURRENCIES_BY_CODE.values()
}


def get_currency(code_or_numeric: str | int) -> Currency:
    if isinstance(code_or_numeric, bool) or not isinstance(code_or_numeric, (str, int)):
        raise TypeError("code_or_numeric must be a string or integer")
    if isinstance(code_or_numeric, int):
        if not 0 <= code_or_numeric <= 999:
            raise InvalidCurrencyError("numeric currency code is invalid")
        currency = _CURRENCIES_BY_NUMERIC.get(f"{code_or_numeric:03d}")
    else:
        if not code_or_numeric or code_or_numeric != code_or_numeric.strip():
            raise InvalidCurrencyError("currency code must be non-blank and trimmed")
        if len(code_or_numeric) == 3 and code_or_numeric.isascii():
            currency = (
                _CURRENCIES_BY_NUMERIC.get(code_or_numeric)
                if code_or_numeric.isdigit()
                else _CURRENCIES_BY_CODE.get(code_or_numeric.upper())
            )
        else:
            currency = None
    if currency is None:
        raise InvalidCurrencyError("currency code is unknown")
    return currency


USD = get_currency("USD")
EUR = get_currency("EUR")
KRW = get_currency("KRW")
JPY = get_currency("JPY")
CNY = get_currency("CNY")
