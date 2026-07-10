# bluetape-codec

Strict stdlib codec helpers for backend Python code.

`bluetape-codec` is available from this source workspace. PyPI publication is
on hold, so `pip install bluetape-codec` and `pip install "bluetape[codec]"`
describe the intended post-publication install shape.

## Local Usage

```bash
uv sync --all-packages
```

```python
from bluetape.codec import base64url_decode, base64url_encode, hex_decode, hex_encode

token = base64url_encode(b"order:42")
assert base64url_decode(token) == b"order:42"
assert hex_encode(b"\x0a\xff") == "0aff"
assert hex_decode("0aFF") == b"\x0a\xff"
```

## Contract

- `base64url_encode` emits URL-safe Base64 (`-` and `_`) without padding by
  default. Pass `padded=True` to retain canonical `=` padding.
- `base64url_decode` requires the matching shape: default decode rejects `=`;
  padded decode requires canonical four-character grouping. Both reject
  whitespace, standard Base64 alphabet characters, malformed length, and
  non-canonical unused pad bits.
- `hex_encode` emits lowercase hexadecimal. `hex_decode` accepts ASCII upper
  and lowercase hex digits only; it rejects prefixes, whitespace, separators,
  odd lengths, and non-ASCII text.
- Malformed text raises `CodecError`. Wrong text argument types keep native
  `TypeError`.

## Unsupported

- No Base58/Base62 helpers.
- No permissive decoder mode.
- No PyPI publication in this change.
