# Issue #63 Active-Marker Result Transfer 분석

## 결과

채택한 candidate는 고정 coordination snapshot Lua script를 변경하여 active marker가 result bytes를 반환하지 않게 합니다. Provider는 이 응답을 `result=None`으로 매핑하고 completed 및 missing marker는 기존 bounded result prefix를 유지합니다. Public signature, exception, ACL, key, TTL, round-trip contract는 바뀌지 않습니다.

전체 paired benchmark는 primary correctness target을 충족했습니다.

| Mode | Baseline active bytes | Candidate active bytes | Reduction | Baseline snapshots | Candidate snapshots |
|---|---:|---:|---:|---:|---:|
| sync | 1,572,864 | 0 | 100% | 24 | 25 |
| async | 1,835,008 | 0 | 100% | 28 | 24 |
| total | 3,407,872 | 0 | 100% | 52 | 49 |

Completed-result reuse는 네 sync/async case 모두에서 non-zero로 유지되었고, 모든 scenario invariant가 통과했으며 generic comparison은 `comparable=true`와 빈 reason을 보고했습니다.

## Paired evidence

| Item | Value |
|---|---|
| Pair | `issue-63-pair-000`, index 0, baseline-first |
| Seed/profile/modes | `20260713`, full, sync 및 async |
| Runner | `runner-colima-a`, Colima, macOS arm64, 10 CPUs |
| Python / Redis | 3.13.14 / 8.8.0 (`redis` dependency 8.0.1) |
| Baseline | `b2f3ad5de9c5b0bdb3e1c206ac1581a3df9af474` |
| Candidate | `984c49ad7b701f9e1c17a3176c4ea8fd8f2a1252` |
| Baseline artifact SHA-256 | `3d0cc4f8f88e0a70ae1cc03a647d4c5c1f25f0a6306cd19f1f7dacfbfb5da1ab` |
| Candidate artifact SHA-256 | `c57f3a2d34a68845854c37835eee07443d3762c3c8b4f93340b02296db74d39b` |
| Comparison artifact SHA-256 | `8e287e32e8cd793b59b4b0cc547724d7990476ff63138cd3a77b04c7a4f81861` |
| Lock / registry digest | `a825207f86a8935492348035f65b942db501fe4fb6d3609797c3e678cdcbbd36` / `2cc0e4b8700f3678aa51e004acfd966a4fdd363a9b5435459188b039849e5566` |

두 report 모두 source가 clean했습니다. Paired environment, dependency lock, registry, image, policy identity가 일치했습니다.

## Command-parity 수정

처음 승인한 validator는 모든 scenario에서 raw Redis command equality를 요구했습니다. Concurrent polling으로 active-snapshot count가 달라진 첫 valid candidate를 거부했습니다. 동일한 baseline SHA를 diagnostic rerun하여 raw command drift를 재현했습니다.

| Case | Original commands | Same-SHA rerun | Commands minus active snapshots |
|---|---:|---:|---:|
| sync moderate | 18 | 19 | 8 / 8 |
| sync high | 40 | 39 | 16 / 16 |
| async high | 44 | 41 | 16 / 16 |

Diagnostic artifact SHA-256은 `ea701537942e95bd6a1e8da658e03b4a386a67005cc14a512557b86e875ea98c`입니다. 명시적 승인 후 acceptance rule을 `multi-coordinator`에서만 `redis_commands - active_snapshot_count`를 비교하도록 수정했습니다. 다른 모든 scenario는 raw command parity를 유지합니다. Exact provider test는 sync/async mode에서 snapshot마다 `EVAL` 하나를 추가로 입증합니다.

## Timing 관찰과 제한

Timing은 acceptance metric이 아닙니다. 선택한 high case에서 sync median은 14,104,875 ns에서 15,495,125 ns로, async median은 10,806,625 ns에서 12,304,083 ns로 바뀌었습니다. 이 단일 baseline-first sample은 latency improvement를 입증하지 않으며 capacity 또는 SLO evidence로 사용해서는 안 됩니다. 채택한 주장은 correctness와 command shape를 유지하면서 무시되던 active-marker result bytes를 제거했다는 데 한정됩니다.

Fixture에는 pre-baseline repair도 필요했습니다. Zero-delay `unrelated-keys` correctness case가 scheduler 운에 기대지 않고 concurrent loader를 입증하도록 bounded overlap gate를 사용합니다. Test-only readiness는 실제 integration case 시작 전에 mapped Redis port를 관찰하기 위해 `bluetape.testing.eventually`를 사용합니다.

첫 candidate capture 후 pre-PR review에서 작은 bound edge case를 발견했습니다. `max_marker_size < 7`이면 Lua가 `active:`를 인식하기 전에 marker가 잘렸습니다. 최종 candidate는 최소 7-byte internal probe를 읽고 caller marker bound보다 많이 반환하지 않으며 result read를 피합니다. Sync/async real Redis test가 six-byte boundary를 재현하고 고정합니다. 위 candidate report는 수정된 code checkpoint에서 다시 capture했습니다.
