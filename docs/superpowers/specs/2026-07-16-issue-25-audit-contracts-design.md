# Issue #25 Storage-Neutral Audit Contracts Design

Date: 2026-07-16 KST
Target issue: #25 - `feat: add storage-neutral audit event contracts`
Target milestone: `0.2.0`
Research prerequisite: #14

## Approved Delivery Shape

Add one Python-native, stdlib-only distribution named `bluetape-audit` with the
import path `bluetape.audit`. The package owns immutable audit event values,
explicit size validation, and deterministic caller-side test helpers. It does
not own persistence, history queries, transaction boundaries, serialization,
logging, tracing, redaction, or delivery.

The user approved a values-first delivery on 2026-07-16. A repository or
history protocol is deliberately excluded until a concrete adapter proves a
stable cross-storage contract. The payload boundary is immutable bytes plus
caller-declared content type and schema version, rather than a JSON-specific
tree or a package-owned serializer.

PR creation is authorized for repository `bluetape4k/bluetape-py`, base
`develop`, and head `feat/issue-25-audit-contracts` after all implementation
and review gates pass. Merge, release, tag, and publication remain separate
approval gates.

## Problem

Applications need a stable value to carry an audit fact from business code to
caller-owned storage or an outbox. Bare dictionaries do not establish which
fields identify the event, distinguish subject from actor, preserve causal
links, or bound payload and metadata size. A storage-shaped repository API,
however, would prematurely choose query, transaction, pagination, and history
semantics before the Python ecosystem has a concrete durable adapter.

The first package therefore needs to make the event boundary precise without
claiming ownership of infrastructure. It must preserve caller values exactly,
make size policy explicit, and prevent its own errors and representations from
disclosing payloads or identity values.

## Current Evidence

- Live issue #25 requires immutable values, stable identity and occurrence
  time, subject/actor and causal fields, caller-owned payloads, explicit size
  and redaction boundaries, stdlib-only packaging, and deterministic test
  helpers.
- Issue #14 research separates `bluetape-audit` from SQL helpers and the
  PostgreSQL transactional outbox. It assigns engine, transaction, schema,
  relay, and broker ownership to later focused packages.
- Existing `bluetape-id`, `bluetape-measure`, and `bluetape-money` packages use
  frozen slotted values, explicit error hierarchies, exact ordered exports,
  empty runtime dependencies, and packaging tests that reject a root
  `bluetape/__init__.py`.
- Existing hostile-input tests require validation failures to identify the
  invalid category without echoing caller data.
- `bluetape-go/audit` is a semantic reference for explicit values and defensive
  copies only. Its repository, recorder, outbox, and JSON-shaped contracts are
  not copied into the Python API.

## Goals

1. Define immutable, slotted values for audit identities, payloads, events,
   and caller-visible limits.
2. Preserve valid caller-owned identifiers, timezone-aware timestamps, bytes,
   and metadata without trimming, case folding, UTC conversion, serialization,
   or other hidden normalization.
3. Make payload and metadata bounds explicit through a pure validation call
   that returns the original event on success.
4. Keep payload bytes, identity values, and metadata out of package-generated
   exception messages and object representations.
5. Provide deterministic test helpers that verify value preservation without
   pretending to be durable storage or history.
6. Register, build, document, and visually explain the focused package while
   leaving the default `bluetape` install unchanged.

## Non-Goals

- repository, append, read, list, search, filter, pagination, history, or
  retention protocols;
- SQL schema, SQLAlchemy, DB-API, engine, session, transaction, migration, or
  connection ownership;
- outbox enqueue, claim, relay, scheduler, worker, retry, broker, or transport;
- JSON, MessagePack, Fory, protobuf, object diffing, schema registry, codec, or
  serializer ownership;
- encryption, hashing, signing, authentication, authorization, redaction, data
  classification, or automatic PII detection;
- global current user, request, logger, trace, span, session, registry, or
  framework integration;
- mutable builders, domain-event buses, event dispatch, background tasks, or
  package-owned logging;
- release, tag, PyPI publication, or merge as part of the implementation step.

## Package Boundary

```text
packages/bluetape-audit/
├── pyproject.toml
├── README.md
├── README.ko.md
├── src/bluetape/audit/
│   ├── __init__.py
│   ├── _errors.py
│   ├── _values.py
│   ├── _validation.py
│   └── testing.py
└── tests/
```

