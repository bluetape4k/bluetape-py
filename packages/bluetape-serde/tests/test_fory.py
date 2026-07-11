import importlib.util
import math
import struct
import sys
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any

import bluetape.serde.fory as fory_module
import pyfory
import pytest
from bluetape.serde import (
    ContentTypeMismatchError,
    FormatMismatchError,
    ForyRegistrationError,
    PayloadLimitError,
    PayloadMetadata,
    SerdeEncodeError,
    SerdeErrorCode,
    TrustProfile,
    TrustProfileMismatchError,
    TypeMismatchError,
    UnsupportedVersionError,
)
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyLimits,
    ForyRegistration,
)


@dataclass(slots=True)
class ConformanceRecord:
    record_id: pyfory.Int64
    name: str
    active: bool
    scores: list[pyfory.Int32]


class ConformanceRecordChild(ConformanceRecord):
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


def trusted_metadata(**overrides: Any) -> PayloadMetadata:
    values: dict[str, Any] = {
        "format": FORY_FORMAT,
        "version": FORY_VERSION,
        "content_type": FORY_CONTENT_TYPE,
        "trust_profile": TrustProfile.TRUSTED_INTERNAL,
    }
    values.update(overrides)
    return PayloadMetadata(**values)


def record() -> ConformanceRecord:
    return ConformanceRecord(
        record_id=pyfory.Int64(7),
        name="Ada",
        active=True,
        scores=[pyfory.Int32(10), pyfory.Int32(20)],
    )


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


class _SpyRuntime:
    def __init__(self, registrations: list[tuple[type[object], int]], *, fail: bool = False):
        self._registrations = registrations
        self._fail = fail

    def register(self, python_type: type[object], *, type_id: int) -> None:
        self._registrations.append((python_type, type_id))
        if self._fail:
            raise ValueError("secret provider registration failure")


class _SpyPool:
    def __init__(self, *, fory_factory: Any):
        self.fory_factory = fory_factory
        self.serialize_calls = 0

    def serialize(self, value: object) -> bytes:
        self.serialize_calls += 1
        return b"body"


def test_fory_adapter_constructs_probe_and_pool_with_fixed_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configs: list[dict[str, object]] = []
    registrations: list[tuple[type[object], int]] = []
    pools: list[_SpyPool] = []

    def new_runtime(**kwargs: object) -> _SpyRuntime:
        configs.append(kwargs)
        return _SpyRuntime(registrations)

    def new_pool(*, fory_factory: Any) -> _SpyPool:
        pool = _SpyPool(fory_factory=fory_factory)
        pools.append(pool)
        return pool

    monkeypatch.setattr(fory_module._pyfory, "Fory", new_runtime)
    monkeypatch.setattr(fory_module._pyfory, "ThreadSafeFory", new_pool)

    limits = ForyLimits()
    adapter = ForyAdapter(registration=registration(), limits=limits)

    assert adapter.registration == registration()
    assert adapter.limits is limits
    assert configs == [
        {
            "xlang": True,
            "strict": True,
            "ref": False,
            "compatible": False,
            "max_depth": 64,
            "max_type_fields": 256,
            "max_type_meta_bytes": 4096,
            "max_schema_versions_per_type": 8,
            "max_average_schema_versions_per_type": 2,
        }
    ]
    assert registrations == [(ConformanceRecord, 1001)]
    assert len(pools) == 1
    pooled_runtime = pools[0].fory_factory()
    assert isinstance(pooled_runtime, _SpyRuntime)
    assert configs[1] == configs[0]
    assert registrations == [(ConformanceRecord, 1001), (ConformanceRecord, 1001)]


def test_fory_adapter_translates_only_registration_callback_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fory_module._pyfory,
        "Fory",
        lambda **kwargs: _SpyRuntime([], fail=True),
    )

    with pytest.raises(ForyRegistrationError) as caught:
        ForyAdapter(registration=registration())

    assert str(caught.value) == "Fory registration failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_fory_adapter_propagates_provider_construction_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = RuntimeError("provider construction failed")

    def fail_construction(**kwargs: object) -> _SpyRuntime:
        raise failure

    monkeypatch.setattr(fory_module._pyfory, "Fory", fail_construction)

    with pytest.raises(RuntimeError) as caught:
        ForyAdapter(registration=registration())

    assert caught.value is failure


