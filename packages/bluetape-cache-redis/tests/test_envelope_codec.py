from dataclasses import FrozenInstanceError

import pytest
from _support import sample_envelope, sample_metadata
from bluetape.cache.redis import (
    BinaryEnvelopeFormat,
    EnvelopeDecodeError,
    EnvelopeEncodeError,
    EnvelopeErrorCode,
    EnvelopeSizeError,
    JsonEnvelopeFormat,
    ResultEnvelope,
    ResultEnvelopeCodec,
    ResultEnvelopeMatch,
)
from bluetape.compression import DeflateCompressor, GzipCompressor, ZlibCompressor
from bluetape.serde import SerializedPayload


class RecordingPayloadCodec:
    def __init__(self, *, data: bytes = b"logical") -> None:
        self.data = data
        self.encoded_values: list[object] = []
        self.decoded_payloads: list[SerializedPayload] = []

    def encode(self, value: object) -> SerializedPayload:
        self.encoded_values.append(value)
        return SerializedPayload(metadata=sample_metadata(), data=self.data)

    def decode(self, payload: SerializedPayload) -> object:
        self.decoded_payloads.append(payload)
        return (payload.metadata, payload.data)


class RecordingCompressor:
    def __init__(self, *, algorithm: str = "recording", output: bytes = b"compressed") -> None:
        self._algorithm = algorithm
        self.output = output
        self.compressed_inputs: list[bytes] = []
        self.decompressed_inputs: list[bytes] = []

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def max_output_size(self) -> int:
        return 1024

    def compress(self, data: bytes) -> bytes:
        self.compressed_inputs.append(data)
        return self.output

    def decompress(self, data: bytes) -> bytes:
        self.decompressed_inputs.append(data)
        return b"logical"


def test_binary_is_the_default_and_identity_preserves_metadata() -> None:
    payload_codec = RecordingPayloadCodec()
    codec = ResultEnvelopeCodec(payload_codec=payload_codec)

    encoded = codec.encode("owner-1", object())
    envelope = BinaryEnvelopeFormat().decode(encoded)

    assert envelope.metadata == sample_metadata()
    assert envelope.compression_algorithm == "identity"
    assert envelope.payload == b"logical"
    assert codec.decode(encoded, expected_owner_token="owner-1") == (
        sample_metadata(),
        b"logical",
    )


@pytest.mark.parametrize("data", [b"", b"x"])
def test_configured_compressor_always_runs(data: bytes) -> None:
    compressor = RecordingCompressor()
    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(data=data),
        compressor=compressor,
    )

    encoded = codec.encode("owner-1", object())

    assert compressor.compressed_inputs == [data]
    assert BinaryEnvelopeFormat().decode(encoded).compression_algorithm == "recording"


def test_token_mismatch_does_not_decompress_or_decode() -> None:
    compressor = RecordingCompressor()
    payload_codec = RecordingPayloadCodec()
    writer = ResultEnvelopeCodec(payload_codec=payload_codec, compressor=compressor)
    encoded = writer.encode("owner-1", object())
    payload_codec.decoded_payloads.clear()

    assert writer.decode(encoded, expected_owner_token="other") is None
    assert compressor.decompressed_inputs == []
    assert payload_codec.decoded_payloads == []


def test_decode_matching_distinguishes_legitimate_none_from_mismatch() -> None:
    class NonePayloadCodec(RecordingPayloadCodec):
        def decode(self, payload: SerializedPayload) -> None:
            self.decoded_payloads.append(payload)
            return None

    codec = ResultEnvelopeCodec(payload_codec=NonePayloadCodec())
    encoded = codec.encode("owner-1", object())

    assert codec.decode_matching(encoded, expected_owner_token="owner-1") == ResultEnvelopeMatch(
        value=None
    )
    assert codec.decode_matching(encoded, expected_owner_token="owner-2") is None
    assert codec.decode(encoded, expected_owner_token="owner-1") is None


def test_explicit_migration_reader_selects_only_recorded_algorithm() -> None:
    old = RecordingCompressor(algorithm="old", output=b"old-bytes")
    new = RecordingCompressor(algorithm="new", output=b"new-bytes")
    encoded = ResultEnvelopeCodec(payload_codec=RecordingPayloadCodec(), compressor=old).encode(
        "owner-1", object()
    )
    reader_payloads = RecordingPayloadCodec()
    reader = ResultEnvelopeCodec(
        payload_codec=reader_payloads,
        compressor=new,
        decompressors=(old,),
    )

    assert reader.decode(encoded, expected_owner_token="owner-1") == (
        sample_metadata(),
        b"logical",
    )
    assert old.decompressed_inputs == [b"old-bytes"]
    assert new.decompressed_inputs == []


@pytest.mark.parametrize(
    "decompressors",
    [
        (RecordingCompressor(algorithm="identity"),),
        (RecordingCompressor(algorithm="same"), RecordingCompressor(algorithm="same")),
    ],
)
def test_reader_registry_rejects_reserved_and_duplicate_algorithms(decompressors) -> None:
    with pytest.raises(ValueError, match="algorithm"):
        ResultEnvelopeCodec(
            payload_codec=RecordingPayloadCodec(),
            decompressors=decompressors,
        )