- Distribution: `bluetape-audit`
- Import: `bluetape.audit`
- Python: `>=3.13`
- Runtime dependencies: none
- Build backend: the repository-standard `uv_build`
- Root namespace initializer: absent
- Default `bluetape` dependencies: remain exactly `bluetape-core==0.1.0`
- Optional meta extra: `bluetape[audit]` installs
  `bluetape-audit==0.1.0`
- Aggregate `bluetape[all]` and `bluetape[dev]`: include the focused
  distribution; no aggregate value extra is widened.

The root workspace registers `bluetape-audit` as a member and local source so
generic CI, lint, tests, and `uv build --all-packages` discover it. No dedicated
workflow is added.

## Public API

`bluetape.audit.__all__` has this exact order:

```python
[
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
]
```

The values and validator have these public declarations:

```python
@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class AuditIdentity:
    kind: str = field(repr=False)
    value: str = field(repr=False)

    def __init__(self, kind: str, value: str) -> None: ...
    def __repr__(self) -> str: ...


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class AuditPayload:
    data: bytes = field(repr=False)
    content_type: str = field(repr=False)
    schema_version: str = field(repr=False)

    def __init__(self, data: bytes, content_type: str, schema_version: str) -> None: ...
    def __repr__(self) -> str: ...


@final
@dataclass(frozen=True, slots=True, init=False, repr=False, eq=False)
class AuditEvent:
    event_id: str = field(repr=False)
    action: str = field(repr=False)
    occurred_at: datetime = field(repr=False)
    subject: AuditIdentity = field(repr=False)
    payload: AuditPayload = field(repr=False)
    actor: AuditIdentity | None = field(default=None, repr=False)
    correlation_id: str | None = field(default=None, repr=False)
    causation_id: str | None = field(default=None, repr=False)
    metadata: Mapping[str, str] = field(default_factory=dict, repr=False)

    def __init__(
        self,
        event_id: str,
        action: str,
        occurred_at: datetime,
        subject: AuditIdentity,
        payload: AuditPayload,
        *,
        actor: AuditIdentity | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None: ...

    def __eq__(self, other: object) -> bool: ...
    __hash__ = None

    def __repr__(self) -> str: ...


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class AuditLimits:
    max_event_id_chars: int = 128
    max_action_chars: int = 128
    max_identity_kind_chars: int = 64
    max_identity_value_chars: int = 512
    max_correlation_id_chars: int = 128
    max_causation_id_chars: int = 128
    max_content_type_chars: int = 128
    max_schema_version_chars: int = 64
    max_payload_bytes: int = 1_048_576
    max_metadata_entries: int = 64
    max_metadata_key_chars: int = 128
    max_metadata_value_chars: int = 2_048


def validate_audit_event(event: AuditEvent, limits: AuditLimits) -> AuditEvent: ...
```

The declarations show the complete public field set. Implementations may use
explicit `init=False` constructors to enforce the rules below, but must not add
public fields, hidden clocks, generated identifiers, or implicit defaults for
event identity or occurrence time.

`AuditIdentity`, `AuditPayload`, and `AuditEvent` each define an explicit,
constant-shape representation. The exact results are
`AuditIdentity(<redacted>)`, `AuditPayload(<redacted>)`, and
`AuditEvent(<redacted>)`. No caller-controlled value participates in `repr()`.
`AuditLimits` may use its numeric dataclass representation.

The declarations above are the authoritative constructor signatures. Required
value arguments accept positional or keyword use. Optional event fields are
keyword-only. `metadata=None` constructs an empty snapshot; a present metadata
argument must be an exact `dict[str, str]`. All classes are `@final`, and
runtime exact-type checks make subclassing unsupported. `dataclasses.replace()`
is outside the public contract because the stored metadata proxy is not a valid
constructor input; callers construct a new event explicitly.

`bluetape.audit.testing` exports exactly:

```python
[
    "make_audit_event",
    "assert_audit_event_preserved",
]

def make_audit_event(**overrides: object) -> AuditEvent: ...

def assert_audit_event_preserved(
    actual: AuditEvent,
    expected: AuditEvent,
) -> None: ...
```

The testing module is public but is not re-exported from `bluetape.audit`.

## Value Construction Contract

### Shared string rules

- String fields require exact `str` values; implicit `str()` conversion is
  forbidden.
- Required named fields and identity strings must be non-empty and contain at
  least one non-whitespace character. Metadata values are the explicit
  exception described below.
- Optional strings use `None` for absence. An empty or whitespace-only present
  value is invalid.
- Validation may inspect whitespace but never trims it. A valid value with
  leading or trailing whitespace is preserved exactly.
