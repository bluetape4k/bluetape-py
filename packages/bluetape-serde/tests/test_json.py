import ast
import inspect
import json
import math
import sys
import tracemalloc
from collections.abc import Iterator
from typing import get_type_hints

import pytest
from bluetape.serde import (
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    DEFAULT_MAX_OUTPUT_SIZE,
    MAX_JSON_INTEGER_DIGITS,
    MAX_SUPPORTED_NESTING_DEPTH,
    ContentTypeMismatchError,
    FormatMismatchError,
    ForyConcurrencyError,
    ForyRegistrationError,
    InvalidMetadataError,
    JsonValue,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SchemaMismatchError,
    SerdeEncodeError,
    SerdeError,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfile,
    TrustProfileMismatchError,
    TypeMismatchError,
    UnsupportedVersionError,
    json_deserialize,
    json_serialize,
)
from bluetape.serde._json import _preflight_json_text, _preflight_json_value

EXPECTED_EXPORTS = [
    "DEFAULT_MAX_INPUT_SIZE",
    "DEFAULT_MAX_OUTPUT_SIZE",
    "DEFAULT_MAX_NESTING_DEPTH",
    "MAX_SUPPORTED_NESTING_DEPTH",
    "MAX_JSON_INTEGER_DIGITS",
    "ContentTypeMismatchError",
    "ForyConcurrencyError",
    "ForyRegistrationError",
    "FormatMismatchError",
    "InvalidMetadataError",
    "JsonValue",
    "MalformedPayloadError",
    "PayloadLimitError",
    "PayloadMetadata",
    "SchemaMismatchError",
    "SerializedPayload",
    "SerdeError",
    "SerdeErrorCode",
    "SerdeEncodeError",
    "TrustProfile",
    "TrustProfileMismatchError",
    "TypeMismatchError",
    "UnsupportedVersionError",
    "json_deserialize",
    "json_serialize",
]
DIRECT_EXPORTS = [
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_OUTPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    MAX_SUPPORTED_NESTING_DEPTH,
    MAX_JSON_INTEGER_DIGITS,
    ContentTypeMismatchError,
    ForyConcurrencyError,
    ForyRegistrationError,
    FormatMismatchError,
    InvalidMetadataError,
    JsonValue,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SchemaMismatchError,
    SerializedPayload,
    SerdeError,
    SerdeErrorCode,
    SerdeEncodeError,
    TrustProfile,
    TrustProfileMismatchError,
    TypeMismatchError,
    UnsupportedVersionError,
    json_deserialize,
    json_serialize,
]

LARGE_VALID_JSON_INPUT_LIMIT = 1024 * 1024
_LARGE_VALID_JSON_PREFIX = (
    b'{"odd":"odd ' + b"\\" * 3 + b'" quote {[]}","even":"even ' + b"\\" * 4 + b'","padding":"'
)
_LARGE_VALID_JSON_SUFFIX = b'"}'
_LARGE_VALID_JSON_PADDING_SIZE = (
    LARGE_VALID_JSON_INPUT_LIMIT - len(_LARGE_VALID_JSON_PREFIX) - len(_LARGE_VALID_JSON_SUFFIX)
)
LARGE_VALID_JSON_PAYLOAD = (
    _LARGE_VALID_JSON_PREFIX + b"x" * _LARGE_VALID_JSON_PADDING_SIZE + _LARGE_VALID_JSON_SUFFIX
)
if hasattr(sys, "set_int_max_str_digits"):
    _INTEGER_DIGIT_SETTINGS = [
        pytest.param(sys.int_info.default_max_str_digits, id="default"),
        pytest.param(sys.int_info.str_digits_check_threshold, id="minimum"),
        pytest.param(0, id="disabled"),
    ]
else:
    _INTEGER_DIGIT_SETTINGS = [pytest.param(None, id="unavailable")]


def metadata(
    *,
    format_name: str = "json",
    version: int = 1,
    content_type: str | None = "application/json",
    trust_profile: TrustProfile = TrustProfile.UNTRUSTED,
) -> PayloadMetadata:
    return PayloadMetadata(
        format=format_name,
        version=version,
        content_type=content_type,
        trust_profile=trust_profile,
    )


def assert_error(
    caught: pytest.ExceptionInfo[Exception],
    *,
    error_type: type[Exception],
    code: SerdeErrorCode,
    message: str,
) -> None:
    error = caught.value
    assert type(error) is error_type
    assert isinstance(error, SerdeError)
    assert error.code is code
    assert str(error) == message
    assert error.args == (message,)
    assert error.__cause__ is None
    assert error.__context__ is None


def assert_traceback_does_not_retain_source(
    error: Exception,
    *,
    forbidden_local_names: frozenset[str] = frozenset(),
    source_values: tuple[object, ...] = (),
    source_keys: frozenset[str] = frozenset(),
    raw_source: bytes | None = None,
    text_source: str | None = None,
) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    traceback = error.__traceback__
    while traceback is not None:
        frame = traceback.tb_frame
        if frame.f_code.co_filename.endswith("/bluetape/serde/_json.py"):
            assert frame.f_code.co_name in {"json_deserialize", "json_serialize"}
            assert forbidden_local_names.isdisjoint(frame.f_locals)
            for value in frame.f_locals.values():
                assert all(value is not source for source in source_values)
                if type(value) is str:
                    assert value not in source_keys
                if raw_source is not None:
                    if type(value) is bytes:
                        assert value != raw_source
                    if type(value) is SerializedPayload:
                        assert value.data != raw_source
                if text_source is not None and type(value) is str:
                    assert value != text_source
        traceback = traceback.tb_next


def assert_decode_traceback_does_not_retain_source(
    error: Exception,
    *,
    raw_source: bytes | None = None,
    text_source: str | None = None,
) -> None:
    assert_traceback_does_not_retain_source(
        error,
        forbidden_local_names=frozenset({"payload", "data", "text"}),
        raw_source=raw_source,
        text_source=text_source,
    )


def nested_list(depth: int) -> JsonValue:
    value: JsonValue = None
    for _ in range(depth):
        value = [value]
    return value


def serialized(
    data: bytes = b"null",
    *,
    payload_metadata: PayloadMetadata | None = None,
) -> SerializedPayload:
    return SerializedPayload(metadata=payload_metadata or metadata(), data=data)


