import importlib.util
import math
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyLimits,
    ForyRegistration,
)


class ConformanceRecord:
    pass


def registration(**overrides: Any) -> ForyRegistration[ConformanceRecord]:
    values: dict[str, Any] = {
        "python_type": ConformanceRecord,
        "schema_id": 0x42544659,
        "schema_version": 1,
        "type_id": 1001,
        "logical_name": "io.bluetape.serde.ConformanceRecord",
    }
    values.update(overrides)
    return ForyRegistration(**values)


def test_fory_public_constants_and_values_are_exact_and_immutable() -> None:
    assert (FORY_FORMAT, FORY_VERSION, FORY_CONTENT_TYPE) == (
        "apache-fory-xlang",
        1,
        "application/x-apache-fory",
    )

    value = registration()
    assert value.python_type is ConformanceRecord
    assert value.schema_id == 0x42544659
    assert value.schema_version == 1
    assert value.type_id == 1001
    assert value.logical_name == "io.bluetape.serde.ConformanceRecord"
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.schema_id = 1  # type: ignore[misc]

    limits = ForyLimits()
    assert limits == ForyLimits(
        max_input_size=16 * 1024 * 1024,
        max_output_size=16 * 1024 * 1024,
        max_depth=64,
        max_type_fields=256,
        max_type_meta_bytes=4096,
        max_schema_versions_per_type=8,
        max_average_schema_versions_per_type=2,
        max_concurrency=4,
        acquire_timeout_seconds=5.0,
        reference_tracking=False,
    )
    assert not hasattr(limits, "__dict__")
    with pytest.raises(FrozenInstanceError):
        limits.max_depth = 1  # type: ignore[misc]


def test_fory_values_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        ForyRegistration(ConformanceRecord, 1, 1, 1, "Record")  # type: ignore[misc]
    with pytest.raises(TypeError):
        ForyLimits(20)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("python_type", object()),
        ("schema_id", True),
        ("schema_id", 1.0),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("type_id", True),
        ("type_id", 1.0),
        ("logical_name", b"Record"),
    ],
)
def test_fory_registration_rejects_wrong_exact_types(field: str, invalid: object) -> None:
    with pytest.raises(TypeError):
        registration(**{field: invalid})


@pytest.mark.parametrize(
    ("field", "valid"),
    [
        ("schema_id", 1),
        ("schema_id", 0xFFFFFFFF),
        ("schema_version", 1),
        ("schema_version", 0xFFFF),
        ("type_id", 1),
        ("type_id", 0xFFFFFFFE),
    ],
)
def test_fory_registration_accepts_numeric_boundaries(field: str, valid: int) -> None:
    assert getattr(registration(**{field: valid}), field) == valid


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("schema_id", 0),
        ("schema_id", 0x100000000),
        ("schema_version", 0),
        ("schema_version", 0x10000),
        ("type_id", 0),
        ("type_id", 0xFFFFFFFF),
    ],
)
def test_fory_registration_rejects_numeric_out_of_range(field: str, invalid: int) -> None:
    with pytest.raises(ValueError):
        registration(**{field: invalid})


@pytest.mark.parametrize(
    "logical_name",
    [
        "",
        ".Record",
        "Record.",
        "io..Record",
        "contains space",
        "contains/slash",
        "한글",
        "a" * 129,
    ],
)
def test_fory_registration_rejects_invalid_logical_names(logical_name: str) -> None:
    with pytest.raises(ValueError):
        registration(logical_name=logical_name)


@pytest.mark.parametrize(
    "logical_name",
    ["R", "a" * 128, "io.bluetape_serde-1.Record"],
)
def test_fory_registration_accepts_valid_logical_names(logical_name: str) -> None:
    assert registration(logical_name=logical_name).logical_name == logical_name


_INTEGER_LIMIT_FIELDS = {
    "max_input_size": (20, 1024 * 1024 * 1024),
    "max_output_size": (20, 1024 * 1024 * 1024),
    "max_depth": (1, 256),
    "max_type_fields": (1, 65_535),
    "max_type_meta_bytes": (1, 16 * 1024 * 1024),
    "max_schema_versions_per_type": (1, 65_535),
    "max_average_schema_versions_per_type": (1, 65_535),
    "max_concurrency": (1, 64),
}


