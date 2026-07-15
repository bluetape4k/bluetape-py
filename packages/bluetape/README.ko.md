# bluetape

[English](README.md) | 한국어

Python-native bluetape 패키지를 묶어 설치하는 얇은 메타 배포 패키지입니다.

기본 설치는 `bluetape-core`에만 의존하며 루트 `bluetape` import module을 만들지
않습니다. 각 배포 패키지가 `bluetape.core`, `bluetape.compression` 같은 목적별
import 경로를 소유합니다.

## 설치 형태

```bash
pip install bluetape
pip install "bluetape[asyncio]"
pip install "bluetape[cache]"
pip install "bluetape[cache-redis]"
pip install "bluetape[codec]"
pip install "bluetape[collections]"
pip install "bluetape[compression]"
pip install "bluetape[compression-lz4]"
pip install "bluetape[compression-snappy]"
pip install "bluetape[compression-zstd]"
pip install "bluetape[compression-native]"
pip install "bluetape[id]"
pip install "bluetape[logging]"
pip install "bluetape[measure]"
pip install "bluetape[money]"
pip install "bluetape[values]"
pip install "bluetape[resilience]"
pip install "bluetape[serde]"
pip install "bluetape[fory]"
pip install "bluetape[testing]"
pip install "bluetape[all]"
```

| Extra | 목적별 배포 패키지 | Import 경로 | 기본 설치 |
|---|---|---|---:|
| `asyncio` | `bluetape-async` | `bluetape.asyncio` | no |
| `cache` | `bluetape-cache` | `bluetape.cache` | no |
| `cache-redis` | `bluetape-cache-redis` | `bluetape.cache.redis` | no |
| `codec` | `bluetape-codec` | `bluetape.codec` | no |
| `collections` | `bluetape-collections` | `bluetape.collections` | no |
| `compression` | `bluetape-compression` | `bluetape.compression` | no |
| `compression-lz4` | `bluetape-compression[lz4]` | `bluetape.compression.native` | no |
| `compression-snappy` | `bluetape-compression[snappy]` | `bluetape.compression.native` | no |
| `compression-zstd` | `bluetape-compression[zstd]` | `bluetape.compression.native` | no |
| `compression-native` | `bluetape-compression[native]` | `bluetape.compression.native` | no |
| `id` | `bluetape-id` | `bluetape.id` | no |
| `logging` | `bluetape-logging` | `bluetape.logging` | no |
| `measure` | `bluetape-measure` | `bluetape.measure` | no |
| `money` | `bluetape-money` | `bluetape.money` | no |
| `values` | ID + measure + money | 세 focused import | no |
| `resilience` | `bluetape-resilience` | `bluetape.resilience` | no |
| `serde` | `bluetape-serde` | `bluetape.serde` | no |
| `fory` | `bluetape-serde[fory]` | `bluetape.serde.fory` | no |
| `testing` | `bluetape-testing` | `bluetape.testing` | no |

`cache` extra는 표준 라이브러리만 사용하는 bounded sync/async local TTL loading
cache를 설치합니다. 별도 `cache-redis` extra는 byte-only sync/async Redis
provider, 크기 제한 result envelope, bounded cross-process load coordination을
설치합니다. Durable Redis L2 caching과 upstream에 막힌 별도 near-cache
invalidation issue #56은 제공하지 않습니다.

`asyncio` extra는 호출 범위가 정해진 bounded structured-concurrency 헬퍼를
설치합니다. 기본 설치는 계속 `bluetape-core`로 제한합니다.

`id`, `measure`, `money` extra는 서로 독립된 stdlib-only value package를
설치하며 `values`는 세 패키지를 모두 설치합니다. Root `bluetape` module은
추가하지 않고 core-only default에도 들어가지 않습니다. Distributed ID policy,
custom unit definition, historical currency data, exchange-rate source는 application이
소유합니다.

`resilience` extra는 stdlib-only sync/async retry, circuit breaker, bulkhead,
cooperative async timeout, immutable fluent pipeline을 설치합니다. Sync timeout,
hidden worker, scheduler, global registry는 추가하지 않습니다. 같은 policy
instance를 재사용하면 state 또는 capacity를 의도적으로 공유합니다.

`codec`과 `compression` extra는 각각 strict encoded-text 헬퍼와 제한된
gzip/zlib/raw-DEFLATE compressor를 설치합니다. Native compression extra는 LZ4
frame, raw Snappy, Zstandard frame provider를 하나씩 선택하며,
`compression-native`는 세 provider를 모두 설치합니다. 이 provider들은 기본
설치와 `dev`, `all` extra에 들어가지 않습니다.

`serde` extra는 strict payload 계약과 제한된 JSON v1 serialization을 설치합니다.
별도 `fory` extra는 CPython 3.13용 `bluetape-serde[fory]`를 설치합니다. Fory는
trusted-internal 전용이며 base, `serde`, `dev`, `all` extra에서 제외됩니다.

현재 PyPI 배포는 보류 중입니다. 위 명령은 배포가 활성화된 뒤의 공개 설치 형태를
설명합니다. Source workspace에서는 `uv sync --all-packages --locked`를 사용하거나
목적별 wheel을 빌드해 직접 설치할 수 있습니다.

```bash
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
uv build --package bluetape-serde --out-dir "$tmp_dir/dist"
uv venv "$tmp_dir/venv"
uv pip install --python "$tmp_dir/venv/bin/python" "$tmp_dir"/dist/bluetape_serde-*.whl
"$tmp_dir/venv/bin/python" -c 'from bluetape.serde import PayloadMetadata, TrustProfile, json_deserialize, json_serialize; m = PayloadMetadata(format="json", version=1, content_type="application/json", trust_profile=TrustProfile.UNTRUSTED); p = json_serialize({"ok": True}, metadata=m); assert json_deserialize(p, expected_metadata=m) == {"ok": True}'
```

Serde 공개 surface는 25개 ordered export와 23개 stable domain error code를
제공하며 JSON 정수는 640 decimal digit로 제한합니다. Caller type 및 configuration
오류는 `SerdeError`로 바꾸지 않고 원래 `TypeError` 또는 `ValueError`를 유지합니다.
Apache Fory는 caller가 고정 schema/type registration을 소유하며 payload 내용으로
codec이나 fallback을 선택하지 않습니다.
