# Issue #46 Apache Fory 사양 검토

날짜: 2026-07-11
Artifact: `docs/superpowers/specs/2026-07-11-issue-46-apache-fory-design.md`
Gate: Step 2-R 7-Tier spec review

## Iteration 1

| Tier | 초기 결과 | 적용한 필수 수정 |
| --- | --- | --- |
| Performance | P0=0 P1=3 | Thread-safe reuse, explicit allocation semantics, bounded/path-gated producer CI |
| Stability | P0=0 P1=4 | Frozen registration lifecycle, unchained error, supported provider limit, exact fixture pin |
| Security | P0=0 P1=5 | Exact root type, public Buffer consumption check, exception isolation, fixed trust/resource boundary |
| Operator | P0=0 P1=3 | Artifact-based bidirectional CI, rollout/rollback runbook, caller-owned observability |
| Developer/API | P0=0 P1=4 | Tagged 1.3.0 API alignment, public Buffer path, numeric ID bound, base error contract |
| Caller/User | P0=0 P1=6 | Nested-type scope, complete error/install/routing example, extras matrix, fixed-schema migration |

## 수렴 수정

첫 rerun에서 공유 P1 하나를 발견했다. Upstream `ThreadSafeFory`가 contention
후 unbounded runtime 수를 보존한다. Spec은 이제 bounded semaphore로 provider
call을 제한하고 finite acquisition timeout 동작을 정의하며, public
`fory_factory` seam을 통한 retained-runtime verification을 요구한다.

Stability는 이후 toolchain reproducibility가 불완전함을 발견했다. Spec은 이제
CPython, Go, Rust, Temurin, Gradle, wrapper checksum, dependency version,
fresh-process regeneration을 고정한다. Operator review는 caller-owned
low-cardinality route attribution을 추가했다. Developer review는 불가능한
provider-message 기반 limit classification을 제거하고 eager public probe와
callback sentinel을 통해 registration failure를 격리했다. Caller review는
independent-policy example을 완성하고 local-wheel installation을 수정했다.

## 최종 재실행

| Tier | 최종 결과 | 잔여 참고 |
| --- | --- | --- |
| Performance | P0=0 P1=0 | Native RSS 및 post-allocation output observation은 non-blocking 근거로 남는다. |
| Stability | P0=0 P1=0 | Lazy provider lifecycle 위험은 eager probe와 failure isolation으로 다룬다. |
| Security | P0=0 P1=0 | Hard CPU/RSS isolation은 caller 책임으로 명시한다. |
| Operator | P0=0 P1=0 | Exact CI timeout/cache/retention 값은 검토된 implementation plan으로 이동한다. |
| Developer/API | P0=0 P1=0 | Public `pyfory 1.3.0` implementation surface를 지정했다. |
| Caller/User | P0=0 P1=0 | 남은 documentation refinement는 non-blocking이다. |

## Main integration critique

최종 contract는 caller가 선택하는 하나의 trust/routing model, route마다 하나의
fixed-schema adapter, deterministic numeric identifier, provider-independent
public failure, bounded concurrency, exact body consumption, reproducible
four-language fixture, artifact-based CI proof를 가진다. Cross-tier 수정은
충돌하지 않는다. Provider limit failure는 의도적으로 `INVALID_FORY`로 매핑하고,
outer byte 및 concurrency limit는 정확한 stable code를 유지한다.

Step 3 implementability cross-check에서 wording 모호성을 하나 명확히 했다.
Outer envelope version만 `UnsupportedVersionError`로 매핑한다. 구분할 수 없는
provider parse/version/limit failure는 검토된 error-classification paragraph가
요구한 대로 `INVALID_FORY`로 남긴다.

최종 gate: **P0=0 P1=0**.
