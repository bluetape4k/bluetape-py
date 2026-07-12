"""Strict bounded binary and JSON result-envelope formats."""

import struct
from dataclasses import dataclass

from bluetape.serde import PayloadMetadata, TrustProfile

from ._contracts import (
    DEFAULT_MAX_ENCODED_SIZE,
    EnvelopeDecodeError,
    EnvelopeErrorCode,
    EnvelopeSizeError,
    ResultEnvelope,
)

_MAGIC = b"BTRE"
_VERSION = 1
_U32 = struct.Struct("!I")
_NULL_LENGTH = 0xFFFF_FFFF
_MAX_CONTENT_TYPE_SIZE = 1024
_MAX_U32_VALUE = _NULL_LENGTH - 1


def _validate_max_encoded_size(value: object) -> None:
    if type(value) is not int:
        raise TypeError("max_encoded_size must be an exact int")
    if not 1 <= value <= _MAX_U32_VALUE:
        raise ValueError("max_encoded_size is outside the supported range")


def _encoded_text(value: str, *, field: str, encoding: str, maximum: int) -> bytes:
    try:
        encoded = value.encode(encoding)
    except UnicodeEncodeError:
        raise ValueError(f"{field} must use {encoding}") from None
    if len(encoded) > maximum:
        raise ValueError(f"{field} exceeds its encoded size limit")
    return encoded


def _take(data: bytes, cursor: int, size: int) -> tuple[bytes, int]:
    if size < 0 or size > len(data) - cursor:
        raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
    end = cursor + size
    return data[cursor:end], end


def _read_u32(data: bytes, cursor: int) -> tuple[int, int]:
    raw, cursor = _take(data, cursor, _U32.size)
    return _U32.unpack(raw)[0], cursor


def _read_required_text(
    data: bytes, cursor: int, *, encoding: str, maximum: int
) -> tuple[str, int]:
    size, cursor = _read_u32(data, cursor)
    if not 1 <= size <= maximum:
        raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
    raw, cursor = _take(data, cursor, size)
    try:
        return raw.decode(encoding), cursor
    except UnicodeDecodeError:
        raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE) from None


def _ensure_bound(size: int, maximum: int) -> None:
    if size > maximum:
        raise EnvelopeSizeError(code=EnvelopeErrorCode.ENCODED_SIZE_LIMIT)


@dataclass(frozen=True, slots=True, kw_only=True)
class BinaryEnvelopeFormat:
    """Encode strict network-order v1 result envelopes."""

    max_encoded_size: int = DEFAULT_MAX_ENCODED_SIZE

    def __post_init__(self) -> None:
        _validate_max_encoded_size(self.max_encoded_size)

    @property
    def format_id(self) -> str:
        """Return the stable binary format identifier."""
        return "binary-v1"

    def encode(self, envelope: ResultEnvelope) -> bytes:
        """Encode one validated semantic envelope within the configured bound."""
        if type(envelope) is not ResultEnvelope:
            raise TypeError("envelope must be an exact ResultEnvelope")

        owner = _encoded_text(
            envelope.owner_token, field="owner token", encoding="ascii", maximum=128
        )
        serde_format = _encoded_text(
            envelope.metadata.format, field="serde format", encoding="ascii", maximum=64
        )
        content_type = (
            None
            if envelope.metadata.content_type is None
            else _encoded_text(
                envelope.metadata.content_type,
                field="content type",
                encoding="utf-8",
                maximum=_MAX_CONTENT_TYPE_SIZE,
            )
        )
        trust_profile = _encoded_text(
            envelope.metadata.trust_profile.value,
            field="trust profile",
            encoding="ascii",
            maximum=64,
        )
        algorithm = _encoded_text(
            envelope.compression_algorithm,
            field="compression algorithm",
            encoding="ascii",
            maximum=64,
        )
        fields = (owner, serde_format, trust_profile, algorithm, envelope.payload)
        for field in fields:
            if len(field) > _MAX_U32_VALUE:
                raise EnvelopeSizeError(code=EnvelopeErrorCode.ENCODED_SIZE_LIMIT)
        size = 5 + 7 * _U32.size + sum(len(field) for field in fields)
        if content_type is not None:
            size += len(content_type)
        _ensure_bound(size, self.max_encoded_size)

        output = bytearray(_MAGIC)
        output.append(envelope.version)
        output.extend(_U32.pack(len(owner)))
        output.extend(owner)
        output.extend(_U32.pack(len(serde_format)))
        output.extend(serde_format)
        output.extend(_U32.pack(envelope.metadata.version))
        if content_type is None:
            output.extend(_U32.pack(_NULL_LENGTH))
        else:
            output.extend(_U32.pack(len(content_type)))
            output.extend(content_type)
        output.extend(_U32.pack(len(trust_profile)))
        output.extend(trust_profile)
        output.extend(_U32.pack(len(algorithm)))
        output.extend(algorithm)
        output.extend(_U32.pack(len(envelope.payload)))
        output.extend(envelope.payload)
        encoded = bytes(output)
        _ensure_bound(len(encoded), self.max_encoded_size)
        return encoded

    def decode(self, data: bytes) -> ResultEnvelope:
        """Decode one complete strict binary envelope without fallback."""
        if type(data) is not bytes:
            raise TypeError("data must be exact bytes")
        _ensure_bound(len(data), self.max_encoded_size)
        try:
            magic, cursor = _take(data, 0, len(_MAGIC))
            if magic != _MAGIC:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            version_bytes, cursor = _take(data, cursor, 1)
            version = version_bytes[0]
            if version != _VERSION:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.UNSUPPORTED_VERSION)
            owner, cursor = _read_required_text(data, cursor, encoding="ascii", maximum=128)
            serde_format, cursor = _read_required_text(data, cursor, encoding="ascii", maximum=64)
            serde_version, cursor = _read_u32(data, cursor)
            content_size, cursor = _read_u32(data, cursor)
            if content_size == _NULL_LENGTH:
                content_type = None
            else:
                if content_size > _MAX_CONTENT_TYPE_SIZE:
                    raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
                raw_content, cursor = _take(data, cursor, content_size)
                try:
                    content_type = raw_content.decode("utf-8")
                except UnicodeDecodeError:
                    raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE) from None
            trust_value, cursor = _read_required_text(data, cursor, encoding="ascii", maximum=64)
            algorithm, cursor = _read_required_text(data, cursor, encoding="ascii", maximum=64)
            payload_size, cursor = _read_u32(data, cursor)
            payload, cursor = _take(data, cursor, payload_size)
            if cursor != len(data):
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            metadata = PayloadMetadata(
                format=serde_format,
                version=serde_version,
                content_type=content_type,
                trust_profile=TrustProfile(trust_value),
            )
            return ResultEnvelope(
                version=version,
                owner_token=owner,
                metadata=metadata,
                compression_algorithm=algorithm,
                payload=payload,
            )
        except EnvelopeDecodeError:
            raise
        except (TypeError, ValueError, struct.error):
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE) from None
