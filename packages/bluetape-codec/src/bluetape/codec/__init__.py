"""Strict codec helpers for bluetape-py."""

import base64
import binascii

_BASE64URL_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_HEX_ALPHABET = frozenset("0123456789abcdefABCDEF")


class CodecError(ValueError):
    """Raised when encoded text is malformed or non-canonical."""


def base64url_encode(data: bytes | bytearray | memoryview, *, padded: bool = False) -> str:
    """Encode bytes as canonical URL-safe Base64 text."""
    encoded = base64.urlsafe_b64encode(data).decode("ascii")
    return encoded if padded else encoded.rstrip("=")


def base64url_decode(value: str, *, padded: bool = False) -> bytes:
    """Decode canonical URL-safe Base64 text."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    if padded:
        if len(value) % 4 != 0:
            raise CodecError("invalid padded URL-safe Base64")
        padding_start = value.find("=")
        alphabet = value if padding_start == -1 else value[:padding_start]
        padding = "" if padding_start == -1 else value[padding_start:]
        if len(padding) > 2 or padding != "=" * len(padding):
            raise CodecError("invalid padded URL-safe Base64")
        normalized = value
    else:
        alphabet = value
        if "=" in value or len(value) % 4 == 1:
            raise CodecError("invalid unpadded URL-safe Base64")
        normalized = value + "=" * (-len(value) % 4)

    if not all(character in _BASE64URL_ALPHABET for character in alphabet):
        raise CodecError("invalid URL-safe Base64")

    try:
        decoded = base64.b64decode(normalized.encode("ascii"), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise CodecError("invalid URL-safe Base64") from exc

    if base64url_encode(decoded, padded=padded) != value:
        raise CodecError("non-canonical URL-safe Base64")
    return decoded


def hex_encode(data: bytes | bytearray | memoryview) -> str:
    """Encode bytes as lowercase hexadecimal text."""
    return bytes(data).hex()


def hex_decode(value: str) -> bytes:
    """Decode strict hexadecimal text."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    if len(value) % 2 != 0 or not all(character in _HEX_ALPHABET for character in value):
        raise CodecError("invalid hexadecimal text")
    return bytes.fromhex(value)


__all__ = [
    "CodecError",
    "base64url_decode",
    "base64url_encode",
    "hex_decode",
    "hex_encode",
]
