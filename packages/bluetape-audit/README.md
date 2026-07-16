# bluetape-audit

English | [한국어](README.ko.md)

Storage-neutral, stdlib-only audit event values and validation for Python-native
bluetape applications. The package helps an application carry one audit fact to
caller-owned infrastructure without claiming that the fact was stored.

<picture>
  <source srcset="../../docs/images/readme-diagrams/audit-contract-boundary.svg" type="image/svg+xml">
  <img src="../../docs/images/readme-diagrams/audit-contract-boundary.png" alt="Audit contract ownership boundary">
</picture>

[Open the SVG source](../../docs/images/readme-diagrams/audit-contract-boundary.svg).

## Install

PyPI publication is on hold while package ownership and trusted publishing are
confirmed. Use the source workspace for current development and build the
focused artifact locally when wheel-level verification is required:

```bash
uv sync --all-packages
uv build --package bluetape-audit
```

After publication, install the focused distribution with:

```bash
pip install bluetape-audit
```

Or opt in through the thin meta distribution:

```bash
pip install "bluetape[audit]"
```

The default `pip install bluetape` remains the core-only default install.

## Quickstart

The application serializes its payload and the caller-owned adapter validates
the complete event immediately before its first side effect.

<!-- audit-example:start -->
```python
import json
from datetime import datetime, timezone
from bluetape.audit import (
    AuditError, AuditEvent, AuditIdentity, AuditLimits, AuditPayload, validate_audit_event,
)
storage_limits = AuditLimits(max_payload_bytes=64 * 1024)
stored: list[AuditEvent] = []
def append_to_caller_storage(event: AuditEvent) -> None:
    validate_audit_event(event, storage_limits)
    stored.append(event)  # caller-owned adapter side effect
payload = json.dumps({"reason": "customer_request"}).encode("utf-8")
event = AuditEvent(
    event_id="01JZTESTAUDIT0000000000000",
    action="order.cancelled",
    occurred_at=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
    subject=AuditIdentity("order", "order-123"),
    actor=AuditIdentity("user", "user-456"),
    correlation_id="request-789",
    causation_id="command-012",
    payload=AuditPayload(payload, "application/json", "1"),
    metadata={"source": "orders-api"},
)
try:
    append_to_caller_storage(event)
except AuditError:
    # Record only a bounded package-owned rejection category, never the event.
    raise
```
<!-- audit-example:end -->

Application-level prevalidation can fail fast, but adapter validation is
authoritative. Validation is not durable capture: only the caller-owned
storage/outbox/transport side effect can establish durability or delivery.

## Field Semantics

- `event_id` identifies one audit fact. On a retry of that same fact, reuse the
  event ID; a different fact needs a different ID.
- `action` is a caller-owned action name. The package does not maintain a
  registry or normalize it.
- `occurred_at` is a caller-supplied timezone-aware timestamp and is preserved
  without UTC conversion.
- `subject` identifies what the fact is about; optional `actor` identifies who
  or what acted.
- `correlation_id` and `causation_id` preserve caller-owned request and causal
  links without parsing them.
- `payload.data` is an immutable bytes snapshot. The package never serializes,
  parses, or rewrites it. `metadata` is a copied immutable mapping of strings.

Apply upstream allocation limits before constructing strings, mappings, or
payload bytes. Constructor ceilings bound already-created values; they are not
network, request-body, decompression, or process-memory limits.

## Adapter Validation

The caller-owned adapter invokes `validate_audit_event(event, limits)`
immediately before the first side effect. This placement is authoritative even
when application code prevalidated the event. Use versioned adapter-owned
limits, and check replay compatibility plus producer compatibility before
tightening them. If operators need to identify the active policy, emit an
external bounded policy ID; it is not event metadata, and operators must never
log rejected values.

## Safe Error Handling

Every field may be sensitive. Do not parse exception messages and do not log an
event, payload, identity, metadata, or rejected value. A bounded rejection
metric may use only these package-owned categories:

| Attribute | Safe use |
|---|---|
| `field_category` | Bounded field family such as `payload` or `metadata` |
| `limit_name` | Bounded configured limit name |

```python
from bluetape.audit import AuditLimitExceededError

try:
    append_to_caller_storage(event)
except AuditLimitExceededError as error:
    rejection_counter.add(  # application-owned telemetry
        1,
        {"field_category": error.field_category, "limit_name": error.limit_name},
    )
    raise
```

## Redaction Boundary

`repr()` for identities, payloads, and events has a constant redacted shape.
Package exceptions do not echo caller values. This prevents accidental package
disclosure; it is not a package-owned redaction, classification, encryption,
authorization, or logging system. Callers remain responsible for all output.

## Payload Dispatch

The `(content_type, schema_version)` pair is an untrusted caller assertion.
Match it against an adapter allowlist before parser selection and
before header emission. Unsupported pairs are rejected before parsing. The
pair never selects a Python class, storage adapter, fallback, or transport
implicitly, and the package does not verify that bytes match the asserted
format.

## Incremental Adoption

Adopt the value contract for new writes or through an explicit caller
migration. Adoption never rewrites history. Readers and migrations must
preserve unknown payload bytes exactly rather than parse and reserialize them.
Roll out readers before producers when adding a new payload route, and prove
both replay and producer compatibility against the adapter policy.

## Removal and Rollback

Remove a focused installation with:

```bash
pip uninstall bluetape-audit
```

If the meta distribution itself is also being removed, use:

```bash
pip uninstall bluetape
```

There is no package-owned data migration. The isolated rollback smoke removes
`bluetape-audit` from a meta-extra environment, proves `bluetape` and
`bluetape.core` still import, proves `bluetape.audit is absent`, and passes
dependency checking. The core-only default install also proves
`bluetape.audit is absent`.

## Accepted and Rejected Ownership

The package owns immutable audit values, constructor ceilings, explicit policy
validation, value-safe errors, and deterministic testing helpers. Caller code
owns serialization, allocation limits, policy versioning, repositories,
transactions, durable history, outboxes, relays, brokers, delivery, retries,
retention, authorization, redaction, logging, and telemetry. In short,
repository, history, and outbox remain external.

## Testing Helpers

`bluetape.audit.testing` offers deterministic values and an exact preservation
assertion for adapter tests:

```python
from bluetape.audit.testing import assert_audit_event_preserved, make_audit_event

expected = make_audit_event(action="order.cancelled")
actual = adapter_round_trip(expected)
assert_audit_event_preserved(actual, expected)
```

This is a value assertion, not durable history. The helper does not prove that
an adapter committed, retained, ordered, or delivered an event.
