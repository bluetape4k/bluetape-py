# Issue #12 Resilience Policies 계획 검토

날짜: 2026-07-14 KST
Artifact: `docs/superpowers/plans/2026-07-14-issue-12-resilience-implementation-plan.md`
Approved spec: `docs/superpowers/specs/2026-07-14-issue-12-resilience-design.md`
Gate: Type A Step 3-R

## 검토 방법

Main session이 plan에 대해 여섯 개의 별도 read-only review pass를 수행한 뒤
approved specification, repository package layout, generic CI job, meta
distribution, lock/build rule, fail-closed PyPI classification과 통합 pass를
수행했다. Production code는 구현하지 않았다.

## 검토 수렴

| Lens | 초기 주요 발견 | 수정 | 최종 |
| --- | --- | --- | --- |
| Performance | 새 benchmark가 임의 acceptance gate가 되고 wall-clock sleep이 bounded-wait proof를 느리거나 flaky하게 만들 수 있음 | Evidence-backed N/A threshold 유지, deterministic clock/coordination, bounded wait, 짧은 lock scope, 미승인 benchmark 대신 반복 stability matrix 요구 | P0=0 P1=0 |
| Stability | Owner module이 생기기 전에 24 export를 모두 lock하려 했고 cancellation wording이 이미 emitted admission event를 무시하며 observer failure가 probe/permit을 명시적으로 release하지 않음 | Exact final export gate를 Task 7로 미루되 placeholder는 두지 않고, prior admission과 금지된 cancellation terminal event를 구분하고 admitted-observer cleanup test 및 circuit lock 밖 clock 호출 추가 | P0=0 P1=0 |
| Security/privacy | Argument, result, exception, predicate, callable representation에 대한 event privacy negative proof 부족 | Recursive sentinel inspection, fixed-field/repr assertion, safe error test, low-cardinality policy-name guidance, raw exception/logger/traceback field 없음 추가 | P0=0 P1=0 |
| Operator/ops | 새 workspace distribution이 fail-closed release classifier를 우회하거나 불필요한 dedicated CI/nightly를 trigger할 수 있음 | Workspace-versus-publishable equality proof, resilience를 publishable이지만 v0.1.0 target 아님으로 분류, publication HOLD 유지, generic pytest/build ownership 증명, inconsistency일 때만 release-guide 수정 | P0=0 P1=0 |
| Developer/API | Constructor default, callback non-invocation, callable-object family, runtime awaitable violation, exact final export, decorator signature behavior를 모두 독립 실행할 수 없음 | Constructor/fluent signature table, per-policy validation test, callable-object/wrong-return-family case, ParamSpec/introspection/bound-method proof, 실제 implementation 후 final 24-name export test 추가 | P0=0 P1=0 |
| User/caller | Decorator surface가 direct call과 동등해야 하고 policy order가 universal recommendation으로 오해될 수 있음 | 실행 가능한 `@policy`/`@pipeline` 및 `.call()` example, immutable snake_case `.with_*()` composition, 두 order의 last-added-outermost trace, order가 caller-selected behavior임을 명시 | P0=0 P1=0 |

## Main integration review

- 승인된 10개 acceptance criteria가 Task 1-10과 구체적인 targeted/full command에 매핑된다.
- Task order는 temporary production placeholder 없이 shared value, backoff,
  retry, timeout, circuit, bulkhead, composition, packaging, docs, exact-head
  verification 순으로 실행 가능하다.
- Sync/async write scope는 native synchronization boundary에서 분리하고
  deterministic value, validation, classification, backoff, event creation,
  callable check, pure transition data만 공유한다.
- Cancellation, timeout ownership, predicate/observer failure, stale circuit
  completion, bounded wait expiry, cross-loop use, generator/callable misuse에
  named test와 terminal cleanup expectation을 부여한다.
- Packaging은 root workspace dependency/source/member registration, opt-in meta
  extra, `dev`/`all`, lockfile, build, isolated base/direct/extra install,
  provider-free CI collection, fail-closed release classification을 포함한다.
- English/Korean package/root/meta docs는 executable example과 parity check를
  하나의 task로 다룬다. `AGENTS.md`, package layout, WIP, changelog, Type A
  lesson gate도 명시적으로 소유한다.
- 각 task에 dependency, exact file, RED/GREEN behavior, command, expected result,
  commit point, rollback/rerun boundary가 있다. PR, merge, publication, release,
  tag, workflow dispatch는 권한이 없다.

## 기계 검사

- `git diff --check`: clean
- Placeholder scan은 plan의 명시적 prohibition sentence만 찾았고 `TBD`,
  `FIXME`, deferred implementation, production placeholder step은 없다.
- Planned implementation commit은 10개이며 Task 1-10과 일대일로 맞는다.
- 검토 당시 worktree에는 approved spec/review commit과 이 plan/review만 있었고
  production package file은 생성하지 않았다.

최종 gate: **P0=0 P1=0**.
