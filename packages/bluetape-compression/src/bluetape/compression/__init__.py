"""Bounded compression helpers for bluetape-py."""

import importlib
import sys
from collections import deque
from dataclasses import dataclass
from typing import Protocol

DEFAULT_MAX_OUTPUT_SIZE = 64 * 1024 * 1024
_INPUT_CHUNK_SIZE = 64 * 1024
_GZIP_MINIMUM_MEMBER_SIZE = 20


class CompressionError(ValueError):
    """Raised when compressed data cannot be decoded safely."""


class DecompressionLimitError(CompressionError):
    """Raised when decompressed output would exceed the caller limit."""


class Compressor(Protocol):
    """Structural contract for immutable byte compressors."""

    @property
    def algorithm(self) -> str:
        """Stable algorithm identifier."""
        ...

    @property
    def max_output_size(self) -> int:
        """Largest logical decompressed payload returned by this instance."""
        ...

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        """Compress bytes-like input."""
        ...

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        """Decompress bytes-like input within the configured bound."""
        ...


def _as_bytes(data: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    return bytes(data)


def _validate_level(level: int) -> None:
    if isinstance(level, bool) or not isinstance(level, int):
        raise TypeError("level must be an integer")
    if not -1 <= level <= 9:
        raise ValueError("level is outside the supported range")


def _validate_max_output_size(max_output_size: int) -> None:
    if isinstance(max_output_size, bool) or not isinstance(max_output_size, int):
        raise TypeError("max_output_size must be an integer")
    if not 0 <= max_output_size < sys.maxsize:
        raise ValueError("max_output_size is outside the supported range")


@dataclass(frozen=True, slots=True)
class GzipCompressor:
    """Immutable gzip compressor with bounded decompression."""

    level: int = 9
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE

    def __post_init__(self) -> None:
        _validate_level(self.level)
        _validate_max_output_size(self.max_output_size)

    @property
    def algorithm(self) -> str:
        return "gzip"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        return gzip_compress(_as_bytes(data), level=self.level)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        return gzip_decompress(_as_bytes(data), max_output_size=self.max_output_size)


@dataclass(frozen=True, slots=True)
class ZlibCompressor:
    """Immutable zlib-wrapped compressor with bounded decompression."""

    level: int = -1
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE

    def __post_init__(self) -> None:
        _validate_level(self.level)
        _validate_max_output_size(self.max_output_size)

    @property
    def algorithm(self) -> str:
        return "zlib"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        return zlib_compress(_as_bytes(data), level=self.level)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        return zlib_decompress(_as_bytes(data), max_output_size=self.max_output_size)


@dataclass(frozen=True, slots=True)
class DeflateCompressor:
    """Immutable raw DEFLATE compressor with bounded decompression."""

    level: int = -1
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE

    def __post_init__(self) -> None:
        _validate_level(self.level)
        _validate_max_output_size(self.max_output_size)

    @property
    def algorithm(self) -> str:
        return "deflate"

    def compress(self, data: bytes | bytearray | memoryview) -> bytes:
        return deflate_compress(_as_bytes(data), level=self.level)

    def decompress(self, data: bytes | bytearray | memoryview) -> bytes:
        return deflate_decompress(_as_bytes(data), max_output_size=self.max_output_size)


def _zlib():
    try:
        return importlib.import_module("zlib")
    except ImportError:
        raise CompressionError("zlib support is unavailable") from None


def gzip_compress(data: bytes | bytearray | memoryview, *, level: int = 9) -> bytes:
    """Compress bytes as a gzip member."""
    zlib = _zlib()
    compressor = zlib.compressobj(level, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    return compressor.compress(data) + compressor.flush(zlib.Z_FINISH)


def gzip_decompress(
    data: bytes | bytearray | memoryview,
    *,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
) -> bytes:
    """Decompress bounded gzip bytes."""
    return _decompress(data, max_output_size=max_output_size, format_name="gzip")


def zlib_compress(data: bytes | bytearray | memoryview, *, level: int = -1) -> bytes:
    """Compress bytes as a zlib-wrapped stream."""
    zlib = _zlib()
    compressor = zlib.compressobj(level, zlib.DEFLATED, zlib.MAX_WBITS)
    return compressor.compress(data) + compressor.flush(zlib.Z_FINISH)


def zlib_decompress(
    data: bytes | bytearray | memoryview,
    *,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
) -> bytes:
    """Decompress bounded zlib-wrapped bytes."""
    return _decompress(data, max_output_size=max_output_size, format_name="zlib")


def deflate_compress(data: bytes | bytearray | memoryview, *, level: int = -1) -> bytes:
    """Compress bytes as a raw DEFLATE stream."""
    zlib = _zlib()
    compressor = zlib.compressobj(level, zlib.DEFLATED, -zlib.MAX_WBITS)
    return compressor.compress(data) + compressor.flush(zlib.Z_FINISH)


def deflate_decompress(
    data: bytes | bytearray | memoryview,
    *,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
) -> bytes:
    """Decompress bounded raw DEFLATE bytes."""
    return _decompress(data, max_output_size=max_output_size, format_name="deflate")


def _decompress(
    data: bytes | bytearray | memoryview,
    *,
    max_output_size: int,
    format_name: str,
) -> bytes:
    _validate_max_output_size(max_output_size)

    zlib = _zlib()
    wbits = {
        "gzip": 16 + zlib.MAX_WBITS,
        "zlib": zlib.MAX_WBITS,
        "deflate": -zlib.MAX_WBITS,
    }[format_name]
    gzip = format_name == "gzip"
    source = memoryview(data).cast("B")
    cursor = 0
    remaining = max_output_size
    output: list[bytes] = []
    pending: deque[memoryview] = deque()
    unused_refeed_chunk_size: int | None = None

    while True:
        decompressor = zlib.decompressobj(wbits)

        while not decompressor.eof:
            if pending:
                queued = pending.popleft()
                if unused_refeed_chunk_size is None:
                    chunk_size = min(len(queued), _INPUT_CHUNK_SIZE)
                else:
                    chunk_size = min(len(queued), unused_refeed_chunk_size)
                    unused_refeed_chunk_size = (
                        1
                        if unused_refeed_chunk_size == _GZIP_MINIMUM_MEMBER_SIZE
                        else min(_INPUT_CHUNK_SIZE, unused_refeed_chunk_size * 2)
                    )
                chunk = queued[:chunk_size]
                if chunk_size < len(queued):
                    pending.appendleft(queued[chunk_size:])
            elif cursor < len(source):
                next_cursor = min(cursor + _INPUT_CHUNK_SIZE, len(source))
                chunk = source[cursor:next_cursor]
                cursor = next_cursor
            else:
                chunk = b""

            try:
                decoded = decompressor.decompress(chunk, remaining + 1)
            except zlib.error:
                raise CompressionError("invalid compressed data") from None

            if len(decoded) > remaining:
                raise DecompressionLimitError("decompressed output exceeds max_output_size")
            if decoded:
                output.append(decoded)
                remaining -= len(decoded)

            if decompressor.unconsumed_tail:
                pending.appendleft(memoryview(decompressor.unconsumed_tail))
                continue
            if decompressor.eof:
                break
            if not chunk:
                raise CompressionError("invalid compressed data") from None

        if not gzip:
            if decompressor.unused_data or pending or cursor < len(source):
                raise CompressionError("invalid compressed data") from None
            return b"".join(output)

        if decompressor.unused_data:
            pending.appendleft(memoryview(decompressor.unused_data))
        if pending:
            unused_refeed_chunk_size = _GZIP_MINIMUM_MEMBER_SIZE
        else:
            unused_refeed_chunk_size = None
        if not pending and cursor == len(source):
            return b"".join(output)


__all__ = [
    "DEFAULT_MAX_OUTPUT_SIZE",
    "CompressionError",
    "Compressor",
    "DecompressionLimitError",
    "DeflateCompressor",
    "GzipCompressor",
    "ZlibCompressor",
    "deflate_compress",
    "deflate_decompress",
    "gzip_compress",
    "gzip_decompress",
    "zlib_compress",
    "zlib_decompress",
]
