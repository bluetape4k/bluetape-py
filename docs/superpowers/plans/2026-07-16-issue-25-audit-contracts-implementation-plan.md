# Issue #25 Storage-Neutral Audit Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the stdlib-only `bluetape-audit` distribution with immutable bounded audit values, explicit adapter-side validation, deterministic testing helpers, isolated install proof, bilingual documentation, and an SVG+PNG ownership diagram.

**Architecture:** `bluetape.audit` owns four final value types, one value-safe error hierarchy, and one pure limit validator. Construction applies package hard ceilings before retaining payloads or publishing a private metadata copy; an adapter applies an equal or stricter `AuditLimits` immediately before its first side effect. Serialization, persistence, history, transactions, outbox delivery, logging, tracing, and redaction remain caller-owned.

**Tech Stack:** Python 3.13.14, stdlib dataclasses/datetime/zoneinfo/types, uv workspace and `uv_build`, pytest, Ruff, isolated wheel installs, hand-authored SVG, CairoSVG, and Bluetape diagram audits.

---

## Approved Inputs and Stop Boundary

- Approved specification:
  `docs/superpowers/specs/2026-07-16-issue-25-audit-contracts-design.md`
- Specification review:
  `docs/review/2026-07-16-issue-25-audit-contracts-spec-review.md`
- Target issue/milestone: #25 / `0.2.0`
- Target repository: `bluetape4k/bluetape-py`
- Base/head: `develop` / `feat/issue-25-audit-contracts`
- Distribution/import: `bluetape-audit==0.1.0` / `bluetape.audit`
- Runtime dependencies: none
- Meta extra: `bluetape[audit]`; default dependencies stay exactly
  `bluetape-core==0.1.0`
- Approved PR authority: create a PR from the named head to `develop` only
  after implementation, review, and exact-head gates pass.
- This plan does not authorize merge, tag, release, PyPI publication, workflow
  dispatch, milestone closure, or destructive cleanup. Merge requires a fresh
  explicit user approval after exact-head evidence.

## Execution Rules

- Work only in `.worktrees/feat/issue-25-audit-contracts`.
- Apply `$bluetape-py-patterns` and the mandatory test-first micro-cycle to
  every behavior family: write one focused test, run RED for the intended
  missing behavior, implement the minimum, run GREEN, then run the owning file.
- If a RED test passes before production code exists, repair the test. If RED
  errors for setup/typing instead of failing the intended assertion, repair and
  rerun until the intended failure is visible.
- Production commits must contain complete executable bodies with no deferred
  markers or placeholder branches. They may not add generated identifiers,
  hidden clocks, repository or history protocols, serializers, global context,
  logging, workers, or I/O.
- Every commit follows the Lore protocol and records exact RED/GREEN or
  verification evidence.
- After a rebase, conflict resolution, lock regeneration, or review fix, all
  evidence tied to the old head is stale. Rerun the affected tests and exact-
  head review before reporting merge readiness.

## Artifact Map

| Responsibility | Files |
|---|---|
| Distribution metadata | `packages/bluetape-audit/pyproject.toml`, root `pyproject.toml`, `packages/bluetape/pyproject.toml`, `uv.lock` |
| Error taxonomy | `packages/bluetape-audit/src/bluetape/audit/_errors.py` |
| Immutable values | `packages/bluetape-audit/src/bluetape/audit/_values.py` |
| Explicit size policy | `packages/bluetape-audit/src/bluetape/audit/_validation.py` |
| Public API | `packages/bluetape-audit/src/bluetape/audit/__init__.py` |
| Test helpers | `packages/bluetape-audit/src/bluetape/audit/testing.py` |
| Package tests | `packages/bluetape-audit/tests/test_audit_*.py` |
| Meta/wheel tests | `packages/bluetape/tests/test_audit_wheel_isolation.py`, `packages/bluetape/tests/test_audit_readmes.py` |
| Publish classifier | `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`, `docs/release/pypi-preflight.md` |
| User documentation | package/root EN/KO README pairs, `WIP.md`, `CHANGELOG.md`, `docs/package-layout.md` |
| Diagram | `docs/images/readme-diagrams/audit-contract-boundary.svg` and `.png` |
| Delivery evidence | `docs/review/2026-07-16-issue-25-audit-contracts-*.md`, `docs/lessons/2026-07-16-issue-25-audit-contracts.md` |

## Spec Coverage

| Specification requirement | Owning tasks |
|---|---|
| Stdlib-only focused package, exact meta extra, unchanged default install | 1, 6 |
| Exact errors, exports, final value signatures, safe repr | 1-5 |
| Hard ceilings, exact built-ins, fixed timezone boundary, private metadata copy | 2-3 |
| Equal-or-stricter adapter validation and stable safe error attributes | 4 |
| Deterministic fixture and preservation assertion | 5 |
| Focused/meta/default isolated wheel proof | 6 |
| EN/KO field semantics, examples, ownership, version dispatch, rollback | 7 |
| SVG+PNG architecture asset and audit ledger | 7 |
| Full validation, six-lens review, verifier, Type A lesson | 8 |
| Exact-head PR and merge gate | 9 |

## Step 3-P Risk Prediction

| Risk | Trigger | Prevention/proof | Rollback boundary |
|---|---|---|---|
| Caller value leaks | repr, exception, assertion, or pytest output includes hostile markers | constant redacted repr, constant messages, closed category attributes, hostile-marker matrix | revert owning value/helper commit and rerun all disclosure tests |
| Metadata snapshot differs from validated content | mutable/custom mapping or validation-before-copy | exact built-in dict, size precheck, one private copy, copied-size recheck, validate private copy, publish last | revert Task 3 only |
| Time meaning changes | naive/custom timezone, UTC normalization, instant-only equality | exact datetime plus exact timezone/ZoneInfo, preserve offset/wall/fold, structural equality tests | revert Task 3 only |
| Resource policy is overstated | caller already allocated huge bytes/dict | hard ceilings limit only package retention/copy; docs require upstream allocation limits | revert wording/tests with Task 2 or 7 |
| Adapter skips authoritative validation | application prevalidation is mistaken for storage gate | canonical example and future-adapter contract validate immediately before first side effect | revert Task 4/7 together |
| Default install widens | audit added to root meta dependencies rather than optional extra | exact metadata and isolated default-wheel absence tests | revert Task 1/6 metadata and lock together |
| Storage lifecycle leaks into core | repository/history/outbox API appears during implementation | public symbol negative tests and six-lens boundary review | remove the surface before continuing |
| Diagram implies durability | visual places validation inside storage or labels it recorded/delivered | static ownership lanes, source-backed labels, full-size PNG review | revert asset/docs commit only |

