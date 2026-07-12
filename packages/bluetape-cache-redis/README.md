# bluetape-cache-redis

English | [한국어](README.ko.md)

Opt-in Python 3.13+ Redis byte providers, bounded result envelopes, and sync/
async load coordinators for bluetape-py. The package keeps serialization,
compression, key naming, and rollout policy under application control.

## Install

```bash
pip install "bluetape[cache-redis]"
# or
pip install bluetape-cache-redis
```

PyPI publication is currently on hold. In this repository, use
`uv sync --all-packages --locked` or install a locally built focused wheel.
The package depends on `bluetape-cache==0.1.0`, `redis==8.0.1`,
`bluetape-serde`, and `bluetape-compression`; it is excluded from the default,
`dev`, and `all` meta dependency sets.

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

`decode_matching()` returns `ResultEnvelopeMatch(value=...)` for a matching
owner, including `ResultEnvelopeMatch(value=None)` for a legitimate decoded
`None`, while an owner-token mismatch returns `None`. The compatibility
`decode()` method also returns `None` for a mismatch and never tries another
decoder. A
configured compressor is always used for writes. Reads select only the exact
algorithm named in the envelope from the configured writer/readers, which
supports reader-first compression migrations without content sniffing. Native
LZ4, Snappy, and Zstandard compressors remain explicit
`bluetape-compression` extras.

## Redis Load Coordination

`SyncRedisLoadCoordinator` and `AsyncRedisLoadCoordinator` combine a caller-owned
local cache, Redis provider, result codec, and observer. A local hit performs no
Redis I/O. A cold miss joins the local same-key flight, then uses a bounded Redis
snapshot/lease/load/atomic-publish state machine so independent processes
usually run one loader. Install with `pip install bluetape-cache-redis` or
`pip install "bluetape[cache-redis]"`. The focused package depends on
`bluetape-cache==0.1.0`; the default meta install remains core-only and
Redis-free. Both focused install forms install `bluetape-cache` transitively.

The namespace is part of the wire contract. Use a versioned pseudonym such as
`orders:prod:tenant-a:order-v3`, and share one compatible codec and coordination
configuration among participants. The `ttl` argument controls only the local
cache entry; Redis result and lease TTLs come from `RedisLoadOptions`.

<!-- sync-coordination-example -->
```python
from bluetape.cache import TTLCache
from bluetape.cache.redis import (
    RedisLoadOptions,
    ResultEnvelopeCodec,
    SyncRedisLoadCoordinator,
    SyncRedisProvider,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile


class Utf8Codec:
    def encode(self, value: str) -> SerializedPayload:
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="text",
                version=1,
                content_type="text/plain",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=value.encode(),
        )

    def decode(self, payload: SerializedPayload) -> str:
        return payload.data.decode()


def load_order(key: str) -> str:
    return f"loaded:{key}"

cache = TTLCache[str, str](default_ttl=60.0, max_size=1_000)
with SyncRedisProvider.from_url(
    "redis://localhost:6379/0",
    socket_connect_timeout=0.2,
    socket_timeout=0.3,
    retry_on_timeout=False,
) as provider:
    coordinator = SyncRedisLoadCoordinator(
        cache,
        provider,
        ResultEnvelopeCodec(payload_codec=Utf8Codec()),
        options=RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3"),
    )
    value = coordinator.get_or_load("order-42", load_order, ttl=30.0)
```

<!-- async-coordination-example -->
```python
from bluetape.cache import AsyncTTLCache
from bluetape.cache.redis import (
    AsyncRedisLoadCoordinator,
    AsyncRedisProvider,
    RedisLoadOptions,
    ResultEnvelopeCodec,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile


class Utf8Codec:
    def encode(self, value: str) -> SerializedPayload:
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="text",
                version=1,
                content_type="text/plain",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=value.encode(),
        )

    def decode(self, payload: SerializedPayload) -> str:
        return payload.data.decode()


async def load_order(key: str) -> str:
    return f"loaded:{key}"

async def coordinated_load() -> str:
    cache = AsyncTTLCache[str, str](default_ttl=60.0, max_size=1_000)
    async with AsyncRedisProvider.from_url(
        "redis://localhost:6379/0",
        socket_connect_timeout=0.2,
        socket_timeout=0.3,
        retry_on_timeout=False,
    ) as provider:
        coordinator = AsyncRedisLoadCoordinator(
            cache,
            provider,
            ResultEnvelopeCodec(payload_codec=Utf8Codec()),
            options=RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3"),
        )
        return await coordinator.get_or_load("order-42", load_order, ttl=30.0)
```

Attempts, polls, command time, and encoded artifacts are bounded. Redis failures
do not silently fall back to an uncoordinated cold load. A sync timeout cannot
interrupt a loader after lease acquisition. Async waiters may cancel
independently; last-waiter cancellation follows the cache-owned flight and
shielded-cleanup contract. Lease loss prevents publish. This is no L2 cache and
no fencing mechanism; it is no distributed invalidation or transaction around
loader side effects.

| Outcome | Caller-visible behavior |
|---|---|
| Local hit | Returns the local value with no Redis command or coordination event. |
| Loaded | Publishes atomically, returns the value, and lets the outer cache store it with the caller's local `ttl`. |
| Result reused | Returns a matching completed result without calling the loader and stores it locally. |
| Lease lost | Does not publish, but returns the caller's loaded value and stores it only in that local cache. |
| Timeout/Redis/envelope failure | Raises the stable timeout, provider, or envelope exception; there is no cold-load fallback. |
| Loader failure | Preserves the original loader exception; cleanup failure adds only a static note and `cleanup_failed` event flag. |
| Async cancellation | Preserves `CancelledError`; the cache-owned flight performs at most one shielded owner cleanup. |

