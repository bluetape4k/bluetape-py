from dataclasses import FrozenInstanceError

import pytest
from bluetape.serde import (
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    DEFAULT_MAX_OUTPUT_SIZE,
    MAX_JSON_INTEGER_DIGITS,
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

EXPECTED_EXPORTS = [
    "DEFAULT_MAX_INPUT_SIZE",
    "DEFAULT_MAX_OUTPUT_SIZE",
    "DEFAULT_MAX_NESTING_DEPTH",
    "MAX_SUPPORTED_NESTING_DEPTH",
    "MAX_JSON_INTEGER_DIGITS",
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
EXPECTED_EXPORT_VALUES = [
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_OUTPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    MAX_SUPPORTED_NESTING_DEPTH,
    MAX_JSON_INTEGER_DIGITS,
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

ERROR_CASES = [
    (SerdeErrorCode.INVALID_METADATA, "invalid payload metadata"),
    (
        SerdeErrorCode.FORMAT_MISMATCH,
        "payload format does not match expected format",
    ),
    (
        SerdeErrorCode.CONTENT_TYPE_MISMATCH,
        "payload content type does not match expected content type",
    ),
    (SerdeErrorCode.UNSUPPORTED_VERSION, "payload version is unsupported"),
    (
        SerdeErrorCode.TRUST_PROFILE_MISMATCH,
        "payload trust profile does not match caller policy",
    ),
    (SerdeErrorCode.INPUT_LIMIT, "serialized payload exceeds max_input_size"),
    (SerdeErrorCode.OUTPUT_LIMIT, "serialized output exceeds max_output_size"),
    (SerdeErrorCode.NESTING_LIMIT, "JSON nesting exceeds max_nesting_depth"),
    (
        SerdeErrorCode.INTEGER_DIGIT_LIMIT,
        "JSON integer exceeds MAX_JSON_INTEGER_DIGITS",
    ),
    (SerdeErrorCode.INVALID_UTF8, "payload is not valid UTF-8"),
    (SerdeErrorCode.DUPLICATE_KEY, "JSON object contains a duplicate key"),
    (
        SerdeErrorCode.DECODE_NON_FINITE_NUMBER,
        "JSON payload contains a non-finite number",
    ),
    (SerdeErrorCode.INVALID_JSON, "payload is not valid JSON"),
    (SerdeErrorCode.UNSUPPORTED_VALUE, "value is not JSON-serializable"),
    (SerdeErrorCode.CIRCULAR_REFERENCE, "value contains a circular reference"),
    (
        SerdeErrorCode.ENCODE_NON_FINITE_NUMBER,
        "value contains a non-finite number",
    ),
    (
        SerdeErrorCode.ENCODE_RECURSION,
        "value nesting exceeds encoder recursion support",
    ),
]


class StringLookalike(str):
    pass


class IntegerLookalike(int):
    pass


class BytesLookalike(bytes):
    pass


class PayloadMetadataLookalike(PayloadMetadata):
    pass


def valid_metadata(**changes: object) -> PayloadMetadata:
    values: dict[str, object] = {
        "format": "json",
        "version": 1,
        "content_type": "application/json",
        "trust_profile": TrustProfile.UNTRUSTED,
    }
    values.update(changes)
    return PayloadMetadata(**values)  # type: ignore[arg-type]


def test_public_contract_exports_are_staged_in_deterministic_order() -> None:
    import bluetape.serde as serde

    assert serde.__all__ == EXPECTED_EXPORTS
    assert all(
        getattr(serde, name) is exported
        for name, exported in zip(EXPECTED_EXPORTS, EXPECTED_EXPORT_VALUES, strict=True)
    )


def test_contract_enums_have_exact_public_values() -> None:
    assert [(member.name, member.value) for member in TrustProfile] == [
        ("UNTRUSTED", "untrusted"),
        ("TRUSTED_INTERNAL", "trusted_internal"),
    ]
    assert [member.value for member in SerdeErrorCode] == [
        "invalid_metadata",
        "format_mismatch",
        "content_type_mismatch",
        "unsupported_version",
        "trust_profile_mismatch",
        "input_limit",
        "output_limit",
        "nesting_limit",
        "integer_digit_limit",
        "invalid_utf8",
        "duplicate_key",
        "decode_non_finite_number",
        "invalid_json",
        "unsupported_value",
        "circular_reference",
        "encode_non_finite_number",
        "encode_recursion",
    ]


def test_payload_metadata_is_keyword_only_frozen_and_slotted() -> None:
    metadata = valid_metadata()

    assert metadata.format == "json"
    assert metadata.version == 1
    assert metadata.content_type == "application/json"
    assert metadata.trust_profile is TrustProfile.UNTRUSTED
    assert not hasattr(metadata, "__dict__")
    with pytest.raises(FrozenInstanceError):
        metadata.version = 2  # type: ignore[misc]
    with pytest.raises(TypeError):
        PayloadMetadata("json", 1, None, TrustProfile.UNTRUSTED)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", b"json"),
        ("version", True),
        ("version", 1.0),
        ("content_type", b"application/json"),
        ("trust_profile", "untrusted"),
    ],
)
def test_payload_metadata_rejects_inexact_field_types(field: str, value: object) -> None:
    with pytest.raises(TypeError):
        valid_metadata(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", StringLookalike("json")),
        ("version", IntegerLookalike(1)),
        ("content_type", StringLookalike("application/json")),
    ],
)
def test_payload_metadata_rejects_runtime_subclass_lookalikes(
    field: str,
    value: object,
) -> None:
    with pytest.raises(TypeError):
        valid_metadata(**{field: value})