Risk gate is required because the change adds a public distribution, sensitive
caller values, explicit resource ceilings, datetime semantics, and a future
adapter boundary even though the implementation is stdlib-only and performs no
I/O.

## Exact Production Blueprint

The implementation must preserve this ordered root export list:

```python
__all__ = [
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

The final public signatures and decorators are exact:

| Symbol | Decorators/signature |
|---|---|
| `AuditIdentity` | `@final`, `@dataclass(frozen=True, slots=True, init=False, repr=False)`; `AuditIdentity(kind: str, value: str)` |
| `AuditPayload` | `@final`, `@dataclass(frozen=True, slots=True, init=False, repr=False)`; `AuditPayload(data: bytes, content_type: str, schema_version: str)` |
| `AuditEvent` | `@final`, `@dataclass(frozen=True, slots=True, init=False, repr=False, eq=False)`; required positional-or-keyword `event_id`, `action`, `occurred_at`, `subject`, `payload`; keyword-only `actor=None`, `correlation_id=None`, `causation_id=None`, `metadata: dict[str, str] | None=None` |
| `AuditLimits` | `@final`, `@dataclass(frozen=True, slots=True, kw_only=True)` with the twelve defaults below |
| `validate_audit_event` | `(event: AuditEvent, limits: AuditLimits) -> AuditEvent` |

`AuditEvent` declares the nine stored field annotations from the specification,
implements custom equality and redacted repr, and sets `__hash__ = None`.
`AuditLimits` defaults, in declaration order, are `128`, `128`, `64`, `512`,
`128`, `128`, `128`, `64`, `1_048_576`, `64`, `128`, and `2_048` for the
twelve `max_*` fields listed in the specification.

Hard-ceiling constants remain private in `_values.py` and exactly match the
`AuditLimits` defaults. Constructor validation order is exact type, O(1)
length/byte ceiling, permitted content scan, retention. `_contains_control`
applies only to `content_type` and `schema_version`, which reject
U+0000..U+001F and U+007F..U+009F. Payload bytes are never iterated or copied.
Metadata keys and values preserve C0, DEL, and C1 content after their type and
length checks; keys reject blank strings, while values preserve empty and
whitespace-only content.

The exact limit-error mapping is:

```python
LIMIT_CHECKS = (
    ("event_id", "max_event_id_chars"),
    ("action", "max_action_chars"),
    ("subject.kind", "max_identity_kind_chars"),
    ("subject.value", "max_identity_value_chars"),
    ("actor.kind", "max_identity_kind_chars"),
    ("actor.value", "max_identity_value_chars"),
    ("correlation_id", "max_correlation_id_chars"),
    ("causation_id", "max_causation_id_chars"),
    ("payload.content_type", "max_content_type_chars"),
    ("payload.schema_version", "max_schema_version_chars"),
    ("payload.data", "max_payload_bytes"),
    ("metadata", "max_metadata_entries"),
    ("metadata.key", "max_metadata_key_chars"),
    ("metadata.value", "max_metadata_value_chars"),
)
```

## Task 1: Register the package and lock the error boundary

**Depends on:** committed approved spec and plan approval

**Files:**

- Create `packages/bluetape-audit/pyproject.toml`
- Create `packages/bluetape-audit/README.md`
- Create `packages/bluetape-audit/README.ko.md`
- Create `packages/bluetape-audit/src/bluetape/audit/_errors.py`
- Create `packages/bluetape-audit/src/bluetape/audit/__init__.py`
- Create `packages/bluetape-audit/tests/test_audit_packaging.py`
- Create `packages/bluetape-audit/tests/test_audit_errors.py`
- Create `packages/bluetape/tests/test_audit_wheel_isolation.py`
- Modify root `pyproject.toml`
- Modify `packages/bluetape/pyproject.toml`
- Modify `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`
- Modify `docs/release/pypi-preflight.md`
- Modify `uv.lock`

- [ ] **Step 1: Write RED package and error tests.** Assert the precise missing
  targets first—package `pyproject.toml`, `src/bluetape/audit`, built wheel, and
  import surface—while allowing the distribution directory to hold RED tests.
  Then pin metadata, Python floor, empty runtime dependencies,
  `uv_build`, missing root namespace initializer, exact exception inheritance,
  constant base messages, workspace/member/source registration, `audit` extra,
  `dev`/`all` inclusion, unchanged default dependency, and publish classifier.
  The same RED cycle adds the three isolated focused/meta/default wheel shapes
  described in Task 6; the initial error-only package is sufficient for a real
  installed import and keeps every committed scaffold buildable. Until Task 6,
  the shared installed-wheel probe pins the six error exports as an ordered
  prefix and requires every current `__all__` name to resolve as a module
  attribute, so later task-owned exports can be added without weakening the
  initial error contract.

```python
def test_audit_error_hierarchy_is_value_safe() -> None:
    assert issubclass(InvalidAuditIdentityError, AuditError)
    assert issubclass(InvalidAuditPayloadError, AuditError)
    assert issubclass(InvalidAuditEventError, AuditError)
    assert issubclass(InvalidAuditLimitsError, AuditError)
    error = AuditLimitExceededError("payload.data", "max_payload_bytes")
    assert str(error) == "audit value exceeds configured limit"
    assert error.field_category == "payload.data"
    assert error.limit_name == "max_payload_bytes"
    assert "payload.data" not in str(error)
