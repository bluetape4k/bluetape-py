# Issue #23 Observability Research Lessons

## Context and decision

Issue #23 had to turn changing Python and OpenTelemetry guidance into a stable
package boundary without importing telemetry lifecycle into domain packages.
The decision keeps existing logging, resilience, cache, and provider contracts
OpenTelemetry-free. A future bridge belongs in a separate opt-in distribution
that uses only the OpenTelemetry API in production, while the application owns
the SDK, exporters, global providers, propagation, and shutdown.

## Reusable findings

### Recheck drift-prone facts at closeout

An external research summary identified an older OpenTelemetry Python release
as latest. A live read of the upstream GitHub releases showed `1.43.0` / `0.64b0`
instead, so both the repository note and preserved wiki note were corrected.
Research that records versions, signal maturity, release dates, or support
status must re-read the authoritative source immediately before validation;
source quality does not remove temporal drift.

### Preserve domain event semantics at telemetry boundaries

Typed events are useful telemetry inputs, but similarly shaped events do not
imply one shared observer contract. Resilience observers propagate failure,
whereas Redis observers isolate it. A bridge should translate fixed allowlisted
fields without changing event classes, ordering, synchrony, cleanup, or failure
semantics. Arbitrary caller observers keep those existing rules, while the
bridge adapter must catch its own telemetry/API failures before returning to the
package-local observer call. Instrumentation failure must not become a new
domain result.

### Separate execution context from telemetry payload

Python `contextvars`, OpenTelemetry Context, Baggage, and logging fields have
different ownership and trust boundaries. Task and `asyncio.to_thread()`
propagation does not justify automatic promotion of arbitrary logging context
or baggage into telemetry attributes. Raw threads and executor submissions need
an explicit, separately captured context when propagation is required.

## Verification evidence

- Python 3.13.14 documentation was checked for task, thread, executor, and
  `contextvars.Context` behavior.
- OpenTelemetry specification and Python status pages were checked for
  library/application ownership, signal maturity, cardinality, and sensitive
  data guidance.
- The upstream OpenTelemetry Python release list was re-read live and the stale
  version statement was repaired before review.
- Documentation diff, local links, independent P0/P1 review, and wiki indexing
  are required closeout gates for the research artifact.

## Future guard

Before issue #24 implements a bridge, refresh the OpenTelemetry Python release
and signal status again. Require API-only no-SDK behavior, injected-provider
tests, no global mutation, fixed low-cardinality attributes, hostile sensitive
data markers, and Python 3.13 context cleanup. Do not adopt an implementation
shape solely because it appears in a sibling language repository.
