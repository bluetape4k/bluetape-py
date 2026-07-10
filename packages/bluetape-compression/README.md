# bluetape-compression

Bounded stdlib compression helpers for backend Python code.

`bluetape-compression` is available from this source workspace. PyPI
publication is on hold, so `pip install bluetape-compression` and `pip install
"bluetape[compression]"` describe the intended post-publication install shape.

## Local Usage

```bash
uv sync --all-packages
```

```python
from bluetape.compression import gzip_compress, gzip_decompress

payload = gzip_compress(b"order:42")
assert gzip_decompress(payload) == b"order:42"
```

## Contract

- `gzip_*` writes and reads gzip members; decode accepts complete concatenated
  gzip members only.
- `zlib_*` writes and reads zlib-wrapped streams. `deflate_*` writes and reads
  raw DEFLATE streams. Neither format auto-detects input or accepts trailing
  bytes.
- Decompression returns at most `DEFAULT_MAX_OUTPUT_SIZE` (64 MiB) by default.
  Pass `max_output_size` to set a smaller logical returned-payload limit. It is
  not a process-memory ceiling: callers already own the compressed bytes and
  this bytes-returning API retains the successful result.
- Invalid, truncated, and trailing payloads raise `CompressionError`; output
  beyond the limit raises `DecompressionLimitError`. Error messages do not
  include compressed payload content.
- The package requires a Python build with optional stdlib `zlib` support.
  `import bluetape.compression` remains available without it; calling a helper
  then raises `CompressionError`.

## Unsupported

- No streaming, file/path, registry, or auto-detection API.
- No zstd, lz4, snappy, encryption, or checksums.
- No PyPI publication in this change.