```

- [ ] **Step 2: Run RED and confirm the missing package/error surface.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_packaging.py packages/bluetape-audit/tests/test_audit_errors.py packages/bluetape/tests/test_audit_wheel_isolation.py -v
```

Expected: FAIL because `packages/bluetape-audit/pyproject.toml`, its wheel, and
`bluetape.audit` do not exist; no unrelated collection error.

- [ ] **Step 3: Add exact metadata and the complete error hierarchy.** Use this
  distribution record and no dependency group:

```toml
[project]
name = "bluetape-audit"
version = "0.1.0"
description = "Python-native storage-neutral audit event contracts for bluetape."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.audit"
```

`_errors.py` contains the six classes. `AuditLimitExceededError.__init__`
stores only `field_category` and `limit_name` in slots and calls
`super().__init__("audit value exceeds configured limit")`. The initial
`__init__.py` exports only the six implemented errors in final relative order;
later tasks add symbols only after their RED/GREEN owner exists.
Create concise, build-valid English and Korean package READMEs that describe
only the package boundary and install shape implemented in this task; do not
publish placeholder API or durability claims. Task 7 expands both files after
the complete public contract is green.

- [ ] **Step 4: Register the distribution.** Insert audit alphabetically into
  root project dependencies, uv sources, workspace members, meta uv sources,
  and meta `dev`/`all`; add exact singleton extra
  `audit = ["bluetape-audit==0.1.0"]`. Add `bluetape-audit` to `PUBLISHABLE`
  and the fail-closed preflight classifier, without changing historical release
  targets or HOLD wording.

- [ ] **Step 5: Lock, sync, and run GREEN.**

```bash
uv lock
uv sync --all-packages --all-extras --python 3.13.14 --locked
uv run pytest packages/bluetape-audit/tests/test_audit_packaging.py packages/bluetape-audit/tests/test_audit_errors.py packages/bluetape/tests/test_audit_wheel_isolation.py packages/bluetape-benchmark/tests/test_benchmark_packaging.py -v
uv run ruff check packages/bluetape-audit packages/bluetape-benchmark/tests/test_benchmark_packaging.py
uv run ruff format --check packages/bluetape-audit packages/bluetape-benchmark/tests/test_benchmark_packaging.py
```

Expected: all selected tests pass; lock is current; default meta dependency is
still core-only.

- [ ] **Step 6: Commit one boundary unit.**

Intent: `Establish the audit package boundary before behavior`

Rollback: revert this commit and rerun `uv lock`; no later package task can
remain if registration is removed.

## Task 2: Implement bounded identity, payload, and limits values test-first

**Depends on:** Task 1

**Files:**

- Create `packages/bluetape-audit/src/bluetape/audit/_values.py`
- Create `packages/bluetape-audit/tests/test_audit_values.py`
- Modify `packages/bluetape-audit/src/bluetape/audit/__init__.py`

- [ ] **Step 1: Write RED table-driven tests.** Cover exact types, blank
  required strings, leading/trailing preservation, hard limit and limit+1,
  payload object identity, empty bytes, mutable buffer rejection, exact
  redacted repr literals, control ranges, every numeric default, boolean/zero/
  negative/wider limit rejection, equality, hashing, frozen and slotted state,
  and hostile markers absent from every exception/repr. Include a payload at
  the exact 1,048,576-byte hard ceiling and prove the stored object is the same
  bytes instance; this is the executable no-copy boundary proof. Use
  `inspect.signature`, dataclass metadata, `__slots__`, `__final__`, and hash
  assertions to pin the exact identity, payload, and keyword-only limits
  signatures/decorators at their owning RED boundary.

```python
def test_payload_preserves_exact_bytes_without_disclosure() -> None:
    marker = b"secret-payload-marker"
    payload = AuditPayload(marker, "application/json", "1")
    assert payload.data is marker
    assert repr(payload) == "AuditPayload(<redacted>)"
    assert marker.decode() not in repr(payload)


@pytest.mark.parametrize("value", [True, 0, -1, 129])
def test_event_id_limit_must_be_positive_and_not_wider(value: object) -> None:
    with pytest.raises(InvalidAuditLimitsError, match="audit limits are invalid"):
        AuditLimits(max_event_id_chars=value)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run RED.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_values.py -v
```

Expected: FAIL on missing `AuditIdentity`, `AuditPayload`, and `AuditLimits`.

- [ ] **Step 3: Implement the minimum values.** In `_values.py`, define private
  hard constants, `_require_string`, `_require_optional_string`, and
  `_contains_control`. Type errors use fixed field-category messages; semantic
  and hard-ceiling failures use the owning invalid-value error with no caller
  content. Implement the exact final decorators/signatures from the blueprint.
  Repr results are exactly `AuditIdentity(<redacted>)` and
  `AuditPayload(<redacted>)`. `AuditLimits.__post_init__` iterates its fixed
  numeric field/ceiling tuple and rejects `type(value) is not int`, non-positive,
  or wider values with `InvalidAuditLimitsError("audit limits are invalid")`.

