# Issue #45 Strict Serde JSON — Step 2-R 검토

날짜: 2026-07-10
기준선: `5b804865b4db0331207d09e3ded040505f920d4c`
Spec: `docs/superpowers/specs/2026-07-10-issue-45-serde-json-design.md`

## 범위

여섯 개의 독립적인 read-only 관점에서 strict JSON package boundary를
검토했다. 현재 session은 발견 사항을 통합하고 정규화한 뒤 spec을 수정했으며,
영향받은 모든 blocker lane을 다시 실행했다. 이 gate에는 implementation이나
heavy test command를 포함하지 않았다.

## 관점별 결과

| 관점 | 초기 blocker | 수정 | 최종 결과 |
| --- | --- | --- | --- |
| Performance | P1=1 | incremental `iterencode()` byte budget과 linear constant-state depth scan | P0=0 P1=0 |
| Stability | P1=3 | 정확한 limit range, hard depth cap, immutable ownership, runtime type, error matrix | P0=0 P1=0 |
| Security | P1=1 | authenticated caller-owned expected policy; payload가 trust를 상승시키지 않음 | P0=0 P1=0 |
| Operator/Ops | P1=3 | stable error code, reader-first rollout/rollback, mandatory Fory handoff gate | P0=0 P1=0 |
| Developer/API | P1=4 | 정확한 signature/dataclass, version 1, strict key graph, context-free error | P0=0 P1=0 |
| User/Caller | P1=0 | JSON content type, trust 선택, safe policy example, version recovery 명확화 | P0=0 P1=0 |

## Main-session 통합

통합 검토에서 다음을 확인했다.

- 정확한 Python 3.13 public signature와 keyword-only construction
- deterministic metadata comparison order와 JSON version 1 지원
- string-only object key, 정확한 JSON-native value, cycle/depth validation,
  implicit codec 또는 type reconstruction 없음
- incremental output accounting과 one-pass decode structural preflight
- cause/context 또는 payload marker를 보존하지 않는 normative concrete
  exception class/code/message matrix
- thin default packaging, isolated wheel evidence, multilingual docs, rollout,
  #46 Fory compatibility gate

불가피한 `JSONEncoder.iterencode()` single-chunk allocation risk는 process-memory
비보장으로 명시적으로 문서화했다. adapter가 최종 assembly 전에 aggregate
output consumption을 중단하고 caller가 input object graph를 이미 소유하므로
P0/P1 defect가 아니다.

## 수렴

| 우선순위 | 잔여 |
| --- | ---: |
| P0 | 0 |
| P1 | 0 |
| P2 | 0 |
| P3 | 0 |

판정: Step 2-R PASS. `P0=0 P1=0`.
