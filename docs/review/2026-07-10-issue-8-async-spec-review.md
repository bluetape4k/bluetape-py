# Issue #8 Async 사양 검토

## 범위

구현 계획을 세우기 전에 `bluetape-async` bounded fan-out 계약을 대상으로
`docs/superpowers/specs/2026-07-10-issue-8-async-design.md`를 검토했다.

## 결과

P0: 0

P1: 0

판정: PASS

## 근거

| Review lane | 결과 | 범위 |
|---|---:|---|
| Performance | PASS | bounded admission, iterator pacing, cooperative timeout boundary |
| Stability | PASS | TaskGroup ownership, cancellation, timeout, iterator cleanup |
| Security | PASS | credentials, unsafe input handling, dependency expansion 없음 |
| Operator | PASS | packaging, extras, metadata, documentation, verification command |
| Developer | PASS | API feasibility, validation, cancellation discriminator, testability |
| User | PASS | public API clarity, failure expectation, non-goal |

최종 rerun은 pending cancellation이 없는 상태에서 mapper가 직접 발생시킨
`CancelledError`를 지원되는 terminal signal로 확인했다. `asyncio.current_task().cancel()`
을 통한 mapper self-cancellation은 Python task cancellation이 제공할 수 없는
구분을 약속하지 않도록 계약에서 명시적으로 제외했다. `next(iterator)`의
exception에는 native propagation 및 task-group cleanup 계약이 적용되며,
focused test coverage가 필요하다.

후속 cancellation probe에서 self-cancelled child를 일반적인 TaskGroup
cancellation으로 처리하면 초기화되지 않은 result slot을 반환할 수 있음을
발견했다. 따라서 갱신된 계약은 invocation-owner cancellation state로 external
cancellation을 보존하고, 지원하지 않는 self-cancellation은 cleanup 후 fail
closed하도록 한다. Commit `cf9e9c7`의 stability 및 developer rerun은 모두
P0=0, P1=0을 보고했다.

## Non-blocking note

결합된 invalid argument에는 지정된 validation precedence가 의도적으로 없다.
각 invalid input class는 해당 class의 validation이 수행되는 지점에서 input을
소비하기 전에 실패해야 한다.
