# bluetape-codec

[English](README.md) | 한국어

backend Python code를 위한 엄격한 표준 라이브러리 codec helper입니다.

`bluetape-codec`는 이 source workspace에서 사용할 수 있습니다. PyPI publication은 보류 중이므로 `pip install bluetape-codec`와 `pip install "bluetape[codec]"`는 publication 이후의 의도된 install shape를 설명합니다.

## 로컬 사용

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

## 계약

- `base64url_encode`는 기본적으로 padding 없이 URL-safe Base64(`-`, `_`)를 출력합니다. canonical `=` padding을 유지하려면 `padded=True`를 전달합니다.
- `base64url_decode`는 대응하는 형태를 요구합니다. 기본 decode는 `=`를 거부하고, padded decode는 canonical four-character grouping을 요구합니다. 두 방식 모두 whitespace, standard Base64 alphabet character, 잘못된 길이, non-canonical unused pad bit를 거부합니다.
- `hex_encode`는 lowercase hexadecimal을 출력합니다. `hex_decode`는 ASCII upper/lowercase hex digit만 허용하며 prefix, whitespace, separator, 홀수 길이, non-ASCII text를 거부합니다.
- malformed text는 `CodecError`를 발생시킵니다. 잘못된 text argument type은 native `TypeError`를 유지합니다.

## 지원하지 않는 항목

- Base58/Base62 helper는 제공하지 않습니다.
- permissive decoder mode는 제공하지 않습니다.
- 이 변경에서는 PyPI publication을 수행하지 않습니다.