- [ ] **Step 4: Run GREEN, refactor only after green, and lock exports.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_values.py -v
uv run pytest packages/bluetape-audit/tests/test_audit_errors.py packages/bluetape-audit/tests/test_audit_values.py -v
uv run ruff check packages/bluetape-audit
uv run ruff format --check packages/bluetape-audit
```

Expected: all selected tests pass and `__all__` contains errors followed by the
three implemented values in final relative order. The shared installed-wheel
probe remains interim prefix-plus-accessibility evidence; Task 6 replaces that
interim expectation with the exact final eleven-name tuple.

- [ ] **Step 5: Commit.**

Intent: `Bound audit values before adapters can retain them`

Rollback: revert Task 2; Task 1 remains a buildable error-only package.

## Task 3: Implement immutable event snapshots test-first

**Depends on:** Task 2

**Files:**

- Modify `packages/bluetape-audit/src/bluetape/audit/_values.py`
- Modify `packages/bluetape-audit/src/bluetape/audit/__init__.py`
- Create `packages/bluetape-audit/tests/test_audit_event.py`

- [ ] **Step 1: Write RED event tests.** Cover the authoritative constructor
  signature, positional required fields, keyword-only optional fields, exact
  nested types, fixed/ZoneInfo offsets, naive/custom/subclass rejection,
  preserved object/offset/wall/fold, structural timestamp equality,
  order-insensitive metadata equality, exact-dict-only input, hard entry
  precheck, copied-length recheck, private-copy validation, source mutation
  isolation, an exact 64-entry maximum metadata snapshot, invalid key/value
  matrices, positive preservation of empty/whitespace/C0/DEL/C1 metadata
  values, nonblank metadata keys with leading/trailing whitespace and embedded
  C0/DEL/C1 preserved, whitespace-only keys rejected, optional string rules,
  unhashability,
  frozen/slots/final behavior, exact repr, and `dataclasses.replace()` being
  outside the supported contract. Add a table-driven disclosure matrix for
  event ID, action, occurred time, subject/actor kind and value, correlation
  and causation IDs, payload declarations/data, and metadata keys/values; every
  hostile marker must be absent from exception `str`, `repr`, `args`, and the
  constant event repr. Define a file-local `make_event` helper with
  the same explicit event defaults used below; it returns `AuditEvent` and
  accepts only named event-field overrides. It is test setup, not public code.
  Add constructor hard-ceiling tests at the default and default+1 for event ID,
  action, correlation ID, causation ID, metadata key/value, and entry count;
  pin `InvalidAuditEventError`, value-free messages, and multi-invalid field
  precedence. Pin the exact event signature/decorator/dataclass/hash shape with
  `inspect.signature` and structural assertions.

```python
def make_event(**overrides: object) -> AuditEvent:
    values: dict[str, object] = {
        "event_id": "evt-test-0001",
        "action": "test.action",
        "occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "subject": AuditIdentity("test-subject", "subject-0001"),
        "payload": AuditPayload(b"{}", "application/json", "1"),
        "actor": AuditIdentity("test-actor", "actor-0001"),
        "correlation_id": "corr-test-0001",
        "causation_id": "cause-test-0001",
        "metadata": {"source": "bluetape.audit.testing"},
    }
    values.update(overrides)
    return AuditEvent(**values)  # type: ignore[arg-type]
```

```python
def test_metadata_is_a_private_read_only_snapshot() -> None:
    source = {"source": "orders-api"}
    event = make_event(metadata=source)
    source["source"] = "changed"
    assert dict(event.metadata) == {"source": "orders-api"}
    with pytest.raises(TypeError):
        event.metadata["new"] = "value"  # type: ignore[index]


def test_timestamp_equality_preserves_wall_offset_and_fold() -> None:
    zone = ZoneInfo("America/New_York")
    first = make_event(occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0))
    second = make_event(occurred_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1))
    assert first != second
```

- [ ] **Step 2: Run RED.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_event.py -v
```

Expected: FAIL because `AuditEvent` is not implemented.

- [ ] **Step 3: Implement exact event behavior.** Add `AuditEvent` to
  `_values.py`. Validate fields in declaration order. Require exact
  `datetime`, then exact `timezone` or `ZoneInfo`, evaluate `utcoffset()` once,
  and replace any failure with value-free `InvalidAuditEventError`. For
  metadata: require `None` or exact `dict`; precheck `len`, call a private
  `_copy_metadata(source)` seam that performs exactly one built-in shallow
  `dict.copy()`, recheck the private length, validate only private entries, and
  publish `MappingProxyType(private)` last. Monkeypatch that private seam only
  in deterministic unit tests to return a controlled length-mismatched or
  invalid private dict, proving recheck order, copy-only validation, and failed-
  construction atomicity without threads; separately prove the real seam
  returns a distinct exact dict. Implement `_datetime_key` over wall
  fields, offset, and fold; custom equality uses this key and mapping equality.
  Set `__hash__ = None` explicitly and return exactly
  `AuditEvent(<redacted>)` from repr.

- [ ] **Step 4: Run GREEN and the owning package set.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_event.py -v
uv run pytest packages/bluetape-audit/tests/test_audit_errors.py packages/bluetape-audit/tests/test_audit_values.py packages/bluetape-audit/tests/test_audit_event.py -v
uv run ruff check packages/bluetape-audit
uv run ruff format --check packages/bluetape-audit
```

- [ ] **Step 5: Commit.**

Intent: `Preserve audit events as private immutable snapshots`

Rollback: revert Task 3 only; identity, payload, and limits remain usable.

## Task 4: Implement explicit adapter policy validation test-first

**Depends on:** Task 3

**Files:**

- Create `packages/bluetape-audit/src/bluetape/audit/_validation.py`
- Modify `packages/bluetape-audit/src/bluetape/audit/__init__.py`
- Create `packages/bluetape-audit/tests/test_audit_validation.py`

- [ ] **Step 1: Write RED policy tests.** Pin wrong-argument check order and
  exact value-free messages, same-object success, every limit at boundary and
  limit+1, multi-violation precedence, actor-absent skip, metadata insertion
  order/key-before-value, Unicode character counts, closed
  `field_category`/`limit_name` values, no rejected value retained, and hostile
  markers absent from `str`, `repr`, and `args`. Define the complete file-local
  `make_event` literal below rather than importing the not-yet-implemented
  public testing helper. Pin the exact two-argument validator signature with
  `inspect.signature` at this owning RED boundary.

```python
def make_event(**overrides: object) -> AuditEvent:
    values: dict[str, object] = {
        "event_id": "evt-test-0001",
        "action": "test.action",
        "occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "subject": AuditIdentity("test-subject", "subject-0001"),
        "payload": AuditPayload(b"{}", "application/json", "1"),
        "actor": AuditIdentity("test-actor", "actor-0001"),
        "correlation_id": "corr-test-0001",
        "causation_id": "cause-test-0001",
        "metadata": {"source": "bluetape.audit.testing"},
    }
    values.update(overrides)
    return AuditEvent(**values)  # type: ignore[arg-type]
