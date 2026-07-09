import pytest
from bluetape.core import require_not_blank, require_not_none


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
