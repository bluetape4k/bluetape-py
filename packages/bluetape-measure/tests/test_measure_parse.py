"""Parsing contract tests for bluetape-measure."""

import pytest
from bluetape.measure import METER, Dimension, InvalidMeasureError, Measure, Unit, parse_measure


def test_parse_measure_ascii_grammar() -> None:
    assert parse_measure("1 m") == Measure(1, METER)
    assert parse_measure("+1. m") == Measure(1, METER)
    assert parse_measure("-.5 m") == Measure(-0.5, METER)
    assert parse_measure("1.5e2\tm") == Measure(150, METER)

    for text in (
        " 1 m",
        "1 m ",
        "1\nm",
        "1_m m",
        "\uff11 m",
        "nan m",
        "inf m",
        "1m",
        "1  M",
        "",
    ):
        with pytest.raises(InvalidMeasureError):
            parse_measure(text)
    with pytest.raises(InvalidMeasureError):
        parse_measure("1" * 255 + " m")
    with pytest.raises(TypeError):
        parse_measure(1)  # type: ignore[arg-type]


def test_custom_units_are_caller_owned_and_bounded() -> None:
    furlong = Unit("furlong", "fur", Dimension.LENGTH, 201.168)
    assert parse_measure("2 fur", units=(furlong,)) == Measure(2, furlong)
    with pytest.raises(InvalidMeasureError):
        parse_measure("2 fur")
    with pytest.raises(InvalidMeasureError):
        parse_measure("1 m", units=(METER, METER))
    with pytest.raises(InvalidMeasureError):
        parse_measure(
            "1 x",
            units=(Unit(str(index), f"u{index}", Dimension.LENGTH, 1) for index in range(257)),
        )
