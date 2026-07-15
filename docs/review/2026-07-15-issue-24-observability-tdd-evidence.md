# Issue #24 Observability TDD Evidence

Date: 2026-07-15 KST
Issue: #24, milestone `0.2.0`
Implementation evidence head: `40676c3d963a641ac230f40731fe065b9c2401ee`

## Approved inputs

- Spec SHA256: `f555888ace6273bb7049073bdf953c816870599d725167321ed7e1f06c26f6a1`
- Spec review SHA256: `d28395e897d8944e13b68bda6c0997ebb88b8191ac6173bf75c20549e489b49a`
- Plan SHA256: `1943735f953f0d854a699d4ee7701851684223b9e803d3ed745401568e312339`
- Plan review SHA256: `be76f14965bb544697eeb1c438aae0cb12182bc744b839ae962191c17e22a118`

## Captured RED to GREEN transitions

| Task | RED evidence | GREEN evidence | Owning commit |
|---|---|---|---|
| Distribution boundary | Packaging registry run produced 4 failures and 6 passes because the distribution, workspace registration, lock entry, and classifier were absent | All 10 boundary/classifier nodes passed; wheel metadata contained only `opentelemetry-api>=1.43,<2` | `4d88d91` |
| Bounded recording primitives | `test_recording.py` failed at collection because `bluetape.observability._recording` did not exist | 6 normalization, span, failure-isolation, and source-boundary tests passed | `be3b72b` |
| Resilience and Redis adapters | Public API and adapter tests failed because the two public modules and three classes did not exist | 31 public API, resilience, and Redis mapping tests passed | `ae18d35` |
| Real SDK and context | SDK-selected tests initially had no implementation-backed aggregation/current-context proof | 6 SDK integration tests passed with no skip and caller-owned teardown | `c64891e` |
| Resource and performance | Deterministic ownership, retention, allocation, and benchmark contract tests were absent | 9 deterministic tests passed and both three-run benchmark modes satisfied budgets | `78be6ac` |
| Docs, CI, and wheel isolation | README execution, logging separation, CI ownership, and isolated wheel probes were absent | Documentation tests, `actionlint`, and the focused/default/readme wheel verifier passed | `3bc2e5f` |

Only captured failing runs are labeled RED. Later review additions that passed against already-correct
runtime behavior are recorded as coverage repairs, not retroactive RED claims.

## Review-driven coverage repairs

- `a1245e4` paired actual sync/async Redis providers with unobserved controls, asserted SDK metric
  type/unit/description for every instrument, and proved process-control exceptions propagate at
  adapter normalization boundaries.
- `e672889` moved the workspace-only logging import behind its marker after the focused gate proved
  collection happened before marker deselection.
- `40676c3` gave un-packaged observability tests unique helper/module names, marked only the SDK
  benchmark subprocess parameter as `observability_sdk`, and reconciled the remaining fail-closed
  release classifier.

## Pre-evidence convergence gates

Focused dependency state:

```text
57 passed, 9 deselected
8 SDK-selected passed, 58 deselected
JUnit failures=0 errors=0 skipped=0
Ruff check passed; 15 files formatted; focused sdist and wheel built
```

Full workspace state after a fresh all-package/all-extra sync that proved
`opentelemetry.sdk` absent:

```text
1586 passed, 139 deselected
Ruff check passed; 126 files formatted
15 distributions built as sdist and wheel
wheel verifier, actionlint, and git diff --check passed
```

The evidence commit is intentionally not self-referential. Its exact SHA and a fresh post-commit
rerun of both gates are delivery evidence, not content embedded in this file.