@pytest.mark.parametrize(
    "format_name",
    [
        "a",
        "a" * 64,
        "json-v1_2.3/strict",
    ],
)
def test_payload_metadata_accepts_valid_format_boundaries(format_name: str) -> None:
    assert valid_metadata(format=format_name).format == format_name


@pytest.mark.parametrize(
    "format_name",
    [
        "",
        "a" * 65,
        "JSON",
        "json v1",
        "json+v1",
        "json:v1",
        "jöson",
        "json\n",
    ],
)
def test_payload_metadata_rejects_invalid_format_values(format_name: str) -> None:
    with pytest.raises(InvalidMetadataError, match=r"^invalid payload metadata$"):
        valid_metadata(format=format_name)


@pytest.mark.parametrize("version", [0, -1])
def test_payload_metadata_rejects_non_positive_versions(version: int) -> None:
    with pytest.raises(InvalidMetadataError, match=r"^invalid payload metadata$"):
        valid_metadata(version=version)


def test_payload_metadata_accepts_none_content_type() -> None:
    assert valid_metadata(content_type=None).content_type is None


def test_serialized_payload_is_keyword_only_frozen_slotted_and_preserves_empty_bytes() -> None:
    metadata = valid_metadata()
    empty = b""
    payload = SerializedPayload(metadata=metadata, data=empty)

    assert payload.metadata is metadata
    assert payload.data == b""
    assert payload.data is empty
    assert not hasattr(payload, "__dict__")
    with pytest.raises(FrozenInstanceError):
        payload.data = b"changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        SerializedPayload(metadata, b"")  # type: ignore[misc]