- No value is case-folded, Unicode-normalized, parsed into a UUID, or checked
  against a package-owned naming grammar.
- Construction enforces the package hard ceilings represented by the default
  `AuditLimits()`. This bounds work before an event exists. Explicit validation
  may only use an equal or stricter policy; wider-than-default limits are
  invalid.

### `AuditIdentity`

- `kind` names the caller's identity namespace, for example `user`, `order`,
  or `service`.
- `value` is caller-owned and may contain sensitive data. It is excluded from
  `repr` and every package-generated error message.
- The constructor performs type, non-blank, and package hard-ceiling checks.
  A later `validate_audit_event()` call applies the caller's equal or stricter
  boundary policy.

### `AuditPayload`

- `data` requires exact `bytes`; `bytearray`, `memoryview`, text, mappings, and
  implicit conversions are rejected.
- Empty bytes are invalid. Valid bytes are immutable and preserved without a
  package-owned serialization or copy contract.
- `content_type` and `schema_version` are required non-blank strings preserved
  exactly. The package does not parse media-type parameters or impose a
  semantic-version grammar.
- `content_type` and `schema_version` reject code points U+0000..U+001F,
  U+007F..U+009F (C0, DEL, and C1 controls). They are still untrusted caller
  assertions: adapters must use their own allowlists before parser selection
  or header emission.
- Payload bytes are excluded from `repr`, equality failure messages generated
  by the testing helper, and all package exceptions.
- Construction checks byte length before retaining the value and preserves the
  exact immutable bytes object (`payload.data is data`). It never copies or
  scans payload contents.

### `AuditEvent`

- The caller supplies `event_id`, `action`, and `occurred_at`; the package does
  not generate IDs or read a clock.
- `occurred_at` requires an exact built-in `datetime`, not a subclass. Its
  `tzinfo` must be an exact stdlib `datetime.timezone` or `zoneinfo.ZoneInfo`;
  custom, mutable, or stateful timezone implementations are rejected. Naive
  datetimes are rejected. `utcoffset()` is evaluated once during construction;
  an unexpected exception is replaced by a value-free `InvalidAuditEventError`.
  A valid datetime object, original offset, wall-clock fields, and `fold` value
  are preserved without conversion to UTC.
- `subject` and `payload` require their exact public value types. `actor` is
  either an `AuditIdentity` or `None`.
- Correlation and causation are independent optional identifiers. The package
  does not infer either field from another event or from ambient context.
- The public `metadata` attribute is a `Mapping[str, str]`, but constructor
  input must be an exact built-in `dict`; subclasses and arbitrary `Mapping`
  implementations are rejected so construction cannot invoke caller-defined
  iteration or length behavior. Keys and values require exact `str`. Keys must
  be non-blank; values may be empty because absence and an explicitly empty
  caller value are distinct.
- Every exact metadata value string, including empty and whitespace-only
  strings, is valid subject to its character ceiling. Metadata values are not
  scanned for control characters; adapters must classify them as untrusted.
- Construction checks the exact dictionary length against the package hard
  ceiling, performs one built-in shallow copy, rechecks the private copy's
  length, and validates only that copy in insertion order. It exposes a
  read-only `MappingProxyType` only after every copied entry passes. A failed
  validation publishes no event and never mutates the input. Later input
  mutation cannot change a successful event. Callers must not concurrently
  mutate the source dictionary while construction is in progress if they need
  a specific point-in-time snapshot. Nested copying is unnecessary because the
  contract permits strings only.
- `payload` and `metadata` are excluded from event `repr`; nested identity
  values remain excluded by `AuditIdentity`.
- The read-only metadata snapshot makes an event immutable but not hashable.
  `AuditEvent` explicitly has no hash contract.

Normative field semantics are:

| Field | Meaning and caller obligation |
|---|---|
| `event_id` | Stable identity of one logical audit fact. Reuse it when retrying capture or delivery of that same fact; create a new ID for a distinct fact. Adapters use it as the idempotency/deduplication key. |
| `action` | Caller-defined name for what occurred, such as `order.cancelled`; it is not an authorization decision or package-owned enum. |
| `occurred_at` | Time the audited action occurred, not validation, persistence, or publication time. |
| `subject` | Resource or entity acted upon. |
| `actor` | Optional human, service, or process that initiated the action; it is not inferred from subject or ambient context. |
| `correlation_id` | Optional identifier shared across the broader request, workflow, or trace chosen by the caller. |
| `causation_id` | Optional direct predecessor event or command identifier that caused this audit fact. |
| `payload` | Already serialized caller-owned detail for this fact. |
| `metadata` | Small, bounded string annotations; it is not an extension schema or a destination for arbitrary payload data. |

