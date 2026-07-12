import struct
from dataclasses import replace

import pytest
from _support import sample_envelope
from bluetape.cache.redis import (
    BinaryEnvelopeFormat,
    EnvelopeDecodeError,
    EnvelopeErrorCode,
    EnvelopeSizeError,
    ResultEnvelope,
)


@pytest.mark.parametrize(
    "envelope",
    [sample_envelope(), sample_envelope(payload=b""), sample_envelope(content_type=None)],
)
def test_binary_format_round_trips_exact_semantics(envelope: ResultEnvelope) -> None:
    formatter = BinaryEnvelopeFormat(max_encoded_size=4096)
    encoded = formatter.encode(envelope)

    assert encoded[:5] == b"BTRE\x01"
    assert formatter.decode(encoded) == envelope


def test_binary_format_is_deterministic_and_uses_network_order() -> None:
    envelope = sample_envelope(payload=b"x")
    encoded = BinaryEnvelopeFormat(max_encoded_size=4096).encode(envelope)

    assert encoded[5:9] == struct.pack("!I", len(envelope.owner_token))
    assert encoded == BinaryEnvelopeFormat(max_encoded_size=4096).encode(envelope)


def test_binary_format_rejects_declared_length_before_slicing() -> None:
    hostile = b"BTRE\x01" + struct.pack("!I", 0xFFFF_FFFF)

    with pytest.raises(EnvelopeDecodeError) as captured:
        BinaryEnvelopeFormat(max_encoded_size=64).decode(hostile)

    assert captured.value.code is EnvelopeErrorCode.MALFORMED_ENVELOPE


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: b"NOPE" + data[4:],
        lambda data: data[:4] + b"\x02" + data[5:],
        lambda data: data[:-1],
        lambda data: data + b"trailing",
    ],
)
def test_binary_format_rejects_magic_version_truncation_and_trailing_bytes(mutate) -> None:
    formatter = BinaryEnvelopeFormat(max_encoded_size=4096)
    encoded = formatter.encode(sample_envelope())

    with pytest.raises(EnvelopeDecodeError):
        formatter.decode(mutate(encoded))


def test_binary_format_rejects_invalid_ascii_owner_token() -> None:
    formatter = BinaryEnvelopeFormat(max_encoded_size=4096)
    encoded = bytearray(formatter.encode(sample_envelope()))
    encoded[9] = 0xFF

    with pytest.raises(EnvelopeDecodeError) as captured:
        formatter.decode(bytes(encoded))

    assert captured.value.code is EnvelopeErrorCode.MALFORMED_ENVELOPE


def test_binary_format_rejects_invalid_utf8_content_type() -> None:
    formatter = BinaryEnvelopeFormat(max_encoded_size=4096)
    encoded = formatter.encode(sample_envelope(content_type="x"))
    content_type_offset = encoded.index(b"x", encoded.index(b"json") + 4)
    hostile = encoded[:content_type_offset] + b"\xff" + encoded[content_type_offset + 1 :]

    with pytest.raises(EnvelopeDecodeError):
        formatter.decode(hostile)


def test_binary_format_enforces_exact_encoded_bound() -> None:
    envelope = sample_envelope(payload=b"payload")
    encoded = BinaryEnvelopeFormat(max_encoded_size=4096).encode(envelope)

    assert BinaryEnvelopeFormat(max_encoded_size=len(encoded)).encode(envelope) == encoded
    assert BinaryEnvelopeFormat(max_encoded_size=len(encoded)).decode(encoded) == envelope
    with pytest.raises(EnvelopeSizeError):
        BinaryEnvelopeFormat(max_encoded_size=len(encoded) - 1).encode(envelope)
    with pytest.raises(EnvelopeSizeError):
        BinaryEnvelopeFormat(max_encoded_size=len(encoded) - 1).decode(encoded)


def test_binary_format_rejects_oversize_content_type_before_output() -> None:
    envelope = sample_envelope()
    envelope = replace(
        envelope,
        metadata=replace(envelope.metadata, content_type="x" * 1025),
    )

    with pytest.raises(ValueError, match="content type"):
        BinaryEnvelopeFormat().encode(envelope)


def test_binary_format_rejects_non_exact_bytes() -> None:
    class BytesSubclass(bytes):
        pass

    with pytest.raises(TypeError, match="exact bytes"):
        BinaryEnvelopeFormat().decode(BytesSubclass(b"BTRE"))


@pytest.mark.parametrize("max_encoded_size", [True, 0, -1, 0xFFFF_FFFF])
def test_binary_format_validates_max_encoded_size(max_encoded_size: object) -> None:
    error = TypeError if max_encoded_size is True else ValueError
    with pytest.raises(error):
        BinaryEnvelopeFormat(max_encoded_size=max_encoded_size)  # type: ignore[arg-type]
