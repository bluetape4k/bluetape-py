# Issue #8 Async Package Delivery

## Context

`bluetape-async` adds a small public async API while retaining asyncio's
structured-concurrency cancellation behavior and the thin default install.

## Decision

Use one call-scoped `asyncio.TaskGroup`, an owner cancellation-count baseline,
and terminal admission state. Keep the package optional through
`bluetape[asyncio]` and cap worker allocation at 1024.

## Outcome

Contract tests cover ordered bounded execution, validation before consumption,
iterator and mapper failure, timeout cleanup, direct/self/external
cancellation, and named-task cleanup. Fresh wheel smoke and metadata inspection
confirmed the optional dependency boundary.

## Future Guidance

Public async documentation must show the sync, small known async, and bounded
parallel choices with executable snippets. Before opening a PR, ensure its body
ends in `## DoD Status` and record both a PR comment and a formal review entry.
