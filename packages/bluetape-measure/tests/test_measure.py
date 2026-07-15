import pytest
from bluetape.measure import (
    HOUR,
    KILOGRAM,
    KILOMETER,
    METER,
    SECOND,
    IncompatibleUnitError,
    InvalidMeasureError,
    Measure,
)


def test_conversion_and_arithmetic_reject_dimensions() -> None:
    distance = Measure(1, KILOMETER)
    meters = distance.to(METER)
    assert meters == Measure(1000, METER)
    assert meters.to(KILOMETER) == distance
    assert Measure(750, METER) + Measure(0.25, KILOMETER) == Measure(1000, METER)
    assert Measure(1, KILOMETER) - Measure(250, METER) == Measure(0.75, KILOMETER)
    assert distance * 2 == Measure(2, KILOMETER)
    assert 2 * distance == Measure(2, KILOMETER)
    assert distance / 4 == Measure(0.25, KILOMETER)
    assert distance == Measure(1, KILOMETER)

    for operation in (
        lambda: distance.to(SECOND),
        lambda: distance + Measure(1, SECOND),
        lambda: distance - Measure(1, SECOND),
    ):
        with pytest.raises(IncompatibleUnitError):
            operation()

    assert Measure(2, HOUR).to(SECOND) == Measure(7200, SECOND)
    assert Measure(2, KILOGRAM).amount == 2.0


def test_equivalent_to_contract() -> None:
    assert Measure(1, KILOMETER).equivalent_to(Measure(1000, METER)) is True
    assert Measure(1, KILOMETER).equivalent_to(Measure(1, SECOND)) is False
    assert Measure(1, METER).equivalent_to(Measure(1.0001, METER), rel_tol=0.0, abs_tol=0.001)
    for tolerance in (True, -1.0, float("nan"), float("inf")):
        with pytest.raises((TypeError, InvalidMeasureError)):
            Measure(1, METER).equivalent_to(Measure(1, METER), rel_tol=tolerance)


def test_measure_rejects_invalid_amounts_and_scalars() -> None:
    for value in (True, float("nan"), float("inf")):
        with pytest.raises((TypeError, InvalidMeasureError)):
            Measure(value, METER)
    with pytest.raises(TypeError):
        Measure(1, "m")  # type: ignore[arg-type]
    for scalar in (True, float("nan"), float("inf")):
        with pytest.raises((TypeError, InvalidMeasureError)):
            Measure(1, METER) * scalar
    with pytest.raises(ZeroDivisionError):
        Measure(1, METER) / 0