For example, retrying capture of an order cancellation reuses the same event ID
and occurrence time. The order is the subject, the initiating user or service
is the actor, the request/workflow ID is correlation, and the direct cancel
command ID is causation.

### `AuditLimits`

- Every limit requires an exact positive `int`; booleans and non-positive
  values raise `InvalidAuditLimitsError`.
- Defaults are package hard ceilings that bound constructor work, not storage
  or security guarantees. Callers may construct only an equal or stricter
  policy. A value above its default ceiling raises
  `InvalidAuditLimitsError`.
- String limits count Python characters. Payload size counts exact bytes.
  Metadata is bounded by entry count and per-key/per-value character limits.
- Limits do not truncate, redact, compress, re-encode, or otherwise mutate an
  event.

### Equality, hashing, and validation order

- `AuditIdentity` and `AuditPayload` use exact-type structural equality and are
  hashable because all fields are immutable.
- `AuditEvent` uses exact-type structural equality. Timestamp equality compares
  year, month, day, hour, minute, second, microsecond, UTC offset, and `fold`
  rather than instant-only `datetime.__eq__`. Metadata uses mapping equality;
  insertion order does not affect event equality.
- `AuditEvent.__hash__` is exactly `None`. It is intentionally unhashable rather
  than failing only after a generated hash reaches the metadata proxy.
- `AuditLimits` uses generated structural equality and hashing over its numeric
  fields.
- Every constructor validates in field declaration order. Within a variable
  field the order is exact type, O(1) length or byte ceiling, then non-blank or
  control-character scan, then retention. Metadata checks dictionary type,
  O(1) entry count, one private copy, copied entry count, and then each copied
  key before its value in insertion order.

## Validation Contract

`validate_audit_event(event, limits)` is pure and deterministic:

1. Require an exact `AuditEvent`, then an exact `AuditLimits`. A wrong event
   raises value-free `TypeError("event must be an AuditEvent")`; only after it
   passes can a wrong limits value raise value-free
   `TypeError("limits must be an AuditLimits")`.
2. Check in this total order: event ID, action, subject kind, subject value,
   actor kind then actor value when present, correlation ID, causation ID,
   content type, schema version, payload byte count, metadata entry count, then
   each metadata entry in preserved insertion order with key before value.
3. Raise `AuditLimitExceededError` at the first field that exceeds policy.
4. Return the same event object (`result is event`) when every check passes.

Limit error attributes and preservation-helper categories use this exact
closed mapping:

| Check | `field_category` | `limit_name` | preservation category |
|---|---|---|---|
| event ID | `event_id` | `max_event_id_chars` | `event_id` |
| action | `action` | `max_action_chars` | `action` |
| occurrence time | N/A | N/A | `occurred_at` |
| subject kind | `subject.kind` | `max_identity_kind_chars` | `subject.kind` |
| subject value | `subject.value` | `max_identity_value_chars` | `subject.value` |
| actor presence | N/A | N/A | `actor` |
| actor kind | `actor.kind` | `max_identity_kind_chars` | `actor.kind` |
| actor value | `actor.value` | `max_identity_value_chars` | `actor.value` |
| correlation ID | `correlation_id` | `max_correlation_id_chars` | `correlation_id` |
| causation ID | `causation_id` | `max_causation_id_chars` | `causation_id` |
| payload content type | `payload.content_type` | `max_content_type_chars` | `payload.content_type` |
| payload schema version | `payload.schema_version` | `max_schema_version_chars` | `payload.schema_version` |
| payload bytes | `payload.data` | `max_payload_bytes` | `payload.data` |
| metadata entry count | `metadata` | `max_metadata_entries` | `metadata` |
| metadata key | `metadata.key` | `max_metadata_key_chars` | `metadata` |
| metadata value | `metadata.value` | `max_metadata_value_chars` | `metadata` |

Rows marked N/A never produce `AuditLimitExceededError`. Metadata key/value
helper mismatches intentionally collapse to the value-free `metadata`
category because the helper must not identify a caller key.

The validator never serializes, logs, copies, stores, publishes, or redacts an
event. Constructors own semantic validity and package hard ceilings; the
validator owns an equal or stricter caller-selected size policy. A durable
adapter must call it explicitly at its chosen boundary. This package provides
no rollback, transaction atomicity, or validate-before-I/O guarantee for an
adapter; future adapter conformance tests must prove that validation failure
occurs before the adapter performs a write.

