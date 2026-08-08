# Issue #50 Local Cache 계획 검토

날짜: 2026-07-11
Artifact: `docs/superpowers/plans/2026-07-11-issue-50-local-cache-implementation-plan.md`
Gate: Type A Step 3-R

## 검토 수렴

| Lens | 초기 주요 발견 | 수정 | 최종 |
| --- | --- | --- | --- |
| Performance | Expiry workload/threshold 모호성, median-only rebuild evidence, one-key/many-key contention 비교 누락, timing/memory 방법 혼합 | Scaled workload와 normalized/tail threshold 고정, rebuild-trigger timing proxy와 fixed-worker contention 추가, timing/allocation/fresh-process RSS phase 분리 | P0=0 P1=0 |
| Stability | Async loop ownership이 state use 뒤에 오고 synchronization test의 bounded teardown이 불완전 | async state 접근 전에 atomic loop binding, 모든 경로의 finite wait 및 deterministic thread/task cleanup 요구 | P0=0 P1=0 |
| Security | Secret-bearing task name/stats와 caller error-redaction 책임에 negative proof/documentation 부족 | sentinel test, private `repr=False`, no-format diagnostic, unsanitized error guidance, cancellation-resistant loader warning 추가 | P0=0 P1=0 |
| Operator/Ops | Raw benchmark evidence가 ephemeral하고 CI ownership 및 stats monitoring 의미가 늦거나 암묵적 | SHA evidence가 있는 raw JSON을 durable하게 만들고 즉시 CI collection ownership proof, lifetime counter/point-in-time gauge/polling/no callback 문서화 | P0=0 P1=0 |
| Developer/API | Plan granularity, exact public typing, test selector, heap post-write bound, workspace registration ownership 불완전 | 정확한 `TypeVar`/`Generic` blueprint, named per-node RED/GREEN cycle, concrete terminal algorithm, post-push compaction, single registration ownership 추가 | P0=0 P1=0 |
| User/caller | 현재 source-workspace 실행 경로와 executable root example proof 누락 | 현재 `uv` smoke path, package/root example regression lock, no-migration guidance, Redis #51 boundary 추가 | P0=0 P1=0 |

## Main integration review

- 승인된 모든 spec requirement가 Task 1-9와 구체적인 validation command에 매핑된다.
- Task order는 package/constructor, state와 loop ownership, sync loading, async
  loading, async cancellation, packaging, docs, performance/stability, full
  workflow verification 순으로 실행 가능하다.
- Public signature, stats field, validation taxonomy, generation/flight ownership,
  terminal cleanup을 명시했다.
- New-package registration은 workspace source/member/dependency, meta extra,
  lock, broad CI collection, build, isolated base/extra install, package layout,
  README locale, changelog/WIP state를 다룬다.
- Test design은 success, failure, boundary, concurrency, cancellation, lifecycle,
  mutation, saturation, secret-safe observability, metadata bound와 finite
  teardown을 다룬다.
- Implementation placeholder나 later-task dependency가 없다. Performance 및
  operational evidence는 durable하고 독립적으로 감사할 수 있다.

최종 gate: **P0=0 P1=0**.
