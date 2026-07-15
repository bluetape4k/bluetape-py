import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ._errors import InvalidMeasureError, InvalidUnitError

MAX_UNITS = 256


class Dimension(StrEnum):
    LENGTH = "length"
    TIME = "time"
    MASS = "mass"


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value != value.strip():
        raise InvalidUnitError(f"{name} must be a non-blank trimmed string")
    return value


def _require_positive_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be an integer or float")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise InvalidUnitError(f"{name} must be finite and positive") from error
    if not math.isfinite(normalized) or normalized <= 0:
        raise InvalidUnitError(f"{name} must be finite and positive")
    return normalized


@dataclass(frozen=True, slots=True, init=False)
class Unit:
    name: str
    symbol: str
    dimension: Dimension
    ratio: float

    def __init__(
        self,
        name: str,
        symbol: str,
        dimension: Dimension,
        ratio: int | float,
    ) -> None:
        normalized_name = _require_text(name, "name")
        normalized_symbol = _require_text(symbol, "symbol")
        if not isinstance(dimension, Dimension):
            raise TypeError("dimension must be a Dimension")
        normalized_ratio = _require_positive_number(ratio, "ratio")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "ratio", normalized_ratio)


METER = Unit("meter", "m", Dimension.LENGTH, 1.0)
KILOMETER = Unit("kilometer", "km", Dimension.LENGTH, 1000.0)
CENTIMETER = Unit("centimeter", "cm", Dimension.LENGTH, 0.01)
MILLIMETER = Unit("millimeter", "mm", Dimension.LENGTH, 0.001)
SECOND = Unit("second", "s", Dimension.TIME, 1.0)
MILLISECOND = Unit("millisecond", "ms", Dimension.TIME, 0.001)
MINUTE = Unit("minute", "min", Dimension.TIME, 60.0)
HOUR = Unit("hour", "h", Dimension.TIME, 3600.0)
GRAM = Unit("gram", "g", Dimension.MASS, 1.0)
KILOGRAM = Unit("kilogram", "kg", Dimension.MASS, 1000.0)

BUILTIN_UNITS: tuple[Unit, ...] = (
    METER,
    KILOMETER,
    CENTIMETER,
    MILLIMETER,
    SECOND,
    MILLISECOND,
    MINUTE,
    HOUR,
    GRAM,
    KILOGRAM,
)


def index_units(units: Iterable[Unit]) -> dict[str, Unit]:
    try:
        iterator = iter(units)
    except TypeError as error:
        raise TypeError("units must be an iterable of Unit values") from error

    indexed: dict[str, Unit] = {}
    for position, unit in enumerate(iterator):
        if position >= MAX_UNITS:
            raise InvalidMeasureError("units must contain at most 256 entries")
        if not isinstance(unit, Unit):
            raise TypeError("units must contain only Unit values")
        if unit.symbol in indexed:
            raise InvalidMeasureError("unit symbols must be unique")
        indexed[unit.symbol] = unit
    return indexed
