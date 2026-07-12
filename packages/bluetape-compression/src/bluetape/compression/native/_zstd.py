"""Zstandard frame compressor."""

from dataclasses import dataclass

from bluetape.compression import (
    DEFAULT_MAX_OUTPUT_SIZE,
    CompressionError,
    DecompressionLimitError,
    _as_bytes,
    _validate_max_output_size,
)

from ._support import load_provider, provider_call

_INSTALL_GUIDANCE = "Install bluetape-compression[zstd] to use ZstdCompressor."


def _provider():
    return load_provider("zstandard", install=_INSTALL_GUIDANCE)


def _validate_level(level: int) -> None:
    if isinstance(level, bool) or not isinstance(level, int):
        raise TypeError("level must be an integer")
    if not 1 <= level <= 22:
        raise ValueError("level is outside the supported range")


@dataclass(frozen=True, slots=True)
class ZstdCompressor:
    """Immutable checksummed Zstandard compressor with declared-size preflight."""

    level: int = 3
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE

    def __post_init__(self) -> None:
        _validate_level(self.level)
        _validate_max_output_size(self.max_output_size)
        _provider()

    @property
    def algorithm(self) -> str:
        return "zstd-frame"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        source = _as_bytes(data)
        provider = _provider()
        return provider_call(
            lambda: provider.ZstdCompressor(
                level=self.level,
                write_content_size=True,
                write_checksum=True,
            ).compress(source),
            message="compression failed",
        )

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        source = _as_bytes(data)
        provider = _provider()
        declared_size = provider_call(
            lambda: provider.frame_content_size(source),
            message="invalid compressed data",
        )
        if declared_size in (provider.CONTENTSIZE_UNKNOWN, provider.CONTENTSIZE_ERROR):
            raise CompressionError("invalid compressed data")
        if declared_size > self.max_output_size:
            raise DecompressionLimitError("decompressed output exceeds max_output_size")

        decoded = provider_call(
            lambda: provider.ZstdDecompressor().decompress(
                source,
                max_output_size=declared_size,
                allow_extra_data=False,
            ),
            message="invalid compressed data",
        )
        if len(decoded) != declared_size:
            raise CompressionError("invalid compressed data")
        return decoded
