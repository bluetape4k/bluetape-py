"""Raw Snappy block compressor."""

from dataclasses import dataclass

from bluetape.compression import (
    DEFAULT_MAX_OUTPUT_SIZE,
    CompressionError,
    DecompressionLimitError,
    _as_bytes,
    _validate_max_output_size,
)

from ._support import load_provider, provider_call

_INSTALL_GUIDANCE = "Install bluetape-compression[snappy] to use SnappyCompressor."


def _provider():
    return load_provider("cramjam", install=_INSTALL_GUIDANCE)


@dataclass(frozen=True, slots=True)
class SnappyCompressor:
    """Immutable raw Snappy compressor with declared-size preflight."""

    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE

    def __post_init__(self) -> None:
        _validate_max_output_size(self.max_output_size)
        _provider()

    @property
    def algorithm(self) -> str:
        return "snappy-raw"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        source = _as_bytes(data)
        provider = _provider()
        return provider_call(
            lambda: bytes(provider.snappy.compress_raw(source)),
            message="compression failed",
        )

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        source = _as_bytes(data)
        provider = _provider()
        declared_size = provider_call(
            lambda: provider.snappy.decompress_raw_len(source),
            message="invalid compressed data",
        )
        if declared_size > self.max_output_size:
            raise DecompressionLimitError("decompressed output exceeds max_output_size")

        decoded = provider_call(
            lambda: bytes(provider.snappy.decompress_raw(source)),
            message="invalid compressed data",
        )
        if len(decoded) != declared_size:
            raise CompressionError("invalid compressed data")
        return decoded