```

```python
def test_validator_checks_event_before_limits() -> None:
    with pytest.raises(TypeError, match="^event must be an AuditEvent$"):
        validate_audit_event(object(), object())  # type: ignore[arg-type]


def test_payload_limit_error_is_safe_and_actionable() -> None:
    event = make_event(payload=AuditPayload(b"12", "application/json", "1"))
    with pytest.raises(AuditLimitExceededError) as captured:
        validate_audit_event(event, AuditLimits(max_payload_bytes=1))
    assert captured.value.field_category == "payload.data"
    assert captured.value.limit_name == "max_payload_bytes"
    assert captured.value.args == ("audit value exceeds configured limit",)
```

- [ ] **Step 2: Run RED.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_validation.py -v
```

Expected: FAIL because `validate_audit_event` is missing.

- [ ] **Step 3: Implement explicit ordered checks.** Use direct `if` statements
  in the exact blueprint order rather than a dynamically extensible registry.
  A private `_exceeded(field_category, limit_name)` raises
  `AuditLimitExceededError`; it receives only fixed literals. Check event type,
  limits type, event ID, action, subject kind/value, present actor kind/value,
  correlation, causation, content type, schema version, payload bytes, metadata
  count, then each private mapping item key before value. Payload validation
  calls only `len(event.payload.data)` and never iterates the bytes. Return
  `event`.

- [ ] **Step 4: Run GREEN and hostile-input matrix.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_validation.py -v
uv run pytest packages/bluetape-audit/tests -v
uv run ruff check packages/bluetape-audit
uv run ruff format --check packages/bluetape-audit
```

- [ ] **Step 5: Commit.**

Intent: `Make audit storage policy explicit before side effects`

Rollback: revert Task 4; constructors still enforce package hard ceilings but
no adapter may claim configurable validation.

## Task 5: Add deterministic caller test helpers test-first

**Depends on:** Task 4

**Files:**

- Create `packages/bluetape-audit/src/bluetape/audit/testing.py`
- Create `packages/bluetape-audit/tests/test_audit_testing.py`
- Modify `packages/bluetape-audit/tests/test_audit_packaging.py`
- Modify `packages/bluetape-audit/src/bluetape/audit/__init__.py`

- [ ] **Step 1: Write RED helper tests.** Pin exact `testing.__all__`, complete
  literal defaults, fresh object/metadata per call, every allowed override,
  constant hostile unknown-key failure, invalid override propagation, exact
  actual/expected type errors, total comparison order, every constant mismatch
  category, timestamp wall/offset/fold comparison, payload byte comparison,
  order-insensitive metadata comparison, and absence of repository/history/
  buffer/outbox exports or retained module collections.
  Pin `inspect.signature` for both helpers, including keyword-only arbitrary
  event-field overrides on `make_audit_event` and the exact `actual, expected`
  comparator parameters.

```python
def test_factory_is_deterministic_without_shared_metadata() -> None:
    first = make_audit_event()
    second = make_audit_event()
    assert first == second
    assert first is not second
    assert first.metadata is not second.metadata


def test_unknown_override_never_echoes_the_key() -> None:
    marker = "secret-override-key"
    with pytest.raises(TypeError) as captured:
        make_audit_event(**{marker: object()})
    assert str(captured.value) == "unknown audit event override"
    assert marker not in str(captured.value)
