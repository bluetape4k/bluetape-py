# Issue #45 JSON Serde 코드 검토

## 범위

- 기준: `develop@5b804865b4db0331207d09e3ded040505f920d4c`
- 검토 head: `a4727082cbe97c39e620605165ace69fe21dd50e`
- 계약: `bluetape-serde`의 strict, bounded JSON serialization
- 후속 경계: binary serialization은 Issue #46에 남기며, 여기서 도입한
  payload/error/limit 계약을 재사용해야 한다.

## 검증 gate

금지된 regex 기반 validation 경로와 오래된 performance test selector라는 두
P1 발견 사항을 수정한 뒤 독립 Step 5 verifier를 통과했다. 최종 Step 5 결과는
`P0=0 P1=0`이다.

## Step 6-R 검토 matrix

| Lane | 초기 발견 | 해결 | 최종 결과 |
| --- | --- | --- | --- |
| Performance | P1: `list[bytes]` chunk assembly가 allocation growth를 과도하게 유발 | 하나의 incremental `bytearray`로 chunk accumulation을 교체하고 allocation regression coverage 추가 | `P0=0 P1=0` |
| Stability | P1: failure traceback이 source 또는 partial output object를 보존 | handler 밖에서 새 typed error를 재발생시키고 큰 local을 명시적으로 해제 | `P0=0 P1=0` |
| Security | P1: rejected input이 exception state를 통해 도달 가능; 재실행에서 같은 위험을 가진 native decoder/encoder configuration error 발견 | public 및 native configuration error boundary를 정리하고 targeted security suite 통과 | `P0=0 P1=0` |
| Operator | P1: encode failure가 partial output을 보존; P1: durable Apache Fory 후속 근거가 아직 live하지 않음 | partial output을 해제하고 assignee, milestone, dependency, limits, trust policy, schema ID, cross-language conformance scope가 있는 live Issue #46 확인 | `P0=0 P1=0` |
| Developer | P1: integer acceptance가 CPython process-global digit setting에 의존; P1: 한 commit이 parseable Lore trailer를 노출하지 않음 | 대칭적인 public 640-digit integer limit과 error code를 추가하고 commit metadata 보완 | `P0=0 P1=0` |
| User | P2: local-wheel command가 불완전; P2: native caller-configuration failure가 명확히 문서화되지 않음 | English/Korean/package 문서를 갱신하고 caller-visible failure wording 정규화 | `P0=0 P1=0 P2=0 P3=0` |

## 통합 검토

- Public boundary는 `MAX_JSON_INTEGER_DIGITS`와 `INTEGER_DIGIT_LIMIT`을 포함해
  21개 name과 17개 stable error code를 export한다.
- Serialize 및 deserialize 경로는 process-global CPython 설정에 의존하지 않고
  byte, depth, reference, collection, string, integer-digit limit를 적용한다.
- Rejected value, source buffer, decoded text, metadata intermediate, partial
  output은 public error traceback에 보존되지 않는다.
- Optional package boundary는 격리되어 있다. `bluetape-serde`에는 runtime
  dependency가 없으며 meta package는 `serde`, `dev`, `all` extra를 통해서만
  포함한다.
- README, localized README, package layout, changelog, WIP 범위가 구현된 API와
  Issue #46 binary-serde 후속 작업에 동의한다.
- 이 additive package에는 release나 workflow 변경이 필요하지 않으며,
  repository-wide test와 package build가 registration 경로를 검증한다.
- 로컬 검증에는 Python 3.14.6을 사용했다. Repository CI는 Python 3.13
  compatibility authority이므로 merge 전에 정확한 PR head에서 통과해야 한다.

## 결과

모든 blocking review finding을 해결했다: `P0=0 P1=0`. 기록된 non-blocking
finding도 모두 해결했다: `P2=0 P3=0`.

## PR 이후 검토

정확한 head `a6f5b0fc496ddfe0f11b8fa5e38a6d4de2c3abc8`에 대한 PR #48 검토에서
P1 하나와 중복 제거된 P2 하나를 발견했다.

- P1: shared-reference DAG를 expanded path마다 검증하여, 작은 output limit가
  encoding을 멈추기 전에 exponential preflight CPU를 허용했다.
- P2: encode가 거부한 Python string과 달리 decode가 escaped unpaired UTF-16
  surrogate를 허용하여 strict round-trip model을 깨뜨렸다.

Commit `5f3774c21538792c32d597b8c7724443dac36242`가 두 finding을 해결했다.
처음의 completed container memoization은 repeated-DAG work를 bounded하게
했지만 O(unique containers) auxiliary state를 도입해 승인된 O(depth) 설계를
위반했다. 후속 수정은 active-path-only cycle state를 복원하고 output budget을
보수적인 encoded-byte lower bound로 사용한다. current-node type, cycle,
depth error가 여전히 해당 guard보다 먼저 발생한다. String은 기존 validation
scan 중 두 quote와 UTF-8 scalar width를 더하고, dict key와 colon은 sibling
state를 보존하지 않고 lazy하게 계산한다.

String은 이제 Unicode scalar value만 허용한다. Decode는 유효한 escaped
surrogate pair를 정규화하고, 값을 반환하기 전에 unpaired surrogate를
거부한다. Deterministic bounded-visit, distinct-sibling memory,
validation-order, Unicode, duplicate-key, source-retention regression이 수정된
계약을 검증한다. 정확한 PR head `05845fc`의 performance rerun은 completed-memo
O(unique containers) P1을 발견했다. exact head `b4e7eda`의 세 번째 rerun은
중간 one-byte occurrence guard가 큰 shared string과 key를 재검사할 수 있음을
발견했다. Deterministic large-value counter가 이 경우를 wall-clock threshold
없이 검증한다. Exact selector는 `8 passed, 237 deselected`, serde suite는
`389 passed`, workspace는 `535 passed`였다. 최종 rerun 상태는
`P0=0 P1=0 P2=0 P3=0`이다.
