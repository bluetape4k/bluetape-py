import importlib.util
import math
import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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
    ForyConcurrencyError,
    ForyRegistrationError,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SchemaMismatchError,
    SerdeEncodeError,
    SerdeErrorCode,
    SerializedPayload,
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


def envelope(
    body: bytes,
    *,
    magic: bytes = b"BTFY",
    envelope_version: int = 1,
    flags: int = 0,
    schema_id: int = 0x42544659,
    schema_version: int = 1,
    type_id: int = 1001,
    body_length: int | None = None,
) -> bytes:
    return (
        struct.Struct(">4sBBIHII").pack(
            magic,
            envelope_version,
            flags,
            schema_id,
            schema_version,
            type_id,
            len(body) if body_length is None else body_length,
        )
        + body
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


class _DecodeSpyPool:
    def __init__(self, result: object = None, failure: BaseException | None = None):
        self.result = result
        self.failure = failure
        self.deserialize_calls = 0

    def deserialize(self, buffer: object) -> object:
        self.deserialize_calls += 1
        if self.failure is not None:
            raise self.failure
        if hasattr(buffer, "set_reader_index"):
            buffer.set_reader_index(len(buffer))
        return self.result


def valid_payload(adapter: ForyAdapter[ConformanceRecord] | None = None) -> SerializedPayload:
    active_adapter = adapter or ForyAdapter(registration=registration())
    return active_adapter.serialize(record(), metadata=trusted_metadata())


@pytest.mark.parametrize(
    ("actual_trust", "expected_trust"),
    [
        (TrustProfile.UNTRUSTED, TrustProfile.UNTRUSTED),
        (TrustProfile.UNTRUSTED, TrustProfile.TRUSTED_INTERNAL),
        (TrustProfile.TRUSTED_INTERNAL, TrustProfile.UNTRUSTED),
    ],
)
def test_fory_deserialize_rejects_untrusted_actual_or_expected_policy_before_provider(
    actual_trust: TrustProfile,
    expected_trust: TrustProfile,
) -> None:
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    spy = _DecodeSpyPool(record())
    adapter._pool = spy
    payload = SerializedPayload(
        metadata=trusted_metadata(trust_profile=actual_trust),
        data=produced.data,
    )
    expected = trusted_metadata(trust_profile=expected_trust)

    with pytest.raises(TrustProfileMismatchError):
        adapter.deserialize(payload, expected_metadata=expected)

    assert spy.deserialize_calls == 0


def test_fory_deserialize_uses_caller_expected_metadata_not_received_policy() -> None:
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    spy = _DecodeSpyPool(record())
    adapter._pool = spy
    received = SerializedPayload(metadata=trusted_metadata(), data=produced.data)
    caller_policy = trusted_metadata(content_type="application/octet-stream")

    with pytest.raises(ContentTypeMismatchError):
        adapter.deserialize(received, expected_metadata=caller_policy)

    assert spy.deserialize_calls == 0


@pytest.mark.parametrize(
    ("mutate", "error_type", "code"),
    [
        (lambda data: data[:19], MalformedPayloadError, SerdeErrorCode.INVALID_FORY),
        (
            lambda data: envelope(data[20:], magic=b"NOPE"),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
        (
            lambda data: envelope(data[20:], envelope_version=2),
            UnsupportedVersionError,
            None,
        ),
        (
            lambda data: envelope(data[20:], flags=1),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
        (
            lambda data: envelope(data[20:], schema_id=7),
            SchemaMismatchError,
            None,
        ),
        (
            lambda data: envelope(data[20:], schema_version=2),
            SchemaMismatchError,
            None,
        ),
        (lambda data: envelope(data[20:], type_id=7), TypeMismatchError, None),
        (
            lambda data: envelope(data[20:], body_length=len(data)),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
        (
            lambda data: envelope(b""),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
        (
            lambda data: envelope(bytes([data[20] | 0x02]) + data[21:]),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
        (
            lambda data: envelope(bytes([data[20] | 0x04]) + data[21:]),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
        (
            lambda data: envelope(bytes([data[20] & ~0x01]) + data[21:]),
            MalformedPayloadError,
            SerdeErrorCode.INVALID_FORY,
        ),
    ],
)
def test_fory_deserialize_rejects_envelope_gates_before_provider(
    mutate: Any,
    error_type: type[Exception],
    code: SerdeErrorCode | None,
) -> None:
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    spy = _DecodeSpyPool(record())
    adapter._pool = spy
    payload = SerializedPayload(metadata=trusted_metadata(), data=mutate(produced.data))

    with pytest.raises(error_type) as caught:
        adapter.deserialize(payload, expected_metadata=trusted_metadata())

    if code is not None:
        assert caught.value.code is code
    assert spy.deserialize_calls == 0


def test_fory_deserialize_rejects_total_input_limit_before_provider() -> None:
    producer = ForyAdapter(registration=registration())
    produced = valid_payload(producer)
    adapter = ForyAdapter(
        registration=registration(),
        limits=ForyLimits(max_input_size=20),
    )
    spy = _DecodeSpyPool(record())
    adapter._pool = spy

    with pytest.raises(PayloadLimitError) as caught:
        adapter.deserialize(produced, expected_metadata=trusted_metadata())

    assert caught.value.code is SerdeErrorCode.INPUT_LIMIT
    assert spy.deserialize_calls == 0


def test_fory_deserialize_round_trips_exact_registered_root() -> None:
    adapter = ForyAdapter(registration=registration())
    value = record()
    payload = adapter.serialize(value, metadata=trusted_metadata())

    assert adapter.deserialize(payload, expected_metadata=trusted_metadata()) == value


def test_fory_deserialize_rejects_builtin_and_subclass_results() -> None:
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    child = ConformanceRecordChild(
        record_id=pyfory.Int64(7),
        name="Ada",
        active=True,
        scores=[],
    )
    for invalid in ({"built_in": True}, child):
        adapter._pool = _DecodeSpyPool(invalid)
        with pytest.raises(TypeMismatchError):
            adapter.deserialize(produced, expected_metadata=trusted_metadata())


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("provider depth limit secret"),
        RuntimeError("provider parse secret"),
    ],
)
def test_fory_deserialize_sanitizes_provider_failures(
    failure: BaseException,
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "payload-secret-marker"
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    payload = SerializedPayload(metadata=trusted_metadata(), data=produced.data + marker.encode())
    payload = SerializedPayload(
        metadata=payload.metadata,
        data=envelope(payload.data[20:], body_length=len(payload.data[20:])),
    )
    adapter._pool = _DecodeSpyPool(failure=failure)

    with pytest.raises(MalformedPayloadError) as caught:
        adapter.deserialize(payload, expected_metadata=trusted_metadata())

    assert caught.value.code is SerdeErrorCode.INVALID_FORY
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


@pytest.mark.parametrize("failure", [MemoryError(), KeyboardInterrupt(), SystemExit()])
def test_fory_deserialize_propagates_fatal_provider_failures(failure: BaseException) -> None:
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    adapter._pool = _DecodeSpyPool(failure=failure)

    with pytest.raises(type(failure)) as caught:
        adapter.deserialize(produced, expected_metadata=trusted_metadata())

    assert caught.value is failure


def test_fory_deserialize_rejects_valid_body_with_trailing_byte() -> None:
    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    body = produced.data[20:] + b"\x00"
    payload = SerializedPayload(metadata=trusted_metadata(), data=envelope(body))

    with pytest.raises(MalformedPayloadError) as caught:
        adapter.deserialize(payload, expected_metadata=trusted_metadata())

    assert caught.value.code is SerdeErrorCode.INVALID_FORY


def test_fory_deserialize_maps_semaphore_timeout_without_provider_access() -> None:
    class TimeoutSemaphore:
        def acquire(self, *, timeout: float) -> bool:
            return False

        def release(self) -> None:
            raise AssertionError("unacquired semaphore must not be released")

    adapter = ForyAdapter(registration=registration())
    produced = valid_payload(adapter)
    spy = _DecodeSpyPool(record())
    adapter._pool = spy
    adapter._semaphore = TimeoutSemaphore()

    with pytest.raises(ForyConcurrencyError):
        adapter.deserialize(produced, expected_metadata=trusted_metadata())

    assert spy.deserialize_calls == 0


def test_fory_adapter_caps_lazy_runtimes_and_times_out_fifth_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []
    entered = threading.Barrier(5)
    release = threading.Event()

    class BlockingRuntime:
        def __init__(self) -> None:
            created.append(self)

        def register(self, python_type: type[object], *, type_id: int) -> None:
            pass

        def serialize(self, value: ConformanceRecord, *args: object) -> bytes:
            entered.wait(timeout=2)
            assert release.wait(timeout=2)
            return b"\x01" + value.name.encode()

    monkeypatch.setattr(fory_module._pyfory, "Fory", lambda **kwargs: BlockingRuntime())
    adapter = ForyAdapter(
        registration=registration(),
        limits=ForyLimits(max_concurrency=4, acquire_timeout_seconds=0.01),
    )
    values = [
        ConformanceRecord(pyfory.Int64(index), f"value-{index}", True, []) for index in range(4)
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(adapter.serialize, value, metadata=trusted_metadata())
            for value in values
        ]
        entered.wait(timeout=2)
        with pytest.raises(ForyConcurrencyError):
            adapter.serialize(record(), metadata=trusted_metadata())
        release.set()
        payloads = [future.result(timeout=2) for future in futures]

    assert len(created) == 5  # one discarded probe plus four retained runtimes
    assert {payload.data[21:].decode() for payload in payloads} == {value.name for value in values}


def test_lazy_registration_failure_is_discarded_and_releases_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []

    class RegistrationRuntime:
        def __init__(self) -> None:
            self.number = len(created) + 1
            created.append(self)

        def register(self, python_type: type[object], *, type_id: int) -> None:
            if self.number == 2:
                raise ValueError("first lazy registration fails")

        def serialize(self, value: object, *args: object) -> bytes:
            return b"\x01ok"

    monkeypatch.setattr(
        fory_module._pyfory,
        "Fory",
        lambda **kwargs: RegistrationRuntime(),
    )
    adapter = ForyAdapter(
        registration=registration(),
        limits=ForyLimits(max_concurrency=1, acquire_timeout_seconds=0.01),
    )

    with pytest.raises(ForyRegistrationError):
        adapter.serialize(record(), metadata=trusted_metadata())
    payload = adapter.serialize(record(), metadata=trusted_metadata())

    assert payload.data[20:] == b"\x01ok"
    assert len(created) == 3


def test_ordinary_encode_failure_returns_same_runtime_for_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []
    used: list[object] = []

    class ReusableRuntime:
        def __init__(self) -> None:
            self.fail_next = len(created) == 1
            created.append(self)

        def register(self, python_type: type[object], *, type_id: int) -> None:
            pass

        def serialize(self, value: object, *args: object) -> bytes:
            used.append(self)
            if self.fail_next:
                self.fail_next = False
                raise ValueError("ordinary encode failure")
            return b"\x01reused"

    monkeypatch.setattr(fory_module._pyfory, "Fory", lambda **kwargs: ReusableRuntime())
    adapter = ForyAdapter(
        registration=registration(),
        limits=ForyLimits(max_concurrency=1, acquire_timeout_seconds=0.01),
    )

    with pytest.raises(SerdeEncodeError):
        adapter.serialize(record(), metadata=trusted_metadata())
    payload = adapter.serialize(record(), metadata=trusted_metadata())

    assert payload.data[20:] == b"\x01reused"
    assert len(created) == 2
    assert used[0] is used[1]


def test_ordinary_decode_failure_returns_same_runtime_for_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []
    used: list[object] = []
    expected = record()

    class ReusableRuntime:
        def __init__(self) -> None:
            self.fail_next = len(created) == 1
            created.append(self)

        def register(self, python_type: type[object], *, type_id: int) -> None:
            pass

        def deserialize(self, buffer: object, *args: object) -> ConformanceRecord:
            used.append(self)
            if self.fail_next:
                self.fail_next = False
                raise ValueError("ordinary decode failure")
            buffer.set_reader_index(len(buffer))
            return expected

    monkeypatch.setattr(fory_module._pyfory, "Fory", lambda **kwargs: ReusableRuntime())
    adapter = ForyAdapter(
        registration=registration(),
        limits=ForyLimits(max_concurrency=1, acquire_timeout_seconds=0.01),
    )
    payload = SerializedPayload(metadata=trusted_metadata(), data=envelope(b"\x01"))

    with pytest.raises(MalformedPayloadError):
        adapter.deserialize(payload, expected_metadata=trusted_metadata())
    assert adapter.deserialize(payload, expected_metadata=trusted_metadata()) == expected

    assert len(created) == 2
    assert used[0] is used[1]
