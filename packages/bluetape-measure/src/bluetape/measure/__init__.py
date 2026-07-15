"""Immutable runtime dimension-checked linear measurements."""

from ._errors import IncompatibleUnitError, InvalidMeasureError, InvalidUnitError, MeasureError
from ._measure import Measure
from ._parse import parse_measure
from ._units import (
    BUILTIN_UNITS,
    CENTIMETER,
    GRAM,
    HOUR,
    KILOGRAM,
    KILOMETER,
    METER,
    MILLIMETER,
    MILLISECOND,
    MINUTE,
    SECOND,
    Dimension,
    Unit,
)

__all__ = [  # noqa: RUF022 - public order is part of the package contract
    "MeasureError",
    "InvalidUnitError",
    "InvalidMeasureError",
    "IncompatibleUnitError",
    "Dimension",
    "Unit",
    "Measure",
    "parse_measure",
    "BUILTIN_UNITS",
    "METER",
    "KILOMETER",
    "CENTIMETER",
    "MILLIMETER",
    "SECOND",
    "MILLISECOND",
    "MINUTE",
    "HOUR",
    "GRAM",
    "KILOGRAM",
]
