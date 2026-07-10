# Issue #45 Strict JSON Serde Lessons

## Context

Issue #45 introduced the first shared serialization contracts and a strict,
bounded JSON implementation for `bluetape-py`. The work was reviewed across
performance, stability, security, operator, developer, and user perspectives.

## Decisions

- Treat exception object graphs as part of the resource-safety boundary. `raise
  ... from None` hides a cause but does not remove `__context__` or traceback
  locals. Create the public typed error after leaving the handler and release
  source, decoded text, metadata, and partial output locals first.
- Sanitize native decoder and encoder configuration failures too. Caller-facing
  `TypeError` or `ValueError` tracebacks can retain the same large objects even
  when public serde errors are already clean.
- Assemble incremental output into one `bytearray`. A `list[bytes]` avoids a
  final quadratic copy but can still consume excessive memory for tiny chunks;
  guard this with `tracemalloc` regression tests.
- Define an explicit symmetric integer contract. CPython's process-global
  integer digit setting is mutable and environment-dependent, so JSON encode
  and decode now enforce a public 640-digit limit independently.
- Keep executable verification selectors and parseable Lore trailers under
  test. A stale selector or visually plausible but split trailers weakens the
  evidence chain even when product code is correct.
- Keep Apache Fory outside Issue #45. Issue #46 owns binary serialization and
  must reuse the payload, error, limit, trust, schema-ID, and cross-language
  conformance contracts established here.
- Keep graph preflight state O(depth); a completed-container memo fixes repeated
  DAG traversal but grows O(unique containers). Bound repeated expansion with
  the output budget instead: every validated JSON value occurrence requires at
  least one encoded byte, so exceeding `max_output_size` is already a certain
  `output_limit` failure.
- Treat JSON strings as Unicode scalar values. Python's decoder accepts escaped
  surrogate code points, so normalize valid pairs to non-BMP scalars and reject
  unpaired surrogates explicitly to keep decode output re-encodable.

## Outcome

The final independent review matrix reached `P0=0 P1=0 P2=0 P3=0`. Targeted
serde tests, repository-wide tests, Ruff checks, package builds, wheel metadata,
and isolated installation smoke tests passed locally before publication.

## Guidance for Future Work

- When a failure path handles untrusted or large data, inspect the complete
  traceback and context graph instead of checking only exception messages.
- Measure adversarial chunk sizes and allocation peaks for streaming adapters.
- Test shared-reference graphs with deterministic visit counters; wall-clock
  thresholds are too noisy to prove traversal complexity. Pair that with a
  wide set of distinct sibling containers so complexity fixes cannot silently
  trade bounded CPU for O(unique containers) auxiliary memory.
- Never delegate bounded numeric behavior to mutable interpreter-global
  settings when the format contract must be portable.
- Re-run commands copied into plans or review artifacts exactly as written.
- Validate commit trailers with Git tooling before push when the repository uses
  Lore as a durable decision record.