def test_json_public_contract_has_exact_exports_constants_and_signature() -> None:
    import bluetape.serde as serde

    assert serde.__all__ == EXPECTED_EXPORTS
    assert all(
        getattr(serde, name) is exported
        for name, exported in zip(EXPECTED_EXPORTS, DIRECT_EXPORTS, strict=True)
    )
    assert DEFAULT_MAX_INPUT_SIZE == 16 * 1024 * 1024
    assert DEFAULT_MAX_OUTPUT_SIZE == 16 * 1024 * 1024
    assert DEFAULT_MAX_NESTING_DEPTH == 100
    assert MAX_SUPPORTED_NESTING_DEPTH == 256
    assert MAX_JSON_INTEGER_DIGITS == 640
    assert "MAX_JSON_INTEGER_DIGITS" in (json_serialize.__doc__ or "")
    assert "MAX_JSON_INTEGER_DIGITS" in (json_deserialize.__doc__ or "")

    signature = inspect.signature(json_serialize)
    assert list(signature.parameters) == [
        "value",
        "metadata",
        "max_output_size",
        "max_nesting_depth",
    ]
    assert signature.parameters["value"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert signature.parameters["metadata"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["max_output_size"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["max_nesting_depth"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["max_output_size"].default == DEFAULT_MAX_OUTPUT_SIZE
    assert signature.parameters["max_nesting_depth"].default == DEFAULT_MAX_NESTING_DEPTH
    hints = get_type_hints(json_serialize)
    assert hints == {
        "value": JsonValue,
        "metadata": PayloadMetadata,
        "max_output_size": int,
        "max_nesting_depth": int,
        "return": SerializedPayload,
    }

    deserialize_signature = inspect.signature(json_deserialize)
    assert list(deserialize_signature.parameters) == [
        "payload",
        "expected_metadata",
        "max_input_size",
        "max_nesting_depth",
    ]
    assert (
        deserialize_signature.parameters["payload"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    assert (
        deserialize_signature.parameters["expected_metadata"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert deserialize_signature.parameters["expected_metadata"].default is inspect.Signature.empty
    assert deserialize_signature.parameters["max_input_size"].kind is inspect.Parameter.KEYWORD_ONLY
    assert (
        deserialize_signature.parameters["max_nesting_depth"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert deserialize_signature.parameters["max_input_size"].default == (DEFAULT_MAX_INPUT_SIZE)
    assert deserialize_signature.parameters["max_nesting_depth"].default == (
        DEFAULT_MAX_NESTING_DEPTH
    )
    assert get_type_hints(json_deserialize) == {
        "payload": SerializedPayload,
        "expected_metadata": PayloadMetadata,
        "max_input_size": int,
        "max_nesting_depth": int,
        "return": JsonValue,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, b"null"),
        (False, b"false"),
        (True, b"true"),
        (0, b"0"),
        (-7, b"-7"),
        (1.25, b"1.25"),
        ("hello", b'"hello"'),
        ([1, True, None], b"[1,true,null]"),
        ({"a": 1, "b": [False]}, b'{"a":1,"b":[false]}'),
        ("한글 😺", '"한글 😺"'.encode()),
    ],
)
@pytest.mark.parametrize("trust_profile", list(TrustProfile))
def test_json_serialize_encodes_strict_compact_utf8_and_retains_metadata(
    value: JsonValue,
    expected: bytes,
    trust_profile: TrustProfile,
) -> None:
    payload_metadata = metadata(trust_profile=trust_profile)

    payload = json_serialize(value, metadata=payload_metadata)

    assert type(payload) is SerializedPayload
    assert payload.metadata is payload_metadata
    assert payload.data == expected


@pytest.mark.parametrize(
    ("payload_metadata", "error_type", "code", "message"),
    [
        (
            metadata(format_name="msgpack", version=2, content_type="text/plain"),
            FormatMismatchError,
            SerdeErrorCode.FORMAT_MISMATCH,
            "payload format does not match expected format",
        ),
        (
            metadata(version=2, content_type="text/plain"),
            ContentTypeMismatchError,
            SerdeErrorCode.CONTENT_TYPE_MISMATCH,
            "payload content type does not match expected content type",
        ),
        (
            metadata(version=2),
            UnsupportedVersionError,
            SerdeErrorCode.UNSUPPORTED_VERSION,
            "payload version is unsupported",
        ),
    ],
)
def test_json_serialize_validates_adapter_metadata_in_deterministic_order(
    payload_metadata: PayloadMetadata,
    error_type: type[Exception],
    code: SerdeErrorCode,
    message: str,
) -> None:
    with pytest.raises(error_type) as caught:
        json_serialize(None, metadata=payload_metadata)

    assert_error(caught, error_type=error_type, code=code, message=message)


class MetadataLookalike(PayloadMetadata):
    pass


class IntegerLookalike(int):
    pass


class FloatLookalike(float):
    pass


class StringLookalike(str):
    pass


class DictLookalike(dict[str, object]):
    pass


class HostileList(list[object]):
    def __iter__(self) -> Iterator[object]:
        raise AssertionError("hostile value was traversed")


@pytest.mark.parametrize(
    ("arguments", "error_type", "message"),
    [
        (
            {"metadata": object()},
            TypeError,
            "metadata must be an exact PayloadMetadata",
        ),
        (
            {
                "metadata": MetadataLookalike(
                    format="json",
                    version=1,
                    content_type="application/json",
                    trust_profile=TrustProfile.UNTRUSTED,
                )
            },
            TypeError,
            "metadata must be an exact PayloadMetadata",
        ),
        (
            {"metadata": metadata(), "max_output_size": True},
            TypeError,
            "max_output_size must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_output_size": 1.0},
            TypeError,
            "max_output_size must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_output_size": IntegerLookalike(1)},
            TypeError,
            "max_output_size must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_output_size": -1},
            ValueError,
            "max_output_size must be between 0 and sys.maxsize - 1",
        ),
        (
            {"metadata": metadata(), "max_output_size": sys.maxsize},
            ValueError,
            "max_output_size must be between 0 and sys.maxsize - 1",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": True},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": 1.0},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": IntegerLookalike(1)},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": -1},
            ValueError,
            "max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": 257},
            ValueError,
            "max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH",
        ),
    ],
)
def test_json_serialize_validates_exact_metadata_and_configuration_before_value_or_encoder(
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    constructed = False

    class EncoderSpy:
        def __init__(self, **_: object) -> None:
            nonlocal constructed
            constructed = True

    monkeypatch.setattr("bluetape.serde._json.json.JSONEncoder", EncoderSpy)

    with pytest.raises(error_type) as caught:
        json_serialize(HostileList(), **arguments)  # type: ignore[arg-type]

    assert type(caught.value) is error_type
    assert str(caught.value) == message
    assert constructed is False


@pytest.mark.parametrize(
    ("arguments", "error_type", "message"),
    [
        (
            {"metadata": {"ENCODE_CONFIGURATION_PRIVATE_KEY": "private metadata"}},
            TypeError,
            "metadata must be an exact PayloadMetadata",
        ),
        (
            {"metadata": metadata(), "max_output_size": IntegerLookalike(1)},
            TypeError,
            "max_output_size must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_output_size": -1},
            ValueError,
            "max_output_size must be between 0 and sys.maxsize - 1",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": IntegerLookalike(1)},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"metadata": metadata(), "max_nesting_depth": 257},
            ValueError,
            "max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH",
        ),
    ],
)
def test_json_serialize_configuration_errors_do_not_retain_caller_sources(
    arguments: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    value: JsonValue = {"ENCODE_CONFIGURATION_PRIVATE_KEY": "private value"}

    with pytest.raises(error_type) as caught:
        json_serialize(value, **arguments)  # type: ignore[arg-type]

    assert type(caught.value) is error_type
    assert str(caught.value) == message
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset(
            {"value", "metadata", "max_output_size", "max_nesting_depth"}
        ),
        source_values=(value, *arguments.values()),
        source_keys=frozenset({"ENCODE_CONFIGURATION_PRIVATE_KEY"}),
    )


@pytest.mark.parametrize("fatal_error", [MemoryError(), KeyboardInterrupt(), SystemExit()])
def test_json_serialize_configuration_fatal_errors_remain_native(
    monkeypatch: pytest.MonkeyPatch,
    fatal_error: BaseException,
) -> None:
    def fail_validation(**_arguments: object) -> None:
        raise fatal_error

    monkeypatch.setattr("bluetape.serde._json._validate_configuration", fail_validation)

    with pytest.raises(type(fatal_error)) as caught:
        json_serialize(None, metadata=metadata())

    assert caught.value is fatal_error


def test_json_serialize_accepts_largest_supported_output_size() -> None:
    assert json_serialize(None, metadata=metadata(), max_output_size=sys.maxsize - 1).data


@pytest.mark.parametrize(
    "value",
    [
        (),
        (value for value in [1]),
        object(),
        IntegerLookalike(1),
        FloatLookalike(1.0),
        StringLookalike("value"),
        DictLookalike({"key": "value"}),
        HostileList(),
        {StringLookalike("key"): "value"},
        {1: "number key"},
        {1: "coerced", "1": "string"},
    ],
)
def test_json_serialize_rejects_unsupported_values_without_coercion(value: object) -> None:
    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(value, metadata=metadata())  # type: ignore[arg-type]

    assert_error(
        caught,
        error_type=SerdeEncodeError,
        code=SerdeErrorCode.UNSUPPORTED_VALUE,
        message="value is not JSON-serializable",
    )


@pytest.mark.parametrize(
    "value",
    [
        "\ud800",
        "\udc00",
        "\ud83d\ude00",
        {"\ud800": "value"},
        {"key": "\udc00"},
    ],
)
def test_json_serialize_rejects_surrogate_code_points_without_source_retention(
    value: JsonValue,
) -> None:
    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(value, metadata=metadata())

    assert_error(
        caught,
        error_type=SerdeEncodeError,
        code=SerdeErrorCode.UNSUPPORTED_VALUE,
        message="value is not JSON-serializable",
    )
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(value,),
    )


def test_json_serialize_accepts_unicode_scalar_values_including_non_bmp() -> None:
    assert (
        json_serialize(
            {"emoji": "😀", "music": "𝄞"},
            metadata=metadata(),
        ).data
        == '{"emoji":"😀","music":"𝄞"}'.encode()
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_json_serialize_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(value, metadata=metadata())

    assert_error(
        caught,
        error_type=SerdeEncodeError,
        code=SerdeErrorCode.ENCODE_NON_FINITE_NUMBER,
        message="value contains a non-finite number",
    )


@pytest.mark.parametrize(
    "value",
    [
        10**639,
        -(10**639),
        {"nested": [10**639]},
    ],
)
@pytest.mark.parametrize("setting", _INTEGER_DIGIT_SETTINGS)
def test_json_serialize_accepts_integers_at_640_decimal_digits(
    value: JsonValue,
    setting: int | None,
) -> None:
    original = sys.get_int_max_str_digits() if setting is not None else None
    try:
        if setting is not None:
            sys.set_int_max_str_digits(setting)
        payload = json_serialize(value, metadata=metadata())
    finally:
        if original is not None:
            sys.set_int_max_str_digits(original)

    assert json_deserialize(payload, expected_metadata=metadata()) == value


@pytest.mark.parametrize(
    "value",
    [
        10**640,
        -(10**640),
        {"nested": [10**640]},
    ],
)
@pytest.mark.parametrize("setting", _INTEGER_DIGIT_SETTINGS)
def test_json_serialize_rejects_integers_over_640_digits_before_encoder(
    monkeypatch: pytest.MonkeyPatch,
    value: JsonValue,
    setting: int | None,
) -> None:
    monkeypatch.setattr(
        "bluetape.serde._json.json.JSONEncoder",
        lambda **_options: pytest.fail("encoder was constructed"),
    )

    original = sys.get_int_max_str_digits() if setting is not None else None
    try:
        if setting is not None:
            sys.set_int_max_str_digits(setting)
        with pytest.raises(PayloadLimitError) as caught:
            json_serialize(value, metadata=metadata())
    finally:
        if original is not None:
            sys.set_int_max_str_digits(original)

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.INTEGER_DIGIT_LIMIT,
        message="JSON integer exceeds MAX_JSON_INTEGER_DIGITS",
    )
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(value,),
    )


