# Issue #13 value packages 구현 검토

날짜: 2026-07-15 KST
검토한 implementation head: `76e89614a96e4ab7ea3af37adfc5fb626f0e4981`

## 방법

세 명의 독립적인 read-only reviewer가 승인된 spec, plan, `origin/develop..HEAD`
diff, package test, CI-shaped workspace test, wheel isolation, ISO regeneration,
bilingual docs, final diagram을 대상으로 여섯 관점을 검토했다. P0/P1 finding은
수정과 재검토 전까지 delivery를 차단했다.

## 발견 및 수정

| Priority | Lens | 발견 | 수정 | 결과 |
|---|---|---|---|---|
| P0 | User/caller, performance | Precision-256 arithmetic이 multiplication, division, FX, accumulation 결과를 조용히 반올림했지만 exact money로 반환 | Ordinary arithmetic에서 Decimal `Inexact`/ `Rounded`를 trap하고 explicit `quantize()`에서 caller-selected rounding을 허용, boundary probe 추가 | `76e8961`에서 종료 |
| P1 | Developer/API, stability | ISO parser가 empty table, missing country name, nested field, unexpected attribute를 허용 | 실제 `CcyNm IsFund="true"` contract를 보존하면서 exact root/table/row/field schema check 추가 | `76e8961`에서 종료 |
| P1 | Operator/Ops | Syntactically valid truncated canonical SIX response가 current snapshot이 될 수 있음 | Canonical URL generation에 source row 250개 이상과 unique currency 150개 이상 요구; 현재 source는 280/178 | `76e8961`에서 종료 |
| P2 | Developer/API | Unquantized formatting이 invalid rounding을 무시할 수 있고 unknown-minor-unit error priority가 argument에 따라 다름 | Public rounding argument를 일관되게 validate하고 rounding 전에 currency quantum을 resolve | `76e8961`에서 종료 |
| P2 | Operator/Ops | Provenance test가 manifest field 전체와 full generated output을 묶지 못함 | URL, date, digest, bytes, count, exclusion, byte-identical full-source regeneration assertion | `76e8961`에서 종료 |
| P2 | Security/privacy | Wheel verifier가 Python socket을 거부하지 않고 network-free import로 표시 | 열 개 isolated import probe 모두에서 `socket.socket`과 `socket.create_connection` 거부 | `76e8961`에서 종료 |
| P1 | Operator/Ops, CI | Linux checkout에서 Git이 CRLF provenance source를 LF로 normalize하여 raw download digest와 regeneration equality를 무효화 | ISO source family를 `binary`로 표시하고 exact byte를 재저장하며 Git index/worktree byte equality assertion | PR CI에서 종료 |

## 최종 관점 결과

| Lens | 최종 근거 | P0 | P1 | P2 |
|---|---|---:|---:|---:|
| Developer/API | Exact export/signature, rounding/error priority, serialization, full collection | 0 | 0 | 0 |
| Stability | ID 5,000회, measure/money 10,000회, concurrency, rollback, arithmetic trap | 0 | 0 | 0 |
| Operator/Ops | Canonical completeness, exact regeneration, release classification, wheel isolation | 0 | 0 | 0 |
| Security/privacy | Payload-free error, no secret claim, socket-denied import, runtime fetch 없음 | 0 | 0 | 0 |
| User/caller | Installed-wheel EN/KO example, explicit policy ownership, rollback guidance | 0 | 0 | 0 |
| Performance | Bounded value/state, hidden worker/I/O 없음, repeated stability matrix | 0 | 0 | 0 |

통합 결과: **P0=0, P1=0, P2=0**.

새 re-review 근거는 focused arithmetic/ISO test 47개, complete money test 85개,
wheel 18개, socket-guarded environment 10/10, exact canonical regeneration,
독립적인 zero-finding verdict 세 개다. Reviewer는 implementation을 수정하지 않았다.
