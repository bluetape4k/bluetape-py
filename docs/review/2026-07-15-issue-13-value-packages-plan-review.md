# Issue #13 Value Packages 구현 계획 검토

날짜: 2026-07-15 KST
Issue: #13
판정: PASS
최종 발견: P0=0, P1=0

## 정확한 검토 대상

- Spec SHA-256: `0988eef8463eca44f485b91a472fe2958d3dbdf419a783a0c24a53de9f48923e`
- Plan SHA-256: `81ededc7b59a0d21c2ad9da5727288012fb8a18df60c99e86a1c4bad7c2da812`

## 수렴 기록

세 독립 read-only 관점이 같은 최종 hash를 검토했다.

- Developer/API: P0=0, P1=0. 36개 stable node contract 모두 full node ID,
  concrete fixture, intended RED cause, required GREEN assertion, exact one-node
  command를 가지며 literal Measure/TOML declaration과 task ownership이 실행 가능하다.
- Operations: P0=0, P1=0. 36 node contract와 command가 일대일이다. External
  dependency는 network-disabled local wheel phase 전에 hash-pinned lock export로
  설치한다. Provenance, rollback, rebase, diagram, exact-head replay가 닫혀 있다.
- User/caller: P0=0, P1=0. Compatibility, process-local persistence limit,
  versionless schema, custom-unit ownership, current-ISO limit, uninstall rollback,
  deferred work, EN/KO section parity에 task ownership이 있다.

Main session은 performance, stability, security를 독립 검토했고 각각 P0=0,
P1=0으로 끝냈다. 상세 근거는 sibling spec review에 기록했다.

Task 1에서 세 package-local file이 `test_packaging.py` basename을 공유하여
default pytest import mismatch를 재현했다. 파일을
`test_id_packaging.py`, `test_measure_packaging.py`,
`test_money_packaging.py`로 이름을 바꾸고 모든 owning-file/stable-node/exact
command path를 갱신했다. 수정된 plan hash를 세 독립 read-only re-review가
P0=0, P1=0으로 확인했으며 unique registry entry와 command는 각각 36개다.

## 실행 준비

- Task dependency와 rollback unit을 명시했다.
- Task 1이 executable publish classification과 release documentation을 함께 소유한다.
- 모든 implementation family가 exact RED node로 시작하고 owning-file/package
  verification으로 끝난다.
- ISO regeneration은 literal offline updater invocation과 byte comparison을 가진다.
- Wheel proof는 hash-pinned external dependency preparation과 network-disabled
  `--no-deps --no-index` local-wheel phase를 분리한다.
- README example은 checkout 밖 installed wheel에서 실행한다.
- `$bluetape-diagram`이 SVG+PNG generation, audit, visual inspection, hash,
  root English/Korean embed를 소유하며 Mermaid는 제외한다.
- 최종 convergence는 review 전에 rebase하고 stale evidence를 무효화하며
  generic/specialized proof를 exact unchanged HEAD에서 반복한다.
- PR creation은 승인된 범위지만 merge는 별도의 새 승인 gate다.

## 검증

- Stable node contract: 36
- Exact one-node invocation: 36
- Missing/duplicate invocation: 0
- Python code fence compile: 6
- Literal Measure import/signature smoke: Python 3.13.14에서 통과
- `git diff --check`: 통과

구현 stop condition: 의도하지 않은 이유로 named RED가 실패하거나
GREEN/owning-suite proof가 없으면 behavior family를 진행하지 않는다.
