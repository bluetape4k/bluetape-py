import gzip
import sys

import bluetape.compression as compression
import pytest
from bluetape.compression import (
    DEFAULT_MAX_OUTPUT_SIZE,
    CompressionError,
    DecompressionLimitError,
    __all__,
    deflate_compress,
    deflate_decompress,
    gzip_compress,
    gzip_decompress,
    zlib_compress,
    zlib_decompress,
)


def test_gzip_compress_exports_the_bounded_public_surface() -> None:
    assert gzip_compress(b"bluetape")
    assert DEFAULT_MAX_OUTPUT_SIZE == 64 * 1024 * 1024
    assert set(__all__) == {
        "DEFAULT_MAX_OUTPUT_SIZE",
        "CompressionError",
        "DecompressionLimitError",
        "gzip_compress",
        "gzip_decompress",
        "zlib_compress",
        "zlib_decompress",
        "deflate_compress",
        "deflate_decompress",
    }


@pytest.mark.parametrize(
    ("compress", "decompress"),
    [
        (gzip_compress, gzip_decompress),
        (zlib_compress, zlib_decompress),
        (deflate_compress, deflate_decompress),
    ],
)
@pytest.mark.parametrize("data", [b"", b"bluetape", bytes(range(256))])
def test_compression_round_trips_bytes_like_payloads(compress, decompress, data: bytes) -> None:
    assert decompress(compress(bytearray(data))) == data
    assert decompress(compress(memoryview(data))) == data


def test_compression_errors_have_the_documented_hierarchy() -> None:
    assert issubclass(CompressionError, ValueError)
    assert issubclass(DecompressionLimitError, CompressionError)


@pytest.mark.parametrize(
    ("compress", "decompress"),
    [
        (gzip_compress, gzip_decompress),
        (zlib_compress, zlib_decompress),
        (deflate_compress, deflate_decompress),
    ],
)
def test_decompression_rejects_invalid_and_truncated_payloads(compress, decompress) -> None:
    for payload in (b"not a compressed payload", compress(b"bluetape")[:-1]):
        with pytest.raises(CompressionError) as raised:
            decompress(payload)

        assert "payload" not in str(raised.value)
        assert raised.value.__cause__ is None
        assert raised.value.__suppress_context__ is True


@pytest.mark.parametrize(
    ("compress", "decompress"),
    [
        (gzip_compress, gzip_decompress),
        (zlib_compress, zlib_decompress),
        (deflate_compress, deflate_decompress),
    ],
)
def test_decompression_enforces_a_single_output_budget(compress, decompress) -> None:
    payload = b"x" * 4096
    compressed = compress(payload)

    assert decompress(compressed, max_output_size=len(payload)) == payload
    with pytest.raises(DecompressionLimitError) as raised:
        decompress(compressed, max_output_size=len(payload) - 1)

    assert raised.value.__cause__ is None


