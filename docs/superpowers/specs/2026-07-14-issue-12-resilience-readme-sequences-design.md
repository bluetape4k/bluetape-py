# Issue #12 Resilience README Sequence Diagrams Design

## Goal

Add two source-backed sequence diagrams to the `bluetape-resilience` package
README so readers can see how immutable policy composition becomes runtime
wrapper order for synchronous and asynchronous calls.

The diagrams answer two questions:

1. In which order do configured sync policies execute and unwind?
2. How does the async pipeline add cooperative timeout and cancellation-safe
   cleanup without hidden workers?

## Scope

Create and embed these canonical asset pairs:

- `docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg`
- `docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png`
- `docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg`
- `docs/images/readme-diagrams/bluetape-resilience-async-sequence.png`

Both `packages/bluetape-resilience/README.md` and
`packages/bluetape-resilience/README.ko.md` will embed the same English-label
PNGs between the policy overview and usage sections. Short localized prose will
explain that the last-added policy is the outermost runtime wrapper.

No production Python, package metadata, public API, dependency, or release
surface changes are in scope.

## Reference Adoption

The closest ecosystem reference is the `bluetape4k-projects` resilience4j
module:

- `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.md`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.ko.md`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-diagram-01.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-01.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-02.png`

Adopt its README progression from architecture visuals into features, its
explicit statement that the last decorator runs first, and its separation of
retry, circuit breaker, caller, decorator, and operation participants. Borrow
the CircuitBreaker + Retry lifecycle as a source-model comparison for the sync
asset and the cancellation contract as a comparison for the async asset.

Do not copy Kotlin-only RateLimiter, cache, fallback, Flow, or TimeLimiter
exception semantics into the Python diagrams. Do not preserve the older
reference assets' very tall sparse layout or detached branch-label bands. The
current Bluetape sequence best-practices family remains the visual authority for
numbered labels, transparent chronological frames, muted semantic colors,
fixed arrowheads, row density, and whitespace.

## Source Model

The authoritative behavior is implemented by
`packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py` and locked by
`packages/bluetape-resilience/tests/bluetape_resilience_tests/test_pipeline.py`.

- Each `.with_*()` returns a new pipeline and appends the supplied policy.
- Runtime wrapping iterates in append order, making the last-added policy the
  outermost wrapper.
- Sync supports `Bulkhead`, `Retry`, and `CircuitBreaker` but no timeout.
- Async additionally supports cooperative `AsyncTimeout`.
- Breaker and bulkhead instances retain shared state/capacity when reused.
- Async timeout and external cancellation unwind through policy cleanup without
  detached tasks or hidden workers.

## Visual Design

Both assets use the current Bluetape sequence family:

- handwritten title with concise source-backed subtitle;
- participant headers, dashed lifelines, activation bars, and horizontal
  message lanes;
- visible numbered message pills with 16x16 fixed, explicit per-color markers;
- muted blue calls, olive success/state, amber cleanup, teal returns, and muted
  red errors;
- transparent chronological `loop` and `alt` frames;
- English labels so the same asset can serve both README locales.

The best-practices catalog sequence
`/Users/debop/work/bluetape4k/bluetape4k-wiki/docs/diagrams/best-practices/assets/sequence-workflow-sample.png`
is the style authority. The nearest approved application sequence
`/Users/debop/work/bluetape4k/clinic-appointment/docs/images/readme-diagrams/appointment-api-sequence-01.png`
is the README-scale density reference. The resilience4j assets are behavioral
and ecosystem-layout references, not palette or geometry authorities.

### Synchronous Sequence

Participants: `Caller`, `ResiliencePipeline`, `Bulkhead`, `Retry`,
`CircuitBreaker`, and `Operation`.

The example composition is added as circuit breaker, retry, then bulkhead.
Runtime order is therefore bulkhead admission, retry attempt, circuit admission,
operation, outcome classification, retry when allowed, and final unwind with
permit release. Its retry and circuit-state branches retain the useful
behavioral focus of `infra-resilience4j-sequence-01` while using compact current
sequence frames. A footer states that sync timeout is intentionally absent.

### Asynchronous Sequence

Participants: `Caller`, `AsyncResiliencePipeline`, `AsyncBulkhead`,
`AsyncTimeout`, `AsyncRetry`, `AsyncCircuitBreaker`, and `Async Operation`.

The example composition is added as circuit breaker, retry, timeout, then
bulkhead. Runtime order is therefore bulkhead admission, timeout scope, retry
attempt, circuit admission, awaited operation, and reverse-order cleanup. An
`alt` frame distinguishes success, policy timeout, and external cancellation;
the cancellation branch propagates `CancelledError` unchanged.

## Asset Workflow And Validation

Complete the sync asset before editing the async asset:

1. edit exactly one SVG;
2. run `xmllint --noout`;
3. render with `cairosvg <svg> -o <png> -s 2`;
4. run connector, geometry, endpoint, mixed-corner, and sequence-style audits;
5. inspect the PNG at full size and repair any contradiction;
6. record dimensions, counts, failures, and inspection notes.

Repeat the same loop for the async asset. Then verify both README embeds,
localized prose parity, related-asset paths, and `git diff --check`.

The user performs the final human inspection from the absolute SVG and PNG
paths after local diagram validation passes. The PR must not be reported
merge-ready before that review decision.

## Acceptance Criteria

- Both diagrams match `_pipeline.py` behavior and do not imply package-owned
  threads, schedulers, or detached tasks.
- Each PNG is the CairoSVG 2x render of its matching XML-valid SVG.
- Sequence and common audits report meaningful nonzero entity counts and zero
  failures, or a concrete targeted invariant proves an unsupported generic
  count.
- Full-size inspection finds no clipped labels, line/label overlap, mismatched
  markers, hard mixed corners, connector intrusion, cramped lanes, or excess
  whitespace.
- English and Korean package READMEs expose the same two PNGs at valid relative
  paths with localized explanatory text.
- The final handoff provides absolute paths for all four assets and waits for
  the user's final visual verdict.