@pytest.mark.parametrize(
    ("metadata", "error_type"),
    [
        (trusted_metadata(format="json"), FormatMismatchError),
        (trusted_metadata(version=2), UnsupportedVersionError),
        (trusted_metadata(content_type="application/json"), ContentTypeMismatchError),
        (
            trusted_metadata(trust_profile=TrustProfile.UNTRUSTED),
            TrustProfileMismatchError,
        ),
    ],
)
def test_fory_serialize_rejects_invalid_metadata_before_provider_access(
    monkeypatch: pytest.MonkeyPatch,
    metadata: PayloadMetadata,
    error_type: type[Exception],
) -> None:
    pools: list[_SpyPool] = []
    monkeypatch.setattr(
        fory_module._pyfory,
        "Fory",
        lambda **kwargs: _SpyRuntime([]),
    )

    def new_pool(*, fory_factory: Any) -> _SpyPool:
        pool = _SpyPool(fory_factory=fory_factory)
        pools.append(pool)
        return pool

    monkeypatch.setattr(fory_module._pyfory, "ThreadSafeFory", new_pool)
    adapter = ForyAdapter(registration=registration())

    with pytest.raises(error_type):
        adapter.serialize(record(), metadata=metadata)

    assert pools[0].serialize_calls == 0


def test_fory_serialize_requires_exact_registered_root_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pools: list[_SpyPool] = []
    monkeypatch.setattr(
        fory_module._pyfory,
        "Fory",
        lambda **kwargs: _SpyRuntime([]),
    )

    def new_pool(*, fory_factory: Any) -> _SpyPool:
        pool = _SpyPool(fory_factory=fory_factory)
        pools.append(pool)
        return pool

    monkeypatch.setattr(fory_module._pyfory, "ThreadSafeFory", new_pool)
    adapter = ForyAdapter(registration=registration())
    child = ConformanceRecordChild(
        record_id=pyfory.Int64(7),
        name="Ada",
        active=True,
        scores=[],
    )

    with pytest.raises(TypeMismatchError):
        adapter.serialize(child, metadata=trusted_metadata())

    assert pools[0].serialize_calls == 0


def test_fory_serialize_writes_canonical_header_and_decodable_body() -> None:
    adapter = ForyAdapter(registration=registration())
    value = record()

    payload = adapter.serialize(value, metadata=trusted_metadata())

    body = payload.data[20:]
    expected_header = struct.Struct(">4sBBIHII").pack(
        b"BTFY",
        1,
        0,
        0x42544659,
        1,
        1001,
        len(body),
    )
    assert payload.metadata == trusted_metadata()
    assert payload.data[:20] == expected_header
    assert len(body) > 0

    raw_fory = pyfory.Fory(
        xlang=True,
        strict=True,
        ref=False,
        compatible=False,
        max_depth=64,
        max_type_fields=256,
        max_type_meta_bytes=4096,
        max_schema_versions_per_type=8,
        max_average_schema_versions_per_type=2,
    )
    raw_fory.register(ConformanceRecord, type_id=1001)
    assert raw_fory.deserialize(body) == value


def test_fory_serialize_enforces_total_output_limit() -> None:
    adapter = ForyAdapter(
        registration=registration(),
        limits=ForyLimits(max_output_size=20),
    )

    with pytest.raises(PayloadLimitError) as caught:
        adapter.serialize(record(), metadata=trusted_metadata())

    assert caught.value.code is SerdeErrorCode.OUTPUT_LIMIT


def test_fory_serialize_sanitizes_provider_failure_without_logging(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "caller-secret-marker"

    class FailingPool(_SpyPool):
        def serialize(self, value: object) -> bytes:
            raise ValueError(f"provider rejected {marker}")

    monkeypatch.setattr(
        fory_module._pyfory,
        "Fory",
        lambda **kwargs: _SpyRuntime([]),
    )
    monkeypatch.setattr(fory_module._pyfory, "ThreadSafeFory", FailingPool)
    adapter = ForyAdapter(registration=registration())
    value = record()
    value.name = marker

    with pytest.raises(SerdeEncodeError) as caught:
        adapter.serialize(value, metadata=trusted_metadata())

    assert caught.value.code is SerdeErrorCode.FORY_ENCODE
    assert str(caught.value) == "value cannot be encoded as registered Fory type"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert marker not in str(caught.value)
    traceback = caught.value.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code.co_filename.endswith("/bluetape/serde/fory.py"):
            assert all(
                marker not in repr(local_value)
                for local_value in traceback.tb_frame.f_locals.values()
            )
        traceback = traceback.tb_next
    assert not caplog.records
