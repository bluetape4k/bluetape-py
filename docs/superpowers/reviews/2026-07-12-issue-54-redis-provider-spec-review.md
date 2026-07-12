# Issue #54 Redis Provider Substrate Spec Review

- Artifact: `docs/superpowers/specs/2026-07-12-issue-54-redis-provider-design.md`
- Artifact kind: spec
- Work type: Type A - Full Feature
- Review date: 2026-07-12
- Result: `P0=0 P1=0`

## Review execution

The same spec and repository evidence were reviewed through six bounded
perspective passes, followed by main-session integration. The active
collaboration surface cannot attach the OMX-required native `agent_type`, so
spawning untyped agents would violate the workspace routing rule. The main
session therefore used the workflow's documented local-equivalent fallback and
kept each perspective pass separate until integration.

Upstream lifecycle, pool ownership, factory signatures, and Python-version
support were checked against redis-py documentation and the pinned
`redis==8.0.1` distribution. Those checks are design evidence; implementation
still requires committed unit, integration, packaging, and lifecycle tests.

## Initial findings and repairs

| Priority | Lens | Evidence | Required edit | Rerun lane |
|---|---|---|---|---|
| P1 | Stability | Close-versus-operation admission, concurrent close, event-loop affinity, and cancellation during owned async close were ambiguous. | Define `open`/`closing`/`closed`, admitted-operation draining, shared close completion, first-loop binding, and one shielded non-detached cleanup task spanning the full async close. | Stability |
| P1 | Security | Factory binary enforcement and the redaction boundary around preserved causes were underspecified. | Force `decode_responses=False`, reject incompatible clients/options, wrap creation failures without URLs, and document `__cause__` as a trusted diagnostic channel excluded from observers. | Security |
| P1 | Developer/API | `from_url(**redis_options)` did not state forwarding and reserved-option behavior precisely. | Lock the signature, unchanged forwarding rule, forbidden overrides, ownership semantics, and contract tests. | Developer/API |
| P2 | Performance | Built-in format encoders could predict oversize results but did not require preflight or benchmark evidence. | Require exact binary/JSON size preflight, final byte checks, and a reproducible non-gating binary-versus-JSON microbenchmark. | Performance |
| P2 | Operator/Ops | Atomic compare-and-delete did not declare its Redis script capability or failure policy. | Require `EVAL`/`EVALSHA`, surface ACL denial as a provider failure, and forbid a racy GET/DELETE fallback. | Operator/Ops |
| P2 | User/caller | The composition contract lacked one complete usage example. | Add sync binary/Zstd composition and specify the equivalent async form. | User/caller |
| P2 | Security | Custom format return values were not explicitly revalidated by the outer codec. | Require exact return types, final encoded-size validation, and full semantic-envelope revalidation before token, decompressor, or payload-codec access. | Security |

All findings were repaired in the reviewed spec. None was deferred or filed as
a follow-up.

## Lens reruns

### Tier 1: Performance

`P0=0 P1=0`. Both built-in formats preflight predictable output size and apply
an exact final bound. Decode applies the outer limit before parsing or derived
allocation, and compressor-specific logical output bounds remain mandatory.
The performance scan compares binary and JSON size and latency without turning
a workstation result into a production-capacity claim.

### Tier 2: Stability

`P0=0 P1=0`. Sync and async providers have equivalent command semantics. The
lifecycle contract deterministically handles admission, concurrent close,
borrowed versus owned clients, close failure, cancellation, and event-loop
misuse without holding lifecycle locks across Redis I/O or retaining a detached
task.

### Tier 3: Security

`P0=0 P1=0`. Exact binary responses are enforced; envelope formats fail closed;
encoded and decompressed sizes are bounded; Lua source is constant; no format,
algorithm, or command fallback is permitted. Public errors and events redact
sensitive values while the deliberately preserved exception cause is scoped as
a trusted diagnostic channel.

### Tier 4: Operator/Ops

`P0=0 P1=0`. Redis, serde, and compression remain focused dependencies; default,
`dev`, and `all` installs stay Redis-free. CI, serial Testcontainers coverage,
script capability, namespace rollout, TTL-aware rollback cleanup, wheel smoke
checks, and lock validation are explicit.

### Tier 5: Developer/API

`P0=0 P1=0`. Structural `PayloadCodec` and `EnvelopeFormat` contracts preserve
Python-native extension points. Public signatures, factory option forwarding,
format identifiers, operation results, TTL normalization, ownership, error
codes, and observability values are concrete enough for contract tests.

### Tier 6: User/caller

`P0=0 P1=0`. Callers can independently choose binary or JSON envelopes and any
registered compressor, while application serialization remains caller-owned.
The spec gives install and composition examples, defines token mismatch as a
non-error, and documents lifecycle, trust, compatibility, and rollout rules in
both documentation locales.

### Tier 7: Main-session integration

`P0=0 P1=0`.

- Boundaries: #54 provides envelope and Redis primitives; #55 owns distributed
  coordination and loader behavior.
- Compatibility: Kotlin and Go inform semantic rules without imposing package
  or wire compatibility on Python.
- Failure behavior: every malformed, unavailable, cancelled, stale, closed, or
  capability-denied state has one explicit outcome.
- Testability: acceptance criteria map to contract, integration, packaging,
  performance/stability, and workflow gates.
- Release readiness: bilingual docs, lock and wheel validation, dedicated CI,
  rollout/rollback, review evidence, and PR DoD are included.
- Open decisions: none remain in the approved #54 design scope.

Final integrated gate: `P0=0 P1=0`.
