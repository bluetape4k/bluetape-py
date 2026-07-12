"""Strict bounded binary and JSON result-envelope formats."""

import base64
import binascii
import json
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


def _json_string(value: str) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _object_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
        result[key] = value
    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonEnvelopeFormat:
    """Encode deterministic compact v1 JSON/base64 result envelopes."""

    max_encoded_size: int = DEFAULT_MAX_ENCODED_SIZE

    def __post_init__(self) -> None:
        _validate_max_encoded_size(self.max_encoded_size)

    @property
    def format_id(self) -> str:
        """Return the stable JSON format identifier."""
        return "json-v1"

    def encode(self, envelope: ResultEnvelope) -> bytes:
        """Encode one validated envelope as compact JSON within the configured bound."""
        if type(envelope) is not ResultEnvelope:
            raise TypeError("envelope must be an exact ResultEnvelope")
        if envelope.metadata.content_type is not None:
            content_bytes = envelope.metadata.content_type.encode("utf-8")
            if len(content_bytes) > _MAX_CONTENT_TYPE_SIZE:
                raise ValueError("content type exceeds its encoded size limit")

        owner = _json_string(envelope.owner_token)
        serde_format = _json_string(envelope.metadata.format)
        content_type = (
            b"null"
            if envelope.metadata.content_type is None
            else _json_string(envelope.metadata.content_type)
        )
        trust_profile = _json_string(envelope.metadata.trust_profile.value)
        algorithm = _json_string(envelope.compression_algorithm)
        payload_length = 4 * ((len(envelope.payload) + 2) // 3)
        prefix = b"".join(
            (
                b'{"version":',
                str(envelope.version).encode("ascii"),
                b',"owner_token":',
                owner,
                b',"metadata":{"format":',
                serde_format,
                b',"version":',
                str(envelope.metadata.version).encode("ascii"),
                b',"content_type":',
                content_type,
                b',"trust_profile":',
                trust_profile,
                b'},"compression":',
                algorithm,
                b',"payload":"',
            )
        )
        predicted_size = len(prefix) + payload_length + 2
        _ensure_bound(predicted_size, self.max_encoded_size)
        encoded = prefix + base64.b64encode(envelope.payload) + b'"}'
        _ensure_bound(len(encoded), self.max_encoded_size)
        return encoded

    def decode(self, data: bytes) -> ResultEnvelope:
        """Decode one complete strict compact JSON envelope without fallback."""
        if type(data) is not bytes:
            raise TypeError("data must be exact bytes")
        _ensure_bound(len(data), self.max_encoded_size)
        try:
            text = data.decode("utf-8")
            decoder = json.JSONDecoder(object_pairs_hook=_object_no_duplicates)
            document, cursor = decoder.raw_decode(text)
            if cursor != len(text) or type(document) is not dict:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if list(document) != [
                "version",
                "owner_token",
                "metadata",
                "compression",
                "payload",
            ]:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            metadata_document = document["metadata"]
            if type(metadata_document) is not dict or list(metadata_document) != [
                "format",
                "version",
                "content_type",
                "trust_profile",
            ]:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if type(document["version"]) is not int:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if document["version"] != _VERSION:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.UNSUPPORTED_VERSION)
            if type(document["owner_token"]) is not str:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if type(document["compression"]) is not str:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            payload_text = document["payload"]
            if type(payload_text) is not str or not payload_text.isascii():
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            try:
                payload = base64.b64decode(payload_text, validate=True)
            except (binascii.Error, ValueError):
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE) from None
            if base64.b64encode(payload).decode("ascii") != payload_text:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            serde_format = metadata_document["format"]
            serde_version = metadata_document["version"]
            content_type = metadata_document["content_type"]
            trust_value = metadata_document["trust_profile"]
            if type(serde_format) is not str or type(serde_version) is not int:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if content_type is not None and type(content_type) is not str:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if (
                content_type is not None
                and len(content_type.encode("utf-8")) > _MAX_CONTENT_TYPE_SIZE
            ):
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            if type(trust_value) is not str:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE)
            metadata = PayloadMetadata(
                format=serde_format,
                version=serde_version,
                content_type=content_type,
                trust_profile=TrustProfile(trust_value),
            )
            return ResultEnvelope(
                version=document["version"],
                owner_token=document["owner_token"],
                metadata=metadata,
                compression_algorithm=document["compression"],
                payload=payload,
            )
        except EnvelopeDecodeError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE) from None
