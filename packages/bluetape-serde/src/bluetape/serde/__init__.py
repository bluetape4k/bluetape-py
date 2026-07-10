"""Strict payload contracts and JSON serialization."""

from ._contracts import (
    ContentTypeMismatchError,
    FormatMismatchError,
    InvalidMetadataError,
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
)
from ._json import (
    DEFAULT_MAX_INPUT_SIZE,
    DEFAULT_MAX_NESTING_DEPTH,
    DEFAULT_MAX_OUTPUT_SIZE,
    MAX_SUPPORTED_NESTING_DEPTH,
    JsonValue,
    json_deserialize,
    json_serialize,
)

__all__ = [  # noqa: RUF022 - staged public contract order is intentional
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