def test_serialized_payload_preserves_non_empty_bytes_identity() -> None:
    data = bytes(bytearray(b"payload"))

    payload = SerializedPayload(metadata=valid_metadata(), data=data)

    assert payload.data == b"payload"
    assert payload.data is data


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("metadata", object()),
        ("data", bytearray(b"data")),
        ("data", memoryview(b"data")),
        ("data", "data"),
    ],
)
def test_serialized_payload_rejects_inexact_field_types(field: str, value: object) -> None:
    values = {"metadata": valid_metadata(), "data": b"data"}
    values[field] = value

    with pytest.raises(TypeError):
        SerializedPayload(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "metadata",
            PayloadMetadataLookalike(
                format="json",
                version=1,
                content_type="application/json",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
        ),
        ("data", BytesLookalike(b"payload")),
    ],
)
def test_serialized_payload_rejects_runtime_subclass_lookalikes(
    field: str,
    value: object,
) -> None:
    values = {"metadata": valid_metadata(), "data": b"data"}
    values[field] = value

    with pytest.raises(TypeError):
        SerializedPayload(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(("code", "message"), ERROR_CASES)
def test_serde_error_has_fixed_message_and_immutable_code(
    code: SerdeErrorCode,
    message: str,
) -> None:
    error = SerdeError(code=code)

    assert isinstance(error, ValueError)
    assert error.code is code
    assert str(error) == message
    assert error.args == (message,)
    assert error.__cause__ is None
    assert error.__context__ is None
    with pytest.raises(AttributeError):
        error.code = SerdeErrorCode.INVALID_JSON  # type: ignore[misc]


def test_serde_error_requires_keyword_only_exact_code_type() -> None:
    with pytest.raises(TypeError):
        SerdeError(SerdeErrorCode.INVALID_JSON)  # type: ignore[misc]
    with pytest.raises(TypeError):
        SerdeError(code="invalid_json")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SerdeError(code=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SerdeError(code=SerdeErrorCode.INVALID_JSON, message="custom")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("error_type", "code", "message"),
    [
        (InvalidMetadataError, SerdeErrorCode.INVALID_METADATA, "invalid payload metadata"),
        (
            FormatMismatchError,
            SerdeErrorCode.FORMAT_MISMATCH,
            "payload format does not match expected format",
        ),
        (
            ContentTypeMismatchError,
            SerdeErrorCode.CONTENT_TYPE_MISMATCH,
            "payload content type does not match expected content type",
        ),
        (
            UnsupportedVersionError,
            SerdeErrorCode.UNSUPPORTED_VERSION,
            "payload version is unsupported",
        ),
        (
            TrustProfileMismatchError,
            SerdeErrorCode.TRUST_PROFILE_MISMATCH,
            "payload trust profile does not match caller policy",
        ),
    ],
)
def test_fixed_errors_have_exact_code_and_message(
    error_type: type[SerdeError],
    code: SerdeErrorCode,
    message: str,
) -> None:
    error = error_type()

    assert error.code is code
    assert str(error) == message
    assert error.args == (message,)
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    "error_type",
    [
        InvalidMetadataError,
        FormatMismatchError,
        ContentTypeMismatchError,
        UnsupportedVersionError,
        TrustProfileMismatchError,
    ],
)
def test_fixed_errors_reject_all_arguments(error_type: type[SerdeError]) -> None:
    with pytest.raises(TypeError):
        error_type(SerdeErrorCode.INVALID_METADATA)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "error_type",
    [
        InvalidMetadataError,
        FormatMismatchError,
        ContentTypeMismatchError,
        UnsupportedVersionError,
        TrustProfileMismatchError,
    ],
)
@pytest.mark.parametrize(
    "forbidden_arguments",
    [
        {"code": SerdeErrorCode.INVALID_METADATA},
        {"message": "custom"},
        {"payload": b"data"},
        {"source": object()},
    ],
)
def test_fixed_errors_reject_forbidden_keyword_arguments(
    error_type: type[SerdeError],
    forbidden_arguments: dict[str, object],
) -> None:
    with pytest.raises(TypeError):
        error_type(**forbidden_arguments)  # type: ignore[call-arg]


VARIABLE_ERROR_CASES = [
    (
        PayloadLimitError,
        SerdeErrorCode.INPUT_LIMIT,
        "serialized payload exceeds max_input_size",
    ),
    (
        PayloadLimitError,
        SerdeErrorCode.OUTPUT_LIMIT,
        "serialized output exceeds max_output_size",
    ),
    (
        PayloadLimitError,
        SerdeErrorCode.NESTING_LIMIT,
        "JSON nesting exceeds max_nesting_depth",
    ),
    (
        PayloadLimitError,
        SerdeErrorCode.INTEGER_DIGIT_LIMIT,
        "JSON integer exceeds MAX_JSON_INTEGER_DIGITS",
    ),
    (MalformedPayloadError, SerdeErrorCode.INVALID_UTF8, "payload is not valid UTF-8"),
    (
        MalformedPayloadError,
        SerdeErrorCode.DUPLICATE_KEY,
        "JSON object contains a duplicate key",
    ),
    (
        MalformedPayloadError,
        SerdeErrorCode.DECODE_NON_FINITE_NUMBER,
        "JSON payload contains a non-finite number",
    ),
    (MalformedPayloadError, SerdeErrorCode.INVALID_JSON, "payload is not valid JSON"),
    (
        SerdeEncodeError,
        SerdeErrorCode.UNSUPPORTED_VALUE,
        "value is not JSON-serializable",
    ),
    (
        SerdeEncodeError,
        SerdeErrorCode.CIRCULAR_REFERENCE,
        "value contains a circular reference",
    ),
    (
        SerdeEncodeError,
        SerdeErrorCode.ENCODE_NON_FINITE_NUMBER,
        "value contains a non-finite number",
    ),
    (
        SerdeEncodeError,
        SerdeErrorCode.ENCODE_RECURSION,
        "value nesting exceeds encoder recursion support",
    ),
]

