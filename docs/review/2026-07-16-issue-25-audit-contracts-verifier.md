# Issue #25 audit contracts verifier map

Date: 2026-07-16 KST
Pre-evidence implementation head: `71bf9b1a65c3abac4d9df4e3b805c16fa617dc58`

Status: **READY FOR EXACT-HEAD VERIFICATION**. This file maps every approved
criterion to source and executable evidence. It intentionally does not claim a
final verifier verdict; that read-only verdict must be produced after the
evidence commit at an unchanged candidate SHA.

## Acceptance criterion map

| Criterion | Source evidence | Executable evidence | Pre-head status |
|---|---|---|---|
| Python 3.13+, stdlib-only focused distribution and exact public API | `packages/bluetape-audit/pyproject.toml`, root `__init__.py` | packaging metadata, exact `__all__`, signature, dataclass, and wheel-origin tests | Mapped |
| Frozen/slotted values preserve caller data and timezone meaning | `_values.py` exact constructors, `_datetime_key` | values/event immutability, identity, wall/offset/fold, equality matrices | Mapped |
| Opaque exact bytes and defensive read-only metadata snapshot | `AuditPayload.__init__`, `_copy_metadata`, publish-last `MappingProxyType` | 1 MiB identity retention, real/seam copy, mutation isolation, 64-entry boundaries | Mapped |
| Equal-or-stricter explicit validation returns the same event | `_validation.py` fixed ordered checks | all twelve limits at boundary/limit+1, all 14 ordered outcomes, same-object success | Mapped |
| Failures and representations do not disclose caller values | `_errors.py` fixed messages/reductions and constant repr methods | hostile-marker matrices across errors, values, events, validation, and helpers | Mapped |
| Deterministic helpers compare every field and retain no history | `testing.py` local literals and closed comparator | exact exports/signatures/defaults, all mismatch categories, no retained collections | Mapped |
| No forbidden repository/storage/global surfaces | package source exports only values, errors, validator, and two testing helpers | packaging and helper tests reject repository/history/buffer/outbox surfaces; root exports exact eleven names | Mapped |
| Focused/meta install works and default remains core-only | root/meta `pyproject.toml`, `uv.lock` | offline wheelhouse environments, network-denied `-I` imports, default absence, removal rollback, `uv pip check` | Mapped |
| Every workspace distribution is fail-closed classified | benchmark and resilience packaging `PUBLISHABLE`/`PRIVATE` sets, release preflight | both exhaustive equality tests cover the complete workspace distribution set | Mapped |
| English/Korean ownership, serialization/versioning, policy, and adapter separation | package/root READMEs | identical installed-wheel marked example, locale headings/semantic assertions, exact install/removal and link tests | Mapped |
| Current installation guidance matches the publication hold | package EN/KO Install sections and root status authority | README contracts require hold wording, workspace sync, focused local build, and post-publication registry shape | Mapped |
| SVG+PNG passes source and visual gates | canonical pair and diagram review ledger | XML, 2600x1600 IHDR, source IDs, 4 primary arrows, connector/geometry/endpoint/corner audits, original-pixel inspection | Mapped |
| Canonical quality and independent review gates | Task 8 plan and this mapping | Commands and six fresh review lenses are defined but must run after candidate freeze | Pending exact-head replay |

## Exact public surface to verify

```python
(
    "AuditError",
    "InvalidAuditIdentityError",
    "InvalidAuditPayloadError",
    "InvalidAuditEventError",
    "InvalidAuditLimitsError",
    "AuditLimitExceededError",
    "AuditIdentity",
    "AuditPayload",
    "AuditEvent",
    "AuditLimits",
    "validate_audit_event",
)
```

`bluetape.audit.testing` must export exactly `make_audit_event` and
`assert_audit_event_preserved`, and neither helper may be re-exported from the
root module.

## Forbidden public/storage surface

The final verifier must reject any package-owned repository, append, record,
history, query, buffer, outbox, SQL, transaction, serializer, parser, logger,
trace/span context, worker, scheduler, transport, broker, or global registry.
Documentation may name these only as caller-owned or explicitly excluded.

## Required immutable-head evidence

- Candidate SHA equals `git rev-parse HEAD` before and after every command.
- Worktree remains clean.
- Locked all-package/all-extra sync uses Python `3.13.14`.
- Focused audit/isolation/docs/benchmark set passes.
- Ruff lint and full format check pass.
- Canonical workspace test marker expression passes without hiding audit tests.
- All workspace distributions build; lock, actionlint, and diff checks pass.
- Six fresh lenses each report P0=0/P1=0 at the same SHA.
- Independent verifier confirms every row above at that unchanged SHA.

PR CI, merge, tag, release, and publication are not local verifier claims.
Merge remains a separate fresh user approval gate.
