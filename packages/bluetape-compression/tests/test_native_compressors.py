import sys
from dataclasses import FrozenInstanceError

import pytest
from bluetape.compression import CompressionError, DecompressionLimitError
from bluetape.compression.native import Lz4Compressor, SnappyCompressor

pytestmark = pytest.mark.native_compression


def test_lz4_compressor_is_frozen_and_writes_a_complete_checked_frame() -> None:
    import lz4.frame

    compressor = Lz4Compressor()
    encoded = compressor.compress(b"bluetape")
    frame_info = lz4.frame.get_frame_info(encoded)

    assert compressor.algorithm == "lz4-frame"
    assert compressor.compression_level == 0
    assert frame_info["content_size"] == len(b"bluetape")
    assert frame_info["content_checksum"] is True
    assert not hasattr(compressor, "__dict__")
    with pytest.raises(FrozenInstanceError):
        compressor.max_output_size = 1  # type: ignore[misc]


@pytest.mark.parametrize("data_type", [bytes, bytearray, memoryview])
@pytest.mark.parametrize("data", [b"", b"bluetape", bytes(range(256))])
def test_lz4_compressor_round_trips_bytes_like_values(data_type, data: bytes) -> None:
    compressor = Lz4Compressor()

    encoded = compressor.compress(data_type(data))

    assert type(encoded) is bytes
    assert compressor.decompress(data_type(encoded)) == data


@pytest.mark.parametrize("compression_level", [True, False, -1, 17, 1.5, "1"])
def test_lz4_compressor_rejects_invalid_levels(compression_level: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        Lz4Compressor(compression_level=compression_level)


@pytest.mark.parametrize("limit", [True, False, -1, sys.maxsize, 1.5])
def test_lz4_compressor_rejects_invalid_output_limits(limit: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        Lz4Compressor(max_output_size=limit)


@pytest.mark.parametrize("method_name", ["compress", "decompress"])
def test_lz4_compressor_rejects_non_bytes_like_input(method_name: str) -> None:
    compressor = Lz4Compressor()

    with pytest.raises(TypeError, match="data must be bytes-like"):
        getattr(compressor, method_name)("bluetape")


def test_lz4_compressor_enforces_exact_output_limits() -> None:
    payload = b"x" * 4096
    encoded = Lz4Compressor().compress(payload)

    assert Lz4Compressor(max_output_size=len(payload)).decompress(encoded) == payload
    with pytest.raises(DecompressionLimitError):
        Lz4Compressor(max_output_size=len(payload) - 1).decompress(encoded)


def test_lz4_compressor_rejects_invalid_truncated_and_trailing_payloads() -> None:
    encoded = Lz4Compressor().compress(b"bluetape")

    for payload in (b"", b"invalid", encoded[:-1], encoded + b"trailing"):
        with pytest.raises(CompressionError) as raised:
            Lz4Compressor().decompress(payload)

        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None


def test_lz4_compressor_rejects_checksum_corruption() -> None:
    encoded = bytearray(Lz4Compressor().compress(b"bluetape"))
    encoded[-5] ^= 0x01

    with pytest.raises(CompressionError):
        Lz4Compressor().decompress(encoded)


def test_snappy_compressor_is_frozen_and_uses_raw_blocks() -> None:
    import cramjam

    compressor = SnappyCompressor()
    encoded = compressor.compress(b"bluetape")

    assert compressor.algorithm == "snappy-raw"
    assert cramjam.snappy.decompress_raw_len(encoded) == len(b"bluetape")
    assert bytes(cramjam.snappy.decompress_raw(encoded)) == b"bluetape"
    assert not hasattr(compressor, "__dict__")
    with pytest.raises(FrozenInstanceError):
        compressor.max_output_size = 1  # type: ignore[misc]


@pytest.mark.parametrize("data_type", [bytes, bytearray, memoryview])
@pytest.mark.parametrize("data", [b"", b"bluetape", bytes(range(256))])
def test_snappy_compressor_round_trips_bytes_like_values(data_type, data: bytes) -> None:
    compressor = SnappyCompressor()

    encoded = compressor.compress(data_type(data))

    assert type(encoded) is bytes
    assert compressor.decompress(data_type(encoded)) == data


@pytest.mark.parametrize("limit", [True, False, -1, sys.maxsize, 1.5])
def test_snappy_compressor_rejects_invalid_output_limits(limit: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        SnappyCompressor(max_output_size=limit)


@pytest.mark.parametrize("method_name", ["compress", "decompress"])
def test_snappy_compressor_rejects_non_bytes_like_input(method_name: str) -> None:
    compressor = SnappyCompressor()

    with pytest.raises(TypeError, match="data must be bytes-like"):
        getattr(compressor, method_name)("bluetape")


def test_snappy_compressor_enforces_exact_output_limits() -> None:
    payload = b"x" * 4096
    encoded = SnappyCompressor().compress(payload)

    assert SnappyCompressor(max_output_size=len(payload)).decompress(encoded) == payload
    with pytest.raises(DecompressionLimitError):
        SnappyCompressor(max_output_size=len(payload) - 1).decompress(encoded)


def test_snappy_compressor_rejects_invalid_truncated_and_trailing_payloads() -> None:
    encoded = SnappyCompressor().compress(b"bluetape")

    for payload in (b"", b"invalid", encoded[:-1], encoded + b"trailing"):
        with pytest.raises(CompressionError) as raised:
            SnappyCompressor().decompress(payload)

        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None


def test_snappy_compressor_rejects_declared_oversize_before_decode(monkeypatch) -> None:
    import bluetape.compression.native._snappy as snappy_module

    class SnappySpy:
        @staticmethod
        def decompress_raw_len(data) -> int:
            return 9

        @staticmethod
        def decompress_raw(data):
            pytest.fail("decode must not run after an oversized declaration")

    class ProviderSpy:
        snappy = SnappySpy()

    monkeypatch.setattr(snappy_module, "_provider", ProviderSpy)

    with pytest.raises(DecompressionLimitError):
        SnappyCompressor(max_output_size=8).decompress(b"declared")
