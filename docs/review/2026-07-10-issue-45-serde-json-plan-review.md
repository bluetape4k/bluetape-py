# Issue #45 Strict Serde JSON — Step 3-R 계획 검토

날짜: 2026-07-10
기준선: `3ff99dc`
Spec: `docs/superpowers/specs/2026-07-10-issue-45-serde-json-design.md`
Plan: `docs/superpowers/plans/2026-07-10-issue-45-serde-json-implementation-plan.md`

## 범위

여섯 개의 독립적인 read-only 관점에서 task ordering, API precision, strict
JSON boundary, bounded work, packaging, documentation, rollout, delivery
evidence를 검토했다. 현재 session은 발견 사항을 통합하고 plan을 수정한 뒤
영향받은 모든 lane을 다시 실행했다.

## 관점별 결과

| 관점 | 초기 발견 | 필수 수정 | 최종 결과 |
| --- | --- | --- | --- |
| Performance | P1=2 | O(depth) cursor frame, wide preflight의 bounded-allocation evidence와 linear scanner | P0=0 P1=0 |
| Stability | P1=4 P2=3 | 정확한 input boundary, context-free UTF-8/encoder translation, unmatched-closer regression, parser/config edge | P0=0 P1=0 |
| Security | P1=1 | 두 trust profile에서 finite `parse_float` hook으로 exponent overflow 거부 | P0=0 P1=0 |
| Operator/Ops | P1=2 P2=1 | 명시적인 rollout/rollback, durable #46 제약, 최종 PR-head CI evidence | P0=0 P1=0 |
| Developer/API | P1=4 P2=1 | buildable README ordering, 두 workspace source, staged export, 정확한 alias와 signature | P0=0 P1=0 |
| User/Caller | P1=3 P2=1 | 정확한 ordered export, trusted-profile misuse 경고, 구체적인 migration/install guidance | P0=0 P1=0 |

## Main-session 통합

통합 검토에서 모든 acceptance criterion과 DoD item을 구체적인 task에 매핑하고,
어떤 task도 이후 artifact에 의존하지 않음을 확인했다. 또한 다음을 확인했다.

- package scaffold부터 contract, encode, decode, documentation, wheel proof,
  review, PR, CI까지 strict TDD 순서
- 정확한 public signature, recursive `JsonValue`, staged export, 최종 ordered
  `__all__` 검증
- deterministic configuration, metadata, byte, UTF-8, structural, parser gate와
  고정된 context-free error
- O(depth) encode traversal bookkeeping, incremental output consumption,
  named allocation evidence가 있는 one-pass constant-state decode scanner
- dependency-free wheel metadata, core-only default install, local-extra smoke,
  multilingual documentation, reader-first rollback, #46 Fory handoff
- 마지막 pushed PR head SHA에 고정한 최종 required-check evidence

## 명시적으로 거부한 항목과 근거

Plan은 모든 예상하지 못한 encoder `ValueError`를 `CIRCULAR_REFERENCE`로
매핑하지 않는다. Circularity는 active-path preflight에서 deterministic하게
분류한다. 이후 parsing stdlib exception text를 사용하면 runtime-message
dependency가 생기므로, 예상하지 못한 encoder `ValueError`는
`UNSUPPORTED_VALUE`로 매핑한다. Stability rerun은 이 매핑을 승인했다.

## 수렴

| 우선순위 | 초기 | 잔여 |
| --- | ---: | ---: |
| P0 | 0 | 0 |
| P1 | 16 | 0 |
| P2 | 6 | 0 |
| P3 | 0 | 0 |

열린 질문: 없음.

판정: Step 3-R PASS. `P0=0 P1=0`.