def test_json_serialize_rejects_cycles_but_allows_shared_references() -> None:
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    shared: list[JsonValue] = [1]

    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(cyclic, metadata=metadata())

    assert_error(
        caught,
        error_type=SerdeEncodeError,
        code=SerdeErrorCode.CIRCULAR_REFERENCE,
        message="value contains a circular reference",
    )
    assert json_serialize([shared, shared], metadata=metadata()).data == b"[[1],[1]]"


def test_json_serialize_rejects_circular_dict_but_allows_shared_dict() -> None:
    cyclic: dict[str, JsonValue] = {}
    cyclic["self"] = cyclic
    shared: dict[str, JsonValue] = {"value": 1}

    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(cyclic, metadata=metadata())

    assert_error(
        caught,
        error_type=SerdeEncodeError,
        code=SerdeErrorCode.CIRCULAR_REFERENCE,
        message="value contains a circular reference",
    )
    assert json_serialize([shared, shared], metadata=metadata()).data == (
        b'[{"value":1},{"value":1}]'
    )


def test_json_serialize_enforces_configured_nesting_depth_including_zero() -> None:
    assert json_serialize(None, metadata=metadata(), max_nesting_depth=0).data == b"null"
    assert json_serialize([], metadata=metadata(), max_nesting_depth=1).data == b"[]"
    assert json_serialize(
        nested_list(MAX_SUPPORTED_NESTING_DEPTH),
        metadata=metadata(),
        max_nesting_depth=MAX_SUPPORTED_NESTING_DEPTH,
    ).data

    with pytest.raises(PayloadLimitError) as caught:
        json_serialize([], metadata=metadata(), max_nesting_depth=0)

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


@pytest.mark.parametrize("max_nesting_depth", [1, 7, 100])
def test_json_serialize_accepts_nonzero_depth_n_and_rejects_n_plus_one(
    max_nesting_depth: int,
) -> None:
    assert json_serialize(
        nested_list(max_nesting_depth),
        metadata=metadata(),
        max_nesting_depth=max_nesting_depth,
    ).data

    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(
            nested_list(max_nesting_depth + 1),
            metadata=metadata(),
            max_nesting_depth=max_nesting_depth,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


def test_preflight_auxiliary_memory_does_not_scale_with_wide_sibling_count() -> None:
    narrow: list[JsonValue] = [[] for _ in range(10)]
    wide: list[JsonValue] = [[] for _ in range(100_000)]

    tracemalloc.start()
    _preflight_json_value(
        narrow,
        max_nesting_depth=2,
        max_output_size=sys.maxsize - 1,
    )
    _, narrow_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    _preflight_json_value(
        wide,
        max_nesting_depth=2,
        max_output_size=sys.maxsize - 1,
    )
    _, wide_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert wide_peak - narrow_peak < 64 * 1024


def test_json_serialize_tiny_output_budget_stops_shared_dag_preflight_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bluetape.serde._json as serde_json_module

    original_dict_values = serde_json_module._dict_values
    visits = 0

    def counted_dict_values(value: dict[str, JsonValue]) -> Iterator[tuple[object, int]]:
        nonlocal visits
        visits += 1
        return original_dict_values(value)

    monkeypatch.setattr(serde_json_module, "_dict_values", counted_dict_values)
    shared: JsonValue = {"leaf": None}
    unique_container_count = 1
    for _ in range(18):
        shared = {"left": shared, "right": shared}
        unique_container_count += 1

    monkeypatch.setattr(
        serde_json_module.json,
        "JSONEncoder",
        lambda **_options: pytest.fail("encoder was constructed"),
    )
    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(
            shared,
            metadata=metadata(),
            max_output_size=8,
            max_nesting_depth=unique_container_count,
        )

    assert visits == 1
    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.OUTPUT_LIMIT,
        message="serialized output exceeds max_output_size",
    )


