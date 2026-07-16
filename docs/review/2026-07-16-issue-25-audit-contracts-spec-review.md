# Issue #25 Audit Contracts Specification Review

Date: 2026-07-16 KST
Issue: #25 - `feat: add storage-neutral audit event contracts`
Artifact:
`docs/superpowers/specs/2026-07-16-issue-25-audit-contracts-design.md`

## Review Scope

Six independent read-only perspectives reviewed the written design before
implementation planning. Reviewers had no write, commit, GitHub mutation,
build, or test authority. The main session normalized severity, repaired the
specification, and requested convergence review only for affected lenses.

| Perspective | Role surface | Initial result | Final result |
|---|---|---:|---:|
| Performance | `code-reviewer` | P0=0, P1=1 | P0=0, P1=0 |
| Stability/reliability | `verifier` | P0=0, P1=3 | P0=0, P1=0 |
| Security/privacy | `code-reviewer` | P0=0, P1=2 | P0=0, P1=0 |
| Operator/Ops | `verifier` | P0=0, P1=2 | P0=0, P1=0 |
| Developer/public API | `code-reviewer` | P0=0, P1=5 | P0=0, P1=0 |
| User/caller | `writer` | P0=0, P1=3 | P0=0, P1=0 |

Final independent verdict: **P0=0, P1=0 across all six perspectives**.

## Material Repairs

### Bounded construction and immutable snapshots

Initial performance, stability, and security reviews found that copying an
arbitrary `Mapping` before explicit validation could invoke caller code and
allocate without a package bound. The repaired contract:

- accepts an exact built-in metadata `dict` input only;
- checks the package hard entry ceiling before copying;
- performs one private shallow copy and rechecks its length;
- validates only the private copy in insertion order;
- publishes the read-only proxy only after complete validation;
- documents the caller precondition for concurrent source mutation.

Opaque payload bytes are length-checked without copying or scanning and retain
the exact caller bytes object. Default `AuditLimits` are package hard ceilings;
explicit policies may be equal or stricter, not wider.

### Stable timestamp semantics

The initial design accepted any aware datetime, which allowed mutable or
stateful caller `tzinfo`. The repaired contract accepts an exact built-in
`datetime` with exact stdlib `datetime.timezone` or `zoneinfo.ZoneInfo`, rejects
custom/subclass behavior, preserves wall-clock fields, UTC offset, and `fold`,
and defines structural timestamp equality explicitly.

### Safe and actionable errors

The repaired error surface adds `InvalidAuditLimitsError`, defines exact
constructor-versus-validator exception ownership, and makes every value type's
`repr` a constant redacted literal. `AuditLimitExceededError` exposes only
bounded `field_category` and `limit_name` attributes from a closed mapping; it
stores no rejected value. Wrong validator argument types and testing-helper
unknown overrides use deterministic value-free `TypeError` messages.

### Exact Python API behavior

The repaired design fixes constructor positional/keyword behavior, exact
metadata input typing, final/subclass policy, equality, hashing, representation,
validation precedence, helper comparison order, mismatch categories, and the
complete deterministic factory value. `AuditEvent` is explicitly unhashable,
metadata equality is order-insensitive, and `dataclasses.replace()` is outside
the public contract.

### Caller and operator ownership

The repaired design adds normative semantics for event identity, action,
occurrence time, subject, actor, correlation, and causation. It makes adapter
validation immediately before the first side effect authoritative; earlier
application validation is optional and cannot satisfy that gate.

Successful validation is explicitly not durable capture. Atomic capture,
idempotency by stable event ID, retry classification, ordering, backpressure,
retention, quarantine/dead-letter behavior, and partial-failure recovery remain
adapter/operator-owned. Package ceilings prevent additional retention/copy,
not upstream request allocation or decoding.

### Executable documentation boundary

The design now pins one direct/meta install and install-to-adapter example,
safe error handling, `(content_type, schema_version)` dispatch, incremental
adoption, removal rollback, and an English/Korean parity checklist. Framework
values require explicit caller conversion to the supported built-ins.

## Main-Session Integration Checks

| Check | Evidence | Result |
|---|---|---|
| Issue boundary | Live issue #25 and issue #14 research keep audit values separate from SQL and outbox packages | PASS |
| Public surface | Exact exports, signatures, exception taxonomy, equality/hash/repr, and helper behavior are declared | PASS |
| Storage neutrality | No repository, history, SQL, outbox, broker, worker, serializer, logging, or global context surface | PASS |
| Package boundary | Python 3.13+, stdlib-only, optional `audit` extra, unchanged core-only default | PASS |
| Testability | Boundary, limit+1, hostile-marker, snapshot, timezone, helper, packaging, wheel, and bilingual examples are specified | PASS |
| Operational honesty | Validation is separated from durability, transaction, delivery, and upstream allocation guarantees | PASS |
| Placeholders | No TBD, TODO, FIXME, deferred API choice, or unresolved implementation branch | PASS |
| Diff hygiene | `git diff --check` | PASS |

## Remaining Non-Blocking Risks

- No durable adapter exists yet, so atomic capture, idempotency, replay, and
  delivery behavior remain future adapter obligations rather than proven code.
- Character ceilings do not bound encoded database or transport bytes; adapters
  must enforce destination-specific constraints.
- Exact built-in inputs deliberately trade framework convenience for
  deterministic, side-effect-free construction.
- Caller-owned persistence, logging, tracing, serialization, and transport can
  still disclose values if the caller ignores the documented classification
  and redaction boundary.

## Gate Result

The written specification is internally converged and ready for user review.
Implementation planning and production-code edits remain blocked until the user
approves the committed specification.