@pytest.mark.parametrize("limit", [True, False, 1.5, -1, sys.maxsize])
def test_decompression_rejects_invalid_output_limits(limit: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        gzip_decompress(gzip_compress(b""), max_output_size=limit)  # type: ignore[arg-type]


def test_decompression_accepts_zero_for_empty_payload_and_the_largest_safe_limit() -> None:
    empty = gzip_compress(b"")

    assert gzip_decompress(empty, max_output_size=0) == b""
    assert gzip_decompress(empty, max_output_size=sys.maxsize - 1) == b""


def test_gzip_accepts_complete_concatenated_members_with_one_shared_limit() -> None:
    first = gzip_compress(b"first")
    second = gzip_compress(b"second")

    assert gzip_decompress(first + second, max_output_size=11) == b"firstsecond"
    with pytest.raises(DecompressionLimitError):
        gzip_decompress(first + second, max_output_size=10)


@pytest.mark.parametrize("decompress", [zlib_decompress, deflate_decompress])
def test_zlib_and_raw_deflate_reject_trailing_bytes(decompress) -> None:
    compressor = zlib_compress if decompress is zlib_decompress else deflate_compress

    with pytest.raises(CompressionError):
        decompress(compressor(b"bluetape") + b"trailing")


def test_gzip_rejects_partial_second_member_and_terminal_garbage() -> None:
    first = gzip_compress(b"first")
    second = gzip_compress(b"second")

    for payload in (first + second[:-1], first + b"garbage", first + b"\x00"):
        with pytest.raises(CompressionError):
            gzip_decompress(payload)


def test_gzip_continues_after_a_member_ending_at_the_input_chunk_boundary() -> None:
    first_payload = bytes(range(256)) * 255 + bytes(range(233))
    first = gzip.compress(first_payload, compresslevel=0, mtime=0)
    second = gzip_compress(b"next member")

    assert len(first) == 64 * 1024
    assert gzip_decompress(first + second) == first_payload + b"next member"


def test_gzip_many_members_reprocesses_at_most_one_unused_input_window(monkeypatch) -> None:
    members = [gzip_compress(bytes([value % 251])) for value in range(512)]
    payload = b"".join(members)
    expected = bytes(value % 251 for value in range(512))
    actual_zlib = compression._zlib()
    presented = 0
    calls = 0

    class CountingDecompressor:
        def __init__(self, delegate) -> None:
            self._delegate = delegate

        def decompress(self, data, max_length: int) -> bytes:
            nonlocal calls, presented
            calls += 1
            presented += len(data)
            return self._delegate.decompress(data, max_length)

        def __getattr__(self, name: str):
            return getattr(self._delegate, name)

    class CountingZlib:
        def decompressobj(self, wbits: int):
            return CountingDecompressor(actual_zlib.decompressobj(wbits))

        def __getattr__(self, name: str):
            return getattr(actual_zlib, name)

    monkeypatch.setattr(compression, "_zlib", lambda: CountingZlib())

    assert gzip_decompress(payload) == expected
    assert presented <= len(payload) * 2
    assert calls <= len(members) * 8


def test_gzip_unused_tail_uses_bounded_exponential_refeeding(monkeypatch) -> None:
    first = gzip_compress(b"first")
    second_payload = bytes(range(256)) * 512
    payload = first + gzip.compress(second_payload, compresslevel=0, mtime=0)
    actual_zlib = compression._zlib()
    calls = 0

    class CountingDecompressor:
        def __init__(self, delegate) -> None:
            self._delegate = delegate

        def decompress(self, data, max_length: int) -> bytes:
            nonlocal calls
            calls += 1
            return self._delegate.decompress(data, max_length)

        def __getattr__(self, name: str):
            return getattr(self._delegate, name)

    class CountingZlib:
        def decompressobj(self, wbits: int):
            return CountingDecompressor(actual_zlib.decompressobj(wbits))

        def __getattr__(self, name: str):
            return getattr(actual_zlib, name)

    monkeypatch.setattr(compression, "_zlib", lambda: CountingZlib())

    assert gzip_decompress(payload) == b"first" + second_payload
    assert calls < 32


def test_compression_helpers_fail_closed_when_zlib_is_unavailable(monkeypatch) -> None:
    def unavailable(_: str):
        raise ModuleNotFoundError

    monkeypatch.setattr(compression.importlib, "import_module", unavailable)

    for helper in (
        gzip_compress,
        gzip_decompress,
        zlib_compress,
        zlib_decompress,
        deflate_compress,
        deflate_decompress,
    ):
        with pytest.raises(CompressionError) as raised:
            helper(b"")

        assert raised.value.__cause__ is None
        assert raised.value.__suppress_context__ is True


def test_invalid_output_limits_fail_before_optional_backend_resolution(monkeypatch) -> None:
    def unavailable(_: str):
        raise ModuleNotFoundError

    monkeypatch.setattr(compression.importlib, "import_module", unavailable)

    with pytest.raises(TypeError):
        gzip_decompress(b"", max_output_size=True)


@pytest.mark.parametrize("compress", [gzip_compress, zlib_compress, deflate_compress])
def test_compression_preserves_native_level_validation(compress) -> None:
    with pytest.raises(ValueError):
        compress(b"", level=10)
    with pytest.raises(TypeError):
        compress(b"", level="9")  # type: ignore[arg-type]
