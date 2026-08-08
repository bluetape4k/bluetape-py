# Issue #15 Testcontainers Fixture Families 사양 검토

- Spec: `docs/superpowers/specs/2026-07-17-issue-15-testcontainers-fixtures-design.md`
- Review gate: Type A Step 2-R
- 날짜: 2026-07-17
- 최종 gate: P0=0, P1=0

## 검토 관점

| Lens | 초기 주요 발견 | 해결 | 최종 |
|---|---|---|---|
| Performance | P1=3: 지원하지 않는 PostgreSQL timeout 약속, LocalStack service forwarding 누락, provider-owned Ryuk cost 모호 | PostgreSQL timeout 제거, selected-service exact forwarding, wrapper-owned service cleanup과 provider-owned Ryuk 분리 | P0=0, P1=0 |
| Stability | P1=1: Lifecycle 및 cleanup-retry transition 불완전 | Complete state table, exact cleanup failure, idempotent close, context-manager exception precedence 추가 | P0=0, P1=0 |
| Security | P1=2: Wildcard port exposure와 ambient AWS credential 전달 가능 | Loopback-only dynamic binding 및 environment/provider discovery와 분리된 synthetic LocalStack credential 요구 | P0=0, P1=0 |
| Operations | Initial child lane 정지; main integration에서 CI reproducibility gap 발견 | Exact package extra/test-group sync, Docker preflight, serial service job, failure triage, service-container cleanup 근거 추가; fresh independent verifier가 확인 | P0=0, P1=0 |
| Developer/API | P1=2: Shared-error compatibility와 integration-test dependency가 정확하지 않음 | Compatible constructor/import path, explicit root export, package test group, focused locked command 고정 | P0=0, P1=0 |
| Caller/User | P1=1: Provider-extra ownership과 install guidance 모호 | Exact base/PostgreSQL/LocalStack/all install, dependency recovery, complete fixture example, upgrade guidance 추가 | P0=0, P1=0 |

## 수렴

첫 pass의 모든 P0/P1을 통합했다. Performance, stability, security, operations의
independent residual check는 `P0=0/P1=0`을 반환했다. Native child-thread limit로
추가 follow-up을 할 수 없었던 Developer/API와 caller/user finding은 main
integration이 corrected contract와 직접 대조했으며 잔여 P0/P1 gap은 없다.

Advisory finding도 implementation contract를 명확히 하는 범위에서 반영했다:
Secret-bearing PostgreSQL URL, image user-information rejection, bare-string
LocalStack service rejection, cleanup exception text, copy-paste fixture, caller
resource ownership, Redis-only upgrade compatibility.

## Main integration critique

선택한 경계는 official provider module 위의 thin adapter다. Generic lifecycle
base나 Redis refactor를 추가하지 않는다. Provider-owned Ryuk와 wrapper-owned
service container를 구분하고, provider가 지원하는 timeout만 광고하며, optional
client를 runtime dependency에서 제외하고, CI와 caller에 reproducible install/cleanup
path를 제공한다.

이 gate는 written design을 user review와 subsequent planning에 승인한다.
Implementation을 허가하거나 주장하지 않는다.

최종 gate: **P0=0 P1=0**.
