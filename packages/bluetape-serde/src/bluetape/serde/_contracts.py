"""Immutable payload contracts and stable serde failures."""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class TrustProfile(StrEnum):
    """Describe the caller-selected trust boundary for payload decoding."""

    UNTRUSTED = "untrusted"
    TRUSTED_INTERNAL = "trusted_internal"


class SerdeErrorCode(StrEnum):
    """Stable machine-readable codes for serde failures."""

    INVALID_METADATA = "invalid_metadata"
    FORMAT_MISMATCH = "format_mismatch"
    CONTENT_TYPE_MISMATCH = "content_type_mismatch"
    UNSUPPORTED_VERSION = "unsupported_version"
    TRUST_PROFILE_MISMATCH = "trust_profile_mismatch"
    INPUT_LIMIT = "input_limit"
    OUTPUT_LIMIT = "output_limit"
    NESTING_LIMIT = "nesting_limit"
    INTEGER_DIGIT_LIMIT = "integer_digit_limit"
    INVALID_UTF8 = "invalid_utf8"
    DUPLICATE_KEY = "duplicate_key"
    DECODE_NON_FINITE_NUMBER = "decode_non_finite_number"
    INVALID_JSON = "invalid_json"
    UNSUPPORTED_VALUE = "unsupported_value"
    CIRCULAR_REFERENCE = "circular_reference"
    ENCODE_NON_FINITE_NUMBER = "encode_non_finite_number"
    ENCODE_RECURSION = "encode_recursion"
    SCHEMA_MISMATCH = "schema_mismatch"
    TYPE_MISMATCH = "type_mismatch"
    FORY_REGISTRATION = "fory_registration"
    INVALID_FORY = "invalid_fory"
    FORY_ENCODE = "fory_encode"
    FORY_CONCURRENCY_LIMIT = "fory_concurrency_limit"


_ERROR_MESSAGES: dict[SerdeErrorCode, str] = {
    SerdeErrorCode.INVALID_METADATA: "invalid payload metadata",
    SerdeErrorCode.FORMAT_MISMATCH: "payload format does not match expected format",
    SerdeErrorCode.CONTENT_TYPE_MISMATCH: (
        "payload content type does not match expected content type"
    ),
    SerdeErrorCode.UNSUPPORTED_VERSION: "payload version is unsupported",
    SerdeErrorCode.TRUST_PROFILE_MISMATCH: ("payload trust profile does not match caller policy"),
    SerdeErrorCode.INPUT_LIMIT: "serialized payload exceeds max_input_size",
    SerdeErrorCode.OUTPUT_LIMIT: "serialized output exceeds max_output_size",
    SerdeErrorCode.NESTING_LIMIT: "JSON nesting exceeds max_nesting_depth",
    SerdeErrorCode.INTEGER_DIGIT_LIMIT: "JSON integer exceeds MAX_JSON_INTEGER_DIGITS",
    SerdeErrorCode.INVALID_UTF8: "payload is not valid UTF-8",
    SerdeErrorCode.DUPLICATE_KEY: "JSON object contains a duplicate key",
    SerdeErrorCode.DECODE_NON_FINITE_NUMBER: ("JSON payload contains a non-finite number"),
    SerdeErrorCode.INVALID_JSON: "payload is not valid JSON",
    SerdeErrorCode.UNSUPPORTED_VALUE: "value is not JSON-serializable",
    SerdeErrorCode.CIRCULAR_REFERENCE: "value contains a circular reference",
    SerdeErrorCode.ENCODE_NON_FINITE_NUMBER: "value contains a non-finite number",
    SerdeErrorCode.ENCODE_RECURSION: ("value nesting exceeds encoder recursion support"),
    SerdeErrorCode.SCHEMA_MISMATCH: "Fory schema does not match caller registration",
    SerdeErrorCode.TYPE_MISMATCH: "Fory type does not match caller registration",
    SerdeErrorCode.FORY_REGISTRATION: "Fory registration failed",
    SerdeErrorCode.INVALID_FORY: "payload is not valid Fory",
    SerdeErrorCode.FORY_ENCODE: "value cannot be encoded as registered Fory type",
    SerdeErrorCode.FORY_CONCURRENCY_LIMIT: "Fory adapter concurrency limit reached",
}


class SerdeError(ValueError):
    """Base class for serde failures with a stable public error code."""

    def __init__(self, *, code: SerdeErrorCode) -> None:
        if type(code) is not SerdeErrorCode:
            raise TypeError("code must be an exact SerdeErrorCode")
        self._code = code
        super().__init__(_ERROR_MESSAGES[code])

    @property
    def code(self) -> SerdeErrorCode:
        """Return the immutable machine-readable failure code."""
        return self._code


