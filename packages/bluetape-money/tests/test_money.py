from dataclasses import FrozenInstanceError
from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    Decimal,
    InvalidOperation,
    getcontext,
    localcontext,
)

import pytest
from bluetape.money import (
    EUR,
    USD,
    CurrencyMismatchError,
    InvalidAmountError,
    InvalidCurrencyError,
    Money,
    get_currency,
    sum_money,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("12.30"), Decimal("12.30")),
        (12, Decimal("12")),
        ("12.30", Decimal("12.30")),
        (".5e+2", Decimal("5E+1")),
        ("1" * 256, Decimal("1" * 256)),
        ("1e256", Decimal("1e256")),
        ("1e-256", Decimal("1e-256")),
        ("1e+" + "0" * 508 + "1", Decimal("1e1")),
    ],
)
def test_money_of_accepts_exact_decimal_inputs(
    value: Decimal | int | str, expected: Decimal
) -> None:
    money = Money.of(value, USD)
    assert money == Money(expected, USD)


@pytest.mark.parametrize("value", [True, False, 1.0, float("nan"), object()])
def test_money_rejects_float_and_wrong_types(value: object) -> None:
    with pytest.raises(TypeError):
        Money.of(value, USD)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        "",
        " 1",
        "1 ",
        "1_000",
        "\uff11",
        "NaN",
        "Infinity",
        "1e257",
        "1e-257",
        "1" * 257,
        "1" * 513,
    ],
)
def test_money_rejects_float_and_unbounded_decimal(value: str) -> None:
    with pytest.raises(InvalidAmountError, match="amount"):
        Money.of(value, USD)


def test_amount_errors_do_not_echo_caller_payload() -> None:
    payload = "123_private_payload"
    with pytest.raises(InvalidAmountError) as captured:
        Money.of(payload, USD)
    assert payload not in str(captured.value)


def test_direct_construction_requires_valid_decimal_and_currency() -> None:
    assert Money(Decimal("1.25"), USD) == Money.of("1.25", USD)
    with pytest.raises(TypeError):
        Money("1.25", USD)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Money(Decimal("1.25"), "USD")  # type: ignore[arg-type]
    with pytest.raises(InvalidAmountError):
        Money(Decimal("NaN"), USD)
    with pytest.raises(FrozenInstanceError):
        Money.of(1, USD).amount = Decimal(2)  # type: ignore[misc]


def test_money_arithmetic_and_context_contract() -> None:
    first = Money.of("1.005", USD)
    second = Money.of("2.115", USD)
    assert first + second == Money.of("3.120", USD)
    assert second - first == Money.of("1.110", USD)
    assert -first == Money.of("-1.005", USD)
    assert abs(-first) == first
    assert first * "2.5" == Money.of("2.5125", USD)
    assert 2 * first == Money.of("2.010", USD)
    assert second / 3 == Money.of("0.705", USD)
    assert first < second
    assert first <= second
    assert second > first
    assert second >= first
    with pytest.raises(CurrencyMismatchError):
        _ = first + Money.of(1, EUR)
    with pytest.raises(CurrencyMismatchError):
        _ = first < Money.of(1, EUR)
    with pytest.raises(TypeError):
        _ = first + 1  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = first * 1.5  # type: ignore[operator]
    with pytest.raises(ZeroDivisionError):
        _ = first / 0
    with pytest.raises(InvalidAmountError):
        _ = Money.of("9e256", USD) * 10


def test_arithmetic_uses_package_context_without_mutating_ambient_context() -> None:
    original_precision = getcontext().prec
    with localcontext() as caller_context:
        caller_context.prec = 2
        caller_context.traps[InvalidOperation] = False
        result = Money.of("1.23456789", USD) * "9.87654321"
        assert result.amount == Decimal("12.1932631112635269")
        assert caller_context.prec == 2
        assert caller_context.traps[InvalidOperation] is False
    assert getcontext().prec == original_precision


def test_minor_unit_and_rounding_contract() -> None:
    value = Money.of("12.345", USD)
    assert value.quantize() == Money.of("12.34", USD)
    assert value.quantize(rounding=ROUND_DOWN) == Money.of("12.34", USD)
    assert Money.of("12.355", USD).quantize(rounding=ROUND_HALF_EVEN) == Money.of("12.36", USD)
    assert Money.from_minor(1234, USD) == Money.of("12.34", USD)
    assert Money.of("12.34", USD).minor_units() == 1234
    assert value.minor_units(rounding=ROUND_DOWN) == 1234
    with pytest.raises(InvalidAmountError):
        value.minor_units()
    with pytest.raises(InvalidAmountError):
        value.quantize(rounding="nearest")
    with pytest.raises(TypeError):
        Money.from_minor(True, USD)
    assert Money.from_minor(-1234, USD).minor_units() == -1234
    assert Money.from_minor(12, get_currency("JPY")) == Money.of(12, get_currency("JPY"))
    assert Money.from_minor(1234, get_currency("KWD")) == Money.of("1.234", get_currency("KWD"))
    large_units = 10**255
    assert Money.from_minor(large_units, USD).minor_units() == large_units


def test_missing_minor_unit_fails_for_minor_unit_operations() -> None:
    currency = get_currency("XAU")
    money = Money.of("1.25", currency)
    with pytest.raises(InvalidCurrencyError):
        Money.from_minor(1, currency)
    with pytest.raises(InvalidCurrencyError):
        money.quantize()
    with pytest.raises(InvalidCurrencyError):
        money.minor_units(rounding=ROUND_DOWN)


def test_sum_money_empty_and_mixed_contract() -> None:
    assert sum_money(USD, []) == Money.of(0, USD)
    assert sum_money(USD, [Money.of("1.1", USD), Money.of("2.2", USD)]) == Money.of("3.3", USD)
    with pytest.raises(CurrencyMismatchError):
        sum_money(USD, [Money.of(1, EUR)])
    with pytest.raises(TypeError):
        sum_money(USD, [Money.of(1, USD), object()])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        sum_money(USD, 1)  # type: ignore[arg-type]


def test_repeated_arithmetic_and_parse_stability_matrix() -> None:
    expected = Money.of("12.1932631112635269", USD)
    for _ in range(10_000):
        value = Money.of("1.23456789", USD) * "9.87654321"
        assert value == expected
        assert Money.from_dict(value.to_dict()) == expected