def test_json_serialize_charges_large_shared_string_bytes_on_first_dag_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bluetape.serde._json as serde_json_module

    large_string = "😀" * 1024
    original_validation = serde_json_module._validate_unicode_scalar_string
    large_string_validations = 0

    def counted_validation(value: str) -> int:
        nonlocal large_string_validations
        if value == large_string:
            large_string_validations += 1
        return original_validation(value)

    monkeypatch.setattr(
        serde_json_module,
        "_validate_unicode_scalar_string",
        counted_validation,
    )
    shared: JsonValue = large_string
    for _ in range(12):
        shared = [shared, shared]

    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(
            shared,
            metadata=metadata(),
            max_output_size=32,
            max_nesting_depth=12,
        )

    assert large_string_validations == 1
    assert caught.value.code is SerdeErrorCode.OUTPUT_LIMIT
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(shared, large_string),
    )


def test_json_serialize_charges_large_shared_dict_key_on_first_dag_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bluetape.serde._json as serde_json_module

    large_key = "k" * 4096
    original_validation = serde_json_module._validate_unicode_scalar_string
    large_key_validations = 0

    def counted_validation(value: str) -> int:
        nonlocal large_key_validations
        if value == large_key:
            large_key_validations += 1
        return original_validation(value)

    monkeypatch.setattr(
        serde_json_module,
        "_validate_unicode_scalar_string",
        counted_validation,
    )
    shared: JsonValue = {large_key: None}
    for _ in range(12):
        shared = [shared, shared]

    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(
            shared,
            metadata=metadata(),
            max_output_size=32,
            max_nesting_depth=13,
        )

    assert large_key_validations == 1
    assert caught.value.code is SerdeErrorCode.OUTPUT_LIMIT
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(shared, large_key),
        source_keys=frozenset({large_key}),
    )


@pytest.mark.parametrize("value", ["", '"', "\\", "\x00", "é", "😀"])
def test_json_serialize_string_lower_bound_preserves_exact_output_acceptance(
    value: str,
) -> None:
    expected = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()

    assert (
        json_serialize(
            value,
            metadata=metadata(),
            max_output_size=len(expected),
        ).data
        == expected
    )

    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(
            value,
            metadata=metadata(),
            max_output_size=len(expected) - 1,
        )

    assert caught.value.code is SerdeErrorCode.OUTPUT_LIMIT


@pytest.mark.parametrize(
    ("case", "max_nesting_depth", "error_type", "code"),
    [
        ("unsupported", 2, SerdeEncodeError, SerdeErrorCode.UNSUPPORTED_VALUE),
        ("circular", 2, SerdeEncodeError, SerdeErrorCode.CIRCULAR_REFERENCE),
        ("depth", 1, PayloadLimitError, SerdeErrorCode.NESTING_LIMIT),
    ],
)
def test_json_serialize_current_node_validation_precedes_output_visit_guard(
    case: str,
    max_nesting_depth: int,
    error_type: type[SerdeError],
    code: SerdeErrorCode,
) -> None:
    if case == "unsupported":
        value: object = [object()]
    elif case == "circular":
        cyclic: list[JsonValue] = []
        cyclic.append(cyclic)
        value = cyclic
    else:
        value = [[None]]

    with pytest.raises(error_type) as caught:
        json_serialize(
            value,  # type: ignore[arg-type]
            metadata=metadata(),
            max_output_size=1,
            max_nesting_depth=max_nesting_depth,
        )

    assert caught.value.code is code


def test_preflight_revisits_shared_container_when_entered_at_greater_depth() -> None:
    shared: JsonValue = [[None]]

    with pytest.raises(PayloadLimitError) as caught:
        _preflight_json_value(
            [shared, [shared]],
            max_nesting_depth=3,
            max_output_size=sys.maxsize - 1,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


def test_json_serialize_high_chunk_count_uses_bounded_adapter_allocation() -> None:
    value: JsonValue = [0] * 100_000

    tracemalloc.start()
    payload = json_serialize(value, metadata=metadata())
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert payload.data == b"[" + b"0," * 99_999 + b"0]"
    assert peak < len(payload.data) * 4 + 64 * 1024


@pytest.mark.parametrize(
    ("payload_metadata", "error_type"),
    [
        (metadata(format_name="msgpack"), FormatMismatchError),
        (metadata(content_type="text/plain"), ContentTypeMismatchError),
        (metadata(version=2), UnsupportedVersionError),
    ],
)
def test_json_serialize_metadata_errors_do_not_retain_caller_value(
    payload_metadata: PayloadMetadata,
    error_type: type[SerdeError],
) -> None:
    value: JsonValue = {"ENCODE_METADATA_PRIVATE_KEY": "private value"}

    with pytest.raises(error_type) as caught:
        json_serialize(value, metadata=payload_metadata)

    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(value, payload_metadata),
        source_keys=frozenset({"ENCODE_METADATA_PRIVATE_KEY"}),
    )


@pytest.mark.parametrize(
    ("value_factory", "error_type"),
    [
        (lambda: object(), SerdeEncodeError),
        (lambda: math.nan, SerdeEncodeError),
        (lambda: nested_list(2), PayloadLimitError),
    ],
)
def test_json_serialize_preflight_errors_do_not_retain_traversal_state(
    value_factory: object,
    error_type: type[SerdeError],
) -> None:
    value = value_factory()  # type: ignore[operator]

    with pytest.raises(error_type) as caught:
        json_serialize(value, metadata=metadata(), max_nesting_depth=1)  # type: ignore[arg-type]

    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(value,),
    )


def test_json_serialize_circular_error_does_not_retain_traversal_state() -> None:
    value: list[JsonValue] = []
    value.append(value)

    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(value, metadata=metadata())

    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"value", "metadata"}),
        source_values=(value,),
    )


def test_json_serialize_accepts_exact_output_limit_and_stops_at_first_excess_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    class ExactEncoder:
        def __init__(self, **options: object) -> None:
            assert options == {
                "ensure_ascii": False,
                "allow_nan": False,
                "check_circular": True,
                "separators": (",", ":"),
            }

        def iterencode(self, _: object) -> Iterator[str]:
            requested.append("first")
            yield "é"
            requested.append("second")
            yield "x"

    monkeypatch.setattr("bluetape.serde._json.json.JSONEncoder", ExactEncoder)

    assert json_serialize(None, metadata=metadata(), max_output_size=3).data == b"\xc3\xa9x"
    assert requested == ["first", "second"]

    class ExcessEncoder(ExactEncoder):
        def iterencode(self, _: object) -> Iterator[str]:
            requested.append("first")
            yield "é"
            requested.append("second")
            yield "x"
            requested.append("sentinel")
            raise AssertionError("later chunk requested")

    requested.clear()
    monkeypatch.setattr("bluetape.serde._json.json.JSONEncoder", ExcessEncoder)
    source_value: JsonValue = []
    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(source_value, metadata=metadata(), max_output_size=2)

    assert requested == ["first", "second"]
    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.OUTPUT_LIMIT,
        message="serialized output exceeds max_output_size",
    )
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset(
            {
                "value",
                "metadata",
                "output",
                "chunks",
                "chunk",
                "encoded_chunk",
                "encoder",
            }
        ),
        source_values=(source_value,),
    )


