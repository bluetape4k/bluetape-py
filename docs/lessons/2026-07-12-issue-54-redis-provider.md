# Issue #54 Redis Provider 교훈

## 배경과 결정

Redis 기반 계층은 opt-in `bluetape-cache-redis` distribution으로 유지했으며,
`bluetape.cache.redis` 아래에 둔다. 이 distribution은 정확히
Redis, serde, base compression에만 의존하며 stdlib-only local cache에 의존하거나
오염시키지 않는다. parent cache package는 `pkgutil.extend_path`를 사용해 독립적으로
빌드된 wheel이 nested namespace에서 공존할 수 있도록 한다.

Serialization, envelope format, compression, key naming, rollout은 계속 caller
policy로 둔다. provider는 strict byte operation과 명시적인 client lifecycle만
소유한다. 이를 통해 #55 coordination이 숨은 codec, retry, Redis ownership 결정을
물려받지 않게 한다.

## 구현으로 확인한 내용

- Bounded parser는 JSON/base64 또는 binary field 작업을 수행하기 전에 raw size를
  거부해야 한다. 또한 duplicate, unknown/missing field, trailing byte, invalid
  UTF-8/base64, version drift, algorithm ambiguity도 거부해야 한다.
- 기록된 algorithm과 하나의 exact reader registry를 사용하면 content sniffing이나
  fallback decoding 없이 reader-first compression migration을 지원할 수 있다.
- Async close에는 하나의 shared transient cleanup task가 필요하다. Shielding만으로는
  충분하지 않다. 각 cancelled caller가 cleanup에 계속 join한 뒤 원래 cancellation을
  다시 발생시키고, provider는 terminal state에서 task를 지워야 한다.
- Redis `SET NX PX`와 고정된 Lua compare-delete가 필요한 atomic substrate를 제공한다.
  Script ACL denial은 닫힌 상태로 실패해야 하며, race가 발생하는 GET/DELETE sequence로
  저하해서는 안 된다.

## 예상 밖의 문제와 보호 장치

Focused test만으로는 다른 package와의 pytest module-name collision을 발견하지
못했다. full workspace suite가 이를 찾아냈으므로, 새 package의 test module은 package
import mode를 의도적으로 바꾸지 않는 한 전역에서 서로 다른 basename을 사용해야 한다.

계획한 coexistence smoke는 `bluetape-cache`를 빌드했지만 `TTLCache`를 import하기 전에
provider만 설치했다. 승인된 dependency boundary가 local cache를 올바르게 제외하므로,
이 잘못된 smoke 전제를 통과시키려고 dependency를 추가해서는 안 된다. proof에는 두
wheel을 모두 명시적으로 설치해야 한다.

재사용 가능한 closeout command는 focused non-container lane, native lane, serial
Testcontainers lane, full pytest, all-package build, isolated base 및 focused wheel
import, `actionlint`, ten repeated lifecycle/cancellation run이다. PyPI, PR creation,
merge, issue closure, #55는 각각 별도의 명시적 authority boundary 뒤에 둔다.
