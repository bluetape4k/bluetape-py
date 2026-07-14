# Issue #12 Resilience Policies Plan Review

Date: 2026-07-14 KST
Artifact: `docs/superpowers/plans/2026-07-14-issue-12-resilience-implementation-plan.md`
Approved spec: `docs/superpowers/specs/2026-07-14-issue-12-resilience-design.md`
Gate: Type A Step 3-R

## Review Method

The main session performed six separate read-only review passes over the plan and
then an integration pass against the approved specification, repository package
layout, generic CI job, meta distribution, lock/build rules, and fail-closed PyPI
classification. The passes did not implement production code.

## Review Convergence

| Lens | Initial material findings | Repairs | Final |
| --- | --- | --- | --- |
| Performance | A new benchmark could become an invented acceptance gate, while wall-clock sleeps could make bounded-wait proof slow or flaky. | Kept performance thresholds evidence-backed N/A, required deterministic clocks/coordination, bounded waits, short lock scopes, and a repeated stability matrix instead of an unapproved benchmark. | P0=0 P1=0 |
| Stability | The first draft tried to lock all 24 exports before their owning modules existed; cancellation wording ignored already emitted admission events; admission-observer failures did not explicitly release probes/permits; circuit clock placement was implicit. | Deferred the exact final export gate to Task 7 without placeholders, distinguished prior admission from forbidden cancellation terminal events, added admitted-observer cleanup tests, and moved clock invocation outside circuit locks. | P0=0 P1=0 |
| Security/privacy | Event privacy needed executable negative proof across arguments, results, exceptions, predicates, and callable representations. | Added recursive sentinel inspection, fixed-field/repr assertions, safe error tests, low-cardinality policy-name guidance, and no raw exception/logger/traceback fields. | P0=0 P1=0 |
| Operator/ops | A new workspace distribution could bypass the fail-closed release classifier or trigger an unnecessary dedicated CI/nightly path. | Added workspace-versus-publishable/private equality proof, classified resilience as publishable but not a `v0.1.0` target, preserved publication HOLD, proved generic pytest/build ownership, and made release-guide edits conditional on inconsistency. | P0=0 P1=0 |
| Developer/API | Constructor defaults, callback non-invocation, callable-object families, runtime awaitable violations, exact final exports, and decorator signature behavior were not all independently executable in the first draft. | Added the constructor/fluent signature table, per-policy validation tests, callable-object and wrong-return-family cases, `ParamSpec`/introspection/bound-method proof, and a final 24-name export test after real implementations exist. | P0=0 P1=0 |
| User/caller | The requested decorator surface needed equal standing with direct calls, and policy order could be mistaken for a universal recommendation. | Required executable `@policy`/`@pipeline` and `.call()` examples, immutable snake_case `.with_*()` composition, last-added-outermost traces in both orders, and explicit documentation that order is behavioral and caller-selected. | P0=0 P1=0 |

## Main Integration Review

- All ten approved acceptance criteria map to Tasks 1-10 and concrete targeted or
  full-validation commands.
- Task order is executable without temporary production placeholders: shared values,
  backoff, retry, timeout, circuit, bulkhead, composition, packaging, documentation,
  and exact-head verification.
- Sync and async write scopes stay separated at native synchronization boundaries;
  only deterministic values, validation, classification, backoff, event creation,
  callable checks, and pure transition data may be shared.
- Cancellation, timeout ownership, predicate failure, observer failure, stale circuit
  completions, bounded wait expiry, cross-loop use, and generator/callable misuse all
  have named tests and terminal cleanup expectations.
- Packaging covers root workspace dependency/source/member registration, the opt-in
  meta extra, `dev`/`all`, lockfile, builds, isolated base/direct/extra installs,
  provider-free CI collection, and fail-closed release classification.
- English/Korean package, root, and meta documentation is one task with executable
  examples and parity checks. `AGENTS.md`, package layout, WIP, changelog, and the
  Type A lesson gate are explicitly owned.
- Each task has dependencies, exact files, RED/GREEN behavior, commands, expected
  results, a commit point, and a rollback/rerun boundary. PR, merge, publication,
  release, tag, and workflow dispatch remain unauthorized.

## Mechanical Checks

- `git diff --check`: clean.
- Placeholder scan found only the plan's explicit prohibition sentence; no `TBD`,
  `FIXME`, deferred implementation, or production placeholder step exists.
- Planned implementation commits: 10, aligned one-to-one with Tasks 1-10.
- Worktree contents at review time: approved spec/review commit plus this plan/review
  only; no production package files were created.

Final gate: **P0=0 P1=0**.
