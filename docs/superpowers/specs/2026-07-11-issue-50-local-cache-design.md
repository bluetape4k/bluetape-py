# Issue #50 Sync and Async Local Cache Design

- Issue: [#50](https://github.com/bluetape4k/bluetape-py/issues/50)
- Parent: [#11](https://github.com/bluetape4k/bluetape-py/issues/11)
- Redis follow-up: [#51](https://github.com/bluetape4k/bluetape-py/issues/51)
- Date: 2026-07-11
- Work type: Type A - Full Feature
- Research: `docs/superpowers/research/2026-07-11-issue-50-local-cache-research.md`

## Problem

`bluetape-py`에는 process-local cache 계약이 없다. 범용 라이브러리 사용자는 동기 코드와 asyncio 코드 모두에서 TTL, bounded capacity, explicit invalidation, same-key loader coalescing을 사용할 수 있어야 한다. 구현은 Redis나 framework dependency 없이 local semantics를 먼저 고정해야 한다.

## Approved Direction

별도의 `TTLCache[K, V]`와 `AsyncTTLCache[K, V]`를 제공한다. 두 클래스는 병렬 개념과 메서드 이름을 사용하지만 lock, waiter, cancellation 구현은 공유하지 않는다. 공통 내부 코드는 entry, TTL, LRU, mutation-version 규칙처럼 순수한 상태 전이에만 제한한다.

## Package Boundary

새 distribution:

```text
packages/bluetape-cache/
├── README.md
├── pyproject.toml
├── src/bluetape/cache/__init__.py
└── tests/
    ├── test_ttl_cache.py
    ├── test_async_ttl_cache.py
    └── test_packaging.py
```

계약:

- distribution: `bluetape-cache==0.1.0`
- import: `bluetape.cache`
- Python: `>=3.13`
- production dependencies: none
- `bluetape` default dependencies: unchanged (`bluetape-core` only)
- `bluetape[cache]`: explicit forwarding extra
- root `bluetape/__init__.py`: 생성하지 않음

## Public API

```python
import time
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    loads: int
    load_failures: int
    load_rejections: int
    coalesced_waiters: int
    evictions: int
    expirations: int
    invalidations: int
    inflight_loads: int
    abandoned_loads: int
    superseded_loads: int


class RecursiveLoadError(RuntimeError): ...


class CacheLoadLimitError(RuntimeError): ...


class TTLCache(Generic[K, V]):
    def __init__(
        self,
        *,
        default_ttl: float,
        max_size: int,
        max_inflight: int | None = None,
        clock: Callable[[], int] = time.monotonic_ns,
    ) -> None: ...

    def get(self, key: K) -> V: ...
    def set(self, key: K, value: V, *, ttl: float | None = None) -> None: ...
    def invalidate(self, key: K) -> bool: ...
    def clear(self) -> None: ...
    def get_or_load(
        self,
        key: K,
        loader: Callable[[K], V],
        *,
        ttl: float | None = None,
    ) -> V: ...
    def stats(self) -> CacheStats: ...
    def __len__(self) -> int: ...


class AsyncTTLCache(Generic[K, V]):
    def __init__(
        self,
        *,
        default_ttl: float,
        max_size: int,
        max_inflight: int | None = None,
        clock: Callable[[], int] = time.monotonic_ns,
    ) -> None: ...

    async def get(self, key: K) -> V: ...
    async def set(self, key: K, value: V, *, ttl: float | None = None) -> None: ...
    async def invalidate(self, key: K) -> bool: ...
    async def clear(self) -> None: ...
    async def get_or_load(
        self,
        key: K,
        loader: Callable[[K], Awaitable[V]],
        *,
        ttl: float | None = None,
    ) -> V: ...
    async def stats(self) -> CacheStats: ...
    async def size(self) -> int: ...
```

위 코드는 공개 타입 스텁 표기다. 메서드 body의 `...`는 미정 요구사항이 아니라 구현을 생략한 signature 표기다.

`bluetape.cache.__all__`은 `TTLCache`, `AsyncTTLCache`, `CacheStats`, `RecursiveLoadError`, `CacheLoadLimitError`만 노출한다.

`AsyncTTLCache`는 `__len__`을 제공하지 않는다. Python special method는 await할 수 없고 stale count를 동기적으로 노출하면 병렬 API의 lock 계약을 깨기 때문이다.

## Usage Examples

```python
from bluetape.cache import TTLCache

cache = TTLCache[str, object](default_ttl=30.0, max_size=1_000)
cache.set("default", None)                 # default_ttl 사용
cache.set("short", {"ok": True}, ttl=1.0)

assert cache.get("default") is None
value = cache.get_or_load("user:42", lambda key: {"key": key})
```

```python
from bluetape.cache import AsyncTTLCache

cache = AsyncTTLCache[str, dict[str, str]](
    default_ttl=30.0,
    max_size=1_000,
)

async def load_user(key: str) -> dict[str, str]:
    return {"key": key}

value = await cache.get_or_load("user:42", load_user)           # default_ttl
fresh = await cache.get_or_load("user:43", load_user, ttl=5.0) # per-entry TTL
```

동일 key의 concurrent caller가 다른 loader/TTL을 전달하더라도 flight owner의 loader/TTL만 사용한다. 결과를 바꾸는 tenant/authorization context는 반드시 key에 포함한다.

## Input and Error Contract

- `default_ttl`과 per-entry `ttl`은 bool이 아닌 `int | float` finite positive seconds여야 한다. `None`은 per-entry API에서 constructor `default_ttl`을 사용한다는 뜻이며 non-expiring entry는 v1에서 지원하지 않는다.
- TTL의 bool/non-numeric 값은 `TypeError`, non-finite/non-positive/sub-nanosecond 값은 `ValueError`다.
- `max_size`는 bool이 아닌 positive integer여야 한다.
- `max_inflight`는 bool이 아닌 positive integer이며 기본값은 `max_size`다.
- miss 또는 expired access는 `KeyError(key)`를 발생시킨다. 따라서 `None`도 정상 value다.
- loader exception은 원래 타입과 cause를 유지하여 현재 owner/waiter에게 전달하며 캐시하지 않는다.
- 같은 execution owner가 같은 key를 재귀 load하면 `RecursiveLoadError`를 발생시켜 self-deadlock/self-await를 막는다.
- cache는 hashable key를 요구한다. unhashable key는 Python의 원래 `TypeError`를 유지한다.
- active/superseded/abandoned owned flight 수가 `max_inflight`에 도달한 상태에서 새 key load를 시작하면 `CacheLoadLimitError`를 발생시킨다. 기존 same-key active flight에 합류하는 waiter는 slot을 추가로 소비하지 않는다.
- `clock`은 monotonic nanoseconds를 반환하는 caller-owned callable이다. 기본값은 `time.monotonic_ns`다.

## Entry, TTL, and LRU Semantics

내부 entry는 value, absolute expiry nanoseconds, mutation version을 가진다. recency 순서는 `OrderedDict`, expiry 순서는 `(expires_at, sequence, key, version)` min-heap으로 관리한다. sequence는 동일 expiry에서 key 비교가 발생하지 않게 한다.

- successful `get`과 cache hit `get_or_load`: MRU로 이동
- `set`: 기존 값을 대체하고 MRU로 이동
- insert 전에 heap에서 현재 tick까지의 expiry node를 제거하고 entry version이 일치하는 live node만 만료 처리
- insert가 `max_size`를 넘으면 live LRU부터 eviction
- touched expired entry는 즉시 제거하고 expiration을 증가
- `len()`과 `size()`는 전체 expired entry를 sweep한 live count를 반환
- expiry는 lazy이며 background thread/task를 만들지 않음
- explicit per-entry TTL은 해당 write/load에만 적용
- overwrite/eviction으로 생긴 stale heap node는 pop 시 무시한다. heap 길이가 `2 * max_size`를 넘으면 live entry에서 재구축하여 expiry metadata를 bounded 상태로 유지한다.

TTL을 nanoseconds로 변환할 때 non-finite 값을 거절하고 최소 유효 positive duration이 1ns 미만이면 `ValueError`로 거절한다.

## Mutation Ordering

각 load는 시작 시 global clear epoch와 key mutation version을 캡처한다. cache는 현재 generation에 합류 가능한 active-flight map과 terminal까지 소유해야 하는 owned-flight set을 분리한다.

- load 도중 같은 key에 `set` 또는 `invalidate`가 발생하면 version이 바뀐다.
- `clear`는 global epoch를 바꾼다.
- loader 완료 시 캡처 값이 현재 값과 같고 현재 active-flight map이 동일 flight identity를 가리킬 때만 cache에 기록한다.
- mutation이 먼저 발생한 경우 loader 결과는 해당 호출자와 현재 waiter에게 반환하지만 cache state를 덮어쓰지 않는다.
- mutation은 기존 flight를 `superseded`로 표시하고 active map에서 제거하되 owned set에는 terminal까지 유지한다. mutation 이후 시작한 caller는 superseded flight에 합류하지 않으며, live explicit set을 읽거나 새 generation flight를 시작한다.
- key version metadata는 entry 또는 owned flight가 없을 때 제거하여 unbounded growth를 막는다.
- abandoned async flight는 active map에서 제거하고 key version을 증가시켜 이후 성공처럼 종료되더라도 cache에 게시할 수 없게 한다.

이 규칙은 명시적 caller mutation이 늦게 끝난 loader보다 우선하도록 보장한다.

## Synchronous Coordination

`TTLCache`는 instance-owned `threading.RLock`과 key-local flight를 사용한다.

1. lock 아래에서 live entry를 조회한다.
2. miss이고 현재 generation active flight가 있으면 waiter로 등록하고 condition에서 기다린다. waiter가 전달한 loader와 TTL은 사용하지 않으며 owner의 loader/TTL이 shared outcome과 cache write를 결정한다.
3. miss이고 flight가 없으면 현재 thread가 owner인 flight를 만든다.
4. loader는 global lock 밖에서 실행한다.
5. owner는 lock을 다시 얻어 mutation version과 flight identity를 확인하고 result/failure를 flight 객체에 기록한다.
6. owner는 동일 identity인 active-flight map 항목을 제거하고 owned set에서도 terminal flight를 제거한 뒤 모든 waiter를 깨운다. 이미 합류한 waiter는 map이 아니라 자신이 보유한 flight 객체에서 outcome을 읽는다.
7. superseded owner도 기존 waiter에게 outcome을 게시하되 cache write는 하지 않으며 owned set과 key-version metadata를 terminal path에서 정리한다.
8. owner-only 성공/실패도 active/owned map과 key-version metadata를 terminal path에서 정리한다.

다른 key의 loader body는 global lock 밖에서 동시에 실행할 수 있다. lookup, LRU/expiry mutation, flight map 갱신은 짧은 instance lock 구간에서 직렬화된다. 동일 thread가 자신의 동일-key flight를 다시 기다리려 하면 `RecursiveLoadError`를 발생시킨다. 임의의 child thread가 만든 wait graph는 탐지할 수 없으므로 sync loader가 자신이 join하는 child thread에서 동일 cache/key를 재호출하는 사용은 지원하지 않는다.

## Asynchronous Coordination

`AsyncTTLCache`는 instance-owned `asyncio.Lock`과 key별 strongly owned task/flight를 사용한다. 한 instance는 처음 사용된 event loop에 귀속되며 다른 loop에서 사용하면 `RuntimeError`를 발생시킨다.

1. lock 아래에서 live entry 또는 current-generation active flight를 찾는다. existing flight waiter의 loader와 TTL은 사용하지 않으며 owner의 loader/TTL이 shared outcome과 cache write를 결정한다.
2. flight가 없고 owned flight 수가 limit 미만이면 opaque sequence만 포함한 named task를 생성하고 flight가 강한 참조를 소유한다. task 이름에는 key/value/loader 표현을 포함하지 않는다.
3. 각 caller는 waiter count를 증가시키고 `await asyncio.shield(task)`로 기다린다.
4. caller cancellation은 즉시 `CancelledError`로 전파되지만 생존 waiter의 shared loader task는 유지된다.
5. waiter가 빠질 때 count를 감소시킨다. 마지막 waiter가 사라졌고 task가 미완료면 lock 아래에서 flight를 abandoned로 표시하고 active map에서 제거하며 key version을 증가시킨 뒤, lock 밖에서 task cancel을 요청한다.
6. cancelled caller의 `CancelledError`는 cleanup completion을 기다리지 않고 즉시 전파한다. cache는 abandoned-flight set으로 task를 terminal 시점까지 강하게 소유한다.
7. task `finally`는 lock 아래에서 owned-flight set, abandoned/superseded 상태, version metadata를 정리한다. done callback은 terminal exception을 반드시 조회하여 orphan warning을 막는다.
8. task 성공 시 epoch/version 일치, 동일 active flight identity, `not abandoned`를 모두 만족할 때만 cache에 기록한다.
9. loader가 cancellation을 억제하고 값을 반환해도 abandoned flight는 cache에 기록하지 않는다. terminal이 될 때까지 in-flight slot을 점유하여 unbounded replacement task 생성을 막는다.
10. loader의 `CancelledError` 또는 exception은 캐시하지 않고 flight를 정리한다.

loader scope는 private `ContextVar`에 cache/key identity를 기록한다. 현재 task와 상속된 child task가 동일 cache/key를 재진입하면 `RecursiveLoadError`를 발생시킨다. manually created thread처럼 context를 상속하지 않는 임의 wait graph는 지원 범위 밖이다.

event-loop 귀속은 별도 `threading.Lock` one-time guard로 모든 public async method의 첫 state 접근 전에 원자적으로 결정한다. 서로 다른 thread/loop의 동시 최초 호출 중 하나만 귀속에 성공하고 나머지는 `RuntimeError`를 받는다.

## Stats Contract

`CacheStats`는 lock 아래 복사한 immutable, low-cardinality snapshot이다. raw key/value, exception message, loader identity는 포함하지 않는다.

- `hits`: caller 단위 live hit
- `misses`: caller 단위 miss/expired access
- `loads`: 실제 loader invocation 수
- `load_failures`: 실제 loader exception/cancellation 수
- `load_rejections`: in-flight limit 때문에 새 key load가 거절된 수
- `coalesced_waiters`: existing flight에 합류한 caller 수
- `evictions`: capacity eviction 수
- `expirations`: lazy sweep로 제거한 entry 수
- `invalidations`: existing live entry를 explicit invalidate한 수
- `inflight_loads`: snapshot 시점의 active, superseded, abandoned owned flight 총수
- `abandoned_loads`: snapshot 시점에 waiter가 없고 cancellation 요청 후 terminal을 기다리는 flight 수
- `superseded_loads`: snapshot 시점에 mutation으로 current generation에서 분리됐지만 기존 waiter/owner가 terminal을 기다리는 flight 수

counter는 instance lifetime 동안 누적되고 `clear()`는 entry만 제거하며 counter를 초기화하지 않는다. gauge는 owned-flight 상태 전이와 terminal cleanup을 같은 lock 아래 반영한다.

v1은 callback/listener를 제공하지 않는다. metrics/tracing adapter는 snapshot을 읽거나 public operation을 caller 측에서 감싸며, observer failure가 cache state를 바꾸는 문제를 만들지 않는다.

## Failure Modes and Required Handling

### 1. Loader fails while waiters exist

- 모든 현재 waiter가 failure를 관찰한다.
- entry를 기록하지 않는다.
- flight와 key-version metadata를 정리한다.
- 다음 호출은 새 loader를 실행할 수 있다.

### 2. One async waiter is cancelled

- 해당 waiter만 `CancelledError`를 받는다.
- 생존 waiter가 있으면 shared task를 유지한다.
- 마지막 waiter가 취소되면 task cancel을 요청하고 cache가 terminal까지 강하게 소유한다. caller cancellation은 cleanup을 기다리지 않는다.
- cancellation-resistant loader는 slot을 계속 점유하며 cache는 이를 강제 종료할 수 없다. caller는 untrusted loader에 자체 deadline/cooperative cancellation을 적용해야 한다.

### 3. Explicit mutation races with loader completion

- mutation epoch/version mismatch로 stale loader write를 버린다.
- loader caller는 계산 결과를 받을 수 있지만 cache는 explicit mutation 상태를 유지한다.
- mutation 시 기존 flight는 superseded가 되어 기존 waiter만 outcome을 받는다. mutation 이후 caller는 해당 flight에 합류하지 않는다.
- `set` 이후 caller는 explicit value를 읽고, `invalidate`/`clear` 이후 caller는 capacity가 허용하면 새 generation load를 시작한다.

### 4. Recursive same-key load

- sync self-deadlock 또는 async self-await 전에 `RecursiveLoadError`를 발생시킨다.

### 5. Capacity pressure and expired entries

- insertion 전에 expiry heap에서 현재 tick까지의 entry를 제거한다.
- 여전히 capacity를 넘으면 live LRU를 제거한다.
- expiry heap은 stale-node threshold에서 재구축한다.
- entries, expiry metadata, flights, key versions는 configured capacity에 의해 bounded 상태를 유지한다.

### 6. Clock or TTL misuse

- non-finite/non-positive TTL과 sub-nanosecond positive TTL을 `ValueError`로 거절한다.
- backward clock은 caller가 custom clock을 제공한 계약 위반이며 expiry를 되살리지 않도록 마지막 관찰 tick보다 작은 값은 clamp한다.

### 7. In-flight saturation

- same-key waiter는 기존 flight에 합류한다.
- 새 key는 `CacheLoadLimitError`로 즉시 거절하고 `load_rejections`를 증가시킨다.
- active, superseded, abandoned flight가 owned slot을 소비하며 terminal cleanup 후 slot은 다시 사용 가능하다.
- sync loader와 cancellation-resistant async loader의 실행 시간은 cache가 강제로 제한하지 않는다.

### 8. Untrusted key/value and loader surfaces

- `KeyError(key)`와 원래 loader exception은 caller-visible unsanitized surface다. caller는 secret-bearing key와 exception을 로그/telemetry로 전달하기 전에 redaction해야 한다.
- entry-count `max_size`는 byte-size memory limit이 아니다. untrusted key/value는 cache 진입 전에 caller가 byte/object-size 정책으로 제한해야 한다.
- task name과 stats는 raw key/value/loader/exception message를 포함하지 않는다.

### 9. Caller-owned loader and value semantics

- same-key flight owner의 loader와 TTL만 실행/적용된다. waiter가 전달한 loader와 TTL은 무시된다.
- caller는 same key에 의미상 동등한 loader/TTL을 사용해야 하며 tenant, authorization, locale처럼 결과를 바꾸는 context를 key에 포함해야 한다.
- keys와 values는 strong reference로 보유한다. defensive copy, freeze, serialization을 하지 않고 set/loader result를 동일 identity로 반환한다.
- caller가 mutable value를 변경하면 이후 reader가 같은 변경을 관찰한다. 격리가 필요하면 caller가 immutable value 또는 copy policy를 적용한다.

## Method Detail

- `ttl=None`: constructor `default_ttl` 사용. non-expiring 의미가 아니다.
- `invalidate(key) -> True`: existing live entry를 제거했다.
- `invalidate(key) -> False`: missing, expired, active-flight-only key로 제거한 live entry가 없었다.
- active flight가 있을 때 반환값이 `False`여도 mutation version을 증가시키고 flight를 supersede하여 stale publication을 막는다.
- `clear()`와 `invalidate()`는 active loader를 취소하지 않는다. 기존 waiter는 계산 outcome을 받을 수 있지만 이후 caller/cache state에는 게시되지 않는다.

## Test Design

시간 기반 테스트는 fake monotonic clock을 사용하고 long sleep에 의존하지 않는다.

### Shared behavior

- set/get, `None` value, missing key
- default/per-entry TTL, exact expiry boundary, overwrite
- invalidation, clear, live size
- bounded LRU recency and expired-first removal
- expiry-heap stale-node rebuild and bounded metadata
- invalid TTL/max-size/unhashable key
- TTL `None`, bool, non-numeric, non-finite, non-positive, sub-nanosecond taxonomy
- immutable stats and exact counter semantics
- stats lifetime counters and active/abandoned/superseded gauges
- set/invalidate/clear racing with loader completion
- mutation 이전/이후 waiter generation isolation
- conflicting owner/waiter loaders and TTLs
- caller-owned identity and mutable-value preservation
- invalidate return values for live/missing/expired/active-flight states
- recursive same-key load

### Sync-specific

- `threading.Barrier`/`Event`로 same-key single loader 증명
- different-key loaders의 독립 진행
- current waiter failure sharing and retry
- explicit mutation race
- bounded join timeout으로 thread leak 없음 증명
- owner-only success/failure 반복 후 flight/version metadata 정리
- saturation rejection and recovery

### Async-specific

- same-key task coalescing과 different-key concurrency
- one waiter cancellation with survivor success
- all-waiter cancellation이 caller 반환을 지연하지 않고 loader cancel을 요청하며 cache-owned terminal cleanup을 관찰하는지 검증
- slow `finally`, cancellation suppression, cleanup 중 새 caller 진입
- loader self-cancellation and ordinary failure
- inherited child-task recursive load rejection
- concurrent first-use cross-event-loop ownership race
- no orphan task/lock/flight after every terminal path
- saturation, abandoned-slot retention, terminal recovery

### Packaging

- base/default meta install에 `bluetape-cache`가 없음
- `bluetape[cache]`와 direct distribution wheel import 성공
- workspace source와 `uv.lock` 일치
- exact `bluetape.cache.__all__` export 검증

## Performance and Stability Evidence

이 작업은 hot-path lock, allocation, thread/task lifecycle을 변경하므로 performance/stability scan이 필수다.

- hit/miss/set/get_or_load microbenchmark를 deterministic script로 기록
- same-key contention에서 loader invocation이 1인지 확인
- different-key loader body가 동시에 진행하는지 확인하고 1-key/many-key에서 lock-held latency와 throughput을 비교
- `max_size` 증가와 expiry-heavy overwrite에 따른 heap cleanup/rebuild 비용을 측정
- repeated expiry/invalidation/load failure 후 entries/flights/version metadata가 bounded인지 검사
- async cancellation 반복 후 orphan named task가 없는지 검사

benchmark는 correctness gate가 아니며 환경 metadata와 dependency/Python version을 함께 기록한다. 구현 계획은 실행 전에 warm-up, repetition, key distribution, cache capacity, contention level, latency percentile, allocation/RSS sampling, raw-result path, baseline comparison, relative acceptance threshold를 고정한다.

## Documentation and Registration

변경 대상:

- root `pyproject.toml` workspace dependency/source
- `packages/bluetape-cache/pyproject.toml`
- `packages/bluetape/pyproject.toml` explicit `cache` extra
- `uv.lock`
- root `README.md`, `README.ko.md`, `WIP.md`, `CHANGELOG.md`
- package `README.md`
- CI path/normal test coverage; external service가 없으므로 nightly-only 분리는 필요하지 않음

package README는 direct distribution과 `bluetape[cache]` 설치, sync/async default/per-entry TTL 예제, `KeyError` miss, `None` value, explicit invalidation, same-key owner loader/TTL 규칙, mutable value identity, async cancellation, active loader 중 invalidate/clear 동작을 실행 가능한 예제로 설명한다.

## Compatibility and Migration

신규 package이므로 기존 runtime API migration은 없다. default install은 변하지 않는다. 이후 #51은 `bluetape-cache` concrete contract를 소비하되 Redis 요구를 core API에 역류시키지 않는다. #51에서 adapter 경계가 필요하면 실제 provider evidence를 근거로 additive API를 제안한다.

## Non-Goals

- Redis, distributed locks, pub/sub invalidation, durable L2
- framework decorators or cache annotations
- background expiry worker
- size-by-bytes accounting
- weak references
- disk persistence
- sync loader를 thread pool로 자동 전환
- async cache의 cross-loop/thread sharing
- observer callback/plugin framework
- arbitrary cross-thread recursive wait-graph detection
- forced termination of cancellation-resistant loaders

## Acceptance Criteria

- sync와 async API가 병렬 개념을 제공하고 각각의 동시성 모델이 명확하다.
- same-key loader는 하나로 합쳐지고 different-key loader는 독립 진행한다.
- failure, cancellation, recursive load, mutation race가 leak/stale overwrite 없이 끝난다.
- entries, expiry metadata, active/superseded/abandoned flights가 configured limit에 의해 bounded 상태를 유지한다.
- TTL/LRU/capacity/stats가 fake clock과 deterministic coordination으로 검증된다.
- production implementation은 stdlib-only다.
- default `bluetape` install은 thin 상태를 유지하고 explicit extra만 package를 전달한다.
- README locale, package README, WIP, CHANGELOG, workspace/lock/build/import evidence가 일치한다.
- performance/stability review와 spec/code review가 P0=0, P1=0으로 수렴한다.

## Definition of Done

- approved spec and reviewed implementation plan
- TDD RED/GREEN evidence for every contract family
- targeted tests, full pytest, Ruff, package build, isolated import, diff check
- packaging/default-install isolation proof
- performance/stability evidence
- Step 6-R and Step 7-R P0=0/P1=0
- issue/PR metadata parity and green CI
- explicit merge approval boundary preserved
