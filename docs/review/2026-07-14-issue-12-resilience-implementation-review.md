# Issue #12 Resilience Policies 구현 검토

날짜: 2026-07-14 KST
검토한 implementation HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`

## 검토 수렴

| Lens | 주요 발견 및 수정 | 최종 |
| --- | --- | --- |
| Performance | 승인된 performance threshold 없음. 짧은 state critical section과 background work 없음을 확인하고 benchmark gate를 N/A로 기록 | P0=0 P1=0 |
| Stability | Cancellation-interruptible async reconciliation과 completion-clock probe leakage 발견. one/repeated cancellation, observer cancellation, BaseException, clock-error, stale-generation matrix 추가; cleanup은 caller task에서 완료 | P0=0 P1=0 |
| Security/privacy | Fixed-field frozen event에 argument, result, exception text, timestamp, generated ID 없음. Name은 caller-owned low-cardinality label로 문서화 | P0=0 P1=0 |
| Operator/ops | Full-workspace pytest module collision 발견. 고유 package로 test를 격리하고 generic CI가 1,659 tests를 수집하고 모든 distribution을 build하도록 수정. Publication은 HOLD | P0=0 P1=0 |
| Developer/API | Sync awaitable result를 success/retry failure로 잘못 처리하고 `functools.partial` marker를 오분류. Private TypeError control signal과 dual-target callable inspection 추가; exact export/signature와 snake_case fluent method는 유지 | P0=0 P1=0 |
| User/caller | English/Korean example이 test로 실행되어 decorator/direct use, last-added-outermost, 두 retry/breaker order, cancellation, state sharing, explicit limit을 보여 줌 | P0=0 P1=0 |
| Integration | Default meta install은 core-only, focused wheel은 dependency-free, resilience extra는 focused package만 설치. Lock/build/release classifier 일치 | P0=0 P1=0 |

## 독립 검토

Read-only reviewer가 `823bc8d..979d024`를 승인된 spec/plan과 대조하고
awaitable, clock, cancellation, observer/BaseException, partial-callable 발견을
독립적으로 재현했다. 수정 후 결과:

```text
P0=0
P1=0
P2=0
144 passed
Ruff lint/format: pass
```

`b21a7c6`은 test module placement만 변경하고 full-workspace collection을
증명한다. Independent PASS 후 production code는 변경하지 않았다.

## 범위 검토

- HTTP/framework/Redis/telemetry adapter, sync timeout, fallback, rate limiter,
  cache, distributed circuit state를 추가하지 않았다.
- PR, merge, tag, release, publication, workflow dispatch, issue closure를 수행하지 않았다.
- Testcontainers, native-provider, external-service, nightly workflow, benchmark
  threshold, architecture diagram 변경은 N/A다. Package가 stdlib-only이고 topology가
  두 composition-order example로 완전히 표현되기 때문이다.

최종 implementation 검토: **PASS — P0=0 P1=0**.
