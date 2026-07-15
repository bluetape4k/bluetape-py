import inspect

import pytest
from bluetape.measure import (
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
    InvalidUnitError,
    Measure,
    Unit,
    parse_measure,
)


def test_measure_public_signatures_are_exact() -> None:
    assert tuple(inspect.signature(Unit).parameters) == ("name", "symbol", "dimension", "ratio")
    assert tuple(inspect.signature(Measure).parameters) == ("amount", "unit")
    assert tuple(inspect.signature(Measure.to).parameters) == ("self", "unit")
    assert tuple(inspect.signature(Measure.equivalent_to).parameters) == (
        "self",
        "other",
        "rel_tol",
        "abs_tol",
    )
    assert tuple(inspect.signature(Measure.from_dict).parameters) == ("value", "units")
    assert inspect.signature(Measure.from_dict).parameters["units"].default is BUILTIN_UNITS
    assert inspect.signature(parse_measure).parameters["units"].default is BUILTIN_UNITS


def test_builtin_units_are_immutable_and_ordered() -> None:
    assert [(dimension.name, dimension.value) for dimension in Dimension] == [
        ("LENGTH", "length"),
        ("TIME", "time"),
        ("MASS", "mass"),
    ]
    assert BUILTIN_UNITS == (
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
    assert [(unit.name, unit.symbol, unit.dimension, unit.ratio) for unit in BUILTIN_UNITS] == [
        ("meter", "m", Dimension.LENGTH, 1.0),
        ("kilometer", "km", Dimension.LENGTH, 1000.0),
        ("centimeter", "cm", Dimension.LENGTH, 0.01),
        ("millimeter", "mm", Dimension.LENGTH, 0.001),
        ("second", "s", Dimension.TIME, 1.0),
        ("millisecond", "ms", Dimension.TIME, 0.001),
        ("minute", "min", Dimension.TIME, 60.0),
        ("hour", "h", Dimension.TIME, 3600.0),
        ("gram", "g", Dimension.MASS, 1.0),
        ("kilogram", "kg", Dimension.MASS, 1000.0),
    ]
    with pytest.raises((AttributeError, TypeError)):
        METER.ratio = 2.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (("", "x", Dimension.LENGTH, 1), InvalidUnitError),
        ((" meter", "x", Dimension.LENGTH, 1), InvalidUnitError),
        (("meter", "", Dimension.LENGTH, 1), InvalidUnitError),
        (("meter", "x ", Dimension.LENGTH, 1), InvalidUnitError),
        (("meter", "x", "length", 1), TypeError),
        (("meter", "x", Dimension.LENGTH, True), TypeError),
        (("meter", "x", Dimension.LENGTH, 0), InvalidUnitError),
        (("meter", "x", Dimension.LENGTH, float("inf")), InvalidUnitError),
    ],
)
def test_unit_validation(args, error) -> None:
    with pytest.raises(error):
        Unit(*args)
