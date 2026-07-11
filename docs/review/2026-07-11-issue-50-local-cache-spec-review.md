# Issue #50 Local Cache Spec Review

- Spec: `docs/superpowers/specs/2026-07-11-issue-50-local-cache-design.md`
- Review gate: Type A Step 2-R
- Date: 2026-07-11
- Final gate: P0=0, P1=0

## Review Lenses

| Lens | Initial material findings | Resolution | Final |
| --- | --- | --- | --- |
| Performance | Different-key concurrency wording was too broad; expiry sweeping risked O(max_size) work; benchmark inputs were not pinned. | Narrowed the concurrency claim to loader bodies, introduced a bounded stale-node expiry heap, and required a reproducible benchmark matrix. | P0=0, P1=0 |
| Stability | Owner-only flights and abandoned async loaders could leak or publish stale values; cancellation and loop binding needed exact ownership rules. | Separated active and owned flights, made abandonment versioned and non-publishable, specified immediate caller cancellation with terminal cache ownership, and added atomic loop binding. | P0=0, P1=0 |
| Security | Distinct-key loads were unbounded; observability could expose sensitive data; entry count is not a byte limit. | Added `max_inflight`, low-cardinality snapshots, opaque task names, and explicit caller responsibilities for redaction and untrusted object sizing. | P0=0, P1=0 |
| Operator | Snapshot counters did not expose current flight occupancy. | Added current active/abandoned/superseded gauges and their lock-consistent lifecycle semantics. | P0=0, P1=0 |
| User | Same-key owner precedence, `invalidate()` results, `ttl=None`, value identity, and adoption examples were ambiguous. | Defined owner loader/TTL precedence, return values, default-TTL behavior, strong identity semantics, and required README examples. | P0=0, P1=0 |
| Developer | Mutation generations, key typing, validation taxonomy, exports, and stats lifetime were underspecified. | Added generation isolation, `Hashable` typing, exact exceptions/exports, and counter-versus-gauge lifetime rules. | P0=0, P1=0 |

## Integrated Verdict

The spec is implementation-ready for planning. It keeps Redis coordination in issue #51, preserves the thin default installation, and defines bounded entry and loader ownership for both synchronous and asynchronous callers.

P0=0 P1=0
