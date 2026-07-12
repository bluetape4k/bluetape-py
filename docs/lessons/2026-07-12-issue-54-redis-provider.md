# Issue #54 Redis Provider Lessons

## Context and Decision

The Redis substrate was kept in an opt-in `bluetape-cache-redis` distribution
under `bluetape.cache.redis`. It depends exactly on Redis, serde, and base
compression; it does not depend on or contaminate the stdlib-only local cache.
The parent cache package uses `pkgutil.extend_path` so independently built
wheels can coexist at the nested namespace.

Serialization, envelope format, compression, key naming, and rollout remain
caller policy. The provider only owns strict byte operations and explicit
client lifecycle. This keeps #55 coordination from inheriting hidden codec,
retry, or Redis ownership decisions.

## What the Implementation Proved

- Bounded parsers must reject raw size before JSON/base64 or binary field work,
  and must reject duplicates, unknown/missing fields, trailing bytes, invalid
  UTF-8/base64, version drift, and algorithm ambiguity.
- A recorded algorithm plus one exact reader registry supports reader-first
  compression migration without content sniffing or fallback decoding.
- Async close needs one shared transient cleanup task. Shielding is not enough:
  each cancelled caller must keep joining cleanup, then rethrow its original
  cancellation, and the provider must clear the task at terminal state.
- Redis `SET NX PX` and a fixed Lua compare-delete provide the required atomic
  substrate. Script ACL denial must fail closed rather than degrade to a racy
  GET/DELETE sequence.

## Surprises and Guards

Focused tests alone missed a pytest module-name collision with another package.
The full workspace suite caught it, so new package test modules need globally
distinct basenames unless package import mode changes deliberately.

The planned coexistence smoke built `bluetape-cache` but installed only the
provider before importing `TTLCache`. Because the approved dependency boundary
correctly excludes local cache, the proof must install both wheels explicitly;
adding a dependency to make an incorrect smoke premise pass would violate the
design.

Reusable closeout commands are the focused non-container lane, native lane,
serial Testcontainers lane, full pytest, all-package build, isolated base and
focused wheel imports, `actionlint`, and ten repeated lifecycle/cancellation
runs. Keep PyPI, PR creation, merge, issue closure, and #55 behind their own
explicit authority boundaries.

