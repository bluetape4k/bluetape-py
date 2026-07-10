# Issue #45 Strict Serde JSON — Step 3-R Plan Review

Date: 2026-07-10
Baseline: `3ff99dc`
Spec: `docs/superpowers/specs/2026-07-10-issue-45-serde-json-design.md`
Plan: `docs/superpowers/plans/2026-07-10-issue-45-serde-json-implementation-plan.md`

## Scope

Six independent read-only perspectives reviewed task ordering, API precision,
strict JSON boundaries, bounded work, packaging, documentation, rollout, and
delivery evidence. The current session integrated findings, revised the plan,
and reran every affected lane.

## Perspective Results

| Perspective | Initial findings | Required revision | Final result |
| --- | --- | --- | --- |
| Performance | P1=2 | O(depth) cursor frames; bounded-allocation evidence for wide preflight and linear scanner | P0=0 P1=0 |
| Stability | P1=4 P2=3 | Exact input boundaries; context-free UTF-8 and encoder translation; unmatched-closer regression; parser and config edges | P0=0 P1=0 |
| Security | P1=1 | Reject exponent overflow through a finite `parse_float` hook under both trust profiles | P0=0 P1=0 |
| Operator/Ops | P1=2 P2=1 | Enumerated rollout/rollback; durable #46 constraints; final PR-head CI evidence | P0=0 P1=0 |
| Developer/API | P1=4 P2=1 | Buildable README ordering; both workspace sources; staged exports; exact aliases and signatures | P0=0 P1=0 |
| User/Caller | P1=3 P2=1 | Exact ordered exports; trusted-profile misuse warning; concrete migration and install guidance | P0=0 P1=0 |

## Main-Session Integration

The integration review mapped every acceptance criterion and DoD item to a
concrete task and verified that no task depends on a later artifact. It also
confirmed:

- strict TDD ordering from package scaffold through contracts, encode, decode,
  documentation, wheel proof, review, PR, and CI;
- exact public signatures, recursive `JsonValue`, staged exports, and final
  ordered `__all__` verification;
- deterministic configuration, metadata, byte, UTF-8, structural, and parser
  gates with fixed context-free errors;
- O(depth) encode traversal bookkeeping, incremental output consumption, and a
  one-pass constant-state decode scanner with named allocation evidence;
- dependency-free wheel metadata, core-only default install, local-extra smoke,
  multilingual documentation, reader-first rollback, and the #46 Fory handoff;
- final required-check evidence pinned to the last pushed PR head SHA.

## Explicit Reject With Rationale

The plan does not map every unexpected encoder `ValueError` to
`CIRCULAR_REFERENCE`. Circularity is classified deterministically during the
active-path preflight. Parsing stdlib exception text afterward would create a
runtime-message dependency; an unexpected encoder `ValueError` therefore maps
to `UNSUPPORTED_VALUE`. The stability rerun accepted this mapping.

## Convergence

| Priority | Initial | Remaining |
| --- | ---: | ---: |
| P0 | 0 | 0 |
| P1 | 16 | 0 |
| P2 | 6 | 0 |
| P3 | 0 | 0 |

Open questions: none.

Verdict: Step 3-R PASS. `P0=0 P1=0`.
