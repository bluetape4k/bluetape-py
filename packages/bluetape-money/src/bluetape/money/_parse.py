from __future__ import annotations

import re

from ._currency import get_currency
from ._decimal import MAX_TEXT_LENGTH
from ._errors import InvalidAmountError
from ._money import Money

_MONEY_PATTERN = re.compile(
    r"(?P<currency>[A-Za-z]{3}) "
    r"(?P<amount>[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)",
    re.ASCII,
)


def parse_money(text: str) -> Money:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text) > MAX_TEXT_LENGTH + 4:
        raise InvalidAmountError("text must contain at most 516 characters")
    matched = _MONEY_PATTERN.fullmatch(text)
    if matched is None:
        raise InvalidAmountError("text must use the strict money grammar")
    return Money.of(matched.group("amount"), get_currency(matched.group("currency")))
