import pytest
from bluetape.measure import METER, Dimension, InvalidMeasureError, Measure, Unit


def test_custom_unit_serialization_requires_registry() -> None:
    furlong = Unit("furlong", "fur", Dimension.LENGTH, 201.168)
    value = Measure(1.25, furlong)
    assert value.to_dict() == {"amount": "1.25", "unit": "fur"}

    iterations = 0

    def units():
        nonlocal iterations
        iterations += 1
        yield furlong

    assert Measure.from_dict(value.to_dict(), units=units()) == value
    assert iterations == 1
    with pytest.raises(InvalidMeasureError):
        Measure.from_dict(value.to_dict())

    for payload in (
        {},
        {"amount": "1.0"},
        {"unit": "m"},
        {"amount": "1.0", "unit": "m", "extra": "x"},
        {"amount": 1.0, "unit": "m"},
        {"amount": "1.0", "unit": 1},
    ):
        with pytest.raises((TypeError, InvalidMeasureError)):
            Measure.from_dict(payload)


def test_format_is_exact_and_locale_independent() -> None:
    value = Measure(1500, METER)
    assert value.format() == "1500 m"
    assert value.format(spec=".2f") == "1500.00 m"
    assert value.format(Unit("kilometer", "km", Dimension.LENGTH, 1000), spec="g") == "1.5 km"
