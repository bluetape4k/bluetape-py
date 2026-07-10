# Issue #8 Async Spec Review

## Scope

Reviewed `docs/superpowers/specs/2026-07-10-issue-8-async-design.md` for the
`bluetape-async` bounded fan-out contract before implementation planning.

## Result

P0: 0

P1: 0

Verdict: PASS

## Evidence

| Review lane | Result | Coverage |
|---|---:|---|
| Performance | PASS | Bounded admission, iterator pacing, cooperative timeout boundary |
| Stability | PASS | TaskGroup ownership, cancellation, timeout, iterator cleanup |
| Security | PASS | No credentials, unsafe input handling, or dependency expansion |
| Operator | PASS | Packaging, extras, metadata, documentation, and verification commands |
| Developer | PASS | API feasibility, validation, cancellation discriminator, testability |
| User | PASS | Public API clarity, failure expectations, and non-goals |

The final reruns confirmed that a direct mapper-raised `CancelledError` with no
pending cancellation is the supported terminal signal. Mapper self-cancellation
through `asyncio.current_task().cancel()` is explicitly outside the contract,
which avoids promising a distinction Python task cancellation cannot provide.
An exception from `next(iterator)` now has a native propagation and task-group
cleanup contract, with focused test coverage required.

## Non-blocking note

Combined invalid arguments intentionally have no specified validation precedence;
each invalid input class is required to fail before input consumption where that
class's validation occurs.
