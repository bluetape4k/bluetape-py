# Issue #12 Circuit Breaker State Diagram Design

## Goal

Add one source-backed Circuit Breaker state diagram to the
`bluetape-resilience` package README so readers can understand the shared state
model used by synchronous and asynchronous breakers.

The diagram answers four questions:

1. What opens a `CLOSED` breaker?
2. Why does an `OPEN` breaker reject calls?
3. When does `OPEN` become `HALF_OPEN`?
4. How do recovery probes close or reopen the breaker?

## Scope

Create and embed this canonical asset pair:

- `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg`
- `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png`

Both `packages/bluetape-resilience/README.md` and
`packages/bluetape-resilience/README.ko.md` will embed the same English-label
PNG after the policy overview and before the existing policy-composition
sequence diagrams. Short localized prose will explain that sync and async
breakers share the same state semantics.

No production Python, tests, package metadata, public API, dependencies, or
release surfaces are in scope.

## Source Model

The authoritative state machine is `_CircuitData` in
`packages/bluetape-resilience/src/bluetape/resilience/_circuit.py`. The public
sync and async breakers coordinate access differently, but both delegate state
transitions to this model.

The diagram must encode these behaviors exactly:

- The initial state is `CLOSED`.
- A classified failure increments `consecutive_failures` while `CLOSED`.
- `CLOSED` becomes `OPEN` when `consecutive_failures >= failure_threshold`.
- Entering `OPEN` sets `open_until = now + open_duration`.
- An admission before `open_until` is rejected with `CircuitOpenError`; the
  breaker remains `OPEN`.
- No timer or worker changes the breaker state. The first admission at or after
  `open_until` lazily changes `OPEN` to `HALF_OPEN`.
- `HALF_OPEN` admits at most `half_open_max_calls` concurrent probes. An extra
  admission is rejected with `CircuitOpenError` without changing state.
- A successful probe increments `recovery_successes`.
- `HALF_OPEN` becomes `CLOSED` when
  `recovery_successes >= recovery_success_threshold`.
- Any classified probe failure changes `HALF_OPEN` to `OPEN` and starts a new
  open interval.
- An ignored or non-classified exception releases an owned half-open slot and
  does not count as a success or failure transition.
- Async cancellation likewise releases its owned half-open slot and does not
  count as a state transition.
- Generation checks prevent late outcomes from an older state generation from
  mutating the current state.

The primary state diagram will emphasize state-changing transitions and
admission decisions. Slot release, cancellation, and generation safety will be
summarized in a compact invariant note rather than represented as extra states.

## Chosen Representation

Use one shared UML-style state machine, not separate sync and async diagrams.
The state model is identical, and duplicating it would imply behavioral
differences that do not exist.

The asset contains:

- a filled initial node leading to `CLOSED`;
- three large state cards for `CLOSED`, `OPEN`, and `HALF_OPEN`;
- labeled, directed connectors for every state-changing transition;
- a rejection loop or adjacent decision annotation on `OPEN`;
- a capacity-rejection loop or adjacent decision annotation on `HALF_OPEN`;
- a prominent `lazy admission` label on `OPEN → HALF_OPEN`;
- one compact invariant note for ignored outcomes, cancellation, slot release,
  and generation safety.

There is no final state: a Circuit Breaker is a reusable, nonterminal policy.
Counter-only changes such as a successful `CLOSED` call resetting consecutive
failures remain inside the `CLOSED` card rather than becoming pseudo-states.

## Visual Design

The diagram uses the established Bluetape README visual family while applying
UML state-machine semantics:

- white canvas with generous but bounded outer whitespace;
- handwritten title and concise technical subtitle consistent with the
  existing resilience sequence assets;
- three visually balanced rounded state cards with large state names and short
  counter/admission summaries;
- muted blue for normal admission/recovery flow, muted red for failure/opening
  flow, amber for rejection/waiting decisions, and olive or teal for successful
  recovery;
- explicit, fixed arrow markers whose color matches each connector;
- short labels placed off connector strokes, with no detached label bands;
- no decorative icons, shadows, gradients, or framework logos.

The intended canvas is approximately `1900 × 1100` SVG units. `CLOSED` sits on
the left, `OPEN` on the upper right, and `HALF_OPEN` on the lower right. This
triangular layout keeps the three state-changing routes distinct:

- `CLOSED → OPEN` across the upper lane;
- `OPEN → HALF_OPEN` down the right lane;
- `HALF_OPEN → CLOSED` across the lower lane;
- `HALF_OPEN → OPEN` uses a short return route on the right without crossing
  the recovery connector.

The final geometry may move within the canvas during audit repair, but it must
preserve this topology and keep all connectors outside card interiors except at
their endpoints.

## Diagram Standards Mapping

This asset is a UML state machine rather than a participant/lifeline sequence
diagram. Therefore:

- Bluetape diagram common rules remain authoritative for source-backed content,
  SVG/PNG pairing, typography, palette, whitespace, marker consistency,
  geometry, endpoint, and full-size visual inspection.
- The Fireworks technical-graph state-machine conventions supply the
  specialized node-and-transition semantics.
- Sequence-only requirements such as participants, lifelines, activations,
  chronological message numbering, `alt` frames, and `loop` frames are not
  applicable.
- Unsupported generic audit counts must be replaced by targeted XML invariants,
  never silently waived.

The existing sync and async sequence diagrams remain the authority for runtime
wrapper order. The new state asset explains only Circuit Breaker lifecycle and
must not duplicate their call chronology.

## README Placement

Add a localized section named `Circuit Breaker state model` / `Circuit Breaker
상태 모델` immediately after the Policies table and its lazy-recovery paragraph.
The resulting reader flow is:

1. policy capabilities and constraints;
2. Circuit Breaker state model;
3. policy-composition execution order;
4. synchronous and asynchronous usage.

Each README embeds the PNG once using the same repository-relative asset. The
English prose and Korean prose must carry the same claims, especially that
recovery is admission-driven and does not use a background timer.

## Asset Workflow And Validation

Treat this as a one-asset workflow:

1. edit only the state-machine SVG;
2. validate XML with `xmllint --noout`;
3. render with
   `cairosvg <svg> -o <png> -s 2`;
4. run connector, geometry, endpoint, mixed-corner, and applicable state or
   architecture-style audits;
5. run targeted XML invariants for the three state nodes, one initial node,
   four state-changing transitions, both rejection decisions, marker use, and
   nonempty labels;
6. inspect the PNG at original size after the final coordinate change;
7. update both READMEs and the diagram review ledger;
8. verify asset links, locale parity, dimensions, counts, and
   `git diff --check`.

The user performs the final human inspection from the absolute SVG and PNG
paths. The branch and draft PR must not be pushed or reported merge-ready before
that visual decision.

## Rejected Alternatives

### Separate sync and async state diagrams

Rejected because both breakers share `_CircuitData`. Two nearly identical
assets would add review and maintenance cost while suggesting a semantic split.

### Add state overlays to the existing sequence diagrams

Rejected because the sequences already answer wrapper-order and cleanup
questions. Adding a full state machine would make both assets denser and less
readable.

### Show an automatic timer transition

Rejected because the implementation has no timer-driven `OPEN → HALF_OPEN`
transition. Only a later admission observes `open_until` and performs the
transition.

### Model counters and ignored outcomes as extra states

Rejected because they are state data or non-transitioning outcomes. Cards and
an invariant note communicate them without inventing lifecycle states.

## Acceptance Criteria

- The diagram contains exactly one initial node and the three implemented
  states: `CLOSED`, `OPEN`, and `HALF_OPEN`.
- Every state-changing connector agrees with `_CircuitData`; no connector
  implies a background timer, detached task, or hidden worker.
- Pre-deadline `OPEN` admission and over-capacity `HALF_OPEN` admission are
  visibly rejected without a state change.
- Ignored exceptions and cancellation are described as slot-releasing,
  non-counting outcomes, not success or failure transitions.
- The PNG is the CairoSVG 2x render of the XML-valid SVG.
- Common audits and targeted state invariants report meaningful nonzero counts
  and zero failures.
- Original-size inspection finds no clipped labels, connector crossings,
  connector/card intrusion, mismatched markers, hard mixed corners, cramped
  text, or excess whitespace.
- English and Korean package READMEs embed the same PNG once and preserve claim
  parity in localized prose.
- The final handoff provides the absolute SVG and PNG paths and waits for the
  user's visual verdict before any push.
