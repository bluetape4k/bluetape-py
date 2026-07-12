# bluetape-compression

English | [한국어](README.ko.md)

Immutable byte-compressor contracts with bounded decompression for backend
Python code.

`bluetape-compression` is available from this source workspace. PyPI
publication is on hold, so the install commands below describe the intended
post-publication shape.

## Install

The base package uses only the optional stdlib `zlib` module and provides gzip,
zlib-wrapped, and raw-DEFLATE codecs. Native providers are explicit extras:

```bash
pip install bluetape-compression
pip install "bluetape-compression[lz4]"
pip install "bluetape-compression[snappy]"
pip install "bluetape-compression[zstd]"
pip install "bluetape-compression[native]"  # all three native providers
```

The `bluetape` meta distribution forwards the same choices as `compression`,
`compression-lz4`, `compression-snappy`, `compression-zstd`, and
`compression-native`. Native providers are excluded from the default,
`dev`, and `all` dependency sets.

For local workspace development:

```bash
uv sync --package bluetape-compression --extra native --locked
```

## Compressor Contract

`Compressor` is a structural `typing.Protocol`. A caller can accept any object
that exposes the same properties and methods; implementations do not need to
inherit from a package base class.

```python
from bluetape.compression import Compressor, GzipCompressor


def roundtrip(compressor: Compressor, source: bytes) -> bytes:
    return compressor.decompress(compressor.compress(source))


assert roundtrip(GzipCompressor(), b"order:42") == b"order:42"
```

Every bundled implementation is a frozen, slotted dataclass. It exposes a
stable `algorithm` identifier, accepts `bytes`, `bytearray`, or `memoryview`,
returns `bytes`, and enforces its `max_output_size` while decompressing.

| Class | Algorithm ID | Format | Level |
|---|---|---|---|
| `GzipCompressor` | `gzip` | Complete gzip members | `-1..9`, default `9` |
| `ZlibCompressor` | `zlib` | One zlib-wrapped stream | `-1..9`, default `-1` |
| `DeflateCompressor` | `deflate` | One raw DEFLATE stream | `-1..9`, default `-1` |
| `Lz4Compressor` | `lz4-frame` | Complete LZ4 frame with content size and checksum | `0..16`, default `0` |
| `SnappyCompressor` | `snappy-raw` | Raw Snappy block | fixed by provider |
| `ZstdCompressor` | `zstd-frame` | Complete Zstandard frame with content size and checksum | `1..22`, default `3` |

Import native implementations from `bluetape.compression.native`:

```python
from bluetape.compression.native import Lz4Compressor, SnappyCompressor, ZstdCompressor

compressor = ZstdCompressor(level=3, max_output_size=8 * 1024 * 1024)
encoded = compressor.compress(b"redis-value")
assert compressor.decompress(encoded) == b"redis-value"
```

The native namespace itself is importable without the providers. Constructing
a native compressor without its matching extra raises `ModuleNotFoundError`
with the exact install guidance.

## Functions and Failure Rules

The original `gzip_*`, `zlib_*`, and `deflate_*` functions remain public. The
stdlib compressor classes delegate to those functions, so existing behavior is
preserved.

- Empty input round-trips for every compressor.
- Decompression returns at most `DEFAULT_MAX_OUTPUT_SIZE` (64 MiB) unless the
  caller supplies another non-negative bound.
- Invalid, truncated, size-mismatched, or trailing payloads raise
  `CompressionError`. Output beyond the bound raises
  `DecompressionLimitError`.
- Gzip accepts complete concatenated members. The other formats require one
  complete payload and reject trailing data.
- Error messages never contain compressed payload content, and the package
  does not log caller data.
- The bound limits the logical returned payload, not total process memory.
  Callers already own the compressed input, and successful methods return a
  complete `bytes` value.

## Redis Payload Composition

Compression is intentionally separate from serialization and Redis transport:

```text
value -> serialize -> compress -> Redis bytes
Redis bytes -> decompress -> deserialize -> value
```

Choose the serializer schema and compressor configuration in application
configuration; never infer either from untrusted payload bytes. These Python
contracts preserve the same feature and failure-rule semantics used by sibling
bluetape libraries, but they do not promise cross-language wire compatibility.

## Out of Scope

- Streaming, file/path, registry, or auto-detection APIs.
- Encryption or automatic serializer/compressor negotiation.
- PyPI publication in this change.
