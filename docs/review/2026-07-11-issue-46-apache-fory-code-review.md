# Issue #46 Apache Fory Code Review

Date: 2026-07-11
Scope: `origin/develop...feat/issue-46-apache-fory`
Gate: Step 6-R implementation review

## Initial Review

| Lane | P0 | P1 | Finding |
| --- | ---: | ---: | --- |
| Performance | 0 | 0 | Bounded semaphore/pool behavior, post-failure reuse, allocation observations, and isolated RSS evidence match the approved non-absolute gate. |
| Stability | 0 | 1 | The legacy JSON contract test still expected the pre-Fory root export list, so the full suite failed despite focused Fory tests passing. |
| Security | 0 | 0 | Trusted metadata, fixed envelope/schema/type gates, exact body consumption, provider failure sanitization, and no payload-selected dispatch are covered. |
| Operator/Ops | 0 | 1 | CI provider commands depended on a prior `uv sync` instead of selecting the `bluetape-serde` package, `fory` extra, and CPython 3.13.14 on each invocation. |
| Developer/API | 0 | 1 | The approved design example used positional `ForyAdapter(registration)` while the implemented public constructor is keyword-only. |
| Caller/User | 0 | 0 | Install matrix, independent producer/consumer policy, trusted-only routing, migration, telemetry, rollback, and hard-containment boundaries are documented. |

## Corrections

- Expanded the JSON contract test to the complete 25-export root surface and
  reran the full suite.
- Made every provider-dependent CI invocation explicitly select
  `--package bluetape-serde --extra fory --python 3.13.14`.
- Corrected the design example to
  `ForyAdapter(registration=registration)`.

## Final Rerun

| Lane | P0 | P1 | Evidence |
| --- | ---: | ---: | --- |
| Performance | 0 | 0 | 5 performance/allocation/RSS observations passed; no flaky absolute threshold was introduced. |
| Stability | 0 | 0 | 737 tests passed on CPython 3.13.14; deterministic four-language generation and verification passed. |
| Security | 0 | 0 | 339 focused contract/Fory/packaging tests passed, including malformed input and failure-isolation cases. |
| Operator/Ops | 0 | 0 | `actionlint`, all-package build, artifact manifest verification, and clean-worktree checks passed. |
| Developer/API | 0 | 0 | Ruff check/format passed; public docs and examples match the keyword-only API and explicit extra boundary. |
| Caller/User | 0 | 0 | English/Korean root docs and package docs describe the same install, route, migration, telemetry, and rollback contracts. |

## Residual P2/P3 Decisions

- Timing and RSS values remain observations rather than release thresholds.
- Apache Fory remains CPython 3.13-only and trusted-internal only.
- The implementation does not add nested application-class registration,
  automatic compatibility, or codec fallback.

Final gate: **P0=0 P1=0**.
