# Issue #50 Local Cache 코드 검토

날짜: 2026-07-11
범위: `origin/develop...feat/issue-50-local-cache`
Gate: Type A Step 6-R pre-PR review

## 검토 수렴

구현은 계획된 각 task 이후 incremental하게 검토했다. 다음 P1 발견 사항을
최종 pass 전에 재현하고 수정했다.

- float nanosecond conversion에서 overflow할 만큼 큰 finite positive TTL
- 첫 state access까지 허용되던 non-callable clock
- 첫 assertion failure 이후 join을 중단하던 thread teardown
- waiter와 flight capacity를 고립시키던 sync publication exception
- admitted flight를 누수시키던 async task-factory rejection
- waiter release를 중단하던 반복 caller cancellation
- coroutine을 누수시키고 caller cancellation을 덮어쓰던 release-task factory rejection
- package contract example보다 짧았던 root example

모든 수정에는 deterministic regression coverage가 있다. 최종 branch review는
현재 통합 diff와 raw benchmark/package 근거를 대상으로 한다.

| Lens | P0 | P1 | 최종 근거 |
|---|---:|---:|---|
| Performance | 0 | 0 | Deterministic raw JSON이 hit-cost, contention, expiry-scaling, rebuild-proxy threshold를 통과하며 cache lock 안에서 blocking loader body를 실행하지 않는다. |
| Stability | 0 | 0 | Sync thread, loop binding, cancellation, repeated cancellation, task-factory/publication failure, supersession, saturation, terminal cleanup을 finite lifecycle test로 다룬다. |
| Security | 0 | 0 | Logging/callback surface는 key, value, loader, flight, error를 format하지 않는다. Unsanitized `KeyError(key)`와 loader exception은 caller-owned/redaction-required surface로 명시한다. |
| Operator/Ops | 0 | 0 | Immutable lifetime counter와 point-in-time gauge를 문서화하고 default install은 core-only로 유지한다. 숨은 thread, scheduler, listener, external backend는 없다. |
| Developer/API | 0 | 0 | Exact export, keyword-only constructor, sync/async concept parity, native hash error, `None` identity, focused distribution, lockfile, wheel metadata, doctest example이 일치한다. |
| User/Caller | 0 | 0 | English/Korean root/package docs가 install state, TTL/loading/mutation/cancellation behavior, limit, monitoring, secret redaction, Redis issue #51을 다룬다. |

## Main-session 통합 검토

- State ownership은 `_CacheState`에 중앙화하고 sync 및 async wrapper가 각자의
  lock과 flight lifecycle을 소유한다.
- Version, epoch, active-flight identity gate가 `set`, `invalidate`, `clear`,
  cancellation, supersession 이후 stale loader publication을 막는다.
- Versioned expiry node와 post-write rebuilding으로 heap metadata를 bounded하게
  유지하며 entry나 owned flight가 남지 않은 unused key version을 제거한다.
- Loader body는 cache lock 밖에서 실행한다. 같은 key의 caller는 coalesce하고
  다른 key는 독립적으로 진행한다. Hard admission count는 joinable active
  flight가 아니라 owned terminal-pending flight를 센다.
- Meta package는 명시적인 `cache` extra만 추가한다. default install은
  `bluetape-core`만 유지하고 root `bluetape/__init__.py` surface는 없다.
- Acceptance signal의 단위와 threshold가 다르므로 benchmark와 review 문서는
  chart가 아닌 table을 사용한다. 합친 visual은 결과를 더 명확하게 하지 않는다.

## 잔여 P2/P3 결정

- Timing 및 RSS observation은 portable SLA가 아닌 machine-local regression evidence다.
- Redis, cross-process invalidation, background expiry, byte-size accounting,
  callback/listener, framework adapter는 issue #50 범위 밖이다.
- Cancellation-resistant async loader는 terminal까지 admission slot을 계속
  소유한다. Caller는 cooperative cancellation과 deadline을 제공해야 한다.

최종 gate: **P0=0 P1=0**.
