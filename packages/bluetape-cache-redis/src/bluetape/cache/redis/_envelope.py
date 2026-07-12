"""Composition of caller-owned payload codecs, formats, and compression."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from bluetape.compression import Compressor
from bluetape.serde import SerializedPayload

from ._contracts import (
    DEFAULT_MAX_ENCODED_SIZE,
    EnvelopeDecodeError,
    EnvelopeEncodeError,
    EnvelopeError,
    EnvelopeErrorCode,
    EnvelopeFormat,
    EnvelopeSizeError,
    PayloadCodec,
    ResultEnvelope,
    ResultEnvelopeMatch,
    _validate_algorithm,
    _validate_owner_token,
)
from ._formats import BinaryEnvelopeFormat, JsonEnvelopeFormat, _validate_max_encoded_size


def _algorithm_for(compressor: Compressor) -> str:
    try:
        algorithm = compressor.algorithm
    except Exception:
        raise ValueError("compressor algorithm cannot be read") from None
    _validate_algorithm(algorithm)
    if algorithm == "identity":
        raise ValueError("compressor algorithm identity is reserved")
    return algorithm


def _build_reader_registry(
    writer: Compressor | None, readers: tuple[Compressor, ...]
) -> dict[str, Compressor]:
    registry: dict[str, Compressor] = {}
    for compressor in (() if writer is None else (writer,)) + readers:
        algorithm = _algorithm_for(compressor)
        if algorithm in registry:
            raise ValueError("compressor algorithm must be unique")
        registry[algorithm] = compressor
    return registry


def _validated_envelope(value: object) -> ResultEnvelope:
    if type(value) is not ResultEnvelope:
        raise EnvelopeDecodeError(code=EnvelopeErrorCode.UNSUPPORTED_FORMAT)
    try:
        return ResultEnvelope(
            version=value.version,
            owner_token=value.owner_token,
            metadata=value.metadata,
            compression_algorithm=value.compression_algorithm,
            payload=value.payload,
        )
    except (TypeError, ValueError):
        raise EnvelopeDecodeError(code=EnvelopeErrorCode.MALFORMED_ENVELOPE) from None


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelopeCodec[T]:
    """Compose caller payload policy with one explicit envelope format and compressor registry."""

    payload_codec: PayloadCodec[T]
    envelope_format: EnvelopeFormat = field(default_factory=BinaryEnvelopeFormat)
    compressor: Compressor | None = None
    decompressors: tuple[Compressor, ...] = ()
    max_encoded_size: int = DEFAULT_MAX_ENCODED_SIZE
    _readers: Mapping[str, Compressor] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _validate_max_encoded_size(self.max_encoded_size)
        try:
            readers = tuple(self.decompressors)
        except TypeError:
            raise TypeError("decompressors must be iterable") from None
        if type(self.envelope_format) in (BinaryEnvelopeFormat, JsonEnvelopeFormat):
            format_bound = self.envelope_format.max_encoded_size
            if format_bound < self.max_encoded_size:
                raise ValueError("built-in format bound must cover codec bound")
        registry = _build_reader_registry(self.compressor, readers)
        object.__setattr__(self, "decompressors", readers)
        object.__setattr__(self, "_readers", MappingProxyType(registry))

    def encode(self, owner_token: str, value: T) -> bytes:
        """Encode a value using the configured caller policy and exact writer compressor."""
        _validate_owner_token(owner_token)
        try:
            serialized = self.payload_codec.encode(value)
        except EnvelopeError:
            raise
        except Exception as error:
            raise EnvelopeEncodeError(code=EnvelopeErrorCode.PAYLOAD_CODEC_FAILURE) from error
        if type(serialized) is not SerializedPayload:
            raise EnvelopeEncodeError(code=EnvelopeErrorCode.PAYLOAD_CODEC_FAILURE)

        algorithm = "identity"
        payload = serialized.data
        if self.compressor is not None:
            algorithm = _algorithm_for(self.compressor)
            try:
                payload = self.compressor.compress(serialized.data)
            except Exception as error:
                raise EnvelopeEncodeError(code=EnvelopeErrorCode.COMPRESSION_FAILURE) from error
            if type(payload) is not bytes:
                raise EnvelopeEncodeError(code=EnvelopeErrorCode.COMPRESSION_FAILURE)
        envelope = ResultEnvelope(
            version=1,
            owner_token=owner_token,
            metadata=serialized.metadata,
            compression_algorithm=algorithm,
            payload=payload,
        )
        try:
            encoded = self.envelope_format.encode(envelope)
        except EnvelopeError:
            raise
        except Exception as error:
            raise EnvelopeEncodeError(code=EnvelopeErrorCode.UNSUPPORTED_FORMAT) from error
        if type(encoded) is not bytes:
            raise EnvelopeEncodeError(code=EnvelopeErrorCode.UNSUPPORTED_FORMAT)
        if len(encoded) > self.max_encoded_size:
            raise EnvelopeSizeError(code=EnvelopeErrorCode.ENCODED_SIZE_LIMIT)
        return encoded

    def decode(self, data: bytes, *, expected_owner_token: str) -> T | None:
        """Decode a matching envelope while preserving the legacy mismatch sentinel."""
        match = self.decode_matching(data, expected_owner_token=expected_owner_token)
        return None if match is None else match.value

    def decode_matching(
        self, data: bytes, *, expected_owner_token: str
    ) -> ResultEnvelopeMatch[T] | None:
        """Decode one envelope and distinguish token mismatch from a decoded ``None``."""
        if type(data) is not bytes:
            raise TypeError("data must be exact bytes")
        _validate_owner_token(expected_owner_token)
        if len(data) > self.max_encoded_size:
            raise EnvelopeSizeError(code=EnvelopeErrorCode.ENCODED_SIZE_LIMIT)
        try:
            envelope = self.envelope_format.decode(data)
        except EnvelopeError:
            raise
        except Exception as error:
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.UNSUPPORTED_FORMAT) from error
        envelope = _validated_envelope(envelope)
        if envelope.version != 1:
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.UNSUPPORTED_VERSION)
        if envelope.owner_token != expected_owner_token:
            return None

        if envelope.compression_algorithm == "identity":
            logical = envelope.payload
        else:
            reader = self._readers.get(envelope.compression_algorithm)
            if reader is None:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.UNKNOWN_ALGORITHM)
            try:
                logical = reader.decompress(envelope.payload)
            except Exception as error:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.COMPRESSION_FAILURE) from error
            if type(logical) is not bytes:
                raise EnvelopeDecodeError(code=EnvelopeErrorCode.COMPRESSION_FAILURE)
        serialized = SerializedPayload(metadata=envelope.metadata, data=logical)
        try:
            return ResultEnvelopeMatch(value=self.payload_codec.decode(serialized))
        except EnvelopeError:
            raise
        except Exception as error:
            raise EnvelopeDecodeError(code=EnvelopeErrorCode.PAYLOAD_CODEC_FAILURE) from error
