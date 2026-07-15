"""Serialization contract tests for bluetape-money."""

import pytest
from bluetape.money import USD, InvalidAmountError, Money


def test_money_primitive_schema_is_exact() -> None:
    value = Money.of("1234.500", USD)
    assert value.to_dict() == {"amount": "1234.500", "currency": "USD"}
    assert Money.from_dict(value.to_dict()) == value
    assert Money.from_dict({"amount": "1.25", "currency": "840"}) == Money.of("1.25", USD)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"amount": "1"},
        {"currency": "USD"},
        {"amount": "1", "currency": "USD", "extra": "x"},
    ],
)
def test_from_dict_rejects_missing_or_extra_keys(value: dict[str, object]) -> None:
    with pytest.raises(InvalidAmountError):
        Money.from_dict(value)


@pytest.mark.parametrize(
    "value",
    [
        {"amount": 1, "currency": "USD"},
        {"amount": 1.0, "currency": "USD"},
        {"amount": "1", "currency": 840},
    ],
)
def test_from_dict_rejects_wrong_value_types(value: dict[str, object]) -> None:
    with pytest.raises(TypeError):
        Money.from_dict(value)


def test_from_dict_rejects_wrong_container_type() -> None:
    with pytest.raises(TypeError):
        Money.from_dict("USD 1")  # type: ignore[arg-type]
