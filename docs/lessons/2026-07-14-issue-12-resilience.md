# Issue #12 Resilience Policies Lessons

## Context and decision

Python-native resilience는 sync와 async를 하나의 adapter로 감싸는 문제가 아니라,
각 실행 계열이 소유할 수 있는 취소와 동기화 범위를 명시하는 문제였다. 첫 배포는
stdlib-only policy와 immutable fluent pipeline에 한정하고 sync timeout, hidden
worker, scheduler, detached task, global registry/logger를 제외했다.

## Reusable findings

### Cooperative timeout ownership

`asyncio.timeout()`은 현재 caller task의 cancellation을 이용하므로 package-owned
expiry만 `PolicyTimeoutError`로 번역하고 외부 `CancelledError`는 그대로 전파해야
한다. Sync callable은 안전하게 선점할 수 없으므로 worker를 버리는 형태의 sync
timeout을 제공하지 않는 것이 올바른 계약이다.

### Generation-tagged circuit completion

Circuit admission마다 generation을 기록하면 이전 epoch의 늦은 성공/실패가 새
`OPEN`, `HALF_OPEN`, `CLOSED` 상태를 바꾸지 못한다. 이 규칙은 counter보다 먼저
검증해야 하며 sync thread와 async task 양쪽에서 stale success/failure를 모두
테스트해야 한다. Caller clock이 completion 시 실패해도 owned half-open slot은 먼저
반환해야 한다.

### Cancellation before observation, cleanup before propagation

Cancellation은 failure event나 circuit count가 아니라 control signal이다. 다만
operation이 끝난 직후 state lock을 기다리는 동안 취소될 수 있고, cleanup 중 다시
취소될 수도 있다. `shield()`는 내부 task를 만들고 caller가 먼저 빠질 수 있으므로
사용하지 않았다. 대신 같은 caller task에서 lock-acquire cancellation을 흡수하고
permit/probe reconciliation을 끝낸 뒤 원래 cancellation을 전파했다. Internal
critical section에는 lock acquire 외 await가 없어 cleanup coroutine 재시도가 중복
mutation을 만들지 않는다. Observer가 직접 `CancelledError`를 던지는 경로와 sync
`BaseException`도 같은 ownership 규칙으로 정리해야 한다.

### Last-added-outermost composition

Immutable pipeline은 policy instance를 clone하지 않고 명시적으로 공유한다. 각
`.with_*()`는 새 pipeline을 반환하며 마지막에 추가한 policy가 outermost가 된다.
따라서 breaker 뒤에 retry를 추가하면 breaker가 매 attempt를 보고, retry 뒤에
breaker를 추가하면 breaker는 최종 retry 결과만 본다. 한 가지 순서를 보편적
권장값으로 숨기지 말고 두 trace를 문서와 테스트로 보여 주는 편이 안전하다.

### Python callable and workspace test boundaries

Callable family 검사는 plain function뿐 아니라 callable instance와
`functools.partial`의 coroutine/generator marker를 함께 봐야 한다. Sync 함수가
동적으로 awaitable을 반환하는 경우에는 coroutine을 닫고 native `TypeError`를
policy stack 전체로 전파해 retry/circuit/bulkhead state를 오염시키지 않아야 한다.

여러 distribution을 한 pytest process에서 수집할 때 top-level `tests` package나
동일 basename은 충돌할 수 있다. Focused package 테스트도 고유 package 이름으로
격리하고, package 단독 통과 뒤 반드시 full-workspace collection을 실행해야 한다.

## Verification evidence

- Resilience stability: 144 tests x 5 consecutive runs, zero failure/hang.
- Full workspace: 1,659 tests passed.
- Ruff lint/format, 14-distribution sdist+wheel build, actionlint, diff check passed.
- Fresh base/direct/meta-extra environments proved core-only default, dependency-free
  focused wheel, exact 24 exports, no sync `Timeout`, and explicit extra activation.
- Independent final code review: P0=0, P1=0, P2=0.

## Future guard

새 policy나 adapter를 추가할 때는 실행 계열, cancellation owner, cleanup ordering,
state generation, wait bound, observer cardinality, policy instance sharing, wrapper
order를 먼저 문서화한다. 그 뒤 single/repeated cancellation과 full-workspace
collection까지 검증하며, hidden work가 필요해지는 기능은 기존 package에 암묵적으로
넣지 말고 별도 경계로 다시 설계한다.
