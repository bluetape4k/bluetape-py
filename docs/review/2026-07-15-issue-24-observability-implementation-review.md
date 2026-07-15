# Issue #24 Observability Implementation Review

Date: 2026-07-15 KST
Reviewed implementation head: `40676c3d963a641ac230f40731fe065b9c2401ee`

## Method

Six separate evidence passes reviewed the same approved spec, plan, branch diff, focused tests,
full-workspace tests, benchmark output, CI workflow, wheel verifier, and bilingual documentation.
Each pass used only its assigned lens before findings were integrated. Every P0/P1 blocked closure.

## Findings and repairs

| Priority | Lens | Evidence | Repair | Result |
|---|---|---|---|---|
| P1 | Developer/API | The named Redis provider preservation test called adapters directly instead of comparing real provider control and observed paths | Added sync success/failure-cause and async success/cancellation control pairs in `a1245e4` | Closed |
| P1 | Developer/API | Real SDK assertions pinned only one instrument descriptor | Asserted the complete five-instrument name/type/unit/description set in `a1245e4` | Closed |
| P1 | Stability | Helper tests proved process-control propagation, but adapter normalization boundaries did not | Added policy and Redis boundary tests for `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` in `a1245e4` | Closed |
| P1 | Operator/Ops | Focused collection imported a workspace-only logging package before marker deselection | Deferred that import to the marked test body in `e672889` | Closed |
| P1 | Developer/API | Full-workspace pytest collection collided on bare `_support` and duplicate test module basenames | Renamed the helper and duplicate modules with an observability prefix in `40676c3` | Closed |
| P1 | Stability | The generic suite executed the SDK benchmark subprocess after deliberately proving the SDK absent | Marked only the `sdk` parameter as `observability_sdk` in `40676c3` | Closed |
| P1 | Operator/Ops | A second existing fail-closed release classifier omitted the new distribution | Added `bluetape-observability` to that classifier in `40676c3` | Closed |
| P2 | User/caller | Korean rollback and observer-replacement wording mixed untranslated English into sentences | Kept contract phrases as parenthetical literals and restored natural Korean in `a1245e4` | Closed |

## Final lens results

| Lens | Final evidence | P0 | P1 | Deferred |
|---|---|---:|---:|---|
| Performance | Three-run API/SDK budgets; 64 KiB retention ceiling; zero owned resources | 0 | 0 | External exporter latency is N/A |
| Stability | Sync/async outcome preservation, cancellation, BaseException, teardown, repeat subprocesses | 0 | 0 | External collector recovery is application-owned |
| Security/privacy | Closed enum allowlists, bounded numerics, forbidden-field sentinels, baggage/log separation | 0 | 0 | None |
| Operator/Ops | Direct install boundary, local diagnostics contract, rollback text, CI/wheel ownership | 0 | 0 | PR CI awaits PR authority |
| Developer/API | Exact exports/signatures/descriptors, namespace packaging, full-workspace collection | 0 | 0 | None |
| User/caller | Executable bilingual examples, prerequisites, composition and failure policy | 0 | 0 | None |

Integrated result: **P0=0, P1=0, P2=0**.

No tag, release, publication, workflow dispatch, PR creation, or merge was performed. Those are
outside the approved local implementation scope.
