# Issue #46 Apache Fory 계획 검토

날짜: 2026-07-11
Artifact: `docs/superpowers/plans/2026-07-11-issue-46-apache-fory-implementation-plan.md`
Gate: Step 3-R 7-Tier plan review

## 초기 검토

| Tier | 초기 결과 | 주요 blocker 주제 |
| --- | --- | --- |
| Performance | P0=0 P1=3 P2=2 | Pool failure/reuse semantics, eager-probe accounting, executable final verifier, RSS isolation, exact cache input |
| Stability | P0=0 P1=5 P2=1 | Lazy registration failure, exact Python pin order, manifest lifecycle, reproducible Go/Kotlin generation, same-runtime reuse |
| Security | P0=0 P1=5 P2=2 | Trust gate, exception-local cleanup, semaphore release, import-failure classification, empty/root-body handling 및 no-log proof |
| Operator/Ops | P0=0 P1=3 P2=3 P3=2 | Normal-CI fixture proof, producer manifest fragment, observability boundary, exact trigger, operational limit, canary/rollback, cache/temp hygiene |
| Developer/API | P0=0 P1=2 | Explicit optional-extra execution과 cross-language field identity |
| Caller/User | P0=0 P1=3 P2=2 | Application ID ownership, local meta-extra install proof, troubleshooting, fixed-schema migration, API/error documentation |

## 적용한 수정

- Eager-probe와 pooled-runtime accounting, ordinary failure reuse, lazy
  registration failure translation, semaphore release, deterministic
  runtime-identity test를 정의했다.
- Provider 작업 전에 CPython 3.13.14를 고정하고 모든 provider command가
  `--package bluetape-serde --extra fory`를 명시적으로 선택하도록 했다.
- 모든 fixture가 존재할 때까지 canonical four-producer manifest를 미루고,
  각 producer가 정확한 toolchain과 고정 locale/timezone의 isolated temporary
  path에서 두 번 생성하도록 했다.
- SHA-256 validation이 있는 runnable verifier distribution을 tar로 묶어
  artifact transfer에서 executable mode를 보존했다.
- Pre-provider gate와 concurrency timeout에도 fresh-error isolation을
  확장하고 direct/transitive/ABI import classification, no-log, empty-body,
  Fory root-header, sensitive-local test를 추가했다.
- Normal-CI checksum/Python decode gate, machine-readable producer fragment,
  exact workflow trigger, authoritative lock check, per-route observability
  isolation, resource-limit scope, actionable canary/rollback을 추가했다.
- 공식 API가 요구하는 Kotlin KSP `@ForyField` metadata를 유지하고 Python
  `pyfory.field`, Go struct tag, Rust attribute, Kotlin annotation을 통해
  field ID 1-4를 맞췄다.
- No-index local meta-extra installation proof, application-owned ID manifest
  contract, ABI troubleshooting, versioned-route migration, public API/error
  table 갱신을 추가했다.

## 최종 재실행

| Tier | 최종 결과 | 잔여 참고 |
| --- | --- | --- |
| Performance | P0=0 P1=0 | Timing과 RSS는 flaky absolute gate가 아닌 기록된 근거로 남긴다. |
| Stability | P0=0 P1=0 | Task dependency와 exact generation command를 순서대로 구현할 수 있다. |
| Security | P0=0 P1=0 | Hard CPU/RSS containment는 명시적으로 문서화한 process boundary다. |
| Operator/Ops | P0=0 P1=0 | CI, artifact, observability, rollback에 구체적인 verification path가 있다. |
| Developer/API | P0=0 P1=0 | Provider command와 four-language field metadata가 지원되는 1.3.0 surface를 사용한다. |
| Caller/User | P0=0 P1=0 | Install, ownership, error recovery, migration, docs 계약이 완료되었다. |

## Main integration critique

승인된 모든 spec requirement는 Task 1-13에 매핑되며 canonical artifact를
producer task보다 먼저 소비하는 task는 없다. Plan은 provider-free base behavior와
explicit provider verification을 분리하고, 네 runtime에서 하나의 field-ID와
varint schema를 사용하며, expensive generation은 path-gated로 유지하고 normal
CI에서는 저비용 committed-fixture check를 수행한다. Public behavior 변경은
두 root README locale, package README, changelog, package layout, rollout,
rollback, application ownership을 모두 다룬다.

최종 plan에는 구체적인 red/green command, failure/lifecycle test, full
verification, review convergence, PR/CI 처리, lesson, knowledge capture가 있다.
미해결 placeholder나 later-task dependency는 남아 있지 않다.

최종 gate: **P0=0 P1=0**.