Events contain only bounded, low-cardinality fields. `cleanup_failed` reports
best-effort cleanup failure without exposing raw keys or values; callers attach
static external route labels. Do not put sensitive identifiers in namespaces or
keys. Production Redis must not be unauthenticated. Use `rediss://` with a
trusted CA, required peer-certificate and hostname verification (for example,
`ssl_ca_certs=...`, `ssl_cert_reqs="required"`, and
`ssl_check_hostname=True`). Never downgrade or fall back to plaintext. Use an
ACL principal that allows required key commands and `EVAL` for the fixed scripts.

To roll back, stop coordinated writers, restore the previous version, retain
compatible readers, wait at least
`max(lease_ttl, result_ttl) + redis_io_timeout`, use bounded `SCAN` over the
retired namespace, remove confirmed remnants with `UNLINK`, and retire old
readers only after expiry and telemetry evidence.

### Contract and operations checklist

- The cache, provider, codec, and observer are borrowed. The coordinator has no
  `close()` method; close only the resources your application owns.
- Use one local cache and one coordinator configuration per logical cache.
  Conflicting configurations are unsupported. Every participant must use
  compatible codecs and options.
- The namespace must identify application, environment or tenant, and schema
  version. Its SHA-256 digest and each key digest are pseudonyms, not
  confidentiality. Redis artifacts are unauthenticated, so caller codecs must
  validate expected metadata and must not perform unsafe deserialization.
- Local cache mutation is not distributed invalidation. A two-namespace rollout
  may run duplicate loaders (`loader_count == 2`); deploy compatible readers
  before switching writers and keep the overlap bounded.
- Local hits emit no coordination event. Each cache-owned distributed flight
  emits exactly one terminal event. Alert on stable provider or coordination
  error codes with attempts, polls, elapsed time, and `cleanup_failed`. Attach
  static external route labels; diagnostics must exclude raw namespaces, keys,
  tokens, endpoints, exceptions, and artifact metadata.
- Redis command policy must use finite connect/socket timeouts with zero retry.
  `BlockingConnectionPool` is unsupported because pool acquisition is outside
  those command bounds. TLS must not downgrade. The runtime ACL should restrict `GET`, `SET`, `DEL`,
  `EXISTS`, `STRLEN`, `GETRANGE`, and `EVAL` to
  `bluetape:cache:coord:<sha256(namespace)>:*`. Grant `SCAN` and `UNLINK` only
  to the bounded rollback operator.
- Stable `RedisProviderError`, `EnvelopeError`, `RedisCoordinationError`, and
  their error codes are the caller handling surface.

Rollback is a quiescence gate: (1) stop old participants or route all traffic
to the new namespace; (2) wait the TTL/I/O interval above; (3) verify event and
readiness quiescence, aborting immediately if traffic resumes; (4) bounded
`SCAN` only the retired digest prefix; (5) batch `UNLINK`, or bounded `DEL`
fallback, never `KEYS` or the active namespace; (6) record scanned, deleted,
and remaining counts, then recheck quiescence; (7) on cleanup/recovery failure,
alert on stable codes and keep traffic disabled until readiness and
remaining-count checks pass.

After confirming the retired namespace and quiescence, derive and print the
prefix before scanning. Review each bounded batch and its counts before
uncommenting the `UNLINK` command:

```bash
: "${REDISCLI_AUTH:?set the operator ACL password in REDISCLI_AUTH}"
: "${REDIS_CA_CERT:?set the trusted CA certificate path}"
: "${REDIS_HOST:?set the Redis hostname}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_USER="${REDIS_USER:-coordination-operator}"
redis_args=(--tls --cacert "$REDIS_CA_CERT" --user "$REDIS_USER" -h "$REDIS_HOST" -p "$REDIS_PORT")
namespace='orders:prod:tenant-a:order-v2'
namespace_id="$(printf '%s' "$namespace" | shasum -a 256 | awk '{print $1}')"
pattern="bluetape:cache:coord:${namespace_id}:*"
printf 'retired pattern: %s\n' "$pattern"
keys_file="$(mktemp)"
trap 'rm -f "$keys_file"' EXIT
redis-cli "${redis_args[@]}" --scan --pattern "$pattern" --count 100 > "$keys_file"
scanned="$(wc -l < "$keys_file" | tr -d ' ')"
printf 'scanned: %s\n' "$scanned"
# if [ -s "$keys_file" ]; then
#   deleted="$(xargs -n 100 redis-cli "${redis_args[@]}" UNLINK < "$keys_file" | awk '{sum += $1} END {print sum + 0}')"
#   printf 'deleted: %s\n' "$deleted"
# fi
remaining="$(redis-cli "${redis_args[@]}" --scan --pattern "$pattern" --count 100 | wc -l | tr -d ' ')"
printf 'remaining: %s\n' "$remaining"
```

Never run this with the active namespace digest. Record scanned, deleted, and
remaining counts, then repeat the quiescence/readiness check.

## Redis Providers

`SyncRedisProvider` and `AsyncRedisProvider` expose the same byte-only
operations:

- `get(key)`
- `set(key, value, ttl=...)`
- `set_if_absent(key, value, ttl=...)`
- `delete(key)`
- `delete_if_value(key, expected_value)`
- `coordination_snapshot(marker_key, result_key, ..., max_result_size=...)`
- `publish_if_value(condition_key, expected_value, ..., ttl=...)`

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
`KEYS`. Coordination follows the same versioned namespace and bounded TTL
rules. Local mutation remains local and is not distributed invalidation.

## Development

```bash
uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers"
uv run pytest -m testcontainers packages/bluetape-cache-redis
uv run ruff check packages/bluetape-cache-redis
```
