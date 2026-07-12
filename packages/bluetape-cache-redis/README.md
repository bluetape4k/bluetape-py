# bluetape-cache-redis

English | [한국어](README.ko.md)

Opt-in Python 3.13+ Redis byte providers and bounded result envelopes for
bluetape-py. The package keeps serialization, compression, key naming, and
rollout policy under application control.

## Install

```bash
pip install "bluetape[cache-redis]"
# or
pip install bluetape-cache-redis
```

PyPI publication is currently on hold. In this repository, use
`uv sync --all-packages --locked` or install a locally built focused wheel.
The package depends on `redis==8.0.1`, `bluetape-serde`, and
`bluetape-compression`; it is excluded from the default, `dev`, and `all` meta
dependency sets.

## Result Envelopes

`ResultEnvelopeCodec` composes a caller-owned `PayloadCodec`, one explicit
envelope format, and an optional compressor. Binary v1 is the default compact
format; JSON v1 is intended for inspection and diagnostics. Both formats are
strict, versioned, complete-input parsers with a 16 MiB encoded-size default.

```python
from bluetape.cache.redis import (
    BinaryEnvelopeFormat,
    JsonEnvelopeFormat,
    ResultEnvelopeCodec,
    SyncRedisProvider,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile


class Utf8Codec:
    def encode(self, value: str) -> SerializedPayload:
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="text",
                version=1,
                content_type="text/plain; charset=utf-8",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=value.encode("utf-8"),
        )

    def decode(self, payload: SerializedPayload) -> str:
        return payload.data.decode("utf-8")


codec = ResultEnvelopeCodec(
    payload_codec=Utf8Codec(),
    envelope_format=BinaryEnvelopeFormat(),
)

with SyncRedisProvider.from_url("redis://localhost:6379/0") as provider:
    provider.set("example:result", codec.encode("owner-42", "ready"), ttl=30.0)
    stored = provider.get("example:result")
    result = None if stored is None else codec.decode(
        stored, expected_owner_token="owner-42"
    )
```

Leaving `compressor=None` records the exact `identity` algorithm. For opt-in
Zstandard writes, install `bluetape-compression[zstd]` and configure it
explicitly; a JSON envelope is selected just as explicitly:

```python
from bluetape.compression.native import ZstdCompressor

json_zstd_codec = ResultEnvelopeCodec(
    payload_codec=Utf8Codec(),
    envelope_format=JsonEnvelopeFormat(),
    compressor=ZstdCompressor(),
)
```

An owner-token mismatch returns `None`; it never tries another decoder. A
configured compressor is always used for writes. Reads select only the exact
algorithm named in the envelope from the configured writer/readers, which
supports reader-first compression migrations without content sniffing. Native
LZ4, Snappy, and Zstandard compressors remain explicit
`bluetape-compression` extras.

## Redis Providers

`SyncRedisProvider` and `AsyncRedisProvider` expose the same byte-only
operations:

- `get(key)`
- `set(key, value, ttl=...)`
- `set_if_absent(key, value, ttl=...)`
- `delete(key)`
- `delete_if_value(key, expected_value)`

All writes require a positive TTL. `set_if_absent` uses Redis `SET NX PX`.
`delete_if_value` uses one fixed Lua compare-and-delete script and deliberately
has no racy read/delete fallback when scripts are denied. Its Redis principal
therefore needs permission for the operation and `EVAL`.

```python
import asyncio

from bluetape.cache.redis import AsyncRedisProvider


async def store_result(data: bytes) -> None:
    async with AsyncRedisProvider.from_url("redis://localhost:6379/0") as provider:
        async with asyncio.timeout(2.0):
            await provider.set("example:async", data, ttl=30.0)
```

`from_url()` owns the redis-py client and closes it on context exit. Passing a
client to the constructor borrows it, so provider shutdown drains admitted
operations but leaves that client open. Async providers bind to the first
running event loop and preserve cancellation while completing one shielded
owned-client cleanup. Callers own operation deadlines, for example with
`asyncio.timeout()`.

Providers require binary redis-py clients (`decode_responses=False`). Domain
failures expose stable `RedisErrorCode` or `EnvelopeErrorCode` values and
redacted messages. The chained provider cause is a trusted diagnostic boundary
and may contain redis-py details, so do not expose or log it without caller-owned
redaction. A caller-owned `RedisObserver` can receive low-cardinality
mode, operation, outcome, error-code, and elapsed-time events; observer failure
never changes the provider result.

## Rollout Boundary

Applications should version key namespaces, deploy readers before writers when
changing an envelope format or compression algorithm, keep TTLs bounded, and
scan TTL-aware namespaces for retirement evidence. Do not use unbounded
`KEYS`. This package provides byte storage and result envelopes only; Redis
load coordination, leases, and stampede control remain issue #55 work.

## Development

```bash
uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers"
uv run pytest -m testcontainers packages/bluetape-cache-redis
uv run ruff check packages/bluetape-cache-redis
```