```

- [ ] **Step 2: Run RED.**

```bash
uv run pytest packages/bluetape-audit/tests/test_audit_testing.py -v
```

Expected: FAIL because `bluetape.audit.testing` is missing.

- [ ] **Step 3: Implement the exact deterministic literal and comparator.**
  Create new default nested values and metadata on every call. Defaults are
  event ID `evt-test-0001`, action `test.action`, UTC
  `datetime(2026, 1, 1, tzinfo=timezone.utc)`, subject
  `AuditIdentity("test-subject", "subject-0001")`, payload
  `AuditPayload(b"{}", "application/json", "1")`, actor
  `AuditIdentity("test-actor", "actor-0001")`, correlation
  `corr-test-0001`, causation `cause-test-0001`, and metadata
  `{"source": "bluetape.audit.testing"}`. Reject any key
  outside the nine event constructor fields before merging. The comparator
  checks exact event types, then event ID, action, structural timestamp,
  subject kind/value, actor presence/kind/value, correlation, causation,
  payload content type/schema/data, and metadata. Its closed categories are
  `event_id`, `action`, `occurred_at`, `subject.kind`, `subject.value`, `actor`,
  `actor.kind`, `actor.value`, `correlation_id`, `causation_id`,
  `payload.content_type`, `payload.schema_version`, `payload.data`, and
  `metadata`. Raise only `audit event field was not preserved: ` followed by
  one of those literals.

- [ ] **Step 4: Finalize root exports and run GREEN.** Root `__all__` becomes
  the exact eleven-name blueprint. Testing helpers remain available only from
  `bluetape.audit.testing` and are not re-exported.

```bash
uv run pytest packages/bluetape-audit/tests -v
uv run ruff check packages/bluetape-audit
uv run ruff format --check packages/bluetape-audit
uv build --package bluetape-audit
```

Expected: all package tests pass and the focused wheel builds.

- [ ] **Step 5: Commit.**

Intent: `Let callers prove audit values without fake storage`

Rollback: revert Task 5; production values and validator remain intact.

## Task 6: Prove focused, meta-extra, and default installation isolation

**Depends on:** Task 5

**Files:**

- Re-run `packages/bluetape/tests/test_audit_wheel_isolation.py`
- Re-run `packages/bluetape-audit/tests/test_audit_packaging.py`
- Modify metadata or `uv.lock` only by returning to the owning earlier task if
  final isolation exposes drift

- [ ] **Step 1: Re-read the Task 1 isolated-wheel test against the final public
  surface.** It builds `bluetape-core`,
  `bluetape`, and `bluetape-audit` into a temporary directory. Create three
  Python 3.13.14 venvs and stage all three wheels in a temporary local
  wheelhouse. Install focused audit with `--offline --no-index --no-deps`;
  install `bluetape[audit]` and default `bluetape` with offline dependency
  resolution via `--find-links <wheelhouse>`. In all probes replace
  `socket.socket` and `socket.create_connection` with a raising guard, run
  Python with `-I`, require origins under the venv, run `uv pip check`, assert
  audit is present in the first two and absent in default, and inspect wheel
  METADATA for zero `Requires-Dist` in the focused audit wheel plus no
  `bluetape/__init__.py`. Inspect the meta wheel separately: its default
  dependency remains exactly `bluetape-core==0.1.0`, and its `audit` extra has
  exactly `Requires-Dist: bluetape-audit==0.1.0; extra == 'audit'`.

```python
PROBE = r"""
import importlib.util
import importlib
import socket
import sys
from pathlib import Path

def deny_network(*args, **kwargs):
    raise AssertionError("network access is forbidden during isolated imports")

socket.socket = deny_network
socket.create_connection = deny_network
spec = importlib.util.find_spec(sys.argv[1])
expected = sys.argv[2] == "present"
assert (spec is not None) is expected
if spec is not None:
    assert spec.origin is not None
    assert Path(spec.origin).resolve().is_relative_to(Path(sys.prefix).resolve())
    module = importlib.import_module(sys.argv[1])
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert tuple(module.__all__) == (
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
"""
```

- [ ] **Step 2: Confirm the test still proves final installed behavior without
  source-tree imports.** It uses `uv build --package`, `uv venv`, and
  `uv pip install --offline --no-index`; only the dependency-free focused wheel
  uses `--no-deps`, while meta installs resolve exclusively from the local
  wheelhouse. It never installs from the source tree into a probe environment.
  If it fails, return to the task that
  owns the metadata/export drift, repair there, and rerun that task's GREEN
  set before continuing.

- [ ] **Step 3: Prove removal rollback in the meta-extra environment.** Uninstall
  `bluetape-audit`, then require `bluetape` and `bluetape.core` to remain
  installed, `bluetape.audit` to be absent under the same network-denied `-I`
  probe, and `uv pip check` to pass. This is an install rollback smoke only;
  there is no package-owned data migration.

```bash
uv pip uninstall --python "$META_EXTRA_VENV/bin/python" bluetape-audit
"$META_EXTRA_VENV/bin/python" -I -c "$ROLLBACK_PROBE"
uv pip check --python "$META_EXTRA_VENV/bin/python"
```

`ROLLBACK_PROBE` installs the same raising `socket.socket` and
`socket.create_connection` guards as `PROBE`, imports `bluetape` and
`bluetape.core`, asserts the concrete `bluetape.core` module origin is under
`sys.prefix`, and proves root `bluetape` is a namespace package with every
`__path__`/`submodule_search_locations` entry under `sys.prefix`; it does not
expect a root `__file__`. It then asserts
`importlib.util.find_spec("bluetape.audit") is None`. The test requires all
three subprocess exit codes to be zero.

- [ ] **Step 4: Run final isolation, build all packages, and verify lock consistency.**

```bash
uv run pytest packages/bluetape-audit packages/bluetape/tests/test_audit_wheel_isolation.py packages/bluetape-benchmark/tests/test_benchmark_packaging.py -v
uv build --all-packages
uv lock --check
```

Expected: audit focused/meta environments import from installed wheels, default
does not resolve `bluetape.audit`, all wheel metadata is consistent, and every
workspace distribution builds.

- [ ] **Step 5: Record exact environment results in the later TDD/verifier
  ledgers.** Do not create an evidence-only commit here; Task 8 owns durable
  proof after the complete candidate head exists.

Rollback: return to and revert the owning metadata/lock task if isolation fails;
do not retain an unproved extra claim or modify the verifier to accept drift.

## Task 7: Synchronize bilingual docs and create the SVG+PNG boundary visual

**Depends on:** Tasks 1-6 and green package/wheel tests

**Pattern skills:** `$bluetape-writer`, `$bluetape-diagram`

**Files:**

- Modify `packages/bluetape-audit/README.md`
- Modify `packages/bluetape-audit/README.ko.md`
- Create `packages/bluetape/tests/test_audit_readmes.py`
- Modify root `README.md` and `README.ko.md`
- Modify `WIP.md`, `CHANGELOG.md`, `docs/package-layout.md`
- Create `docs/images/readme-diagrams/audit-contract-boundary.svg`
- Create `docs/images/readme-diagrams/audit-contract-boundary.png`
- Create `docs/review/2026-07-16-issue-25-audit-contracts-diagram-review.md`

- [ ] **Step 1: Write RED README parity/example tests.** Extract one identical
  marked Python example from EN/KO package READMEs; execute it against an
  installed focused wheel. Require install, field semantics, adapter validation,
  safe errors, redaction, `(content_type, schema_version)` dispatch, adoption,
  rollback, accepted/rejected ownership, and testing-helper headings in both
  locales. Require both package READMEs to embed the same SVG with a PNG
  fallback, root EN/KO docs to reference that same asset pair, and both SVG/PNG
  files to exist. Require the pair to be described as an untrusted caller
  assertion, allowlisted by the adapter before parser selection or header
  emission, with unsupported pairs rejected before parsing. Require stricter-
  policy rollout guidance: versioned adapter-owned limits, replay/producer
  compatibility checks before tightening, and an external bounded policy ID
  that is neither inserted into metadata nor paired with rejected-value logs.
  Pin exact focused `bluetape-audit` and meta `bluetape[audit]` install
  commands; incremental adoption applies only to new writes or an explicit
  caller migration, never rewrites history, and preserves unknown payload
  bytes. Pin exact removal commands, the no-package-owned-migration statement,
  and the Task 6 core-only/absent-audit rollback smoke result.

- [ ] **Step 2: Run RED.**

```bash
uv run pytest packages/bluetape/tests/test_audit_readmes.py -v
```

Expected: FAIL on missing final sections/example/assets.

- [ ] **Step 3: Write source-equivalent EN/KO docs.** Use the spec's canonical
  install-to-adapter example verbatim in both locale markers. State that
  adapter validation immediately before the first side effect is authoritative,
  validation is not durable capture, every field may be sensitive, upstream
  allocation limits precede construction, event IDs are reused for retries of
  the same fact, and repository/history/outbox remain external.
  Document allowlisting before parser/header use and rejection before parsing.
  Document stricter-limit rollout, replay/producer compatibility, and an
  external bounded policy identifier without metadata injection or rejected-
  value logging.
  Add a safe handling example/table that uses only
  `AuditLimitExceededError.field_category` and `.limit_name`, forbids message
  parsing and caller-value logging, and a bilingual helper example using both
  `make_audit_event` and `assert_audit_event_preserved` with an explicit
  “value assertion, not durable history” disclaimer.
  Embed `audit-contract-boundary.svg` with the PNG fallback in both package
  READMEs using paths that resolve from `packages/bluetape-audit/`; keep the
  root English and Korean references aligned to the identical SVG+PNG pair.

- [ ] **Step 4: Pin the diagram source model before drawing.** Reader question:
  “What does `bluetape.audit` own, and where does durability begin?” Kind:
  static flow-style architecture, not time-ordered sequence. Use
  `docs/images/readme-diagrams/value-packages-boundary.png` as the approved
  repo-local visual family. Model three horizontal ownership regions:
  caller serialization; bounded `bluetape.audit` values/validation; caller-
  owned storage/outbox/transport. Use text-only cards, four primary 14x14
  arrows, no infrastructure icon, and an ownership legend. Never label
  validation as recorded, committed, or delivered.
  Draw optional application prevalidation as a distinct dashed fast-fail path.
  In the caller-owned adapter region, show the authoritative call to
  `validate_audit_event` immediately before a labeled first-side-effect
  boundary; validation remains package code invoked under adapter ownership,
  while durability stays external. Require source/XPath and original-size PNG
  assertions for both placements.

- [ ] **Step 5: Create one SVG, then complete the one-asset loop.** Use
  `Architects Daughter` and `Comic Mono`, balanced margins, distinct light-theme
  cards, straight or rounded orthogonal routes, perpendicular endpoints,
  corner clearance, and no evidence text inside the image.

```bash
xmllint --noout docs/images/readme-diagrams/audit-contract-boundary.svg
cairosvg docs/images/readme-diagrams/audit-contract-boundary.svg \
  -o docs/images/readme-diagrams/audit-contract-boundary.png -s 2
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" \
  docs/images/readme-diagrams/audit-contract-boundary.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" \
  --fail-diagonal docs/images/readme-diagrams/audit-contract-boundary.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" \
  docs/images/readme-diagrams/audit-contract-boundary.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" \
  docs/images/readme-diagrams/audit-contract-boundary.svg
