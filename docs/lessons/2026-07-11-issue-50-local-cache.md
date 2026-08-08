# Issue #50 로컬 캐시 교훈

## 배경

Issue #50에서는 `bluetape-cache`에 집중한 distribution에서 stdlib-only bounded
synchronous 및 asyncio TTL loading cache를 도입했다. 어려운 경계는 기본적인 TTL
저장이 아니라, 모든 terminal 및 admission failure에서 generation, waiter,
cancellation, capacity ownership을 보존하는 일이었다.

## 결정 사항

- active/joinable flight와 terminal-pending owned flight를 분리한다. superseded 또는
  abandoned load는 waiter를 더 받지 않지만 loader가 terminal 상태가 될 때까지
  `max_inflight`를 계속 사용해야 한다.
- clear epoch, key version, active identity, abandoned/superseded state로 publication을
  제어한다. `set`, `invalidate`, `clear`는 loader를 기다리지 않으며 stale publication을
  허용하지 않는다.
- loader body는 cache lock 바깥에서 실행하고 모든 state transition은 owning lock
  아래에서 수행한다. explicit write와 loader publication에 하나의 shared store
  primitive를 사용해 expiry, LRU, version, eviction, heap compaction이 서로 어긋나지
  않게 한다.
- caller cancellation과 loader ownership을 분리한다. async caller는 shielded shared
  task를 await하고, 마지막으로 떠나는 waiter는 loader를 abandon하고 cancel하되
  terminal cleanup을 await하지 않는다.
- cleanup 자체도 cancellation과 task factory에 영향을 받지 않게 한다. 반복된
  cancellation은 `await`를 `finally` 안에서 중단할 수 있고 cleanup task 생성 자체도
  실패할 수 있다. 두 경로 모두 deterministic regression test와 exactly-once waiter
  transition이 필요하다.
- thin install boundary를 유지한다. `bluetape-cache`는 stdlib-only이며 명시적 meta
  extra로 사용할 수 있고, default `bluetape` dependency는 계속 core-only다.

## 결과와 증거

- cache test 120개가 contract, state, concurrency, cancellation, saturation,
  packaging, isolated namespace 동작을 다룬다.
- 모든 package와 extra를 명시적으로 sync한 뒤 workspace suite가 737개에서 정확히
  857개로 늘어났고 통과했다.
- Ruff, lock validation, all-package build, isolated no-index install, actionlint,
  doctest, diff check가 통과했다.
- committed deterministic benchmark가 raw sample을 기록하며 모든
  performance/stability threshold를 통과했다.
- 최종 통합 review는 `P0=0 P1=0`에 도달했다.

## 검토에서 놓친 점과 향후 보호 장치

- test teardown은 production-grade concurrency code다. survivor를 assertion하기 전에
  모든 owned helper를 join 또는 gather해 첫 failure가 이후 cleanup을 막지 않게 한다.
- publication 자체가 실패해도 terminal helper는 cleanup해야 한다. clock과 task-factory
  injection은 드문 admission 및 cleanup 경로를 결정적으로 증명하는 유용한 방법이다.
- cancellation 한 번만으로는 async 증거가 부족하다. cache lock을 잡은 상태에서 cleanup이
  기다리는 동안 반복 cancellation을 전달한다.
- 기본 `uv run`은 optional workspace extra를 다시 정리할 수 있다. 전체 multi-package
  suite에서는 모든 package/extra를 sync하고 `--no-sync`로 pytest를 실행해 provider
  test가 의도한 environment를 사용하도록 한다.
- documentation parity는 heading이나 비슷한 문장을 맞추는 일이 아니라 동작이 동등한
  example을 제공하는 것이다.
- Issue #51은 여기서 정립한 generation, ownership, cancellation, redaction,
  bounded-admission contract를 재사용해야 한다. Redis coordination이 이를 약화하거나
  local point-in-time statistic을 high-cardinality telemetry로 조용히 바꾸면 안 된다.