## Error and Disclosure Contract

```python
class AuditError(ValueError): ...
class InvalidAuditIdentityError(AuditError): ...
class InvalidAuditPayloadError(AuditError): ...
class InvalidAuditEventError(AuditError): ...
class InvalidAuditLimitsError(AuditError): ...
class AuditLimitExceededError(AuditError):
    field_category: str
    limit_name: str
```

- Constructor type errors raise `TypeError`. Constructor semantic or package
  hard-ceiling failures raise their owning `InvalidAuditIdentityError`,
  `InvalidAuditPayloadError`, or `InvalidAuditEventError`. Invalid or wider-than-
  default policies raise `InvalidAuditLimitsError`. Only
  `validate_audit_event()` policy failures raise `AuditLimitExceededError`.
- `AuditLimitExceededError.field_category` and `.limit_name` are stable,
  bounded strings selected from the public field categories and declared
  `AuditLimits` field names. The error stores no rejected value. Operators may
  use these two low-cardinality attributes in metrics; message parsing and
  caller values as labels are forbidden.
- Error messages, `repr()`, and testing-helper assertion messages must not
  contain any caller-controlled field: payload bytes, identity kinds or values,
  metadata keys or values, event IDs, actions, timestamps, media/schema labels,
  correlation IDs, causation IDs, or hostile marker strings.
- The package never logs automatically. Redaction before serialization,
  persistence, logging, tracing, or transport remains caller-owned. Callers
  must classify every field, not only payload and metadata; identifiers,
  actions, timestamps, identity kinds, and media/schema labels may also be
  sensitive in a particular domain.

## Deterministic Testing Contract

`make_audit_event()` creates a new event for every call with fixed, documented
value equivalent to this literal:

```python
AuditEvent(
    event_id="evt-test-0001",
    action="test.action",
    occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    subject=AuditIdentity("test-subject", "subject-0001"),
    payload=AuditPayload(b"{}", "application/json", "1"),
    actor=AuditIdentity("test-actor", "actor-0001"),
    correlation_id="corr-test-0001",
    causation_id="cause-test-0001",
    metadata={"source": "bluetape.audit.testing"},
)
```

Overrides replace only named `AuditEvent` constructor fields while every
non-overridden field keeps the literal above.
The helper checks keys against a fixed allowlist before construction; an
unknown field raises a constant, value-free `TypeError`. No global counter,
random source, clock, registry, or retained event list is used.

The unknown-override message is exactly `unknown audit event override`; it
does not include the rejected key.

`assert_audit_event_preserved()` requires two exact `AuditEvent` values and
checks event ID, action, timestamp, subject kind/value, actor presence and
kind/value, correlation ID, causation ID, payload content type, payload schema
version, payload data, and metadata in that total order. Timestamp preservation means
the same year, month, day, hour, minute, second, microsecond, UTC offset, and
`fold`; timezone object identity is not required. It then checks exact payload
bytes and metadata with order-insensitive mapping equality. A mismatch raises
`AssertionError` with exactly `audit event field was not preserved: <category>`,
where `<category>` is one of the fixed field names above. It never interpolates
either event or field value into the message.
The helper verifies adapter round-trip behavior but does not implement append,
history, fake storage, an outbox, or eventual delivery.

## Caller-Owned Data Flow

```text
caller serialization
        |
        v
AuditPayload(bytes, content_type, schema_version)
        |
        v
AuditEvent(identity, time, subject/actor, causal links, metadata)
        |
        +---- optional application prevalidation
        |
        v
caller-owned transaction / storage / outbox adapter
        |
        +---- mandatory validate_audit_event(event, adapter AuditLimits)
        |
        +---- adapter-owned write / enqueue / transport handoff
```

The durable adapter owns the authoritative storage policy and must validate
immediately before its first side effect. Earlier application validation is an
optional fast-fail convenience and never satisfies the adapter gate. The
package boundary ends when validation returns. A later PostgreSQL adapter may
map the stable fields into columns and store payload bytes, but it must not
widen this package with connection, transaction, claim, or relay ownership.

## Canonical Caller Example

Install either the focused distribution or the optional meta extra:

```bash
uv add bluetape-audit
# or, through the thin meta distribution:
uv add 'bluetape[audit]'
```

The README source-of-truth example uses exact built-ins, caller serialization,
adapter-owned limits, and value-free rejection handling:

```python
import json
from datetime import datetime, timezone

from bluetape.audit import (
    AuditError,
    AuditEvent,
    AuditIdentity,
    AuditLimits,
    AuditPayload,
    validate_audit_event,
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

The English and Korean package READMEs execute the same code block. Framework
objects, datetime subclasses, custom timezones, mapping subclasses, mutable
buffers, and domain objects must be converted explicitly by caller code before
construction; the package performs no hidden conversion.

## Serialization and Versioning Guidance

- The package does not define `to_dict`, `from_dict`, JSON encoders, wire
  formats, database column types, or timestamp text formats.
- The caller serializes domain changes before constructing `AuditPayload` and
  declares both `content_type` and `schema_version`.
- `schema_version` versions the caller's payload schema, not the
  `bluetape-audit` package or `AuditEvent` envelope.
- Consumers dispatch payload decoding by the pair `(content_type,
  schema_version)` and must reject unsupported pairs before parsing. A writer
  introduces a new pair only after every intended reader can preserve or
  understand it. Existing payload bytes remain unchanged during rollout;
  conversion of historical dictionary or database records is adapter-owned.
- Adapters must preserve unknown payload bytes and metadata exactly. They may
  reject values according to their own documented storage constraints before
  I/O, but must not silently normalize them.
- Evolution of the public event envelope follows normal package compatibility
  rules. New required fields or changed meanings require a future design and a
  versioned migration path; v1 does not reserve an extension dictionary beyond
  the bounded string metadata map.

## Operational Delivery Boundary

Successful construction or validation means only that an in-memory value
satisfies the selected contract. It does not mean the audit fact was recorded,
committed, published, replicated, or delivered. Callers and concrete adapters
own:

- atomic capture with the business change, normally through a shared database
  transaction or a documented alternative;
- idempotency and duplicate detection keyed by stable `event_id`;
- retry classification, ordering guarantees, backpressure, retention,
  quarantine/dead-letter handling, and partial-failure recovery;
- authorization, encryption, access control, integrity protection, monitoring,
  and operational alerting.

Adapters also own versioned `AuditLimits` configuration. A stricter policy is
rolled out only after producers and queued-event replay have been checked
against it. The adapter may record a bounded external policy identifier for
operations, but it does not inject that identifier into caller metadata or log
rejected values.

Package hard ceilings inspect already allocated caller objects. They prevent
additional package retention or metadata-copy work beyond the declared bounds;
they do not limit request-body reads, decoding, JSON expansion, or upstream
allocation. Applications must enforce those limits before constructing audit
values.

## Alternatives Considered

### Repository/history protocols in v1

Rejected. Append return types, transaction ownership, query filters,
pagination, ordering, consistency, retention, and async shape depend on the
first durable adapter. Values-first avoids freezing speculative storage
semantics.

### Generic Python payload object

Rejected. `object`, `Any`, or arbitrary mappings would make immutability,
size, equality, safe representation, and adapter interoperability ambiguous.

### Immutable JSON tree

Rejected. A JSON-only tree would privilege one codec, require recursive copy
and number semantics, and block protobuf, Fory, encrypted, or otherwise opaque
caller payloads. Immutable bytes keep serialization ownership explicit.

### Package-owned JSON serialization

Rejected. It would add format/version behavior unrelated to the storage-neutral
event value and could silently normalize datetimes, keys, or bytes.

### Mutable metadata dictionary

Rejected. Retaining a caller dictionary would let an event change after
validation. A top-level defensive snapshot is sufficient because keys and
values are strings.

### Automatic redaction or sensitive-key denylist

Rejected. The package cannot infer caller classification rules reliably.
Instead it prevents its own disclosure and documents that callers must redact
before payload construction or external emission.

### Generated event IDs and current timestamps

Rejected. Hidden randomness and clocks reduce determinism and obscure which
service owns idempotency and temporal semantics.

## Failure Modes and Recovery

| Failure | Prevention or detection | Recovery owner |
|---|---|---|
| Mutable caller metadata changes after validation | exact-dict precheck, bounded defensive snapshot, and mutation tests | package |
| Payload or identity marker leaks through errors/repr | hostile-marker tests across constructors, limits, repr, and helper assertions | package |
| Naive datetime creates ambiguous occurrence time | constructor rejects `utcoffset() is None`; offset-preservation tests | caller fixes event |
| Oversized input was already allocated upstream | request-body/decoder limits before construction; package ceilings prevent extra retention/copy | application then package |
| Stricter adapter policy is skipped before I/O | explicit `AuditLimits`; future adapter test proves rejection before write | adapter |
| Validation success is mistaken for durable capture | operational docs and adapter contract distinguish value validity from commit/delivery | caller/adapter |
| Capture retry creates duplicates | stable `event_id` reuse and adapter idempotency/deduplication | adapter |
| Business commit and audit capture diverge | shared transaction or explicitly documented partial-failure recovery | caller/adapter |
| Queue pressure or poison payload stalls delivery | adapter-owned backpressure, retry classification, and quarantine/dead-letter policy | adapter/operator |
| JSON-specific API blocks another codec | opaque exact bytes plus caller-declared media/schema fields | caller serializer |
| A test helper is mistaken for durable history | no retained collection or repository methods; docs state process-local value fixture only | caller chooses durable adapter |
| SQL or outbox concerns leak into core package | stdlib-only metadata and package/repo boundary reviews | follow-up package |
| Default meta install grows unexpectedly | exact dependency/extras packaging tests and isolated-wheel smoke checks | package |

## Test and Conformance Plan

Implementation follows red-green-refactor. Tests are organized by public
behavior rather than private modules.

### Value tests

- successful construction and frozen/slotted behavior for all four values;
- exact caller-value and datetime-offset preservation;
- invalid type, empty, whitespace-only, naive datetime, wrong nested value,
  empty payload, invalid metadata key/value types, and mapping mutation cases;
- exact built-in datetime and timezone acceptance; datetime subclass, custom
  timezone, fixed-offset, ZoneInfo, and DST-fold cases;
- exact built-in dictionary input, subclass/custom mapping rejection, hard
  ceiling precheck, copied-length recheck, single private-copy validation,
  source mutation isolation, and failed-construction atomicity;
- constant-size `repr` hostile markers for every caller-controlled field;
- event unhashability and metadata read-only behavior.

### Limit tests

- exact default declarations, positive exact-int validation, and rejection of
  wider-than-default policies with exact `InvalidAuditLimitsError` assertions;
- each field at its limit and one unit beyond;
- empty metadata and maximum entry count;
- multi-byte Unicode proving character-count semantics;
- same-object return on success, published total-order precedence for multiple
  violations, and fail-fast typed errors on violation;
- hostile markers absent from every limit error.
- stable `field_category` and `limit_name` attributes from fixed allowlists,
  with no rejected value retained on the exception.

### Testing-helper tests

- deterministic equality across separate factory calls with no shared mutable
  metadata;
- each named override, hostile unknown override rejection with a constant
  message, and invalid override propagation;
- successful all-field preservation assertion;
- one mismatch per field category in the published order with exact,
  value-free assertion messages and order-insensitive metadata equality;
- scalar-first comparison order, exact payload object retention at
  construction, and proof that no timing benchmark is needed for bounded value
  operations;
- proof that the module exposes no repository/history/buffer API.

### Packaging and documentation tests

- exact empty runtime dependency list, Python version, build backend, module
  name, ordered `__all__`, and absent root namespace initializer;
- root workspace member/source registration;
- default meta dependency remains core-only;
- exact `audit`, `dev`, and `all` extras behavior;
- focused wheel, meta-extra wheel, and default-meta isolation/import smoke;
- English/Korean package README examples execute from installed artifacts;
- canonical field-semantics, install-to-adapter, validation ownership, safe
  error, payload-version dispatch, and removal/rollback examples remain aligned;
- root README, root Korean README, WIP, package layout, and changelog remain
  aligned.

## Documentation and Diagram

The delivery updates:

- `packages/bluetape-audit/README.md` and `README.ko.md` with install, values,
  validation, redaction, serialization/versioning, test helpers, and explicit
  adapter separation;
- root `README.md` and `README.ko.md` with package and extra visibility;
- `WIP.md`, `CHANGELOG.md`, and `docs/package-layout.md` with milestone and
  ownership boundaries;
- one English-label SVG plus deterministic PNG showing the caller-owned flow
  from serialization through values and validation to external adapters.

README locale parity is checked for focused/meta install commands, the exact
canonical caller example, field-semantics table, adapter-owned validation gate,
safe error handling, serialization/version dispatch, migration/rollback,
redaction, and accepted/rejected ownership. A missing or meaningfully drifted
row blocks documentation completion.

The visual is produced and audited with `$bluetape-diagram`; Mermaid is not
used. SVG source and PNG output live under
`docs/images/readme-diagrams/`. Both package READMEs embed the same asset so
locale claims cannot drift from the technical boundary.

## Baseline and Validation Commands

The isolated worktree begins at
`4b4df925a0a1cf3d1187cf6f4fb351595a5a02b3`. Dependency sync passed with:

```bash
uv sync --all-packages --all-extras --python 3.13.14 --locked
```

An unfiltered `uv run pytest` discovers six existing observability SDK tests
whose separately owned `test` dependency group is not installed by the root
all-extras sync. The repository CI intentionally excludes markers
`observability_sdk` and `observability_workspace` from its generic test job.
The canonical source baseline for this issue is therefore:

```bash
uv run pytest -m 'not observability_sdk and not observability_workspace'
```

Baseline result: `1841 passed, 9 deselected`. The observability dependency-group
shape is pre-existing and outside issue #25.

Final validation escalates from focused tests to:

```bash
uv run pytest packages/bluetape-audit packages/bluetape/tests
uv run ruff check .
uv run ruff format --check .
uv run pytest -m 'not observability_sdk and not observability_workspace'
uv build --all-packages
git diff --check
```

Installed-wheel isolation and README example commands are added to the
implementation plan after the design is approved.

## Compatibility and Migration

This is a new optional distribution, so existing default installs and imports
have no migration. Applications opt in with `bluetape-audit` or
`bluetape[audit]`, explicitly convert framework values to the supported
built-ins, serialize their own payload bytes, supply all event identity and
time fields, and pass the event to an adapter that applies its authoritative
limits immediately before I/O. Application-side prevalidation is optional.

Incremental adoption leaves existing dictionary-shaped or stored audit records
under their current adapter. Callers translate only new writes or an explicitly
planned migration; this package does not rewrite historical data. Consumers
dispatch by `(content_type, schema_version)` and preserve unknown bytes until a
compatible reader is deployed.

Installation rollback removes the optional extra or focused distribution and
requires no package-owned data migration. A post-removal smoke check proves
that the default meta distribution still resolves only `bluetape-core` and
that `bluetape.audit` is absent from the isolated environment.

Future SQL or outbox packages depend on these values rather than adding
storage methods here. If a concrete adapter proves a missing envelope field,
the change requires a separately reviewed compatibility design; it must not be
smuggled in through metadata semantics or a generic extension object.

## Acceptance Criteria

- `bluetape-audit` is a Python 3.13+, stdlib-only focused distribution under
  `bluetape.audit` with the exact public API above.
- All public values are frozen and slotted; valid caller data and timezone
  offsets are preserved without hidden normalization.
- Metadata is a defensive read-only snapshot and payload is exact non-empty
  bytes with explicit content type and schema version; package hard ceilings
  bound additional package retention and copy work before either value becomes
  observable. Upstream allocation limits remain caller-owned.
- Validation uses caller-visible `AuditLimits`, returns the same event on
  success, and covers every declared bound at limit and limit+1.
- Errors, representations, and testing-helper failures do not expose payload,
  identity, metadata, identifiers, timestamp, media/schema labels, or hostile
  marker values.
- Testing helpers are deterministic, compare all fields, retain no history,
  and expose no repository, buffer, or outbox surface.
- Default `bluetape` dependencies remain core-only; focused, `audit`, `dev`,
  and `all` installation shapes are verified from built artifacts.
- English/Korean documentation explains ownership, serialization/versioning,
  size/redaction policy, and adapter separation.
- The SVG+PNG diagram passes the Bluetape diagram validation and rendered
  visual inspection gates.
- Focused and full canonical tests, lint, format, builds, diff checks, and
  independent P0/P1 review gates pass before PR creation.

## Definition of Done

- [ ] Written design reviewed by six independent perspectives and approved by
      the user before implementation planning.
- [ ] Detailed implementation and test plan written, independently reviewed,
      and approved before production-code edits.
- [ ] Tests demonstrate red-green-refactor evidence for every public contract.
- [ ] Package, meta extras, workspace registration, docs, and diagram match the
      approved boundary.
- [ ] Targeted and canonical workspace validation pass from a locked Python
      3.13.14 environment.
- [ ] Independent implementation review reports P0=0 and P1=0 at the exact
      branch head.
- [ ] Type A lesson artifact records reusable decisions and rejected scope.
- [ ] PR targets `develop`, ends with `## DoD Status`, and is verified at the
      exact remote head before merge-ready reporting.
- [ ] Merge occurs only after fresh explicit user approval; release, tag, and
      publication remain out of scope.