@pytest.mark.parametrize(
    ("source_error", "code", "message"),
    [
        (
            TypeError("private marker"),
            SerdeErrorCode.UNSUPPORTED_VALUE,
            "value is not JSON-serializable",
        ),
        (
            ValueError("private marker"),
            SerdeErrorCode.UNSUPPORTED_VALUE,
            "value is not JSON-serializable",
        ),
        (
            RecursionError("private marker"),
            SerdeErrorCode.ENCODE_RECURSION,
            "value nesting exceeds encoder recursion support",
        ),
    ],
)
def test_json_serialize_translates_encoder_failures_without_chaining_or_marker(
    monkeypatch: pytest.MonkeyPatch,
    source_error: Exception,
    code: SerdeErrorCode,
    message: str,
) -> None:
    class FailingEncoder:
        def __init__(self, **_: object) -> None:
            pass

        def iterencode(self, _: object) -> Iterator[str]:
            raise source_error
            yield "unreachable"

    monkeypatch.setattr("bluetape.serde._json.json.JSONEncoder", FailingEncoder)
    source_value: JsonValue = {"ENCODER_FAILURE_PRIVATE_KEY": "private value"}

    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(source_value, metadata=metadata())

    assert_error(caught, error_type=SerdeEncodeError, code=code, message=message)
    assert "private marker" not in repr(caught.value)
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset(
            {
                "value",
                "metadata",
                "output",
                "chunks",
                "chunk",
                "encoded_chunk",
                "encoder",
            }
        ),
        source_values=(source_value,),
        source_keys=frozenset({"ENCODER_FAILURE_PRIVATE_KEY"}),
    )


@pytest.mark.parametrize("fatal_error", [MemoryError(), KeyboardInterrupt(), SystemExit()])
def test_json_serialize_does_not_translate_fatal_encoder_failures(
    monkeypatch: pytest.MonkeyPatch,
    fatal_error: BaseException,
) -> None:
    class FailingEncoder:
        def __init__(self, **_: object) -> None:
            pass

        def iterencode(self, _: object) -> Iterator[str]:
            raise fatal_error
            yield "unreachable"

    monkeypatch.setattr("bluetape.serde._json.json.JSONEncoder", FailingEncoder)

    with pytest.raises(type(fatal_error)):
        json_serialize(None, metadata=metadata())


@pytest.mark.parametrize("trust_profile", list(TrustProfile))
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"null", None),
        (b"false", False),
        (b"42", 42),
        (b"-1.25", -1.25),
        ('"한글 😺"'.encode(), "한글 😺"),
        (b'[1,true,{"key":"value"}]', [1, True, {"key": "value"}]),
    ],
)
def test_json_deserialize_decodes_strict_json_identically_for_both_profiles(
    trust_profile: TrustProfile,
    data: bytes,
    expected: JsonValue,
) -> None:
    policy = metadata(trust_profile=trust_profile)

    assert (
        json_deserialize(
            serialized(data, payload_metadata=policy),
            expected_metadata=policy,
        )
        == expected
    )


@pytest.mark.parametrize("setting", _INTEGER_DIGIT_SETTINGS)
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"9" * 640, 10**640 - 1),
        (b"-" + b"9" * 640, -(10**640 - 1)),
        (b'{"nested":[' + b"9" * 640 + b"]}", {"nested": [10**640 - 1]}),
    ],
)
def test_json_deserialize_accepts_640_digit_integers_independent_of_global_limit(
    setting: int | None,
    data: bytes,
    expected: JsonValue,
) -> None:
    original = sys.get_int_max_str_digits() if setting is not None else None
    try:
        if setting is not None:
            sys.set_int_max_str_digits(setting)
        assert json_deserialize(serialized(data), expected_metadata=metadata()) == expected
    finally:
        if original is not None:
            sys.set_int_max_str_digits(original)


@pytest.mark.parametrize("setting", _INTEGER_DIGIT_SETTINGS)
@pytest.mark.parametrize(
    "data",
    [
        b"9" * 641,
        b"-" + b"9" * 641,
        b'{"nested":[' + b"9" * 641 + b"]}",
    ],
)
def test_json_deserialize_rejects_641_digit_integers_independent_of_global_limit(
    setting: int | None,
    data: bytes,
) -> None:
    original = sys.get_int_max_str_digits() if setting is not None else None
    try:
        if setting is not None:
            sys.set_int_max_str_digits(setting)
        with pytest.raises(PayloadLimitError) as caught:
            json_deserialize(serialized(data), expected_metadata=metadata())
    finally:
        if original is not None:
            sys.set_int_max_str_digits(original)

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.INTEGER_DIGIT_LIMIT,
        message="JSON integer exceeds MAX_JSON_INTEGER_DIGITS",
    )
    assert_decode_traceback_does_not_retain_source(caught.value, raw_source=data)


class HostilePayload:
    def __getattribute__(self, name: str) -> object:
        if name in {"metadata", "data"}:
            raise AssertionError("payload data was accessed")
        return super().__getattribute__(name)


