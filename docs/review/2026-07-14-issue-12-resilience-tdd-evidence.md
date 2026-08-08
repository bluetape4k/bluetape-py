# Issue #12 Resilience Policies TDD 근거

날짜: 2026-07-14 KST
Implementation evidence HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`

## Task 진행

| Boundary | Commit | 해당 boundary의 새 GREEN 근거 |
|---|---|---|
| Shared contract 및 package scaffold | `37e8aa0` | 32 contract/packaging test |
| Deterministic backoff | `757759b` | 56 relevant contract/backoff test |
| Sync/async retry | `15ad5f6` | 71 relevant test |
| Cooperative async timeout | `52e3181` | 24 relevant retry/timeout test |
| Generation-safe circuit breaker | `dcd8620` | 31 circuit 및 주변 policy test |
| Bounded bulkhead | `4bc1318` | 23 bulkhead 및 주변 policy test |
| Immutable pipeline 및 observability | `0d53f54` | 105 package test |
| Meta/lock/build registration | `686e472` | 11 packaging/classification test 및 focused build |
| Bilingual docs 및 executable example | `9d6efa0` | 121 package test |
| Ownership 및 callable correction | `2955071`, `979d024` | 144 package test |
| Workspace-safe test isolation | `b21a7c6` | 144 package test; 1,659 workspace test collection |

위 count는 implementation run에서 보존한 boundary result이며 RED claim을
재구성한 것이 아니다. 각 owning task는 named test를 먼저 사용하고 task
commit 전에 owning file을 다시 실행했다.

## 기록한 RED/GREEN 수정

| Contract | RED 근거 | GREEN 근거 |
|---|---|---|
| Bilingual executable README 및 workspace registration | Docs 전 `test_readme_examples.py` 13 failures | 13 passed 후 package test 121개 통과 |
| Awaitable을 반환하는 sync callable | Retry exhausted, breaker/bulkhead가 coroutine 반환, pipeline wrong terminal propagation 등 focused failure 4개 | 4 focused pass; invocation 1회, circuit count 없음, permit leak 없음 |
| Completion clock callback failure | Sync/async half-open test 4개가 `half_open_in_flight=1`을 남김 | 4 passed; slot이 0으로 복원 |
| Async reconciliation 중 cancellation | Focused test 4개가 한 번 또는 반복 cancellation에서 permit/probe 누수 | 4 passed; cancellation이 빠져나가기 전에 caller task에서 cleanup 완료 |
| `functools.partial` callable classification | Async partial 거부, generator partial 허용 등 focused failure 3개 | Package-wide rerun 전에 3 passed |
| Workspace pytest collection | Top-level `tests` package import error 10개, 이후 basename collision 3개 | 고유 `bluetape_resilience_tests` package에서 1,659 test collection 및 통과 |

## Deterministic control

- `FakeClock`이 circuit deadline과 generation change를 wall-clock sleep 없이 조절한다.
- `threading.Event`와 bounded `join(1)`이 sync capacity와 stale completion을 조정한다.
- `asyncio.Event`, `wait_for(..., 1)`, explicit task cancellation이 async
  waiter, completion reconciliation, repeated cancellation을 조정한다.
- Test는 최종 `in_flight`, `waiters`, `half_open_in_flight` snapshot을
  assertion하고 caller-created thread/task를 남기지 않는다.

구현 evidence HEAD의 최종 package command:

```text
uv run pytest packages/bluetape-resilience -q
144 passed in 0.16s
```
