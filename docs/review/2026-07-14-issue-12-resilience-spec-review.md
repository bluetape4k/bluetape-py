# Issue #12 Resilience Spec Review

Date: 2026-07-14 KST
Artifact: `docs/superpowers/specs/2026-07-14-issue-12-resilience-design.md`
Artifact kind: spec

## Scope

The review covered the approved `bluetape-resilience` package boundary, public
sync/async API, fluent decorator composition, retry/backoff behavior, cooperative
async timeout, circuit and bulkhead state ownership, observability, packaging,
acceptance criteria, and validation evidence.

The current collaboration surface did not expose a role-selectable native review
dispatcher, so the six required perspectives were run as separate read-only passes in
the main session. No delegated assertion was treated as evidence. The main integration
pass normalized findings and reread every repaired section.

## Initial Findings and Repairs

| Priority | Lens | Evidence | Required edit | Result |
|---|---|---|---|---|
| P1 | Stability | Cancellation observation could allow an observer error to replace `CancelledError`. | Propagate cancellation before observer invocation and emit no cancellation event in v1. | Fixed in failure classification and acceptance coverage. |
| P1 | Stability | An operation-raised `TimeoutError` could be confused with the timeout context's own expiry. | Translate only policy-owned expiry and preserve an operation's original `TimeoutError`. | Fixed in the async timeout contract. |
| P1 | Stability | A raising circuit failure predicate did not explicitly release a half-open probe. | Release the generation-tagged slot without recording an outcome, then propagate the predicate error. | Fixed in the circuit contract and failure-mode table. |
| P1 | Developer/API | Public exports, enum members, event fields, snapshots, constructor inputs, and event ordering were category-level rather than executable contracts. | Fix the ordered exports, exact value shapes, signatures, pipeline methods, and event matrix. | Fixed in the public API and observability sections. |
| P1 | Security/Ops | Caller-provided policy names could become sensitive or high-cardinality labels. | Require stable non-sensitive names and document their presence in events and domain errors. | Fixed in the naming and observability contracts. |

## Final Perspective Results

| Perspective | Result | Evidence reviewed |
|---|---:|---|
| Performance | PASS | Bounded concurrency/waiting, no background reset/scheduler, user code outside locks, inline hook latency ownership |
| Stability | PASS | Cancellation precedence, owned timeout distinction, generation-tagged circuit completion, predicate/permit/probe cleanup, loop binding |
| Security | PASS | No caller arguments/results/raw exceptions in events, no global logging/exporter, stable non-sensitive policy-name boundary |
| Operator/Ops | PASS | Typed event matrix, immutable snapshots, lazy recovery, explicit observer failure semantics, package/README/release boundaries |
| Developer/API | PASS | Exact exports and value shapes, keyword-only constructors, separate sync/async families, immutable last-added-outermost pipeline, decorator/direct-call typing |
| User/caller | PASS | Small sync/async examples, explicit state sharing, order-dependent semantics, generator/sync-timeout exclusions, domain errors |

## Main Integration Verdict

- P0: 0
- P1: 0
- P2: 0
- P3: 0
- Verdict: PASS

The repaired specification remains within the user-approved design: stdlib-only
focused distribution, separate sync/async policies, async-only cooperative timeout,
and individual policy plus fluent pipeline decorators. The repairs close ambiguity
without adding HTTP/framework adapters, sync preemption, global state, or implementation
authority.
