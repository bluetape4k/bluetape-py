# Issue #50 Local Cache Research

- Issue: [#50](https://github.com/bluetape4k/bluetape-py/issues/50)
- Parent: [#11](https://github.com/bluetape4k/bluetape-py/issues/11)
- Date: 2026-07-11
- Work type: Type A - Full Feature

## Research Question

Python 3.13 이상에서 범용 라이브러리로 사용할 수 있는 동기·비동기 로컬 TTL/loading cache를 어떤 경계와 동시성 계약으로 제공할 것인가?

## Current Repository Evidence

- 패키지는 `packages/<distribution>/src/bluetape/<module>/` 구조를 사용한다.
- `bluetape` 기본 설치는 `bluetape-core`만 포함하며 선택 기능은 명시적 extra로 전달한다.
- `bluetape-async`는 `asyncio.TaskGroup`, 명시적 취소 전파, 강한 task 소유권을 사용한다.
- 공개 API는 단일 `__init__.py` 표면과 명시적 `__all__`을 사용하고 패키지별 README와 테스트를 함께 둔다.
- 승인 직후 기준 전체 테스트는 CPython 3.13.14에서 `737 passed`였다. 첫 실행은 Fory extra 누락으로 collection 실패했고 `uv sync --all-packages --all-extras` 후 정상 통과했다.

## Ecosystem Evidence

`bluetape-go/cache`는 기본 cache와 loading cache 계약을 분리하고 같은 키의 동시 loader를 합치는 방향을 사용한다. Redis near-cache와 cross-process stampede coordination은 별도 패키지로 분리되어 있다.

채택할 원칙:

- local contract를 Redis provider보다 먼저 확정한다.
- 같은 키만 합치고 다른 키의 진행은 막지 않는다.
- loader 실패는 현재 waiter에게 전달하지만 값으로 캐시하지 않는다.
- invalidate, clear, explicit set이 진행 중 loader보다 우선한다.

그대로 이식하지 않을 부분:

- Go의 context-first interface와 zero-value/error tuple은 Python API로 복제하지 않는다.
- 동기와 비동기를 하나의 다형 interface로 합치지 않는다.
- Redis lock/result-envelope 계약은 후속 [#51](https://github.com/bluetape4k/bluetape-py/issues/51)에서 별도 설계한다.

## Python 3.13 Evidence

- [`asyncio` task cancellation and shielding](https://docs.python.org/3.13/library/asyncio-task.html): 취소 정리는 `try/finally`로 수행하고 `CancelledError`를 다시 전파해야 한다. `asyncio.shield()`는 waiter 취소가 공유 task를 취소하지 않게 하지만 task의 강한 참조를 소유해야 한다.
- [`time.monotonic_ns()`](https://docs.python.org/3.13/library/time.html#time.monotonic_ns): 시스템 시각 변경의 영향을 받지 않는 monotonic clock이며 정수 나노초로 TTL 경계를 안정적으로 계산할 수 있다.
- [`threading.Condition`](https://docs.python.org/3/library/threading.html#condition-objects): 동기 waiter는 condition wait 동안 lock을 해제하고 통지 후 다시 획득할 수 있다.
- [`collections.OrderedDict`](https://docs.python.org/3.13/library/collections.html#collections.OrderedDict.move_to_end): bounded LRU recency 갱신을 stdlib만으로 구현할 수 있다.

## Alternatives

### A. Single mixed sync/async cache

한 클래스가 일반 값과 awaitable loader를 모두 받는다.

- 장점: 클래스 수가 적다.
- 단점: 반환 타입, lock 종류, 취소 소유권, loop 경계가 모호하다.
- 결정: 거절. 범용성은 혼합 API가 아니라 명확한 병렬 계약으로 제공한다.

### B. Parallel sync and async classes

`TTLCache`와 `AsyncTTLCache`가 같은 개념과 메서드 이름을 공유하되 동시성 구현을 분리한다.

- 장점: Python 호출 방식과 취소 모델이 명확하고 각 구현을 독립 검증할 수 있다.
- 단점: 일부 내부 상태·정책 코드가 반복될 수 있다.
- 결정: 채택. 순수 entry/TTL/LRU 규칙만 작은 내부 도우미로 공유하고 lock/flight 로직은 분리한다.

### C. Backend Protocol framework first

local/Redis/memory backend를 위한 추상 provider 계층을 먼저 만든다.

- 장점: 후속 provider 확장이 쉬워 보인다.
- 단점: local contract가 검증되기 전에 Redis 요구를 추측하고 공개 API를 고정한다.
- 결정: 거절. #50은 local concrete API를 확정하고 #51이 실제로 요구하는 최소 adapter 경계를 별도 도출한다.

## Dependency Decision

- `bluetape-cache` production dependency: none.
- TTL/LRU: `time.monotonic_ns`, `collections.OrderedDict`, bounded stale-node `heapq` expiry index.
- sync coordination: `threading.RLock`와 key-local flight/condition.
- async coordination: `asyncio.Lock`, strongly owned `Task`, `asyncio.shield`.
- Redis and Testcontainers: #50 production/test dependency에서 제외하고 #51에서 재평가한다.

## Design Consequences

- 두 public class는 병렬 개념을 제공하지만 상속이나 공통 async/sync Protocol을 강제하지 않는다.
- cache miss는 `KeyError`로 명확히 표현하여 `None` 값도 정상 캐시할 수 있게 한다.
- TTL은 lazy expiry이며 background thread/task를 만들지 않는다.
- max-size는 entry count 기준 bounded LRU다.
- stats는 key/value를 포함하지 않는 immutable snapshot이다.
- 진행 중 load가 끝나기 전에 set/invalidate/clear가 발생하면 loader 결과는 호출자에게 반환할 수 있지만 cache에는 다시 기록하지 않는다.
- entry count와 별도로 active/superseded/abandoned owned loader flight를 hard-limit하여 unique-key load 폭주가 task/metadata를 무제한 생성하지 않게 한다.