@pytest.mark.parametrize(
    ("payload_value", "expected_value", "message"),
    [
        (object(), metadata(), "payload must be an exact SerializedPayload"),
        (HostilePayload(), metadata(), "payload must be an exact SerializedPayload"),
        (serialized(), object(), "expected_metadata must be an exact PayloadMetadata"),
        (
            serialized(),
            MetadataLookalike(
                format="json",
                version=1,
                content_type="application/json",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            "expected_metadata must be an exact PayloadMetadata",
        ),
    ],
)
def test_json_deserialize_rejects_inexact_runtime_contract_types_before_data_access(
    payload_value: object,
    expected_value: object,
    message: str,
) -> None:
    with pytest.raises(TypeError) as caught:
        json_deserialize(  # type: ignore[arg-type]
            payload_value,
            expected_metadata=expected_value,
        )

    assert type(caught.value) is TypeError
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"max_input_size": True}, TypeError, "max_input_size must be an exact int"),
        ({"max_input_size": 1.0}, TypeError, "max_input_size must be an exact int"),
        (
            {"max_input_size": IntegerLookalike(1)},
            TypeError,
            "max_input_size must be an exact int",
        ),
        (
            {"max_input_size": -1},
            ValueError,
            "max_input_size must be between 0 and sys.maxsize - 1",
        ),
        (
            {"max_input_size": sys.maxsize},
            ValueError,
            "max_input_size must be between 0 and sys.maxsize - 1",
        ),
        (
            {"max_nesting_depth": True},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"max_nesting_depth": 1.0},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"max_nesting_depth": IntegerLookalike(1)},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            {"max_nesting_depth": -1},
            ValueError,
            "max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH",
        ),
        (
            {"max_nesting_depth": 257},
            ValueError,
            "max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH",
        ),
    ],
)
def test_json_deserialize_validates_configuration_before_payload_data_access(
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    accessed = False

    def hostile_data(_: SerializedPayload) -> bytes:
        nonlocal accessed
        accessed = True
        raise AssertionError("payload data was accessed")

    monkeypatch.setattr("bluetape.serde._json._payload_data", hostile_data)

    with pytest.raises(error_type) as caught:
        json_deserialize(
            serialized(),
            expected_metadata=metadata(),
            **changes,  # type: ignore[arg-type]
        )

    assert type(caught.value) is error_type
    assert str(caught.value) == message
    assert accessed is False


@pytest.mark.parametrize(
    ("payload_value", "expected_value", "changes", "error_type", "message"),
    [
        (
            {"DECODE_CONFIGURATION_PRIVATE_KEY": "private payload"},
            metadata(),
            {},
            TypeError,
            "payload must be an exact SerializedPayload",
        ),
        (
            serialized(b'{"DECODE_CONFIGURATION_PRIVATE_KEY":"private value"}'),
            {"DECODE_CONFIGURATION_PRIVATE_KEY": "private metadata"},
            {},
            TypeError,
            "expected_metadata must be an exact PayloadMetadata",
        ),
        (
            serialized(b'{"DECODE_CONFIGURATION_PRIVATE_KEY":"private value"}'),
            metadata(),
            {"max_input_size": IntegerLookalike(1)},
            TypeError,
            "max_input_size must be an exact int",
        ),
        (
            serialized(b'{"DECODE_CONFIGURATION_PRIVATE_KEY":"private value"}'),
            metadata(),
            {"max_input_size": -1},
            ValueError,
            "max_input_size must be between 0 and sys.maxsize - 1",
        ),
        (
            serialized(b'{"DECODE_CONFIGURATION_PRIVATE_KEY":"private value"}'),
            metadata(),
            {"max_nesting_depth": IntegerLookalike(1)},
            TypeError,
            "max_nesting_depth must be an exact int",
        ),
        (
            serialized(b'{"DECODE_CONFIGURATION_PRIVATE_KEY":"private value"}'),
            metadata(),
            {"max_nesting_depth": 257},
            ValueError,
            "max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH",
        ),
    ],
)
def test_json_deserialize_configuration_errors_do_not_retain_caller_sources(
    payload_value: object,
    expected_value: object,
    changes: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type) as caught:
        json_deserialize(  # type: ignore[arg-type]
            payload_value,
            expected_metadata=expected_value,
            **changes,
        )

    assert type(caught.value) is error_type
    assert str(caught.value) == message
    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset(
            {"payload", "expected_metadata", "max_input_size", "max_nesting_depth"}
        ),
        source_values=(payload_value, expected_value, *changes.values()),
        source_keys=frozenset({"DECODE_CONFIGURATION_PRIVATE_KEY"}),
        raw_source=b'{"DECODE_CONFIGURATION_PRIVATE_KEY":"private value"}',
    )


@pytest.mark.parametrize("fatal_error", [MemoryError(), KeyboardInterrupt(), SystemExit()])
def test_json_deserialize_configuration_fatal_errors_remain_native(
    monkeypatch: pytest.MonkeyPatch,
    fatal_error: BaseException,
) -> None:
    def fail_validation(**_arguments: object) -> None:
        raise fatal_error

    monkeypatch.setattr(
        "bluetape.serde._json._validate_deserialize_configuration",
        fail_validation,
    )

    with pytest.raises(type(fatal_error)) as caught:
        json_deserialize(serialized(), expected_metadata=metadata())

    assert caught.value is fatal_error


def test_json_deserialize_accepts_largest_supported_input_and_depth_configuration() -> None:
    assert (
        json_deserialize(
            serialized(),
            expected_metadata=metadata(),
            max_input_size=sys.maxsize - 1,
            max_nesting_depth=MAX_SUPPORTED_NESTING_DEPTH,
        )
        is None
    )


@pytest.mark.parametrize(
    ("expected", "error_type", "code", "message"),
    [
        (
            metadata(format_name="msgpack", version=999, content_type="text/plain"),
            FormatMismatchError,
            SerdeErrorCode.FORMAT_MISMATCH,
            "payload format does not match expected format",
        ),
        (
            metadata(version=999, content_type="text/plain"),
            ContentTypeMismatchError,
            SerdeErrorCode.CONTENT_TYPE_MISMATCH,
            "payload content type does not match expected content type",
        ),
        (
            metadata(version=999),
            UnsupportedVersionError,
            SerdeErrorCode.UNSUPPORTED_VERSION,
            "payload version is unsupported",
        ),
    ],
)
def test_json_deserialize_validates_supported_expected_metadata_before_payload_data(
    monkeypatch: pytest.MonkeyPatch,
    expected: PayloadMetadata,
    error_type: type[Exception],
    code: SerdeErrorCode,
    message: str,
) -> None:
    monkeypatch.setattr(
        "bluetape.serde._json._payload_data",
        lambda _: pytest.fail("payload data was accessed"),
    )

    with pytest.raises(error_type) as caught:
        json_deserialize(serialized(), expected_metadata=expected)

    assert_error(caught, error_type=error_type, code=code, message=message)


def test_json_deserialize_rejects_matching_unsupported_versions() -> None:
    unsupported = metadata(version=999)

    with pytest.raises(UnsupportedVersionError) as caught:
        json_deserialize(
            serialized(payload_metadata=unsupported),
            expected_metadata=unsupported,
        )

    assert_error(
        caught,
        error_type=UnsupportedVersionError,
        code=SerdeErrorCode.UNSUPPORTED_VERSION,
        message="payload version is unsupported",
    )


@pytest.mark.parametrize(
    ("actual", "error_type", "code", "message"),
    [
        (
            metadata(format_name="msgpack", version=999, content_type="text/plain"),
            FormatMismatchError,
            SerdeErrorCode.FORMAT_MISMATCH,
            "payload format does not match expected format",
        ),
        (
            metadata(version=999, content_type="text/plain"),
            ContentTypeMismatchError,
            SerdeErrorCode.CONTENT_TYPE_MISMATCH,
            "payload content type does not match expected content type",
        ),
        (
            metadata(version=999, trust_profile=TrustProfile.TRUSTED_INTERNAL),
            UnsupportedVersionError,
            SerdeErrorCode.UNSUPPORTED_VERSION,
            "payload version is unsupported",
        ),
        (
            metadata(trust_profile=TrustProfile.TRUSTED_INTERNAL),
            TrustProfileMismatchError,
            SerdeErrorCode.TRUST_PROFILE_MISMATCH,
            "payload trust profile does not match caller policy",
        ),
    ],
)
def test_json_deserialize_compares_actual_metadata_in_deterministic_order(
    monkeypatch: pytest.MonkeyPatch,
    actual: PayloadMetadata,
    error_type: type[Exception],
    code: SerdeErrorCode,
    message: str,
) -> None:
    monkeypatch.setattr(
        "bluetape.serde._json._payload_data",
        lambda _: pytest.fail("payload data was accessed"),
    )

    with pytest.raises(error_type) as caught:
        json_deserialize(
            serialized(payload_metadata=actual),
            expected_metadata=metadata(),
        )

    assert_error(caught, error_type=error_type, code=code, message=message)