git diff --check -- docs/images/readme-diagrams/audit-contract-boundary.svg \
  docs/images/readme-diagrams/audit-contract-boundary.png
```

Expected: XML/render success, nonzero markers/connectors/cards/paths,
intrusions=0, crossings=0, geometry failures=0, endpoint failures=0, mixed-
corner failures=0. If a generic count is zero/WEAK, add targeted XPath proof
for three ownership regions, the package boundary, all cards, four connectors,
four primary arrowheads, and the legend.

- [ ] **Step 6: Inspect the final PNG at original size after the final coordinate
  change.** Verify readable labels, fonts, 14x14 solid heads, perpendicular
  endpoints, no clipping/crossing/card intrusion, clear ownership legend,
  balanced whitespace, and no implication of durability inside the package.
  Record dimensions, SHA-256 hashes, audit counts, XPath fallback counts,
  inspection notes, reference path, embed paths, and all DIA-01..08,
  DIA-COM-01..09, DIA-ARC-01..04 rows in the diagram review ledger. Icon row is
  N/A with text-only source evidence; review-page row is N/A only after proving
  no local review page exists.

- [ ] **Step 7: Run GREEN and locale/link checks.**

```bash
uv run pytest packages/bluetape/tests/test_audit_readmes.py -v
uv run pytest packages/bluetape-audit packages/bluetape/tests/test_audit_wheel_isolation.py packages/bluetape/tests/test_audit_readmes.py -v
git diff --check
```

- [ ] **Step 8: Commit docs and the completed visual loop together.**

Intent: `Explain where audit validation ends and caller ownership begins`

Rollback: revert docs, both asset forms, and diagram ledger together; never
leave an SVG-only or stale PNG embed.

## Task 8: Run full verification, six-lens review, verifier, and lesson gate

**Depends on:** Tasks 1-7 at one candidate head

**Files:**

- Create `docs/review/2026-07-16-issue-25-audit-contracts-tdd-evidence.md`
- Create `docs/review/2026-07-16-issue-25-audit-contracts-implementation-review.md`
- Create `docs/review/2026-07-16-issue-25-audit-contracts-verifier.md`
- Create `docs/lessons/2026-07-16-issue-25-audit-contracts.md`

- [ ] **Step 1: Render the TDD ledger.** For every behavior family record the
  exact RED command/failure reason, GREEN command/count, production commit, and
  refactor rerun. Missing or wrong-failure RED evidence blocks completion.
  Add a performance-proof row that ties source and tests to these bounded
  operations: payload construction performs exact-type check, `len()`, and
  identity retention without byte scanning; policy validation reads payload
  length without scanning bytes; metadata performs one shallow copy and one
  bounded validation pass over at most 64 entries; datetime equality builds a
  fixed scalar key. Record the focused/all-package build commands as packaging
  cost evidence and explicitly reject wall-clock microbenchmarks as noisy and
  unnecessary for these hard-bounded, non-I/O operations.

- [ ] **Step 2: Finish repository-owned evidence before the exact-head gate.**
  Write the required Type A lesson, the implementation-review ledger with all
  pre-head findings and repairs, and the verifier checklist with acceptance-
  criterion/source/test mappings. The lesson records why values-first, exact
  built-ins, private-copy validation, strict-only limits, structural time
  equality, adapter-owned durability, safe error attributes, isolated wheels,
  and PNG-authoritative review are reusable, plus the rejected repository,
  history, JSON, and global-context scope. These files must contain no claim
  that a final exact-head review has already passed.

- [ ] **Step 3: Commit every repository-owned evidence and lesson artifact.**

Intent: `Preserve audit delivery evidence for future adapters`

After this commit, record its SHA as the candidate exact head. Do not mutate
the worktree while Steps 4-6 run. Any correction or evidence-file edit creates
a new head and restarts Step 4.

- [ ] **Step 4: Run the fresh canonical validation set sequentially at that
  exact committed head.**

```bash
uv sync --all-packages --all-extras --python 3.13.14 --locked
uv run pytest packages/bluetape-audit packages/bluetape/tests/test_audit_wheel_isolation.py packages/bluetape/tests/test_audit_readmes.py packages/bluetape-benchmark/tests/test_benchmark_packaging.py
uv run ruff check .
uv run ruff format --check .
uv run pytest -m 'not observability_sdk and not observability_workspace'
uv build --all-packages
uv lock --check
actionlint
git diff --check
```

Expected: all focused and canonical tests pass, Ruff/format/build/lock/actionlint/
diff checks exit zero, and no ignored marker beyond the documented existing
observability groups is used to hide an audit failure. Confirm the worktree is
clean and `HEAD` is unchanged after the commands.

- [ ] **Step 5: Run six independent implemented-diff perspectives at the same
  exact head.** Use fresh
  agents for performance, stability/reliability, security/privacy,
  operator/Ops, developer/public API, and user/caller. Each is read-only,
  receives the immutable base/head range, spec, plan, test outputs, and diagram
  ledger, and reports P0-P3 evidence. The main session normalizes and repairs.
  Rerun only affected lenses until every final perspective reports P0=0/P1=0.
  Record final SHA, role/lens, counts, and evidence refs in the active
  `.bluetape` workflow receipt and later PR body, not in another repository
  commit.

- [ ] **Step 6: Run an independent verifier at that unchanged head.** Prove every
  acceptance criterion, exact exports/signatures, no forbidden public/storage
  symbols, wheel isolation, docs parity, visual evidence, test counts, commit
  provenance, and current diff hygiene. Any correction changes the head and
  invalidates canonical validation and every review/verifier result. Record the
  unchanged final SHA and verdict in the active workflow receipt and PR body;
  do not create a post-verification commit.

Rollback: any code/doc correction after this commit requires refreshing the
affected ledger, reviews, verifier, and lesson references at the new head.

## Task 9: Create the exact-head PR and verify GitHub gates

**Depends on:** Task 8, clean worktree, local review P0=0/P1=0

- [ ] **Step 1: Confirm local branch and commit provenance.** Require current
  branch `feat/issue-25-audit-contracts`. Run `git fetch --prune origin`, set
  `BASE_SHA=$(git merge-base origin/develop HEAD)` and
  `HEAD_SHA=$(git rev-parse HEAD)`, and run
  `git diff --check "$BASE_SHA" "$HEAD_SHA"`. Require only approved paths,
  Lore-compliant commits, and a clean worktree; plain `git diff --check` after
  commit is not accepted as committed-range evidence.

- [ ] **Step 2: Push without force and create the approved PR.** Target
  `bluetape4k/bluetape-py`, base `develop`, head
  `feat/issue-25-audit-contracts`. The English body links issue #25, spec/plan,
  test and wheel evidence, diagram, reviews, verifier, lesson, and known N/A
  rows; it ends with the workflow-required `## DoD Status` section.

