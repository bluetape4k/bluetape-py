import re
from collections.abc import Iterable

from ._errors import InvalidMeasureError
from ._measure import Measure, parse_number
from ._units import BUILTIN_UNITS, Unit, index_units

_MEASURE_PATTERN = re.compile(
    r"(?P<amount>[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)[ \t]+(?P<symbol>.+)",
    re.ASCII,
)


def parse_measure(
    text: str,
    *,
    units: Iterable[Unit] = BUILTIN_UNITS,
) -> Measure:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text) > 256:
        raise InvalidMeasureError("text must contain at most 256 characters")
    matched = _MEASURE_PATTERN.fullmatch(text)
    if matched is None:
        raise InvalidMeasureError("text must use the strict measure grammar")
    indexed = index_units(units)
    symbol = matched.group("symbol")
    try:
        unit = indexed[symbol]
    except KeyError as error:
        raise InvalidMeasureError("unit symbol is unknown") from error
    return Measure(parse_number(matched.group("amount")), unit)
