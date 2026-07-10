"""Bounded compression helpers for bluetape-py."""

import importlib
import sys
from collections import deque

DEFAULT_MAX_OUTPUT_SIZE = 64 * 1024 * 1024
_INPUT_CHUNK_SIZE = 64 * 1024
_GZIP_MINIMUM_MEMBER_SIZE = 20


class CompressionError(ValueError):
    """Raised when compressed data cannot be decoded safely."""


class DecompressionLimitError(CompressionError):
    """Raised when decompressed output would exceed the caller limit."""


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
    if isinstance(max_output_size, bool) or not isinstance(max_output_size, int):
        raise TypeError("max_output_size must be an integer")
    if not 0 <= max_output_size < sys.maxsize:
        raise ValueError("max_output_size is outside the supported range")

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
    "DecompressionLimitError",
    "deflate_compress",
    "deflate_decompress",
    "gzip_compress",
    "gzip_decompress",
    "zlib_compress",
    "zlib_decompress",
]
