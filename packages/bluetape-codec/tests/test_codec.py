import pytest
from bluetape.codec import (
    CodecError,
    __all__,
    base64url_decode,
    base64url_encode,
    hex_decode,
    hex_encode,
)


def test_base64url_encode_returns_unpadded_url_safe_text() -> None:
    assert base64url_encode(b"\xfb\xff") == "-_8"
    assert set(__all__) == {
        "CodecError",
        "base64url_encode",
        "base64url_decode",
        "hex_encode",
        "hex_decode",
    }


@pytest.mark.parametrize("data", [b"", b"a", b"ab", b"abc", b"\xfb\xff"])
def test_base64url_round_trips_canonical_text(data: bytes) -> None:
    encoded = base64url_encode(data)

    assert base64url_decode(encoded) == data
    assert base64url_decode(base64url_encode(data, padded=True), padded=True) == data


@pytest.mark.parametrize(
    "value,padded",
    [
        ("a", False),
        ("ab=", False),
        ("ab+c", False),
        ("ab c", False),
        ("__", False),
        ("YQ", True),
        ("YQ==", False),
        ("YQ=", True),
        ("YR==", True),
        ("YQ==\n", True),
        ("한글", False),
    ],
)
def test_base64url_decode_rejects_malformed_or_noncanonical_text(value: str, padded: bool) -> None:
    with pytest.raises(CodecError):
        base64url_decode(value, padded=padded)


def test_hex_round_trips_bytes_and_normalizes_output() -> None:
    assert hex_encode(bytearray(b"\x0a\xff")) == "0aff"
    assert hex_encode(memoryview(b"")) == ""
    assert hex_decode("0aFF") == b"\x0a\xff"


@pytest.mark.parametrize("value", ["f", "0x0a", "0a ff", "0a-ff", "0g", "한글"])
def test_hex_decode_rejects_non_strict_text(value: str) -> None:
    with pytest.raises(CodecError):
        hex_decode(value)


def test_codec_errors_have_the_documented_base_class() -> None:
    assert issubclass(CodecError, ValueError)


@pytest.mark.parametrize("function,args", [(base64url_decode, (b"YQ",)), (hex_decode, (b"0a",))])
def test_text_decoders_preserve_native_type_errors(function, args: tuple[bytes]) -> None:
    with pytest.raises(TypeError):
        function(*args)  # type: ignore[arg-type]
