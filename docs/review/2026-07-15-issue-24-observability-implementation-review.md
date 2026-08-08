# Issue #24 Observability 구현 검토

날짜: 2026-07-15 KST
검토한 implementation head: `40676c3d963a641ac230f40731fe065b9c2401ee`

## 방법

여섯 개의 독립 evidence pass가 같은 approved spec, plan, branch diff, focused
test, full-workspace test, benchmark output, CI workflow, wheel verifier,
bilingual docs를 검토했다. 각 pass는 통합 전에 assigned lens만 사용했다. 모든
P0/P1은 close를 차단했다.

## 발견 및 수정

| Priority | Lens | 근거 | 수정 | 결과 |
|---|---|---|---|---|
| P1 | Developer/API | Named Redis provider preservation test가 real provider control/observed path 비교 대신 adapter를 직접 호출 | `a1245e4`에서 sync success/failure-cause와 async success/cancellation control pair 추가 | 종료 |
| P1 | Developer/API | Real SDK assertion이 하나의 instrument descriptor만 고정 | `a1245e4`에서 다섯 instrument의 name/type/unit/description 전체 assertion | 종료 |
| P1 | Stability | Helper test는 process-control propagation을 증명했지만 adapter normalization boundary는 증명하지 않음 | `a1245e4`에서 `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`에 대한 policy/Redis boundary test 추가 | 종료 |
| P1 | Operator/Ops | Focused collection이 marker deselection 전에 workspace-only logging package를 import | `e672889`에서 해당 import를 marked test body로 이동 | 종료 |
| P1 | Developer/API | Full-workspace pytest가 bare `_support`와 duplicate test module basename 충돌 | `40676c3`에서 helper와 duplicate module에 observability prefix 부여 | 종료 |
| P1 | Stability | SDK absence를 증명한 뒤 generic suite가 SDK benchmark subprocess를 실행 | `40676c3`에서 `sdk` parameter만 `observability_sdk`로 mark | 종료 |
| P1 | Operator/Ops | 두 번째 기존 fail-closed release classifier가 새 distribution 누락 | `40676c3`에서 `bluetape-observability` 추가 | 종료 |
| P2 | User/caller | Korean rollback/observer-replacement wording에 untranslated English가 섞임 | Contract phrase를 parenthetical literal로 유지하고 `a1245e4`에서 자연스러운 Korean 복원 | 종료 |

## 최종 관점 결과

| Lens | 최종 근거 | P0 | P1 | Deferred |
|---|---|---:|---:|---|
| Performance | 3-run API/SDK budget, 64 KiB retention ceiling, owned resource 0 | 0 | 0 | External exporter latency N/A |
| Stability | Sync/async outcome preservation, cancellation, BaseException, teardown, repeated subprocess | 0 | 0 | External collector recovery는 application-owned |
| Security/privacy | Closed enum allowlist, bounded numeric, forbidden-field sentinel, baggage/log separation | 0 | 0 | 없음 |
| Operator/Ops | Direct install boundary, local diagnostics contract, rollback text, CI/wheel ownership | 0 | 0 | PR CI는 PR authority 대기 |
| Developer/API | Exact export/signature/descriptor, namespace packaging, full-workspace collection | 0 | 0 | 없음 |
| User/caller | Executable bilingual example, prerequisite, composition, failure policy | 0 | 0 | 없음 |

통합 결과: **P0=0, P1=0, P2=0**.

Tag, release, publication, workflow dispatch, PR creation, merge는 수행하지 않았다.
승인된 local implementation scope 밖이다.