@pytest.mark.parametrize("field", _INTEGER_LIMIT_FIELDS)
@pytest.mark.parametrize("invalid", [True, 1.0])
def test_fory_limits_reject_wrong_integer_types(field: str, invalid: object) -> None:
    with pytest.raises(TypeError):
        replace(ForyLimits(), **{field: invalid})


@pytest.mark.parametrize(
    ("field", "valid"),
    [
        (field, boundary)
        for field, boundaries in _INTEGER_LIMIT_FIELDS.items()
        for boundary in boundaries
    ],
)
def test_fory_limits_accept_integer_boundaries(field: str, valid: int) -> None:
    overrides = {field: valid}
    if field == "max_schema_versions_per_type" and valid < 2:
        overrides["max_average_schema_versions_per_type"] = valid
    if field == "max_average_schema_versions_per_type" and valid > 8:
        overrides["max_schema_versions_per_type"] = valid
    limits = replace(ForyLimits(), **overrides)
    assert getattr(limits, field) == valid


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        (field, invalid)
        for field, (minimum, maximum) in _INTEGER_LIMIT_FIELDS.items()
        for invalid in (minimum - 1, maximum + 1)
    ],
)
def test_fory_limits_reject_integer_values_out_of_range(field: str, invalid: int) -> None:
    with pytest.raises(ValueError):
        replace(ForyLimits(), **{field: invalid})


def test_fory_limits_reject_average_schema_count_above_per_type_count() -> None:
    with pytest.raises(ValueError):
        ForyLimits(
            max_schema_versions_per_type=2,
            max_average_schema_versions_per_type=3,
        )


@pytest.mark.parametrize("invalid", [True, 5, "5.0"])
def test_fory_limits_reject_wrong_timeout_type(invalid: object) -> None:
    with pytest.raises(TypeError):
        ForyLimits(acquire_timeout_seconds=invalid)  # type: ignore[arg-type]


@pytest.mark.parametrize("valid", [0.001, 60.0])
def test_fory_limits_accept_timeout_boundaries(valid: float) -> None:
    assert ForyLimits(acquire_timeout_seconds=valid).acquire_timeout_seconds == valid


@pytest.mark.parametrize("invalid", [0.0009, 60.0001, math.inf, -math.inf, math.nan])
def test_fory_limits_reject_invalid_timeout(invalid: float) -> None:
    with pytest.raises(ValueError):
        ForyLimits(acquire_timeout_seconds=invalid)


@pytest.mark.parametrize("invalid", [True, 0, None])
def test_fory_limits_require_reference_tracking_to_be_exact_false(invalid: object) -> None:
    expected_error = ValueError if invalid is True else TypeError
    with pytest.raises(expected_error):
        ForyLimits(reference_tracking=invalid)  # type: ignore[arg-type]


def _load_fory_with_provider_import(
    monkeypatch: pytest.MonkeyPatch,
    provider_error: BaseException,
) -> ModuleType:
    import builtins

    module_path = Path(__file__).parents[1] / "src/bluetape/serde/fory.py"
    module_name = "bluetape.serde._fory_import_contract_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    original_import = builtins.__import__

    def controlled_import(name: str, *args: object, **kwargs: object) -> Any:
        if name == "pyfory":
            raise provider_error
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", controlled_import)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_direct_missing_provider_has_fixed_installation_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ModuleNotFoundError) as caught:
        _load_fory_with_provider_import(
            monkeypatch,
            ModuleNotFoundError("No module named 'pyfory'", name="pyfory"),
        )

    assert caught.value.name == "pyfory"
    assert str(caught.value) == (
        "Install bluetape-serde[fory] with CPython 3.13 to use Apache Fory."
    )
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "provider_error",
    [
        ModuleNotFoundError("No module named 'provider_helper'", name="provider_helper"),
        ImportError("provider ABI is incompatible"),
        OSError("provider shared library failed"),
        RuntimeError("provider initialization failed"),
    ],
)
def test_non_direct_provider_import_failures_propagate_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    provider_error: BaseException,
) -> None:
    with pytest.raises(type(provider_error)) as caught:
        _load_fory_with_provider_import(monkeypatch, provider_error)

    assert caught.value is provider_error
    assert "Install bluetape-serde[fory]" not in str(caught.value)
