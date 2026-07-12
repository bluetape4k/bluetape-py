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

## Redis Load Coordination

`SyncRedisLoadCoordinator`와 `AsyncRedisLoadCoordinator`는 호출자가 소유하는
local cache, Redis provider, result codec, observer를 조합합니다. Local hit에는
Redis I/O가 없습니다. Cold miss는 local same-key flight에 참여한 뒤 제한된 Redis
snapshot/lease/load/atomic-publish 상태 머신을 사용하므로 서로 다른 process에서도
보통 loader 하나만 실행합니다. `pip install bluetape-cache-redis` 또는
`pip install "bluetape[cache-redis]"`로 설치합니다. Focused 패키지는
`bluetape-cache==0.1.0`에 의존하고, 기본 meta 설치는 core-only이며 Redis-free입니다.
두 focused 설치 방식 모두 `bluetape-cache`를 transitively 설치합니다.

Namespace는 wire contract의 일부입니다.
`orders:prod:tenant-a:order-v3`처럼 버전이 있는 pseudonym을 사용하고 참여자 사이에
호환되는 codec과 설정 하나를 공유합니다. `ttl`은 local entry만 제어하며 Redis
result와 lease TTL은 `RedisLoadOptions`에서 설정합니다.

<!-- sync-coordination-example -->
```python
from bluetape.cache import TTLCache
from bluetape.cache.redis import RedisLoadOptions, ResultEnvelopeCodec, SyncRedisLoadCoordinator, SyncRedisProvider

cache = TTLCache[str, str](default_ttl=60.0, max_size=1_000)
provider = SyncRedisProvider.from_url("redis://localhost:6379/0", socket_connect_timeout=0.2, socket_timeout=0.3, retry_on_timeout=False)
coordinator = SyncRedisLoadCoordinator(cache, provider, ResultEnvelopeCodec(payload_codec=Utf8Codec()), options=RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3"))
value = coordinator.get_or_load("order-42", load_order, ttl=30.0)
provider.close()
```

<!-- async-coordination-example -->
```python
from bluetape.cache import AsyncTTLCache
from bluetape.cache.redis import AsyncRedisLoadCoordinator, AsyncRedisProvider, RedisLoadOptions, ResultEnvelopeCodec

async def coordinated_load() -> str:
    cache = AsyncTTLCache[str, str](default_ttl=60.0, max_size=1_000)
    provider = AsyncRedisProvider.from_url("redis://localhost:6379/0", socket_connect_timeout=0.2, socket_timeout=0.3, retry_on_timeout=False)
    coordinator = AsyncRedisLoadCoordinator(cache, provider, ResultEnvelopeCodec(payload_codec=Utf8Codec()), options=RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3"))
    try:
        return await coordinator.get_or_load("order-42", load_order, ttl=30.0)
    finally:
        await provider.aclose()
```

시도, polling, command 시간, encoded artifact 크기는 제한됩니다. Redis 실패를
coordination 없는 cold load로 fallback하지 않습니다. Sync timeout은 lease를 얻은
loader를 중단하지 못합니다. Async waiter는 개별 cancel할 수 있고 마지막 waiter의
cancellation은 cache-owned flight와 shielded cleanup 계약을 따릅니다. Lease를
잃으면 publish하지 않습니다. 이 기능은 no L2 cache, no fencing mechanism,
distributed invalidation이나 loader side effect transaction이 아닙니다.

Event에는 제한된 field와 redacted key digest만 포함합니다. `cleanup_failed`는 raw
key나 value 없이 best-effort cleanup 실패를 알립니다. Namespace나 key에 민감한
식별자를 넣지 않습니다. Production Redis는 unauthenticated 상태로 운영하지 않고,
TLS와 고정 script의 `EVAL` 및 필수 key command를 허용한 ACL principal을 사용합니다.

Rollback할 때는 coordinated writer를 중단하고 이전 버전을 복구하며 호환 reader를
유지한 채 `max(lease_ttl, result_ttl) + redis_io_timeout` 이상 기다립니다. 이후
폐기할 namespace를 bounded `SCAN`으로 확인해 `UNLINK`로 제거하고, 만료와 telemetry
근거가 확보된 뒤에만 이전 reader를 제거합니다.

### 계약 및 운영 점검표

- Cache, provider, codec, observer는 빌려서 사용합니다. Coordinator에는
  `close()`가 없으며 애플리케이션이 소유한 resource만 닫습니다.
- Logical cache 하나에는 local cache 하나와 coordinator 설정 하나를 사용합니다.
  서로 충돌하는 설정은 지원하지 않으며 모든 참여자는 호환되는 codec과 option을
  사용해야 합니다.
- Namespace에는 application, environment 또는 tenant, schema version을 넣습니다.
  Namespace와 key의 SHA-256 digest는 pseudonym일 뿐 confidentiality가 아닙니다.
  Redis artifact는 unauthenticated이므로 caller codec이 expected metadata를
  검증하고 unsafe deserialization을 피해야 합니다.
- Local cache mutation은 distributed invalidation이 아닙니다. 두 namespace가
  겹치는 rollout에서는 duplicate loader(`loader_count == 2`)가 가능하므로
  compatible reader를 먼저 배포하고 writer 전환 구간을 제한합니다.
- Local hit에는 coordination event가 없습니다. Cache-owned distributed flight
  하나는 terminal event를 정확히 하나 내보냅니다. Stable provider/coordination
  error code, attempts, polls, elapsed, `cleanup_failed`로 alert하고 static external
  route label을 붙입니다. 진단에는 raw namespace, key, token, endpoint, exception,
  artifact metadata를 포함하지 않습니다.
- Redis command policy는 finite connect/socket timeout과 zero retry를 사용합니다.
  TLS는 downgrade하지 않습니다. Runtime ACL은 `GET`, `SET`, `DEL`, `EXISTS`,
  `STRLEN`, `GETRANGE`, `EVAL`을
  `bluetape:cache:coord:<sha256(namespace)>:*`에만 허용합니다. `SCAN`과 `UNLINK`는
  bounded rollback operator에만 부여합니다.
- Stable `RedisProviderError`, `EnvelopeError`, `RedisCoordinationError`와 각 error
  code가 caller handling surface입니다.

Rollback은 quiescence gate입니다. (1) 이전 participant를 중단하거나 모든 traffic을
새 namespace로 전환합니다. (2) 위 TTL/I/O 간격을 기다립니다. (3) event와 readiness
quiescence를 확인하고 traffic이 재개되면 즉시 중단합니다. (4) 폐기할 digest
prefix만 bounded `SCAN`합니다. (5) batch `UNLINK` 또는 bounded `DEL` fallback을
사용하고 `KEYS`와 active namespace는 건드리지 않습니다. (6) scanned, deleted,
remaining count를 기록하고 quiescence를 다시 확인합니다. (7) cleanup/recovery가
실패하면 stable code로 alert하고 readiness 및 remaining-count 검사가 통과할 때까지
traffic을 비활성 상태로 유지합니다.

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
사용하지 않습니다. Coordination도 같은 versioned namespace와 bounded TTL 규칙을
따릅니다. Local mutation은 local 범위이며 distributed invalidation이 아닙니다.

## 개발

```bash
uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers"
uv run pytest -m testcontainers packages/bluetape-cache-redis
uv run ruff check packages/bluetape-cache-redis
```
