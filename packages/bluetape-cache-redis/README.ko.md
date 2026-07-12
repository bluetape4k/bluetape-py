# bluetape-cache-redis

[English](README.md) | 한국어

bluetape-py용 Python 3.13+ 선택형 Redis 바이트 provider와 크기 제한 result
envelope를 제공합니다. 직렬화, 압축, key 이름, rollout 정책은 애플리케이션이
소유합니다.

## 설치

```bash
pip install "bluetape[cache-redis]"
# 또는
pip install bluetape-cache-redis
```

현재 PyPI 배포는 보류 중입니다. 이 저장소에서는
`uv sync --all-packages --locked`를 사용하거나 로컬에서 빌드한 focused wheel을
설치합니다. 이 패키지는 `redis==8.0.1`, `bluetape-serde`,
`bluetape-compression`에 의존하며 meta 패키지의 기본, `dev`, `all` 의존성에는
포함되지 않습니다.

## Result Envelope

`ResultEnvelopeCodec`은 호출자가 소유하는 `PayloadCodec`, 명시적인 envelope
format 하나, 선택적인 compressor를 조합합니다. 기본값인 binary v1은 작은
payload에 적합하고 JSON v1은 검사와 진단에 적합합니다. 두 format 모두 버전과
크기 제한을 확인하고 입력 전체를 소비하는 strict parser이며, 기본 encoded-size
제한은 16 MiB입니다.

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

`compressor=None`을 유지하면 정확한 `identity` algorithm을 기록합니다. 선택형
Zstandard write에는 `bluetape-compression[zstd]`를 설치하고 명시적으로 설정합니다.
JSON envelope도 같은 방식으로 명시해서 선택합니다.

```python
from bluetape.compression.native import ZstdCompressor

json_zstd_codec = ResultEnvelopeCodec(
    payload_codec=Utf8Codec(),
    envelope_format=JsonEnvelopeFormat(),
    compressor=ZstdCompressor(),
)
```

owner token이 다르면 다른 decoder를 시도하지 않고 `None`을 반환합니다. 설정한
compressor는 write에 항상 사용합니다. Read는 envelope에 기록된 algorithm과
일치하는 writer/reader만 선택하므로 content sniffing 없이 reader-first 압축
migration을 수행할 수 있습니다. Native LZ4, Snappy, Zstandard compressor는 계속
명시적인 `bluetape-compression` extra로만 설치합니다.

## Redis Provider

`SyncRedisProvider`와 `AsyncRedisProvider`는 같은 byte-only operation을
제공합니다.

- `get(key)`
- `set(key, value, ttl=...)`
- `set_if_absent(key, value, ttl=...)`
- `delete(key)`
- `delete_if_value(key, expected_value)`

모든 write에는 양의 TTL이 필요합니다. `set_if_absent`는 Redis `SET NX PX`를
사용합니다. `delete_if_value`는 고정된 Lua compare-and-delete script 하나를
사용하며, script 권한이 없을 때 경쟁 조건이 있는 read/delete 방식으로
fallback하지 않습니다. 따라서 Redis principal에는 해당 operation과 `EVAL` 권한이
필요합니다.

```python
import asyncio

from bluetape.cache.redis import AsyncRedisProvider


async def store_result(data: bytes) -> None:
    async with AsyncRedisProvider.from_url("redis://localhost:6379/0") as provider:
        async with asyncio.timeout(2.0):
            await provider.set("example:async", data, ttl=30.0)
```

`from_url()`로 만든 provider는 redis-py client를 소유하고 context 종료 시
닫습니다. Constructor에 client를 전달하면 빌린 것으로 간주하므로, provider를
종료할 때 이미 수락한 operation을 비우되 client는 닫지 않습니다. Async provider는
처음 사용한 event loop에 귀속되며 cancellation을 보존하면서 소유한 client의
cleanup을 한 번만 shield 처리해 끝냅니다. Operation deadline은 호출자가
`asyncio.timeout()` 같은 방식으로 소유합니다.

Provider에는 binary redis-py client(`decode_responses=False`)가 필요합니다. Domain
실패는 안정적인 `RedisErrorCode` 또는 `EnvelopeErrorCode`와 redacted message를
제공합니다. Chained provider cause는 신뢰하는 진단 경계이며 redis-py 상세 정보를
포함할 수 있으므로, 호출자가 redaction하기 전에는 외부에 노출하거나 기록하지
않습니다. 호출자가 소유한 `RedisObserver`는 mode, operation, outcome, error
code, elapsed time으로 구성된 low-cardinality event를 받을 수 있습니다. Observer
실패는 provider 결과를 바꾸지 않습니다.

## Rollout 경계

애플리케이션은 key namespace에 버전을 부여하고, envelope format이나 압축
algorithm을 바꿀 때 reader를 writer보다 먼저 배포하며, TTL을 제한해야 합니다.
이전 namespace 제거 근거는 TTL을 고려한 scan으로 수집하고 무제한 `KEYS`는
사용하지 않습니다. 이 패키지는 byte storage와 result envelope만 제공합니다.
Redis load coordination, lease, stampede 제어는 issue #55 범위입니다.

## 개발

```bash
uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers"
uv run pytest -m testcontainers packages/bluetape-cache-redis
uv run ruff check packages/bluetape-cache-redis
```
