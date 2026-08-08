# Issue #54 Redis Provider Pre-PR 코드 검토

Review base: `eb272ac58a2fd0b8445de334b84ee8d557d9d3e7`
Mode: Inline execution. 요청에 따라 delegated agent 없이 여섯 관점 pass와 통합을
로컬에서 수행했다.

## 발견 및 수렴

| Priority | Lens | 발견 | 해결 |
|---|---|---|---|
| P1 | Developer/API | Full workspace pytest가 Redis와 serde의 `test_contracts.py` 사이 import-file mismatch를 보고했다. | Redis module 이름을 바꾸고 211 focused regression test와 1,237 full test를 `6ed10b1`에서 통과시켰다. |
| P2 | Operator/Ops | 계획한 isolated smoke가 provider만 설치한 뒤 `TTLCache`를 import하여 spec의 정확한 세 runtime dependency와 모순됐다. | 승인된 dependency boundary를 유지하고 coexistence proof를 위해 두 focused wheel을 명시적으로 설치했다. |

최종 미해결 발견: P0=0, P1=0, P2=0, P3=0.

## 여섯 관점 결과

| Tier | P0 | P1 | P2 | P3 | 새 근거 | 판정 |
|---|---:|---:|---:|---:|---|---|
| Performance | 0 | 0 | 0 | 0 | bounded parser, non-gating benchmark, direct async await | PASS |
| Stability | 0 | 0 | 0 | 0 | lifecycle/cancellation test, 10x repetition, Redis 8 lane | PASS |
| Security | 0 | 0 | 0 | 0 | 고정 Lua source, argument binding, hostile envelope, ACL 및 marker redaction | PASS |
| Operator/Ops | 0 | 0 | 0 | 0 | low-cardinality event, rollout/rollback docs, CI, lock/build/wheel | PASS |
| Developer/API | 0 | 0 | 0 | 0 | 22 ordered export, exact signature, sync/async parity, full suite | PASS |
| User/caller | 0 | 0 | 0 | 0 | 실행 가능한 focused example, 명시적 non-goal, English/Korean parity | PASS |

## 통합 검토 메모

- Performance: raw/derived allocation을 bound하고 Redis round trip을 추가하지
  않는다. Binary가 compact default이며 benchmark threshold는 CI gate가 아니다.
- Stability: sync/async provider가 observer code 전에 admission을 release한다.
  Factory-owned client는 한 번 close하고 borrowed client는 열어 두며 async
  close에는 joined transient task 하나만 있다.
- Security: caller data를 Lua에 interpolate하지 않는다. GET/DELETE fallback,
  decoder auto-detection, dynamic compressor selection, key/token/payload/URL
  logging이 없다. 보존된 cause는 trusted-only로 문서화한다.
- Operator/Ops: error/event는 stable하고 low-cardinality다. ACL requirement,
  versioned namespace rollout, TTL-aware retirement, no-`KEYS` guidance가
  명시되어 있다.
- Developer/API: 새 distribution이 `bluetape.cache.redis`를 소유하고 Redis를
  local cache/core/default/dev/all에 넣지 않는 namespace extension을 사용한다.
- User/caller: identity와 explicit compression, binary와 JSON, deadline ownership,
  owned/borrowed client, #55 non-goal을 두 locale에서 모두 확인할 수 있다.

Workflow scan은 literal `KEYS[1]`을 고정 Lua script 안에서만 찾았다. 이는
Lua key argument reference이며 unbounded Redis `KEYS` command가 아니다.
