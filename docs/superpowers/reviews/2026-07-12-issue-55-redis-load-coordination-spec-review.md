# Issue #55 Redis Load Coordination Spec Review

- Artifact: `docs/superpowers/specs/2026-07-12-issue-55-redis-load-coordination-design.md`
- Artifact kind: spec
- Work type: Type A - Full Feature
- Review date: 2026-07-12
- Result: `P0=0 P1=0 P2=0 P3=0`

## Review execution

The same specification and repository evidence were reviewed through six
bounded perspectives, followed by main-session integration. Each perspective
was rerun after its findings were incorporated. Redis command semantics were
checked against official Redis guidance for `SET NX PX`, unique-token
compare-and-delete, and atomic Lua execution. The Go rediscoord implementation
was used as behavioral evidence, while Python API and packaging conventions
remain authoritative.

This review approves an implementation-ready design. Source, integration,
packaging, documentation, and CI evidence remain mandatory implementation
gates.

## Initial findings and repairs

| Lens | Initial result | Repairs incorporated | Final result |
|---|---:|---|---:|
| Performance | `P1=2` | Put Redis coordination inside the borrowed cache's single local flight; replace unbounded reads and linear polling with bounded atomic snapshots and capped jittered backoff. | `P0=0 P1=0 P2=0 P3=0` |
| Stability | `P1=4` | Define active/completed marker states, supersession rules, lease/deadline ownership, bounded cleanup, and async cancellation at caller, cache-flight, and coordinator layers. | `P0=0 P1=0 P2=0 P3=0` |
| Security | `P1=3` | Bound every Redis read, require finite no-retry I/O policy, use high-entropy tokens, fix redaction/trust boundaries, and test forged artifacts. | `P0=0 P1=0 P2=0 P3=0` |
| Operator/Ops | `P1=4` | Require versioned namespace ownership, TLS and least-privilege ACL guidance, exact low-cardinality events, hidden-retry rejection, and quiescent rollback cleanup. | `P0=0 P1=0 P2=0 P3=0` |
| Developer/API | `P1=4` | Add tagged decode for legitimate `None`, exact public taxonomy and exports, numeric bounds, provider policy access, valid primitive signatures, and exact event/error validation. | `P0=0 P1=0 P2=0 P3=0` |
| User/caller | `P1=5` | Make namespace and TTL meaning explicit; define cancellation and failure expectations, sync/async examples, rollout compatibility, and unsupported conflicting cache binding. | `P0=0 P1=0 P2=0 P3=0` |

No finding was deferred or moved to a follow-up issue.

## Final lens verdicts

### Performance

One same-key local burst enters one cache-owned distributed flight. Every Redis
artifact and loop is size-, count-, TTL-, and deadline-bounded. Polling uses
capped exponential backoff with injectable full jitter, and the validation
contract prevents a polling interval from exceeding the result lifetime.

### Stability

Sync and async behavior is equivalent. Marker transitions, stale-owner
publication, lease loss, loader failure, cancellation, cleanup failure, and
deadline overrun each have one deterministic outcome. A stale owner may return
its local value but cannot publish over or delete a replacement lease.

### Security

Logical keys are pseudonymized with a versioned namespace and digest, while the
spec explicitly avoids claiming confidentiality. Tokens carry at least 256 bits
of entropy. Lua source is fixed, values are passed through arguments, reads are
bounded, observers are redacted, and Redis-controlled metadata cannot elevate
caller codec trust.

### Operator/Ops

The provider exposes finite connect/socket bounds and rejects all discovered
retry mechanisms, including non-empty `retry_on_error`. Deployment guidance
requires TLS where appropriate and only the commands used by the fixed `EVAL`
scripts. Rollout overlap, quiescence, bounded namespace cleanup, rollback, and
failure diagnostics are actionable.

### Developer/API

Public constructors, enums, errors, events, exports, option bounds, command
policy, snapshot, publication, and tagged envelope-match contracts are exact
enough for signature and boundary tests. The three option-limit constants are
normative but deliberately not public imports.

### User/caller

The design explains installation and minimal sync/async composition, local
cache TTL versus Redis result TTL, cancellation ownership, lease-loss behavior,
and required namespace versioning. Callers retain payload codec, loader, cache,
redaction, and rollout ownership.

### Main-session integration

`P0=0 P1=0 P2=0 P3=0`.

- Scope stays within #55: load coordination only, without durable L2 storage,
  lease renewal, fencing, or external-write protection.
- #54 supplies the envelope and Redis substrate; closed dependencies #54 and
  #57 satisfy the implementation prerequisites.
- Acceptance criteria map to unit, sync/async race, RedisServer integration,
  hostile-artifact, ACL, timeout, packaging, documentation, and full CI gates.
- Open decisions: none remain in the approved design scope.

Final integrated gate: `P0=0 P1=0 P2=0 P3=0`.

## Post-plan dependency-boundary amendment

Step 3-R found that the public coordinators borrow `TTLCache` and
`AsyncTTLCache`, but a direct `bluetape-cache-redis` or
`bluetape[cache-redis]` install did not install `bluetape-cache`. The spec was
reopened before metadata changes and amended to add exact
`bluetape-cache==0.1.0` as a focused runtime dependency. The meta extra remains
a single `bluetape-cache-redis==0.1.0` entry and default `bluetape` remains
core-only.

Affected spec lanes were rerun after adding exact lock/Requires-Dist checks,
direct and meta-extra clean-wheel installs, default isolation, bilingual install
commands, package-layout ownership, and milestone release ordering:

| Lens | Final amendment result |
|---|---:|
| Developer/API | `P0=0 P1=0 P2=0 P3=0` |
| Operator/Ops | `P0=0 P1=0 P2=0 P3=0` |
| User/caller | `P0=0 P1=0 P2=0 P3=0` |
| Main-session integration | `P0=0 P1=0 P2=0 P3=0` |

The amendment is review-ready but remains subject to explicit user reapproval
before implementation begins.
