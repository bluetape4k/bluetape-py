from __future__ import annotations

import re
from collections.abc import Callable
from decimal import (
    ROUND_05UP,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)

from ._errors import InvalidAmountError, MoneyError

MAX_TEXT_LENGTH = 512
MAX_COEFFICIENT_DIGITS = 256
MAX_ABS_EXPONENT = 256

_DECIMAL_PATTERN = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?",
    re.ASCII,
)
_ROUNDING_MODES = frozenset(
    {
        ROUND_05UP,
        ROUND_CEILING,
        ROUND_DOWN,
        ROUND_FLOOR,
        ROUND_HALF_DOWN,
        ROUND_HALF_EVEN,
        ROUND_HALF_UP,
        ROUND_UP,
    }
)

MONEY_CONTEXT = Context(
    prec=256,
    rounding=ROUND_HALF_EVEN,
    Emin=-256,
    Emax=256,
)
for _signal in (InvalidOperation, DivisionByZero, Overflow):
    MONEY_CONTEXT.traps[_signal] = True


def _raise_invalid(error_type: type[MoneyError], label: str, cause: Exception | None = None):
    error = error_type(f"{label} must be a finite bounded decimal")
    if cause is None:
        raise error
    raise error from cause


def validate_decimal(
    value: Decimal,
    *,
    error_type: type[MoneyError] = InvalidAmountError,
    label: str = "amount",
) -> Decimal:
    if not value.is_finite():
        _raise_invalid(error_type, label)
    parts = value.as_tuple()
    if len(parts.digits) > MAX_COEFFICIENT_DIGITS or abs(parts.exponent) > MAX_ABS_EXPONENT:
        _raise_invalid(error_type, label)
    return value


def parse_decimal(
    value: Decimal | int | str,
    *,
    error_type: type[MoneyError] = InvalidAmountError,
    label: str = "amount",
) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{label} must be a Decimal, integer, or string")
    if isinstance(value, Decimal):
        return validate_decimal(value, error_type=error_type, label=label)
    if isinstance(value, int):
        return validate_decimal(Decimal(value), error_type=error_type, label=label)
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a Decimal, integer, or string")
    if (
        not value
        or len(value) > MAX_TEXT_LENGTH
        or value != value.strip()
        or _DECIMAL_PATTERN.fullmatch(value) is None
    ):
        _raise_invalid(error_type, label)
    try:
        parsed = Decimal(value)
    except DecimalException as error:
        _raise_invalid(error_type, label, error)
    return validate_decimal(parsed, error_type=error_type, label=label)


def calculate(
    operation: Callable[[], Decimal],
    *,
    error_type: type[MoneyError] = InvalidAmountError,
    label: str = "amount",
) -> Decimal:
    try:
        with localcontext(MONEY_CONTEXT):
            result = operation()
    except (DecimalException, ValueError) as error:
        _raise_invalid(error_type, label, error)
    return validate_decimal(result, error_type=error_type, label=label)


def require_rounding(rounding: str) -> str:
    if not isinstance(rounding, str):
        raise TypeError("rounding must be a string")
    if rounding not in _ROUNDING_MODES:
        raise InvalidAmountError("rounding must be a Decimal rounding constant")
    return rounding
