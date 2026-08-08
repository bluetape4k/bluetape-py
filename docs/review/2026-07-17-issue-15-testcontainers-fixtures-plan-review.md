# Issue #15 Testcontainers Fixture Families 계획 검토

## 범위

- Artifact: `docs/superpowers/plans/2026-07-17-issue-15-testcontainers-fixtures-plan.md`
- Basis: 승인된 issue #15 design, 현재 Redis implementation/test, package metadata,
  CI, 두 README locale, workspace/repository guidance
- Gate: Type A Step 3-R. External provider, Docker networking, credential,
  dependency extra, cleanup ownership을 넘나드므로 risk prediction 포함
- Heavy command: 없음. Plan-only review

## 검토 실행

Performance와 Operator/Ops는 independent read-only native task로 실행했다.
User/caller는 별도 bounded native follow-up으로 실행했다. Stability와 Security
native task는 bounded window를 두 번 초과해 중단했고, native child-thread limit로
fresh Developer/API task를 할당할 수 없었다. Workflow fallback에 따라 main session이
세 local equivalent를 수행했으며 unavailable/stalled role을 숨기지 않았다.

## 통합 발견 및 수정

| 초기 priority | Lens | 근거 | 필수 수정 | 해결 |
|---|---|---|---|---|
| P1 | Performance | Provider phase가 supported wrapper timeout 밖인데 workflow cap 없음 | Wrapper total deadline을 주장하지 않는 whole-job cap | `timeout-minutes: 30`, exact validation, step-aware timeout triage |
| P1 | Stability | `STARTING -> CLEANUP_FAILED -> CLOSED`와 primary `BaseException` lifecycle 미검증 | Primary exception, retained cleanup state, retry, terminal close 증명 | PostgreSQL/LocalStack control-flow 및 cleanup-failure test |
| P1 | Security | Credential-bearing input의 뒤쪽 valid-looking digest를 image validation이 허용 가능 | Digest separator 하나만 parse하고 complete SHA-256 검증, input echo 금지 | Credential-plus-digest rejection 및 valid digest test |
| P1 | Security | Missing-boto3 behavior가 internal error를 mock했지만 `_load_provider()`의 실제 boundary 미증명 | Real lazy-loader exception boundary와 unrelated missing module propagation test | Guarded-import matrix 추가 |
| P1 | Operator/Ops | Empty Docker port binding도 subset assertion 통과 | Loopback-only subset 전에 non-empty binding 요구 | 두 real-service integration test 수정 |
| P1 | Operator/Ops | 모든 whole-job timeout을 infrastructure로 분류 | Docker preflight failure와 later lifecycle/test ambiguous timeout 구분 | Risk/CI wording 수정; later timeout은 blind retry를 차단 |
| P1 | Operator/Ops | Merge-ready command가 unresolved review thread를 조회하지 않음 | Exact PR GraphQL thread, pagination gap, zero-unresolved assertion | Head equality, `reviewThreads`, `hasNextPage` 추가 |
| P1 | Operator/Ops | Install table 교체가 current PyPI publication hold를 제거할 수 있음 | Source-only availability와 post-publication pip label 유지 | Hold 및 exact source-workspace sync command 추가 |
| P2 | Operator/Ops | Abnormal-exit cleanup의 PostgreSQL/LocalStack 식별 절차 없음 | Wrapper-owned service label과 Ryuk 제외 inspect-confirm-remove | Per-service label, unit assertion, bilingual runbook 요구 |
| P1 | User/caller | Stable error table에 `TestcontainerStartError.kind` example 없음 | Raw value 없이 stable kind를 branch하는 copy-paste example | 두 locale에 sanitized example |
| P1 | User/caller | PostgreSQL/LocalStack timeout ownership이 caller-facing하지 않음 | Wrapper timeout scope와 CI cap distinction 문서화 | Bilingual timeout-ownership table |
| P1 | User/caller | Fixture example이 English에만 할당 | Korean에도 full executable example과 warning 요구 | Task 6 Step 1을 두 locale로 확장 |
| P2 | User/caller | Locale scan이 install/error/timeout/cleanup/example section 누락을 놓칠 수 있음 | Paired executable anchor validation과 manual semantic parity | Anchor loop 및 final parity checklist 확장 |
| P1 | User/caller | Thread-safety와 LocalStack unsupported capability가 암묵적 | One-owner/non-thread-safe와 S3만 CI-proven임을 명시 | 두 locale에 caller guidance 추가 |

## 여섯 관점 최종 판정

| Lens | 최종 근거 | P0 | P1 | P2/P3 |
|---|---|---:|---:|---|
| Performance | Provider timeout 불변, serial job outer cap, steady-state hot path 없음으로 benchmark N/A | 0 | 0 | 없음 |
| Stability | Single-use lifecycle, startup/body control-flow, cleanup retry, serial Docker, Ryuk ownership test | 0 | 0 | 없음 |
| Security | Complete digest parser, negative input test, loopback, service label, lazy dependency, redacted error, ambient-AWS isolation | 0 | 0 | 없음 |
| Operator/Ops | Preflight/ambiguous timeout triage, bounded CI, orphan runbook, rollback, source-only availability, exact-head CI/thread evidence | 0 | 0 | P2 수정 |
| Developer/API | Sequential atomic task, shared helper 선행, extra 후 real service, additive export, private provider, compile 가능한 snippet | 0 | 0 | 없음 |
| User/caller | 두 locale에 install, fixture, reset/client ownership, stable error, timeout, cleanup/Ryuk, Redis compatibility, S3 limit | 0 | 0 | P2 수정 |

최종 판정: **P0=0, P1=0, P2=0, P3=0**.

## Step 3-R completeness

| Check | 결과 |
|---|---|
| Spec/DoD traceability | 모든 acceptance group이 Task 1-7과 named evidence에 매핑 |
| Implementable ordering | Shared identity -> adapter -> extra/lock -> real service/CI -> docs/lesson -> verification/PR |
| Backward dependency 없음 | 각 task가 이전 committed artifact만 소비하고 shared file은 sequential |
| Test shape | Success, invalid/empty/boundary, lazy dependency, lifecycle, cleanup retry, primary exception, redaction, backend, packaging, CI 명시 |
| Concurrency/coroutine | N/A. Wrapper는 synchronous/non-thread-safe이며 docs가 one fixture/caller owner, Docker test serial을 요구 |
| Command | Targeted/full sync, wheel smoke, Docker, Ruff, build, actionlint, diff, exact head, CI, GraphQL thread check 구체화 |
| Documentation | Package/root EN/KO, WIP, CHANGELOG, PR DoD, Type A lesson 할당 |
| New module/build registration | N/A. Existing Python distribution 확장이며 extra, lock, wheel metadata, CI job, import isolation으로 대체 |
| Duplication | Pure cross-adapter helper만 추출하고 generic lifecycle base는 피함 |
| Rollback/compatibility | Task별 stop/revert, Redis identity/message, base-only root extra, no publish/release, fresh merge approval 명시 |

## Plan artifact 검증

- Required header, checkbox, exact file scope, command, expected evidence, Lore
  commit, rollback point, traceability, implementation hold가 존재
- `_support.py`, PostgreSQL, LocalStack, unit/integration, packaging, docs Python
  snippet이 plan text로 compile
- Placeholder scan empty
- `git diff --check` 통과
- User가 reviewed written plan을 승인하기 전 implementation은 차단
