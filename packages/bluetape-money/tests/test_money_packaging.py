import importlib
import inspect
import tomllib
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[3]
PACKAGE = ROOT / "packages/bluetape-money"


def test_distribution_metadata_is_stdlib_only() -> None:
    with (PACKAGE / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)

    assert metadata["project"] == {
        "name": "bluetape-money",
        "version": "0.1.0",
        "description": "Python-native exact-decimal money values for bluetape.",
        "readme": "README.md",
        "requires-python": ">=3.13",
        "dependencies": [],
    }
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.money"
    assert not (PACKAGE / "src/bluetape/__init__.py").exists()
    module = importlib.import_module("bluetape.money")
    assert module.__all__ == [
        "MoneyError",
        "InvalidCurrencyError",
        "InvalidAmountError",
        "CurrencyMismatchError",
        "InvalidExchangeRateError",
        "Currency",
        "Money",
        "ExchangeRate",
        "get_currency",
        "parse_money",
        "sum_money",
        "convert",
        "USD",
        "EUR",
        "KRW",
        "JPY",
        "CNY",
    ]
    assert inspect.signature(module.get_currency) == inspect.Signature(
        [
            inspect.Parameter(
                "code_or_numeric",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation="str | int",
            )
        ],
        return_annotation="Currency",
    )
    assert inspect.signature(module.Money.of).return_annotation == "Money"
    assert module.Money(Decimal("1"), module.USD).amount == Decimal("1")
