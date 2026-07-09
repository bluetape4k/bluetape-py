import pytest
from bluetape.core import require_instance, require_not_blank, require_not_empty, require_not_none


def test_require_not_blank_returns_original_value() -> None:
    assert require_not_blank("  bluetape  ", "name") == "  bluetape  "


def test_require_not_blank_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="name must not be blank"):
        require_not_blank(" \t\n", "name")


def test_require_not_none_returns_original_value() -> None:
    marker = object()

    assert require_not_none(marker, "marker") is marker


def test_require_not_none_rejects_none() -> None:
    with pytest.raises(ValueError, match="marker must not be None"):
        require_not_none(None, "marker")


def test_require_not_empty_returns_original_sized_value() -> None:
    values = ["blue"]

    assert require_not_empty(values, "values") is values


def test_require_not_empty_rejects_empty_sized_value() -> None:
    with pytest.raises(ValueError, match="values must not be empty"):
        require_not_empty([], "values")


def test_require_instance_returns_typed_value() -> None:
    value = require_instance("blue", str, "name")

    assert value.upper() == "BLUE"


def test_require_instance_rejects_wrong_type() -> None:
    with pytest.raises(TypeError, match="name must be str"):
        require_instance(42, str, "name")
