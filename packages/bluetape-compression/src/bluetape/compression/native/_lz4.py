"""LZ4 frame compressor."""

from dataclasses import dataclass

from bluetape.compression import (
    DEFAULT_MAX_OUTPUT_SIZE,
    CompressionError,
    DecompressionLimitError,
    _as_bytes,
    _validate_max_output_size,
)

from ._support import load_provider, provider_call

_INPUT_CHUNK_SIZE = 64 * 1024
_INSTALL_GUIDANCE = "Install bluetape-compression[lz4] to use Lz4Compressor."


def _provider():
    return load_provider("lz4.frame", install=_INSTALL_GUIDANCE)


def _validate_compression_level(compression_level: int) -> None:
    if isinstance(compression_level, bool) or not isinstance(compression_level, int):
        raise TypeError("compression_level must be an integer")
    if not 0 <= compression_level <= 16:
        raise ValueError("compression_level is outside the supported range")


@dataclass(frozen=True, slots=True)
class Lz4Compressor:
    """Immutable complete-frame LZ4 compressor with bounded decompression."""

    compression_level: int = 0
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE

    def __post_init__(self) -> None:
        _validate_compression_level(self.compression_level)
        _validate_max_output_size(self.max_output_size)
        _provider()

    @property
    def algorithm(self) -> str:
        return "lz4-frame"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        source = _as_bytes(data)
        provider = _provider()
        return provider_call(
            lambda: provider.compress(
                source,
                compression_level=self.compression_level,
                content_checksum=True,
                store_size=True,
                return_bytearray=False,
            ),
            message="compression failed",
        )

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        source = memoryview(_as_bytes(data))
        provider = _provider()
        decoder = provider_call(
            provider.LZ4FrameDecompressor,
            message="invalid compressed data",
        )
        cursor = 0
        remaining = self.max_output_size
        output: list[bytes] = []

        while True:
            if decoder.needs_input and cursor < len(source):
                next_cursor = min(cursor + _INPUT_CHUNK_SIZE, len(source))
                chunk = source[cursor:next_cursor]
                cursor = next_cursor
            else:
                chunk = b""

            decoded = provider_call(
                lambda chunk=chunk, remaining=remaining: decoder.decompress(
                    chunk, max_length=remaining + 1
                ),
                message="invalid compressed data",
            )
            if len(decoded) > remaining:
                raise DecompressionLimitError("decompressed output exceeds max_output_size")
            if decoded:
                output.append(decoded)
                remaining -= len(decoded)

            if decoder.eof:
                if decoder.unused_data or cursor < len(source):
                    raise CompressionError("invalid compressed data")
                return b"".join(output)

            if not decoded and not chunk:
                raise CompressionError("invalid compressed data")