@pytest.mark.parametrize(
    ("actual", "expected", "error_type"),
    [
        (metadata(format_name="msgpack"), metadata(), FormatMismatchError),
        (metadata(content_type="text/plain"), metadata(), ContentTypeMismatchError),
        (metadata(version=2), metadata(), UnsupportedVersionError),
        (
            metadata(trust_profile=TrustProfile.TRUSTED_INTERNAL),
            metadata(),
            TrustProfileMismatchError,
        ),
        (metadata(), metadata(format_name="msgpack"), FormatMismatchError),
        (metadata(), metadata(content_type="text/plain"), ContentTypeMismatchError),
        (metadata(), metadata(version=2), UnsupportedVersionError),
    ],
)
def test_json_deserialize_metadata_errors_do_not_retain_caller_payload(
    actual: PayloadMetadata,
    expected: PayloadMetadata,
    error_type: type[SerdeError],
) -> None:
    payload = serialized(
        b'{"DECODE_METADATA_PRIVATE_KEY":"private value"}',
        payload_metadata=actual,
    )

    with pytest.raises(error_type) as caught:
        json_deserialize(payload, expected_metadata=expected)

    assert_traceback_does_not_retain_source(
        caught.value,
        forbidden_local_names=frozenset({"payload", "expected_metadata", "data", "text"}),
        source_values=(payload, actual, expected),
        source_keys=frozenset({"DECODE_METADATA_PRIVATE_KEY"}),
    )


def test_json_deserialize_enforces_exact_byte_input_limit_before_decode_or_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "bluetape.serde._json._decode_utf8",
        lambda _: calls.append("decode"),
    )
    monkeypatch.setattr(
        "bluetape.serde._json._preflight_json_text",
        lambda *_args, **_kwargs: calls.append("scan"),
    )
    monkeypatch.setattr(
        "bluetape.serde._json.json.loads",
        lambda *_args, **_kwargs: calls.append("parse"),
    )

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(b"null"),
            expected_metadata=metadata(),
            max_input_size=3,
        )

    assert calls == []
    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.INPUT_LIMIT,
        message="serialized payload exceeds max_input_size",
    )


def test_json_deserialize_input_limit_traceback_does_not_retain_raw_source() -> None:
    raw_source = b'"INPUT_LIMIT_PRIVATE_RAW_MARKER"'

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(raw_source),
            expected_metadata=metadata(),
            max_input_size=len(raw_source) - 1,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.INPUT_LIMIT,
        message="serialized payload exceeds max_input_size",
    )
    assert "INPUT_LIMIT_PRIVATE_RAW_MARKER" not in repr(caught.value)
    assert_decode_traceback_does_not_retain_source(
        caught.value,
        raw_source=raw_source,
    )


def test_json_deserialize_accepts_input_at_exact_byte_limit() -> None:
    assert (
        json_deserialize(
            serialized(b"null"),
            expected_metadata=metadata(),
            max_input_size=4,
        )
        is None
    )


def test_json_deserialize_zero_input_limit_routes_empty_to_parser_and_rejects_nonempty() -> None:
    with pytest.raises(MalformedPayloadError) as empty_caught:
        json_deserialize(
            serialized(b""),
            expected_metadata=metadata(),
            max_input_size=0,
        )
    with pytest.raises(PayloadLimitError) as nonempty_caught:
        json_deserialize(
            serialized(b"0"),
            expected_metadata=metadata(),
            max_input_size=0,
        )

    assert_error(
        empty_caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.INVALID_JSON,
        message="payload is not valid JSON",
    )
    assert_error(
        nonempty_caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.INPUT_LIMIT,
        message="serialized payload exceeds max_input_size",
    )


def test_json_deserialize_rejects_invalid_utf8_without_source_retention() -> None:
    marker = b"private-marker-\xff"

    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(serialized(marker), expected_metadata=metadata())

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.INVALID_UTF8,
        message="payload is not valid UTF-8",
    )
    assert marker.decode("latin-1") not in repr(caught.value)
    assert not hasattr(caught.value, "object")
    assert_decode_traceback_does_not_retain_source(caught.value)


@pytest.mark.parametrize(
    "data",
    [
        b'"\\ud800"',
        b'"\\udc00"',
        b'{"key":"\\ud800"}',
        b'{"\\udc00":"value"}',
    ],
)
def test_json_deserialize_rejects_unpaired_surrogates_without_source_retention(
    data: bytes,
) -> None:
    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(serialized(data), expected_metadata=metadata())

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.INVALID_JSON,
        message="payload is not valid JSON",
    )
    assert_decode_traceback_does_not_retain_source(
        caught.value,
        raw_source=data,
        text_source=data.decode(),
    )


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b'"\\ud83d\\ude00"', "😀"),
        (b'{"\\ud834\\udd1e":"music"}', {"𝄞": "music"}),
        ('"😀"'.encode(), "😀"),
    ],
)
def test_json_deserialize_accepts_surrogate_pairs_and_non_bmp_scalars(
    data: bytes,
    expected: JsonValue,
) -> None:
    decoded = json_deserialize(serialized(data), expected_metadata=metadata())

    assert decoded == expected
    assert (
        json_deserialize(
            json_serialize(decoded, metadata=metadata()),
            expected_metadata=metadata(),
        )
        == expected
    )


def test_json_deserialize_rejects_keys_that_duplicate_after_surrogate_normalization() -> None:
    data = b'{"\\ud83d\\ude00":1,"\xf0\x9f\x98\x80":2}'

    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(serialized(data), expected_metadata=metadata())

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.DUPLICATE_KEY,
        message="JSON object contains a duplicate key",
    )
    assert_decode_traceback_does_not_retain_source(caught.value, raw_source=data)


def nested_json_text(depth: int) -> bytes:
    return ("[" * depth + "null" + "]" * depth).encode()


def test_json_deserialize_depth_zero_accepts_scalars_and_rejects_containers() -> None:
    assert (
        json_deserialize(
            serialized(b'"[not structural]"'),
            expected_metadata=metadata(),
            max_nesting_depth=0,
        )
        == "[not structural]"
    )

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(b"[]"),
            expected_metadata=metadata(),
            max_nesting_depth=0,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


def test_json_deserialize_nesting_limit_traceback_does_not_retain_source() -> None:
    raw_source = b'["NESTING_LIMIT_PRIVATE_TEXT_MARKER",[[]]]'
    text_source = raw_source.decode("utf-8")

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(raw_source),
            expected_metadata=metadata(),
            max_nesting_depth=1,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )
    assert "NESTING_LIMIT_PRIVATE_TEXT_MARKER" not in repr(caught.value)
    assert_decode_traceback_does_not_retain_source(
        caught.value,
        raw_source=raw_source,
        text_source=text_source,
    )


@pytest.mark.parametrize("depth", [1, 7, 100])
def test_json_deserialize_accepts_exact_depth_and_rejects_one_over(depth: int) -> None:
    assert (
        json_deserialize(
            serialized(nested_json_text(depth)),
            expected_metadata=metadata(),
            max_nesting_depth=depth,
        )
        is not None
    )

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(nested_json_text(depth + 1)),
            expected_metadata=metadata(),
            max_nesting_depth=depth,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