def test_unknown_algorithm_does_not_try_registered_readers() -> None:
    first = RecordingCompressor(algorithm="first")
    envelope = sample_envelope()
    envelope = ResultEnvelope(
        version=envelope.version,
        owner_token=envelope.owner_token,
        metadata=envelope.metadata,
        compression_algorithm="missing",
        payload=envelope.payload,
    )
    encoded = BinaryEnvelopeFormat().encode(envelope)
    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(),
        decompressors=(first,),
    )

    with pytest.raises(EnvelopeDecodeError) as captured:
        codec.decode(encoded, expected_owner_token="owner-42")

    assert captured.value.code is EnvelopeErrorCode.UNKNOWN_ALGORITHM
    assert first.decompressed_inputs == []


def test_builtin_format_bound_must_cover_codec_bound() -> None:
    with pytest.raises(ValueError, match="format bound"):
        ResultEnvelopeCodec(
            payload_codec=RecordingPayloadCodec(),
            envelope_format=BinaryEnvelopeFormat(max_encoded_size=64),
            max_encoded_size=65,
        )
    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(),
        envelope_format=JsonEnvelopeFormat(max_encoded_size=65),
        max_encoded_size=64,
    )
    assert codec.max_encoded_size == 64


def test_custom_format_returns_are_revalidated() -> None:
    class InvalidFormat:
        format_id = "invalid-v1"

        def encode(self, envelope: ResultEnvelope) -> bytes:
            return bytearray(b"bad")  # type: ignore[return-value]

        def decode(self, data: bytes) -> ResultEnvelope:
            return object()  # type: ignore[return-value]

    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(),
        envelope_format=InvalidFormat(),
    )
    with pytest.raises(EnvelopeEncodeError):
        codec.encode("owner-1", object())

    class DecodeInvalidFormat(InvalidFormat):
        def encode(self, envelope: ResultEnvelope) -> bytes:
            return b"ok"

    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(),
        envelope_format=DecodeInvalidFormat(),
    )
    with pytest.raises(EnvelopeDecodeError):
        codec.decode(b"ok", expected_owner_token="owner-1")


def test_outer_codec_enforces_custom_format_bound() -> None:
    class LargeFormat:
        format_id = "large-v1"

        def encode(self, envelope: ResultEnvelope) -> bytes:
            return b"x" * 65

        def decode(self, data: bytes) -> ResultEnvelope:
            return sample_envelope()

    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(),
        envelope_format=LargeFormat(),
        max_encoded_size=64,
    )
    with pytest.raises(EnvelopeSizeError):
        codec.encode("owner-1", object())
    with pytest.raises(EnvelopeSizeError):
        codec.decode(b"x" * 65, expected_owner_token="owner-42")


def test_codec_and_compressor_failures_are_translated_with_causes() -> None:
    marker = RuntimeError("sensitive-provider-text")

    class FailingPayloadCodec(RecordingPayloadCodec):
        def encode(self, value: object) -> SerializedPayload:
            raise marker

    codec = ResultEnvelopeCodec(payload_codec=FailingPayloadCodec())
    with pytest.raises(EnvelopeEncodeError) as captured:
        codec.encode("owner-1", object())
    assert captured.value.code is EnvelopeErrorCode.PAYLOAD_CODEC_FAILURE
    assert captured.value.__cause__ is marker
    assert "sensitive-provider-text" not in str(captured.value)


@pytest.mark.parametrize(
    "compressor",
    [GzipCompressor(), ZlibCompressor(), DeflateCompressor()],
)
def test_stdlib_compressors_round_trip(compressor) -> None:
    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(data=b"x" * 1024),
        compressor=compressor,
    )
    encoded = codec.encode("owner-1", object())
    assert codec.decode(encoded, expected_owner_token="owner-1") == (
        sample_metadata(),
        b"x" * 1024,
    )


@pytest.mark.native_compression
def test_native_compressors_round_trip() -> None:
    from bluetape.compression.native import Lz4Compressor, SnappyCompressor, ZstdCompressor

    for compressor in (Lz4Compressor(), SnappyCompressor(), ZstdCompressor()):
        codec = ResultEnvelopeCodec(
            payload_codec=RecordingPayloadCodec(data=b"x" * 1024),
            compressor=compressor,
        )
        encoded = codec.encode("owner-1", object())
        assert codec.decode(encoded, expected_owner_token="owner-1") == (
            sample_metadata(),
            b"x" * 1024,
        )


def test_configuration_is_frozen_and_copies_decompressors() -> None:
    decompressors = [RecordingCompressor(algorithm="old")]
    codec = ResultEnvelopeCodec(
        payload_codec=RecordingPayloadCodec(),
        decompressors=decompressors,  # type: ignore[arg-type]
    )
    decompressors.clear()
    assert len(codec.decompressors) == 1
    with pytest.raises(FrozenInstanceError):
        codec.max_encoded_size = 7  # type: ignore[misc]
