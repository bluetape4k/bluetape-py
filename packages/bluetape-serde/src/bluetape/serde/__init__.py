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

__all__ = [  # noqa: RUF022 - staged public contract order is intentional
    "ContentTypeMismatchError",
    "FormatMismatchError",
    "InvalidMetadataError",
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
]
