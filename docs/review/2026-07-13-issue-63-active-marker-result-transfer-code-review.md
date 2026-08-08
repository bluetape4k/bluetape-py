# Issue #63 Active-Marker Result Transfer Pre-PR 코드 검토

- Review base: `349ef1417a16d7394bc261b685b489caf4a6bf83`
- Final code benchmark checkpoint: `984c49ad7b701f9e1c17a3176c4ea8fd8f2a1252`
- Verified documentation checkpoint: `cda8b80f21f039f8bc8bd6fee1225cac817af72c`
- CI dependency repair checkpoint: `999924f`

## 발견 및 수렴

| Priority | Lens | 발견 | 해결 |
|---|---|---|---|
| P1 | Developer/API | 첫 Lua branch는 caller-bounded marker value에서만 `active:`를 인식했다. `max_marker_size < 7`이면 stale result prefix를 반환했다. | Caller-bound prefix만 반환하면서 internal marker probe를 최소 7 byte로 추가했다. Sync/async real Redis test가 6-byte boundary를 재현하고 수정 후 통과한다. |
| P1 | Performance/stability | Concurrent active polling에서 동일 실행 간 snapshot count가 달라질 수 있는데 첫 acceptance rule은 raw command equality를 요구했다. | Same-SHA baseline rerun에서 variance를 증명했다. 승인된 rule은 `multi-coordinator`에만 기록된 active snapshot을 차감하고, 나머지 scenario는 raw parity를 유지한다. Provider test는 snapshot마다 `EVAL` 하나를 고정한다. |
| P1 | Operator/Ops | Redis package test group에 workspace testing helper가 없어 `bluetape.testing.eventually`를 import하는 package-isolated CI test를 수집하지 못했다. | Redis package test-only dependency group과 lockfile에 `bluetape-testing`을 추가했다. Production dependency는 변경하지 않았다. Exact isolated CI unit과 Testcontainers command가 통과한다. |
| P2 | Performance | Baseline-first pair 하나에서 candidate median이 느렸다. | Observational only로 문서화했다. 승인된 claim은 latency/capacity improvement가 아닌 ignored active result byte를 100% 제거했다는 측정이다. |

최종 미해결 발견: P0=0, P1=0, P2=0, P3=0.

## 여섯 관점 결과

| Lens | P0 | P1 | 근거 | 판정 |
|---|---:|---:|---|---|
| Performance | 0 | 0 | Active result bytes `3,407,872 -> 0`; stable command shape; extra round trip 없음 | PASS |
| Stability | 0 | 0 | Deterministic active-snapshot 및 unrelated-key overlap gate; 1,515 full test | PASS |
| Security | 0 | 0 | Fixed Lua only; existing key, TTL, redaction, binary bound, `EVAL` ACL 불변 | PASS |
| Operator/Ops | 0 | 0 | Deployment/configuration 변경 없음; Colima resource cleanup; all-package build 및 actionlint 통과 | PASS |
| Developer/API | 0 | 0 | Signature/exported-type 변경 없음; six-byte marker boundary 및 completed-result 동작 고정 | PASS |
| User/caller | 0 | 0 | Active snapshot은 `result=None`을 노출하며 completed/missing marker가 bounded result reuse를 보존 | PASS |

## Benchmark 근거

- Pair `issue-63-pair-000`, full sync/async, seed `20260713`, same Colima runner
- Generic comparison: comparable, no reason, distinct clean source SHA
- Baseline/candidate active result bytes: `3,407,872 / 0`
- Candidate sync/async active snapshot: `25 / 24`, 각각 required two보다 큼
- Snapshot-normalized command parity와 나머지 모든 scenario의 raw parity 통과
- Completed-reuse result-byte guard 네 개와 모든 scenario invariant 통과
- Final candidate/comparison SHA-256:
  `c57f3a2d34a68845854c37835eee07443d3762c3c8b4f93340b02296db74d39b` /
  `8e287e32e8cd793b59b4b0cc547724d7990476ff63138cd3a77b04c7a4f81861`

## 검증

- `uv sync --all-packages --all-extras --python 3.13.14 --locked`: 통과
- `uv run pytest`: 1,515 passed. Real Redis와 benchmark integration 포함
- Package-isolated CI parity: 336 unit test와 31 Testcontainers test 통과
- Boundary RED/GREEN: 수정 전 sync/async six-byte active marker test가 stale
  byte 64개와 함께 실패했고, 수정 후 result 없이 통과
- `uv run ruff check .`: 통과
- `uv run ruff format --check .`: 91 files already formatted
- `uv build --all-packages`: workspace distribution 13개 모두 build
- `actionlint`, `git diff --check`, sealed-file validation: 통과
- 검증 후 Docker container: 없음

Inline pre-PR gate는 P0=0, P1=0으로 수렴했다. Rebase merge 전에 GitHub
check와 fresh review-thread state도 통과해야 한다.
