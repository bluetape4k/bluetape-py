# Issue #15 Testcontainers Fixture Families Spec Review

- Spec: `docs/superpowers/specs/2026-07-17-issue-15-testcontainers-fixtures-design.md`
- Review gate: Type A Step 2-R
- Date: 2026-07-17
- Final gate: P0=0, P1=0

## Review Lenses

| Lens | Initial material findings | Resolution | Final |
| --- | --- | --- | --- |
| Performance | P1=3: unsupported PostgreSQL timeout promise, missing LocalStack service forwarding, and ambiguous provider-owned Ryuk cost. | Removed the PostgreSQL timeout, required exact selected-service forwarding, and separated wrapper-owned service cleanup from provider-owned Ryuk. | P0=0, P1=0 |
| Stability | P1=1: incomplete lifecycle and cleanup-retry transitions. | Added the complete state table, exact cleanup failure behavior, idempotent close, and context-manager exception precedence. | P0=0, P1=0 |
| Security | P1=2: wildcard port exposure and possible ambient AWS credential propagation. | Required loopback-only dynamic bindings and fixed synthetic LocalStack credentials isolated from environment and provider discovery. | P0=0, P1=0 |
| Operations | The initial child lane stalled; main integration raised one material CI reproducibility gap. | Added the exact package extra/test-group sync, Docker preflight, serialized service job, failure triage, and service-container cleanup evidence. A fresh independent verifier confirmed the revision. | P0=0, P1=0 |
| Developer/API | P1=2: shared-error compatibility and integration-test dependencies were not exact. | Pinned the compatible constructor/import paths, explicit root exports, package test group, and focused locked test command. | P0=0, P1=0 |
| Caller/User | P1=1: provider-extra ownership and installation guidance were ambiguous. | Added exact base/PostgreSQL/LocalStack/all installation commands, dependency recovery, complete fixture examples, and upgrade guidance. | P0=0, P1=0 |

## Convergence

All first-pass P0/P1 findings were integrated. Independent residual checks for
performance, stability, security, and operations returned `P0=0/P1=0`.
Developer/API and caller/user findings were then matched directly against their
exact corrected contracts by main integration because the native child-thread
limit prevented another follow-up turn; no residual P0/P1 gap remained.

Advisory findings were also incorporated where they clarified the implementation
contract: secret-bearing PostgreSQL URLs, image user-information rejection,
bare-string LocalStack service rejection, cleanup exception text, copy-paste
fixtures, caller resource ownership, and Redis-only upgrade compatibility.

## Main Integration Critique

The selected boundary remains a thin adapter over official provider modules.
The revision does not introduce a generic lifecycle base or refactor Redis. It
now distinguishes provider-owned Ryuk from wrapper-owned service containers,
advertises only provider-supported timeout behavior, keeps optional clients out
of runtime dependencies, and gives CI and callers reproducible install and
cleanup paths.

This gate approves the written design for user review and subsequent planning.
It does not authorize or claim implementation.

Final gate: **P0=0 P1=0**.