- [ ] **Step 3: Verify exact remote head and GitHub state.** Local head,
  `origin/feat/issue-25-audit-contracts`, and PR head must be identical. Check
  CI, reviews, unresolved threads, mergeability, issue linkage, and human-review
  artifact applicability at that exact SHA. Before reporting merge-ready,
  fetch/prune again, recompute base/head SHAs, and rerun the committed-range
  `git diff --check`; any changed base or head invalidates stale evidence. Do
  not enable auto-merge.

- [ ] **Step 4: Report merge-ready evidence and stop.** Obtain a fresh explicit
  user approval before rebase merge. Earlier spec, plan, implementation, or PR
  authority never counts as merge approval.

## Rollback Matrix

| Failure surface | Rollback action |
|---|---|
| Package registration/lock | Revert Task 1 registration and rerun `uv lock`; remove all dependent tasks |
| Identity/payload/limits | Revert Task 2; keep error-only scaffold |
| Event snapshot/time | Revert Task 3; do not expose `AuditEvent` |
| Explicit validation | Revert Task 4; remove adapter-policy claims |
| Testing helpers | Revert Task 5; production values remain |
| Wheel isolation | Reconcile meta/workspace/lock and rerun all three environments before retaining install claims |
| Docs/diagram | Revert README claims, SVG, PNG, and ledger as one unit |
| Review correction | Change code/docs first, then regenerate every affected exact-head evidence artifact |

Every rollback invalidates later task acceptance, lesson, PR body, and exact-
head claims until the relevant verification is rerun.

## Plan Completion Gate

- [ ] Every specification acceptance criterion maps to a task.
- [ ] Every production behavior begins with an intended RED failure.
- [ ] File names, exports, signatures, exception attributes, mismatch
      categories, commands, commit boundaries, and rollback scopes are exact.
- [ ] No repository/history/SQL/outbox/serializer/global context scope appears.
- [ ] Diagram common and architecture checklists are executable with concrete
      evidence requirements.
- [ ] Six independent plan perspectives and main-session self-review converge
      at P0=0/P1=0 before implementation approval is requested.