def test_json_deserialize_accepts_depth_256_and_rejects_configuration_257() -> None:
    assert (
        json_deserialize(
            serialized(nested_json_text(MAX_SUPPORTED_NESTING_DEPTH)),
            expected_metadata=metadata(),
            max_nesting_depth=MAX_SUPPORTED_NESTING_DEPTH,
        )
        is not None
    )

    with pytest.raises(ValueError, match="MAX_SUPPORTED_NESTING_DEPTH"):
        json_deserialize(
            serialized(b"null"),
            expected_metadata=metadata(),
            max_nesting_depth=MAX_SUPPORTED_NESTING_DEPTH + 1,
        )


@pytest.mark.parametrize(
    "data",
    [
        b'"[{}]"',
        b'["escaped quote: \\" [[[]]]"]',
        b'["odd backslashes: \\\\\\" [[[]]]"]',
        b'["even backslashes: \\\\\\\\", [[null]]]',
        b'{"text":"quoted [ { ] }", "value":[{"nested":true}]}',
    ],
)
def test_json_deserialize_depth_scanner_handles_strings_quotes_and_backslash_runs(
    data: bytes,
) -> None:
    assert (
        json_deserialize(
            serialized(data),
            expected_metadata=metadata(),
            max_nesting_depth=3,
        )
        is not None
    )


def test_json_deserialize_large_valid_escaped_string_at_exact_input_limit() -> None:
    assert len(LARGE_VALID_JSON_PAYLOAD) == LARGE_VALID_JSON_INPUT_LIMIT
    assert b"{[]}" in LARGE_VALID_JSON_PAYLOAD
    assert b"\\" * 3 + b'" quote' in LARGE_VALID_JSON_PAYLOAD
    assert b"\\" * 4 + b'","padding"' in LARGE_VALID_JSON_PAYLOAD

    decoded = json_deserialize(
        serialized(LARGE_VALID_JSON_PAYLOAD),
        expected_metadata=metadata(),
        max_input_size=LARGE_VALID_JSON_INPUT_LIMIT,
        max_nesting_depth=1,
    )

    assert decoded == {
        "odd": 'odd \\" quote {[]}',
        "even": "even \\\\",
        "padding": "x" * _LARGE_VALID_JSON_PADDING_SIZE,
    }


@pytest.mark.parametrize("closers", [b"]", b"}", b"]}"])
def test_json_deserialize_unmatched_leading_closers_cannot_hide_later_over_depth(
    monkeypatch: pytest.MonkeyPatch,
    closers: bytes,
) -> None:
    monkeypatch.setattr(
        "bluetape.serde._json.json.loads",
        lambda *_args, **_kwargs: pytest.fail("parser was reached"),
    )

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(closers + b"[[null]]"),
            expected_metadata=metadata(),
            max_nesting_depth=1,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


def test_json_deserialize_near_input_limit_adversarial_text_stops_in_scanner() -> None:
    leading_closers = b"]" * 250_000
    data = leading_closers + b"[[null]]"

    with pytest.raises(PayloadLimitError) as caught:
        json_deserialize(
            serialized(data),
            expected_metadata=metadata(),
            max_input_size=len(data),
            max_nesting_depth=1,
        )

    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.NESTING_LIMIT,
        message="JSON nesting exceeds max_nesting_depth",
    )


def test_decode_depth_scanner_linear_scan_uses_constant_auxiliary_state() -> None:
    small = "]" * 10 + '"quoted [brackets]"' + "[null]"
    large = "]" * 1_000_000 + '"quoted [brackets]"' + "[null]"

    tracemalloc.start()
    _preflight_json_text(small, max_nesting_depth=1)
    _, small_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    _preflight_json_text(large, max_nesting_depth=1)
    _, large_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert large_peak - small_peak < 16 * 1024

    source = inspect.getsource(_preflight_json_text)
    tree = ast.parse(source)
    assert "re." not in source
    assert source.count("_preflight_json_text(") == 1
    assert not any(
        isinstance(
            node,
            (
                ast.List,
                ast.Set,
                ast.Dict,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
                ast.Slice,
            ),
        )
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize("trust_profile", list(TrustProfile))
@pytest.mark.parametrize(
    "data",
    [
        b'{"key":1,"key":2}',
        b'{"outer":{"key":1,"key":2}}',
    ],
)
def test_json_deserialize_rejects_root_and_nested_duplicate_keys(
    trust_profile: TrustProfile,
    data: bytes,
) -> None:
    policy = metadata(trust_profile=trust_profile)

    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(
            serialized(data, payload_metadata=policy),
            expected_metadata=policy,
        )

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.DUPLICATE_KEY,
        message="JSON object contains a duplicate key",
    )


@pytest.mark.parametrize("trust_profile", list(TrustProfile))
@pytest.mark.parametrize(
    "data",
    [
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e309",
        b"-1e309",
        b"[1e309]",
        b'{"value":-1e309}',
    ],
)
def test_json_deserialize_rejects_non_finite_constants_and_float_overflow(
    trust_profile: TrustProfile,
    data: bytes,
) -> None:
    policy = metadata(trust_profile=trust_profile)

    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(
            serialized(data, payload_metadata=policy),
            expected_metadata=policy,
        )

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.DECODE_NON_FINITE_NUMBER,
        message="JSON payload contains a non-finite number",
    )


@pytest.mark.parametrize("data", [b"", b"[", b'{"key":}', b"true false"])
def test_json_deserialize_translates_malformed_syntax_without_source_retention(
    data: bytes,
) -> None:
    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(serialized(data), expected_metadata=metadata())

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.INVALID_JSON,
        message="payload is not valid JSON",
    )
    assert not hasattr(caught.value, "doc")
    if data:
        assert data.decode("utf-8", errors="replace") not in repr(caught.value)
    assert_decode_traceback_does_not_retain_source(caught.value)


@pytest.mark.parametrize("source_error", [ValueError("private marker"), RecursionError()])
def test_json_deserialize_translates_parser_value_and_recursion_errors_narrowly(
    monkeypatch: pytest.MonkeyPatch,
    source_error: Exception,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> JsonValue:
        raise source_error

    monkeypatch.setattr("bluetape.serde._json.json.loads", fail)

    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(serialized(), expected_metadata=metadata())

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.INVALID_JSON,
        message="payload is not valid JSON",
    )
    assert "private marker" not in repr(caught.value)


def test_json_deserialize_does_not_retain_json_decode_error_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = json.JSONDecodeError("private marker", "private document marker", 2)

    def fail(*_args: object, **_kwargs: object) -> JsonValue:
        raise source

    monkeypatch.setattr("bluetape.serde._json.json.loads", fail)

    with pytest.raises(MalformedPayloadError) as caught:
        json_deserialize(serialized(), expected_metadata=metadata())

    assert_error(
        caught,
        error_type=MalformedPayloadError,
        code=SerdeErrorCode.INVALID_JSON,
        message="payload is not valid JSON",
    )
    assert "private document marker" not in repr(caught.value)
    assert not hasattr(caught.value, "doc")
    assert_decode_traceback_does_not_retain_source(caught.value)


@pytest.mark.parametrize("fatal_error", [MemoryError(), KeyboardInterrupt(), SystemExit()])
def test_json_deserialize_does_not_translate_fatal_parser_failures(
    monkeypatch: pytest.MonkeyPatch,
    fatal_error: BaseException,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> JsonValue:
        raise fatal_error

    monkeypatch.setattr("bluetape.serde._json.json.loads", fail)

    with pytest.raises(type(fatal_error)):
        json_deserialize(serialized(), expected_metadata=metadata())
