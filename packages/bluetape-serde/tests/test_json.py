import inspect
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
    json_serialize,
)
from bluetape.serde._json import _preflight_json_value

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


def nested_list(depth: int) -> JsonValue:
    value: JsonValue = None
    for _ in range(depth):
        value = [value]
    return value


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


class HostileList(list[object]):
    def __iter__(self) -> Iterator[object]:
        raise AssertionError("hostile value was traversed")


@pytest.mark.parametrize(
    "arguments",
    [
        {"metadata": object()},
        {
            "metadata": MetadataLookalike(
                format="json",
                version=1,
                content_type="application/json",
                trust_profile=TrustProfile.UNTRUSTED,
            )
        },
        {"metadata": metadata(), "max_output_size": True},
        {"metadata": metadata(), "max_output_size": 1.0},
        {"metadata": metadata(), "max_output_size": IntegerLookalike(1)},
        {"metadata": metadata(), "max_output_size": -1},
        {"metadata": metadata(), "max_output_size": sys.maxsize},
        {"metadata": metadata(), "max_nesting_depth": True},
        {"metadata": metadata(), "max_nesting_depth": 1.0},
        {"metadata": metadata(), "max_nesting_depth": IntegerLookalike(1)},
        {"metadata": metadata(), "max_nesting_depth": -1},
        {"metadata": metadata(), "max_nesting_depth": 257},
    ],
)
def test_json_serialize_validates_exact_metadata_and_configuration_before_value_or_encoder(
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, object],
) -> None:
    constructed = False

    class EncoderSpy:
        def __init__(self, **_: object) -> None:
            nonlocal constructed
            constructed = True

    monkeypatch.setattr("bluetape.serde._json.json.JSONEncoder", EncoderSpy)

    with pytest.raises((TypeError, ValueError)):
        json_serialize(HostileList(), **arguments)  # type: ignore[arg-type]

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
        HostileList(),
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
