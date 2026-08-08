# Issue #12 Resilience 사양 검토

날짜: 2026-07-14 KST
Artifact: `docs/superpowers/specs/2026-07-14-issue-12-resilience-design.md`
Artifact kind: spec

## 범위

승인된 `bluetape-resilience` package boundary, public sync/async API, fluent
decorator composition, retry/backoff, cooperative async timeout, circuit와
bulkhead state ownership, observability, packaging, acceptance criteria,
validation evidence를 검토했다.

현재 collaboration surface에 role-selectable native review dispatcher가 없어
필수 여섯 관점을 main session에서 별도 read-only pass로 수행했다. Delegated
assertion을 근거로 취급하지 않았고, main integration pass에서 발견 사항을
정규화하고 수정된 모든 section을 다시 읽었다.

## 초기 발견 및 수정

| Priority | Lens | 근거 | 필수 수정 | 결과 |
|---|---|---|---|---|
| P1 | Stability | Cancellation observation이 `CancelledError`를 observer error로 대체할 수 있음 | Observer 호출 전에 cancellation을 전파하고 v1에서 cancellation event를 emit하지 않음 | Failure classification 및 acceptance coverage에서 수정 |
| P1 | Stability | Operation-raised `TimeoutError`가 timeout context 자체 expiry와 혼동될 수 있음 | Policy-owned expiry만 translate하고 operation의 원래 `TimeoutError` 보존 | Async timeout contract에서 수정 |
| P1 | Stability | Raising circuit failure predicate가 half-open probe를 release하는지 명시되지 않음 | Generation-tagged slot을 outcome 없이 release한 뒤 predicate error 전파 | Circuit contract와 failure-mode table에서 수정 |
| P1 | Developer/API | Public export, enum member, event field, snapshot, constructor input, event ordering이 executable contract가 아닌 category 수준 | Ordered export, exact value shape, signature, pipeline method, event matrix 고정 | Public API 및 observability section에서 수정 |
| P1 | Security/Ops | Caller policy name이 sensitive/high-cardinality label이 될 수 있음 | Stable non-sensitive name을 요구하고 event/domain error에 포함됨을 문서화 | Naming 및 observability contract에서 수정 |

## 최종 관점 결과

| 관점 | 결과 | 검토 근거 |
|---|---:|---|
| Performance | PASS | Bounded concurrency/waiting, background reset/scheduler 없음, lock 밖 user code, inline hook latency ownership |
| Stability | PASS | Cancellation precedence, owned timeout distinction, generation-tagged circuit completion, predicate/permit/probe cleanup, loop binding |
| Security | PASS | Event에 caller argument/result/raw exception 없음, global logging/exporter 없음, stable non-sensitive policy-name boundary |
| Operator/Ops | PASS | Typed event matrix, immutable snapshot, lazy recovery, explicit observer failure semantics, package/README/release boundary |
| Developer/API | PASS | Exact export/value shape, keyword-only constructor, sync/async family 분리, immutable last-added-outermost pipeline, decorator/direct-call typing |
| User/caller | PASS | 작은 sync/async example, explicit state sharing, order-dependent semantics, generator/sync-timeout exclusion, domain error |

## Main integration 판정

- P0: 0
- P1: 0
- P2: 0
- P3: 0
- 판정: PASS

수정된 specification은 user-approved design 안에 남는다. Stdlib-only focused
distribution, separate sync/async policy, async-only cooperative timeout,
individual policy 및 fluent pipeline decorator를 유지하며 HTTP/framework
adapter, sync preemption, global state, implementation authority를 추가하지 않는다.