class InvalidMetadataError(SerdeError):
    """Report invalid payload metadata."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.INVALID_METADATA)


class FormatMismatchError(SerdeError):
    """Report a mismatch between actual and expected payload formats."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.FORMAT_MISMATCH)


class ContentTypeMismatchError(SerdeError):
    """Report a mismatch between actual and expected content types."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.CONTENT_TYPE_MISMATCH)


class UnsupportedVersionError(SerdeError):
    """Report an unsupported payload version."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.UNSUPPORTED_VERSION)


class TrustProfileMismatchError(SerdeError):
    """Report a payload trust profile rejected by caller policy."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.TRUST_PROFILE_MISMATCH)


class SchemaMismatchError(SerdeError):
    """Report a Fory schema registration mismatch."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.SCHEMA_MISMATCH)


class TypeMismatchError(SerdeError):
    """Report a Fory type registration mismatch."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.TYPE_MISMATCH)


class ForyRegistrationError(SerdeError):
    """Report a Fory registration failure."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.FORY_REGISTRATION)


class ForyConcurrencyError(SerdeError):
    """Report exhaustion of the Fory adapter concurrency bound."""

    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.FORY_CONCURRENCY_LIMIT)


class _RestrictedSerdeError(SerdeError):
    allowed_codes: ClassVar[frozenset[SerdeErrorCode]]

    def __init__(self, *, code: SerdeErrorCode) -> None:
        if type(code) is not SerdeErrorCode:
            raise TypeError("code must be an exact SerdeErrorCode")
        if code not in self.allowed_codes:
            raise ValueError("code is not valid for this error type")
        super().__init__(code=code)


class PayloadLimitError(_RestrictedSerdeError):
    """Report a configured input, output, or nesting limit violation."""

    allowed_codes = frozenset(
        {
            SerdeErrorCode.INPUT_LIMIT,
            SerdeErrorCode.OUTPUT_LIMIT,
            SerdeErrorCode.NESTING_LIMIT,
            SerdeErrorCode.INTEGER_DIGIT_LIMIT,
        }
    )


class MalformedPayloadError(_RestrictedSerdeError):
    """Report malformed serialized input."""

    allowed_codes = frozenset(
        {
            SerdeErrorCode.INVALID_UTF8,
            SerdeErrorCode.DUPLICATE_KEY,
            SerdeErrorCode.DECODE_NON_FINITE_NUMBER,
            SerdeErrorCode.INVALID_JSON,
            SerdeErrorCode.INVALID_FORY,
        }
    )


class SerdeEncodeError(_RestrictedSerdeError):
    """Report a value that cannot be safely encoded."""

    allowed_codes = frozenset(
        {
            SerdeErrorCode.UNSUPPORTED_VALUE,
            SerdeErrorCode.CIRCULAR_REFERENCE,
            SerdeErrorCode.ENCODE_NON_FINITE_NUMBER,
            SerdeErrorCode.ENCODE_RECURSION,
            SerdeErrorCode.FORY_ENCODE,
        }
    )


_ALLOWED_FORMAT_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_./")


@dataclass(frozen=True, slots=True, kw_only=True)
class PayloadMetadata:
    """Describe the format, version, media type, and caller-selected trust profile."""

    format: str
    version: int
    content_type: str | None
    trust_profile: TrustProfile

    def __post_init__(self) -> None:
        if type(self.format) is not str:
            raise TypeError("format must be an exact str")
        if type(self.version) is not int:
            raise TypeError("version must be an exact int")
        if self.content_type is not None and type(self.content_type) is not str:
            raise TypeError("content_type must be an exact str or None")
        if type(self.trust_profile) is not TrustProfile:
            raise TypeError("trust_profile must be an exact TrustProfile")
        if (
            not 1 <= len(self.format) <= 64
            or not all(char in _ALLOWED_FORMAT_CHARACTERS for char in self.format)
            or self.version <= 0
        ):
            raise InvalidMetadataError


@dataclass(frozen=True, slots=True, kw_only=True)
class SerializedPayload:
    """Pair validated payload metadata with immutable serialized bytes."""

    metadata: PayloadMetadata
    data: bytes

    def __post_init__(self) -> None:
        if type(self.metadata) is not PayloadMetadata:
            raise TypeError("metadata must be an exact PayloadMetadata")
        if type(self.data) is not bytes:
            raise TypeError("data must be exact bytes")