VARIABLE_ERROR_ALLOWED_CODES = {
    PayloadLimitError: frozenset(
        {
            SerdeErrorCode.INPUT_LIMIT,
            SerdeErrorCode.OUTPUT_LIMIT,
            SerdeErrorCode.NESTING_LIMIT,
            SerdeErrorCode.INTEGER_DIGIT_LIMIT,
        }
    ),
    MalformedPayloadError: frozenset(
        {
            SerdeErrorCode.INVALID_UTF8,
            SerdeErrorCode.DUPLICATE_KEY,
            SerdeErrorCode.DECODE_NON_FINITE_NUMBER,
            SerdeErrorCode.INVALID_JSON,
        }
    ),
    SerdeEncodeError: frozenset(
        {
            SerdeErrorCode.UNSUPPORTED_VALUE,
            SerdeErrorCode.CIRCULAR_REFERENCE,
            SerdeErrorCode.ENCODE_NON_FINITE_NUMBER,
            SerdeErrorCode.ENCODE_RECURSION,
        }
    ),
}

DISALLOWED_VARIABLE_ERROR_CASES = [
    (error_type, code)
    for error_type, allowed_codes in VARIABLE_ERROR_ALLOWED_CODES.items()
    for code in SerdeErrorCode
    if code not in allowed_codes
]


@pytest.mark.parametrize(("error_type", "code", "message"), VARIABLE_ERROR_CASES)
def test_variable_errors_accept_only_their_codes(
    error_type: type[SerdeError],
    code: SerdeErrorCode,
    message: str,
) -> None:
    error = error_type(code=code)

    assert error.code is code
    assert str(error) == message
    assert error.args == (message,)
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(("error_type", "foreign_code"), DISALLOWED_VARIABLE_ERROR_CASES)
def test_variable_errors_reject_cross_class_codes(
    error_type: type[SerdeError],
    foreign_code: SerdeErrorCode,
) -> None:
    with pytest.raises(ValueError):
        error_type(code=foreign_code)


@pytest.mark.parametrize(
    ("error_type", "allowed_code"),
    [
        (PayloadLimitError, SerdeErrorCode.INPUT_LIMIT),
        (MalformedPayloadError, SerdeErrorCode.INVALID_JSON),
        (SerdeEncodeError, SerdeErrorCode.UNSUPPORTED_VALUE),
    ],
)
def test_variable_errors_reject_wrong_types_and_positional_code(
    error_type: type[SerdeError],
    allowed_code: SerdeErrorCode,
) -> None:
    with pytest.raises(TypeError):
        error_type(code="invalid_json")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        error_type(allowed_code)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("error_type", "allowed_code"),
    [
        (PayloadLimitError, SerdeErrorCode.INPUT_LIMIT),
        (MalformedPayloadError, SerdeErrorCode.INVALID_JSON),
        (SerdeEncodeError, SerdeErrorCode.UNSUPPORTED_VALUE),
    ],
)
@pytest.mark.parametrize(
    "forbidden_arguments",
    [
        {"message": "custom"},
        {"payload": b"data"},
        {"source": object()},
    ],
)
def test_variable_errors_reject_forbidden_keyword_arguments(
    error_type: type[SerdeError],
    allowed_code: SerdeErrorCode,
    forbidden_arguments: dict[str, object],
) -> None:
    with pytest.raises(TypeError):
        error_type(code=allowed_code, **forbidden_arguments)  # type: ignore[call-arg]
