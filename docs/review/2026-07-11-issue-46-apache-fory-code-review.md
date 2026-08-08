# Issue #46 Apache Fory 코드 검토

날짜: 2026-07-11
범위: `origin/develop...feat/issue-46-apache-fory`
Gate: Step 6-R 구현 검토

## 초기 검토

| Lane | P0 | P1 | 발견 |
| --- | ---: | ---: | --- |
| Performance | 0 | 0 | Bounded semaphore/pool 동작, failure 이후 재사용, allocation 관찰, isolated RSS 근거가 승인된 non-absolute gate와 일치한다. |
| Stability | 0 | 1 | Legacy JSON contract test가 pre-Fory root export list를 여전히 기대하여 focused Fory test는 통과해도 전체 suite가 실패했다. |
| Security | 0 | 0 | Trusted metadata, 고정 envelope/schema/type gate, 정확한 body consumption, provider failure sanitization, payload-selected dispatch 없음이 적용되어 있다. |
| Operator/Ops | 0 | 1 | CI provider command가 매 invocation에서 `bluetape-serde` package, `fory` extra, CPython 3.13.14를 선택하지 않고 앞선 `uv sync`에 의존했다. |
| Developer/API | 0 | 1 | 승인된 design example은 positional `ForyAdapter(registration)`을 사용했지만 구현된 public constructor는 keyword-only다. |
| Caller/User | 0 | 0 | Install matrix, independent producer/consumer policy, trusted-only routing, migration, telemetry, rollback, hard-containment boundary를 문서화했다. |

## 수정 사항

- JSON contract test를 전체 25-export root surface로 확장하고 전체 suite를 다시 실행했다.
- 모든 provider-dependent CI invocation이 `--package bluetape-serde --extra fory --python 3.13.14`를 명시적으로 선택하도록 했다.
- Design example을 `ForyAdapter(registration=registration)`으로 수정했다.

## 최종 재실행

| Lane | P0 | P1 | 근거 |
| --- | ---: | ---: | --- |
| Performance | 0 | 0 | 5개의 performance/allocation/RSS observation이 통과했고 flaky absolute threshold는 추가하지 않았다. |
| Stability | 0 | 0 | CPython 3.13.14에서 737 tests가 통과했고 deterministic four-language generation 및 verification도 통과했다. |
| Security | 0 | 0 | malformed input과 failure isolation을 포함한 339개의 focused contract/Fory/packaging test가 통과했다. |
| Operator/Ops | 0 | 0 | `actionlint`, all-package build, artifact manifest verification, clean-worktree check가 통과했다. |
| Developer/API | 0 | 0 | Ruff check/format이 통과했고 public docs/example이 keyword-only API와 explicit extra boundary에 일치한다. |
| Caller/User | 0 | 0 | English/Korean root docs 및 package docs가 같은 install, route, migration, telemetry, rollback 계약을 설명한다. |

## 잔여 P2/P3 결정

- Timing 및 RSS 값은 release threshold가 아니라 observation으로 남긴다.
- Apache Fory는 CPython 3.13-only 및 trusted-internal only로 유지한다.
- Nested application-class registration, automatic compatibility, codec fallback은 추가하지 않는다.

최종 gate: **P0=0 P1=0**.

## Step 7-R PR 검토

PR #49를 저장된 body, `origin/develop...HEAD` diff, issue metadata, live check와
대조해 검토했다. Assignee `debop`, milestone `0.2.0`, label `enhancement`가
Issue #46과 일치하며, `## DoD Status`가 body의 마지막 section이다. PR은 clean
merge state에서 merge 가능하고 review comment나 unresolved thread가 없다.

CI run `29138092706`은 workspace test job을 통과했다. Apache Fory Conformance
run `29138092746`은 Python, Go, Rust, Kotlin, downloaded-artifact final
conformance job을 모두 통과했다. Node runtime과 cache-reservation annotation은
non-blocking runner warning이며, 실패한 check는 없고 artifact correctness를
변경하지 않는다.

Step 7-R 최종 gate: **P0=0 P1=0**.
