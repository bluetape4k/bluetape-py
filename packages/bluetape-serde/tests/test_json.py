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
    MAX_SUPPORTED_NESTING_DEPTH,
    ContentTypeMismatchError,
    FormatMismatchError,
    InvalidMetadataError,
    JsonValue,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SerdeEncodeError,
    SerdeError,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfile,
    TrustProfileMismatchError,
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
    "ContentTypeMismatchError",
    "FormatMismatchError",
    "InvalidMetadataError",
    "JsonValue",
    "MalformedPayloadError",
    "PayloadLimitError",
    "PayloadMetadata",
    "SerializedPayload",
    "SerdeError",
    "SerdeErrorCode",
    "SerdeEncodeError",
    "TrustProfile",
    "TrustProfileMismatchError",
    "UnsupportedVersionError",
    "json_deserialize",
    "json_serialize",
]
DIRECT_EXPORTS = [
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_OUTPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    MAX_SUPPORTED_NESTING_DEPTH,
    ContentTypeMismatchError,
    FormatMismatchError,
    InvalidMetadataError,
    JsonValue,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SerializedPayload,
    SerdeError,
    SerdeErrorCode,
    SerdeEncodeError,
    TrustProfile,
    TrustProfileMismatchError,
    UnsupportedVersionError,
    json_deserialize,
    json_serialize,
]


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


def assert_decode_traceback_does_not_retain_source(error: Exception) -> None:
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code.co_name == "json_deserialize":
            assert "payload" not in traceback.tb_frame.f_locals
            assert "data" not in traceback.tb_frame.f_locals
            assert "text" not in traceback.tb_frame.f_locals
        traceback = traceback.tb_next


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


def test_preflight_bookkeeping_peak_does_not_scale_with_wide_sibling_count() -> None:
    narrow = [None] * 10
    wide = [None] * 100_000

    tracemalloc.start()
    _preflight_json_value(narrow, max_nesting_depth=1)
    _, narrow_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    _preflight_json_value(wide, max_nesting_depth=1)
    _, wide_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert wide_peak - narrow_peak < 64 * 1024


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
    with pytest.raises(PayloadLimitError) as caught:
        json_serialize(None, metadata=metadata(), max_output_size=2)

    assert requested == ["first", "second"]
    assert_error(
        caught,
        error_type=PayloadLimitError,
        code=SerdeErrorCode.OUTPUT_LIMIT,
        message="serialized output exceeds max_output_size",
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

    with pytest.raises(SerdeEncodeError) as caught:
        json_serialize(None, metadata=metadata())

    assert_error(caught, error_type=SerdeEncodeError, code=code, message=message)
    assert "private marker" not in repr(caught.value)


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


def test_decode_depth_scanner_uses_constant_auxiliary_state() -> None:
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
