# Issue #63 Active-Marker Result Transfer Lessons

## Context and decision

분산 load coordination의 atomic snapshot은 marker가 active인 동안에도 이미 저장된
result prefix를 함께 반환했다. 호출자는 이 값을 사용하지 않으므로 Redis에서 Python
client로 불필요한 bytes가 전송됐다. 공개 API, key, TTL, ACL, round-trip 수를 바꾸지
않고 fixed Lua snapshot이 active marker에는 result를 반환하지 않도록 결정했다.

완료되거나 없는 marker의 bounded result reuse는 유지했다. Full paired benchmark에서
sync/async active result bytes는 합계 `3,407,872 -> 0`이었지만, 단일
baseline-first pair의 latency는 개선되지 않았다. 따라서 성능 주장은 전송 제거에만
한정하고 latency나 capacity 개선으로 확대하지 않는다.

## What the work proved

- 동시성 benchmark fixture는 scheduler 운에 기대면 안 된다. Zero-delay
  `unrelated-keys` case도 bounded overlap gate로 실제 동시 loader를 증명해야 한다.
- Concurrent polling의 raw Redis command 수는 동일 SHA 재실행에서도 active snapshot
  횟수만큼 달라질 수 있다. `multi-coordinator`만
  `redis_commands - active_snapshot_count`로 비교하고, 다른 scenario는 raw parity를
  유지하며 provider test로 snapshot당 `EVAL` 1회를 고정한다.
- Lua가 caller bound만큼 marker를 먼저 자르면 `max_marker_size < 7`에서 `active:`를
  식별하지 못한다. 내부 판정은 최소 7 bytes를 읽되 caller-visible marker와 result
  bound는 그대로 지켜야 한다.
- 이미 채워진 workspace 환경은 package-isolated CI dependency 누락을 숨긴다.
  `bluetape-cache-redis` test group은 `bluetape-testing`을 명시하고 임시
  `UV_PROJECT_ENVIRONMENT`로 exact sync/test를 재현해야 한다.
- CI green은 기술 검증이지 merge 권한이 아니다. PR은 승인된 delivery scope에서
  별도 승인 없이 만들 수 있지만, diagram/visual, lesson, current review/thread 등
  사람 판정 artifact를 모두 끝내 merge-ready를 보고한 뒤 fresh explicit approval을
  받아야 한다. 초기의 create-and-merge 요청이나 plan 승인을 재사용해서는 안 된다.

## Workflow failure and correction

PR #69는 9개 CI check와 P0/P1=0을 확인했지만, substantial Type F 작업에 필요한 이
lesson을 만들지 않았다. 후속 authority audit에서는 merge-ready 이후의 fresh
approval evidence도 확인할 수 없었다. 두 항목은 구현 결과와 무관한 workflow
위반으로 판정했다.

후속 작업에서는 중앙 `bluetape-workflow`와 workspace guidance를 다음처럼 교정했다.

1. 모든 task는 merge-ready 전에 lesson artifact 또는 evidence-backed `N/A`를 기록한다.
2. Type A는 정당한 evidence-backed `N/A`도 명시하는 committed lesson file이
   필수이고, substantial Type F는 실제 reusable learning을 담은 durable lesson이
   필수다.
3. PR creation은 approved delivery plan 이후 추가 승인을 요구하지 않는다.
4. 모든 merge는 CI, 최신 review/thread, applicable visual/diagram, lesson 및 기타
   human-review artifact를 완료한 뒤 fresh explicit user approval을 받아야 한다.
5. Auto-merge는 사용하지 않는다.

## Verification evidence

- Paired benchmark: active result bytes `3,407,872 -> 0`, completed-result reuse 유지.
- Full workspace: `uv run pytest`에서 1,515 tests 통과.
- Package-isolated CI parity: 336 unit tests와 31 Testcontainers tests 통과.
- Boundary RED/GREEN: 6-byte active marker가 수정 전 stale 64 bytes를 반환했고 수정 후
  result를 반환하지 않았다.
- Ruff, all-package build, actionlint, sealed-file validation, PR #69의 9개 CI check 통과.
- Final pre-PR review: P0=0, P1=0, P2=0, P3=0.

## Future guard

이 최적화를 다시 확장할 때는 deterministic concurrency gate, same-SHA benchmark
variance probe, small marker bounds, completed-result reuse, snapshot당 command shape,
package-isolated dependency 설치를 함께 검증한다. Benchmark 결과에는 측정한 claim만
기록한다. 마지막으로 PR 생성과 merge 권한을 분리하고, merge-ready 보고 후 받은
fresh approval 없이는 절대 merge하지 않는다.
