# Issue #45 Strict Serde JSON Implementation Plan

Date: 2026-07-10
Status: Approved; Step 3-R reviewed, P0=0 P1=0; implementation in progress
Scope: issue #45, milestone `0.2.0`, `bluetape-serde`

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a dependency-free `bluetape-serde` distribution with immutable
payload contracts and a strict, bounded UTF-8 JSON bytes adapter.

**Architecture:** `bluetape.serde._contracts` owns immutable values, trust
profiles, stable error codes, and the normative error matrix.
`bluetape.serde._json` owns exact JSON-native graph validation, incremental
encoding, metadata enforcement, structural depth preflight, and strict decode.
The public `bluetape.serde` module re-exports only the reviewed surface; the
meta distribution exposes it through optional extras without changing the
core-only default.

**Tech Stack:** Python 3.13+, stdlib `dataclasses`, `enum`, `json`, `math`, and
`sys`; `uv`/`uv_build`; pytest; Ruff.

---

## Execution Constraints

- Apply `$bluetape-py-patterns` to every code, test, packaging, and public API
  task.
- Use strict TDD: add the smallest failing public-contract test, run it and
  observe the expected failure, implement the minimum behavior, then rerun the
  focused suite.
- No third-party dependency, registry, pickle, stream/file API, fallback,
  compression, encryption, Pydantic, or Fory implementation.
- No concurrency helper is applicable: the package is synchronous,
  deterministic, and owns no shared mutable state, thread, task, or resource.
- No README diagram task is required: the existing workspace topology does not
  change and the feature adds no visual architecture relationship.
- No CI YAML task is required: `.github/workflows/ci.yml` already runs
  `uv sync --all-packages`, Ruff, the full pytest suite, and
  `uv build --all-packages` without package-specific path filters.
- No `AGENTS.md` edit is required: repo guidance describes package boundaries
  generically and contains no enumerated module registry.

## File Structure

| Path | Responsibility |
| --- | --- |
| `packages/bluetape-serde/pyproject.toml` | Dependency-free distribution metadata and `bluetape.serde` module mapping. |
| `packages/bluetape-serde/src/bluetape/serde/__init__.py` | Exact reviewed public exports. |
| `packages/bluetape-serde/src/bluetape/serde/_contracts.py` | Trust enum, frozen payload values, error codes/classes/messages. |
| `packages/bluetape-serde/src/bluetape/serde/_json.py` | Strict graph validation, incremental encode, depth scan, strict decode. |
| `packages/bluetape-serde/tests/test_contracts.py` | Dataclass, metadata, ownership, enum, error matrix, and export tests. |
| `packages/bluetape-serde/tests/test_json.py` | Encode/decode, limits, metadata order, strictness, performance, and disclosure tests. |
| `packages/bluetape-serde/README.md` | English install, trust, limits, error, rollout, and usage contract. |
| `pyproject.toml`, `uv.lock` | Workspace dependency/source/member registration and locked resolution. |
| `packages/bluetape/pyproject.toml`, `packages/bluetape/README.md` | `serde`, `dev`, and `all` extras while preserving core-only default. |
| `README.md`, `README.ko.md` | Multilingual package status, install, usage, and documentation links. |
| `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md` | Package lifecycle, issue status, and user-facing change record. |
| `docs/review/2026-07-10-issue-45-serde-json-code-review.md` | Step 6-R convergence and verification evidence. |
| `docs/lessons/2026-07-10-issue-45-serde-json.md` | Durable error-context and strict-graph lessons before PR creation. |

## Task 1: Register the optional package boundary

**complexity:** low

**Files:**

- Create: `packages/bluetape-serde/pyproject.toml`
- Create: `packages/bluetape-serde/README.md`
- Create: `packages/bluetape-serde/src/bluetape/serde/__init__.py`
- Create: `packages/bluetape-serde/src/bluetape/serde/_contracts.py`
- Create: `packages/bluetape-serde/src/bluetape/serde/_json.py`
- Create: `packages/bluetape-serde/tests/test_contracts.py`
- Create: `packages/bluetape-serde/tests/test_json.py`
- Modify: `pyproject.toml`
- Modify: `packages/bluetape/pyproject.toml`
- Modify: `uv.lock`

**Current-code assumption:** package versions remain `0.1.0` in the source
workspace, matching newly added codec/compression distributions; milestone
`0.2.0` is planning scope, not an instruction to publish or retag packages.

- [ ] **Step 1: Create the minimal distribution scaffold**

Create `packages/bluetape-serde/pyproject.toml` with the exact boundary:

```toml
[project]
name = "bluetape-serde"
version = "0.1.0"
description = "Strict payload contracts and JSON serialization for bluetape-py."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.serde"
```

Create the three source modules with docstrings and an empty public `__all__`;
create empty test files so subsequent red tests have stable paths. Create a
minimal valid package README identifying the source-workspace/PyPI-hold status
so the declared build metadata resolves; Task 5 expands this same file. Do not
add behavior in this step.

- [ ] **Step 2: Register workspace and meta-package metadata**

Add `bluetape-serde==0.1.0` to root dependencies, add
`bluetape-serde = { workspace = true }` to both the root and meta-package
`[tool.uv.sources]`, and add `packages/bluetape-serde` to workspace members.
Add:

```toml
serde = ["bluetape-serde==0.1.0"]
```

to meta optional dependencies and add the same requirement to `dev` and `all`.
Keep meta default dependencies exactly:

```toml
dependencies = ["bluetape-core==0.1.0"]
```

- [ ] **Step 3: Resolve and verify the package boundary**

Run:

```bash
uv lock
uv sync --all-packages --locked
uv lock --check
uv run python -c "import bluetape.serde"
uv sync --project packages/bluetape --extra serde
```

Expected: resolution and placeholder import pass; no runtime dependency is
added to `bluetape-serde`.

- [ ] **Step 4: Commit the package boundary**

Commit with a Lore intent such as `build: isolate serde behind an optional
boundary`, including `Tested: uv lock --check; placeholder import`.

**Rollback point:** revert this commit if workspace resolution or meta default
dependencies differ from the expected core-only shape.

## Task 2: Implement immutable payload and error contracts with TDD

**complexity:** high

**Files:**

- Modify: `packages/bluetape-serde/tests/test_contracts.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/_contracts.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/__init__.py`

**Current-code assumption:** public errors follow the repository's
`ValueError`-based domain-error convention, while wrong Python runtime argument
types remain `TypeError`.

- [ ] **Step 1: Write failing trust, dataclass, and ownership tests**

Add tests equivalent to:

```python
from dataclasses import FrozenInstanceError

import pytest

from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile


def metadata(**overrides: object) -> PayloadMetadata:
    values = {
        "format": "json",
        "version": 1,
        "content_type": "application/json",
        "trust_profile": TrustProfile.UNTRUSTED,
    }
    values.update(overrides)
    return PayloadMetadata(**values)  # type: ignore[arg-type]


def test_payload_contracts_are_keyword_only_frozen_and_bytes_owned() -> None:
    contract = metadata()
    payload = SerializedPayload(metadata=contract, data=b"")

    assert payload.data == b""
    with pytest.raises(FrozenInstanceError):
        payload.data = b"changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        SerializedPayload(metadata=contract, data=bytearray())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        PayloadMetadata("json", 1, "application/json", TrustProfile.UNTRUSTED)  # type: ignore[misc]
```

Parametrize exact runtime type failures for `format`, `version` (including
`True`), `content_type`, `trust_profile`, `metadata`, and `data`. Parametrize
semantic failures for blank/uppercase/invalid format identifiers and version
zero/negative values. Assert `TrustProfile` is a `StrEnum` with values
`untrusted` and `trusted_internal`.

- [ ] **Step 2: Run the contract tests red**

Run:

```bash
uv run pytest packages/bluetape-serde/tests/test_contracts.py -q
```

Expected: import/export failures because the contract has not been implemented.

- [ ] **Step 3: Implement exact immutable values**

Implement the reviewed shape in `_contracts.py`:

```python
from dataclasses import dataclass
from enum import StrEnum

_FORMAT_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_./")


class TrustProfile(StrEnum):
    UNTRUSTED = "untrusted"
    TRUSTED_INTERNAL = "trusted_internal"


@dataclass(frozen=True, slots=True, kw_only=True)
class PayloadMetadata:
    format: str
    version: int
    content_type: str | None
    trust_profile: TrustProfile

    def __post_init__(self) -> None:
        if type(self.format) is not str:
            raise TypeError("format must be a string")
        if type(self.version) is not int:
            raise TypeError("version must be an integer")
        if self.content_type is not None and type(self.content_type) is not str:
            raise TypeError("content_type must be a string or None")
        if type(self.trust_profile) is not TrustProfile:
            raise TypeError("trust_profile must be a TrustProfile")
        if not 1 <= len(self.format) <= 64 or any(
            character not in _FORMAT_CHARACTERS for character in self.format
        ):
            raise InvalidMetadataError()
        if self.version <= 0:
            raise InvalidMetadataError()


@dataclass(frozen=True, slots=True, kw_only=True)
class SerializedPayload:
    metadata: PayloadMetadata
    data: bytes

    def __post_init__(self) -> None:
        if type(self.metadata) is not PayloadMetadata:
            raise TypeError("metadata must be PayloadMetadata")
        if type(self.data) is not bytes:
            raise TypeError("data must be bytes")
```

Keep content type generic at the envelope level; JSON-specific equality is
enforced in `_json.py`. Define `InvalidMetadataError` before dataclass runtime
construction. Use no regex or mutable module-global state.

- [ ] **Step 4: Write the failing normative error-matrix tests**

Parametrize every reviewed class/code/message row:

```python
@pytest.mark.parametrize(
    ("error_type", "code", "message"),
    [
        (PayloadLimitError, SerdeErrorCode.INPUT_LIMIT,
         "serialized payload exceeds max_input_size"),
        (PayloadLimitError, SerdeErrorCode.OUTPUT_LIMIT,
         "serialized output exceeds max_output_size"),
        (MalformedPayloadError, SerdeErrorCode.INVALID_UTF8,
         "payload is not valid UTF-8"),
        (SerdeEncodeError, SerdeErrorCode.CIRCULAR_REFERENCE,
         "value contains a circular reference"),
    ],
)
def test_variable_code_errors_use_the_fixed_matrix(error_type, code, message) -> None:
    error = error_type(code=code)

    assert error.code is code
    assert str(error) == message
    assert error.__cause__ is None
    assert error.__context__ is None
```

Expand the table to all spec rows. Test zero-argument fixed-code errors,
cross-class code rejection, keyword-only variable constructors, immutable
public `code`, and absence of arbitrary message/source/payload constructor
parameters.

- [ ] **Step 5: Implement the error matrix**

Implement `SerdeErrorCode`, the fixed message dictionary, `SerdeError`, five
fixed-code errors, and three restricted multi-code errors. The central pattern
is:

```python
class SerdeError(ValueError):
    __slots__ = ("_code",)

    def __init__(self, *, code: SerdeErrorCode) -> None:
        if type(code) is not SerdeErrorCode:
            raise TypeError("code must be SerdeErrorCode")
        self._code = code
        super().__init__(_ERROR_MESSAGES[code])

    @property
    def code(self) -> SerdeErrorCode:
        return self._code


class PayloadLimitError(SerdeError):
    _ALLOWED = frozenset(
        {
            SerdeErrorCode.INPUT_LIMIT,
            SerdeErrorCode.OUTPUT_LIMIT,
            SerdeErrorCode.NESTING_LIMIT,
        }
    )

    def __init__(self, *, code: SerdeErrorCode) -> None:
        if code not in self._ALLOWED:
            raise ValueError("code is not valid for PayloadLimitError")
        super().__init__(code=code)
```

Give fixed-code subclasses zero-argument constructors. Implement the complete
matrix exactly as the spec states; no error stores source exceptions, payload
bytes, decoded text, or custom messages.

- [ ] **Step 6: Export and verify the contract**

At this stage export and test exact ordered equality for contract-layer names
only: `PayloadMetadata`, `SerializedPayload`, `SerdeError`, `SerdeErrorCode`,
all eight concrete errors, and `TrustProfile`. Directly import every staged
name. Task 3 adds JSON constants, `JsonValue`, and `json_serialize`; Task 4
installs and verifies this complete final order:

```python
__all__ = [
    "DEFAULT_MAX_INPUT_SIZE",
    "DEFAULT_MAX_OUTPUT_SIZE",
    "DEFAULT_MAX_NESTING_DEPTH",
    "MAX_SUPPORTED_NESTING_DEPTH",
    "ContentTypeMismatchError",
    "FormatMismatchError",
    "InvalidMetadataError",
    "JsonValue",
    "MalformedPayloadError",
    "PayloadLimitError",
    "PayloadMetadata",
    "SerializedPayload",
    "SerdeError",
    "SerdeErrorCode",
    "SerdeEncodeError",
    "TrustProfile",
    "TrustProfileMismatchError",
    "UnsupportedVersionError",
    "json_deserialize",
    "json_serialize",
]
```

Do not create temporary placeholder JSON exports to satisfy this list. Run:

```bash
uv run pytest packages/bluetape-serde/tests/test_contracts.py -q
uv run ruff check packages/bluetape-serde
uv run ruff format --check packages/bluetape-serde
```

Expected: all contract tests and Ruff checks pass.

- [ ] **Step 7: Commit the contract**

Commit with Lore intent `feat: make serde trust and failures explicit` and
record the focused test command.

## Task 3: Implement bounded strict JSON encoding with TDD

**complexity:** high

**Files:**

- Modify: `packages/bluetape-serde/tests/test_json.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/_json.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/__init__.py`

**Current-code assumption:** JSON version 1 requires format `json`, content type
`application/json`, and either reviewed trust profile. The generic envelope may
represent other formats, but this adapter never accepts them.

Define and export the public alias and implement the exact encoder signature;
cover both with annotation, `inspect.signature`, keyword-only, and default-value
tests:

```python
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


def json_serialize(
    value: JsonValue,
    *,
    metadata: PayloadMetadata,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> SerializedPayload: ...
```

- [ ] **Step 1: Write failing encode success and metadata-order tests**

Add round-trip-ready encode tests for scalar/list/dict values, Unicode, both
trust profiles, deterministic compact UTF-8 output, and exact metadata
retention. Keep `b""` envelope ownership in Task 2 and its malformed-decode
meaning in Task 4. Parametrize adapter metadata failures and
assert validation order: format, content type, version. Test that metadata and
limit type/config failures happen before a generator/hostile value can be
traversed.

- [ ] **Step 2: Write failing strict graph tests**

Cover exact JSON-native values and reject:

```python
@pytest.mark.parametrize(
    "value,code",
    [
        ({1: "a"}, SerdeErrorCode.UNSUPPORTED_VALUE),
        ({1: "a", "1": "b"}, SerdeErrorCode.UNSUPPORTED_VALUE),
        ((1, 2), SerdeErrorCode.UNSUPPORTED_VALUE),
        (float("nan"), SerdeErrorCode.ENCODE_NON_FINITE_NUMBER),
        (float("inf"), SerdeErrorCode.ENCODE_NON_FINITE_NUMBER),
    ],
)
def test_json_serialize_rejects_non_native_or_ambiguous_values(value, code) -> None:
    with pytest.raises(SerdeEncodeError) as raised:
        json_serialize(value, metadata=JSON_METADATA)

    assert raised.value.code is code
```

Add circular-list/dict fixtures, repeated shared non-circular references,
depth exactly at/over configured limit, and unexpected encoder recursion
translation. Configured depth excess must be
`PayloadLimitError(NESTING_LIMIT)`, not `SerdeEncodeError`.

- [ ] **Step 3: Write failing incremental output-budget tests**

Test output at the limit and one byte over. Accept `sys.maxsize - 1` and reject
`sys.maxsize` as configuration before encoder construction. Monkeypatch module-local
`json.JSONEncoder` with an instrumented iterator that records chunk requests;
yield one accepted chunk, one over-budget chunk, then a sentinel chunk. Assert
`PayloadLimitError(OUTPUT_LIMIT)` and prove the sentinel chunk is never
requested. Also verify invalid limits (`True`, float, negative, `sys.maxsize`)
fail before encoder construction.

- [ ] **Step 4: Run encode tests red**

Run:

```bash
uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'serialize or encode'
```

Expected: missing `json_serialize` and constants.

- [ ] **Step 5: Implement config and adapter metadata validation**

Define:

```python
DEFAULT_MAX_INPUT_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_OUTPUT_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_NESTING_DEPTH = 100
MAX_SUPPORTED_NESTING_DEPTH = 256


def _validate_byte_limit(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value < sys.maxsize:
        raise ValueError(f"{name} is outside the supported range")
    return value


def _validate_depth_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("max_nesting_depth must be an integer")
    if not 0 <= value <= MAX_SUPPORTED_NESTING_DEPTH:
        raise ValueError("max_nesting_depth is outside the supported range")
    return value
```

Implement `_validate_json_metadata` in format/content/version order and return
the reviewed fixed errors. Validate all caller configuration before traversing
the value.

- [ ] **Step 6: Implement iterative JSON-native graph preflight**

Use iterator/cursor frames plus active container ids so the explicit stack and
active set retain only the current traversal path and remain O(depth), rather
than enqueueing all siblings. Scalars must be exact builtins; booleans are
checked before integers; floats must be finite; dict keys must be exact `str`;
tuples/subclasses/custom objects are rejected. On configured depth overflow
raise `PayloadLimitError(code=NESTING_LIMIT)`. Repeated shared references are
accepted after the first branch leaves the active set; cycles raise
`SerdeEncodeError(code=CIRCULAR_REFERENCE)`. Add a wide-container `tracemalloc`
regression showing preflight bookkeeping does not scale with sibling count.

- [ ] **Step 7: Implement incremental encoding without retained context**

Construct `json.JSONEncoder(ensure_ascii=False, allow_nan=False,
check_circular=True, separators=(",", ":"))`. Consume `iterencode()` one chunk
at a time. Translate encoder `TypeError` and `ValueError` to
`SerdeEncodeError(UNSUPPORTED_VALUE)` and `RecursionError` to
`SerdeEncodeError(ENCODE_RECURSION)`; circular input is classified by the
preflight, not by parsing exception text. Instrument each unexpected encoder
failure independently and assert its fixed class/code/message and empty
cause/context. Store the public replacement inside the handler, leave the
handler, and then raise it so `__context__` is `None`. UTF-8 encode each chunk,
check it against the remaining budget, append only accepted bytes, and never
request the next chunk after failure. Join accepted chunks only after the
iterator ends.

Return:

```python
SerializedPayload(metadata=metadata, data=b"".join(chunks))
```

- [ ] **Step 8: Run focused encode verification**

```bash
uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'serialize or encode'
uv run ruff check packages/bluetape-serde
uv run ruff format --check packages/bluetape-serde
```

Expected: encode tests pass, including operation-order and disclosure checks.

- [ ] **Step 9: Commit strict encoding**

Commit with Lore intent `feat: bound strict JSON encoding before assembly`.

## Task 4: Implement bounded strict JSON decoding with TDD

**complexity:** high

**Files:**

- Modify: `packages/bluetape-serde/tests/test_json.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/_json.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/__init__.py`

Implement the exact decoder signature and cover its annotations,
`inspect.signature`, keyword-only parameters, and default values:

```python
def json_deserialize(
    payload: SerializedPayload,
    *,
    expected_metadata: PayloadMetadata,
    max_input_size: int = DEFAULT_MAX_INPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> JsonValue: ...
```

- [ ] **Step 1: Write failing metadata and UTF-8 tests**

Construct `SerializedPayload` values whose format, content type, version, and
trust all differ; assert deterministic first-error order. Prove matching
expected/actual version `999` still raises `UnsupportedVersionError`. Assert
wrong payload/expected types and invalid limits fail before data access. Cover
invalid UTF-8 and empty bytes as `MalformedPayloadError` with codes
`INVALID_UTF8` and `INVALID_JSON` respectively. Test input exactly at the limit
and one byte over; the over-limit case must fail before UTF-8 conversion,
scanner, or parser invocation. At `max_input_size=0`, empty input reaches JSON
parsing and becomes `INVALID_JSON`, while any non-empty input is `INPUT_LIMIT`.
Accept `sys.maxsize - 1` and reject `sys.maxsize` as configuration.

- [ ] **Step 2: Write failing structural depth tests**

Test scalar JSON at depth zero, containers at exact/over limits, 256 accepted,
257 config rejected, and mixed bracket/escape fixtures:

```python
@pytest.mark.parametrize(
    "text",
    [
        '"{[]}"',
        '"escaped quote: \\\" ["',
        '"even slashes: \\\\"',
    ],
)
def test_depth_scan_ignores_structural_text_inside_strings(text: str) -> None:
    payload = SerializedPayload(metadata=JSON_METADATA, data=text.encode())
    assert json_deserialize(payload, expected_metadata=JSON_METADATA,
                            max_nesting_depth=0) == json.loads(text)
```

Add a near-configured-input-limit quoted bracket/backslash fixture to exercise
the one-pass scanner without regex, slicing, recursion, or backtracking. Add
explicit odd/even backslash-run cases before a quote, plus malformed inputs
whose unmatched leading `]` or `}` precedes over-limit nesting; those must still
fail with `NESTING_LIMIT` before the parser.

Add non-flaky allocation evidence around the module-local scanner: prebuild
materially different input sizes, start `tracemalloc` only for the scan, and
assert peak auxiliary allocation remains within a fixed small tolerance rather
than growing with input length. Pair it with an implementation/source audit
that the loop is one forward traversal and builds no input-sized collection.

- [ ] **Step 3: Write failing strict parse and disclosure tests**

Cover duplicate keys at root and nested objects, `NaN`, `Infinity`,
`-Infinity`, overflowing finite syntax (`1e309`, `-1e309`, and nested/object
variants), malformed syntax, parser `ValueError`, deep-parser `RecursionError`,
and both trust profiles. For every translated failure, including invalid UTF-8,
assert fixed code/message, payload marker absence, `__cause__ is None`, and
`__context__ is None`. Direct regressions must prove the underlying
`UnicodeDecodeError` bytes/decoder state and `JSONDecodeError.doc` are not
reachable through the public exception.

- [ ] **Step 4: Run decode tests red**

```bash
uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'deserialize or decode or depth'
```

Expected: missing strict decode behavior.

- [ ] **Step 5: Implement metadata and input gates**

Implement `json_deserialize` in this exact order:

1. Exact payload and expected-metadata runtime types.
2. Input/depth limit configuration.
3. Supported expected format/content/version.
4. Actual format, content type, version, and trust comparison.
5. Input byte length.
6. Strict UTF-8 conversion with context-free error translation.
7. Structural preflight.
8. Strict JSON parse.

Every mismatch uses its fixed concrete error and code.

- [ ] **Step 6: Implement one-pass structural preflight**

Use `in_string`, `escaped`, and integer `depth` state. On a quote outside a
string enter string state; inside a string, one backslash escapes exactly the
next character, which handles odd/even runs. Count `{`/`[` only outside strings;
on `}`/`]`, decrement only when depth is positive so an unmatched closer cannot
hide later depth.
Raise `PayloadLimitError(code=NESTING_LIMIT)` immediately above the configured
depth.

- [ ] **Step 7: Implement strict hooks and context-free translation**

Catch `UnicodeDecodeError` separately, create
`MalformedPayloadError(INVALID_UTF8)` inside the handler, and raise it only
after leaving the handler. Use an object-pairs hook with a local `set[str]` to
reject duplicate keys, a parse-constant hook to reject named non-finite values,
and a `parse_float` hook that constructs the float and rejects non-finite
overflow such as `1e309`. Catch private hook failures,
`json.JSONDecodeError`, parser `ValueError`, and `RecursionError`; create the
corresponding public error inside the handler, leave the handler, and raise it
afterward. Parser `ValueError` and decode recursion map to
`MalformedPayloadError(code=INVALID_JSON)`. Never retain a source exception or
decoded document.

- [ ] **Step 8: Run full serde verification**

Finalize `__all__` in the exact Task 2 order and assert ordered equality plus
direct importability of every exported name before running:

```bash
uv run pytest packages/bluetape-serde/tests -q
uv run ruff check packages/bluetape-serde
uv run ruff format --check packages/bluetape-serde
```

Expected: all contract and JSON tests pass.

- [ ] **Step 9: Commit strict decoding**

Commit with Lore intent `feat: reject ambiguous JSON before deserialization`.

## Task 5: Publish the source-workspace contract

**complexity:** medium

**Files:**

- Modify: `packages/bluetape-serde/README.md`
- Modify: `packages/bluetape/README.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write the package README**

Document the source-workspace/PyPI-hold status and label every install command
as currently runnable from the source workspace/local wheel set or available
only after publication. Cover direct/future-extra install,
exact import surface, version 1 metadata, 16 MiB/100 defaults, 256 hard depth
cap, `UNTRUSTED` recommendation, authenticated caller-owned policy, strict
key/nonfinite/duplicate/UTF-8 behavior, fixed error-code catches, reader-first
rollout/rollback, process-memory non-guarantee, non-goals, and #46 Fory handoff.
State that `TRUSTED_INTERNAL` is valid only for an authenticated and authorized
closed boundary; an internal network location or payload claim is insufficient,
and both profiles retain identical strict parsing and finite limits.

- [ ] **Step 2: Add import-backed safe-policy examples**

Show producer metadata and separately constructed consumer policy. Add an
import-backed two-profile example proving `TRUSTED_INTERNAL` does not disable
limits or strict parsing. Add a
failure example that catches `PayloadLimitError`, `MalformedPayloadError`, and
metadata mismatch errors by class/code; explicitly warn against using
`payload.metadata` as `expected_metadata`.

- [ ] **Step 3: Update multilingual root and meta docs**

Add `bluetape-serde` to English/Korean workspace tables, install commands,
focused package commands, usage, package documentation links, current status,
and strict-boundary caveats. Update meta README extra list. Keep the default
install statement core-only and identify Fory as planned follow-up, not current
behavior.

- [ ] **Step 4: Update lifecycle records**

Mark #45 implemented in WIP, add the distribution/import/extra to package
layout, and add an English `Unreleased / Added` CHANGELOG record. Do not edit
release/tag/PyPI policy because publishing is outside this issue.

Spell out the rollout contract: deploy version-1-capable readers first; isolate
old and new formats in a versioned namespace, topic, or explicit application
path; on rollback stop version-1 writes first; retain the previous reader/writer
until version-1 data drains, expires, or is explicitly migrated; treat an
unsupported version as a hard reject; and permit an explicitly configured older
reader only outside this package, never as implicit fallback.

- [ ] **Step 5: Verify and harden the durable Fory handoff**

Inspect live issue #46 and update it if required so the first Fory release—not
only a future untrusted mode—must reuse `PayloadMetadata` and
`SerializedPayload`, accept caller-owned trust policy, enforce finite byte,
depth, and reference limits, start as `TRUSTED_INTERNAL` only, use explicit
schema/type identifiers, prohibit payload-selected dynamic type loading, and
pass Python/Go/Rust/Kotlin conformance fixtures. Verify live assignee `debop`,
milestone `0.2.0`, and an explicit `Blocked by #45` dependency. Keep all public
issue text in English.

- [ ] **Step 6: Verify public claims against source**

Run literal searches for every documented class, enum value, constant, function,
extra, package name, trust warning, and each enumerated reader-first/rollback/no-
fallback statement. Execute README examples with `uv run python` or focused
pytest smoke tests. Run `git diff --check`.

- [ ] **Step 7: Commit documentation**

Commit with Lore intent `docs: make serde trust policy usable without fallback`.

## Task 6: Run release-quality local verification

**complexity:** high

**Files:**

- Modify if evidence requires a fix: files from Tasks 1-5 only

- [ ] **Step 1: Run deterministic validation in order**

```bash
uv lock --check
uv sync --all-packages --locked
uv run pytest packages/bluetape-serde/tests
uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'auxiliary_memory or linear_scan'
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
git diff develop...HEAD --check
```

Expected: all commands pass. If a command fails, diagnose the evidenced defect,
apply the smallest scoped fix, rerun the targeted failure, then restart this
matrix from `uv lock --check`.

- [ ] **Step 2: Inspect built wheel metadata**

Prove:

- `bluetape-serde` has no `Requires-Dist`.
- Meta default `Requires-Dist` is exactly `bluetape-core==0.1.0`.
- `bluetape-serde==0.1.0` appears only under `serde`, `dev`, and `all` markers.
- No serde requirement appears in unrelated extras.

- [ ] **Step 3: Run isolated wheel smokes**

In fresh temporary virtual environments:

1. Install the focused serde wheel and run a strict JSON round trip.
2. Install the meta wheel without extras and prove `bluetape-serde` is absent.
3. Install the meta wheel with the local `serde` extra/wheel set and prove
   `import bluetape.serde` plus a strict round trip succeeds.

Use temp directories and cleanup traps/context management; do not publish.

- [ ] **Step 4: Verify repository scope**

Inspect `git status -uall`, `git diff develop...HEAD`, public names in docs, and
the commit list. Exclude `.venv`, `dist`, caches, and unrelated files.

## Task 7: Close verifier, review, lesson, PR, and CI gates

**complexity:** high

**Files:**

- Create: `docs/review/2026-07-10-issue-45-serde-json-code-review.md`
- Create: `docs/lessons/2026-07-10-issue-45-serde-json.md`
- Modify if P0/P1 requires repair: scoped implementation/tests/docs only

- [ ] **Step 1: Run Step 5 verification against spec and plan**

Use the full-feature Step 5 verifier checklist. Map every spec acceptance item
to tests, source, package metadata, or docs. A `NEEDS_FIX` verdict returns to
the smallest Task 2-6 step, then reruns targeted tests and Task 6.

- [ ] **Step 2: Run Step 6 final checklist**

Verify Python tests, Ruff, lock/build, multilingual READMEs, actual public-name
claims, thin default, Lore commits, and clean scope. Kotlin/Go/Rust diagnostics,
Testcontainers, workflows/actionlint, diagrams, and concurrency helpers are N/A
with explicit reasons.

- [ ] **Step 3: Run Step 6-R six-lane code review**

Run fresh performance, stability, security, operator/Ops, developer/API, and
user/caller read-only lanes on `develop...HEAD`; integrate in the current
session. Fix every P0/P1, rerun targeted validation and affected lanes, and
record convergence only at `P0=0 P1=0`.

- [ ] **Step 4: Write and commit the lesson before PR**

Record why `raise ... from None` does not remove `__context__`, why strict JSON
encode must validate keys/value graph before stdlib coercion, and how to test
incremental output consumption. Include final verification evidence. Commit
with Lore trailers.

- [ ] **Step 5: Create the issue-linked PR**

Push the feature branch and create an English PR assigned to `debop`, targeting
`develop`, with issue/milestone #45/0.2.0 and relevant labels. The body must
contain `Closes #45`, background, solved risks, work, validation/review, and end
exactly with `## DoD Status`. Verify the live body with `gh pr view --json body`.

- [ ] **Step 6: Run post-PR review and CI gate**

Run the six PR perspectives plus main integration against the actual PR diff,
comments, and checks. Record both a PR comment and formal review. Fix/rerun any
P0/P1. After every push, record the PR's current `headRefOid`; watch required CI
and verify every required check/status-rollup result belongs to that exact SHA
before accepting only `SUCCESS` or `SKIPPED` conclusions.

- [ ] **Step 7: Deliver merge approval gate**

Produce the full Step 9 DoD table with issue, spec, plan, tests, reviews, CI,
lessons, and commit evidence. Request explicit merge approval; never merge
without it.

## Plan Self-Review

| Spec/DoD requirement | Plan coverage |
| --- | --- |
| Optional dependency-free distribution; core-only default | Tasks 1, 5, 6 |
| Exact immutable payload/trust/error contracts | Task 2 |
| Stable error class/code/message and no retained context | Tasks 2, 3, 4 |
| Version 1 and deterministic metadata/trust enforcement | Tasks 3, 4 |
| Strict exact JSON-native encode and no key coercion | Task 3 |
| Incremental bounded output and no later chunk consumption | Task 3 |
| UTF-8/input/depth/duplicate/nonfinite/malformed rejection | Task 4 |
| Linear string/escape-aware structural preflight | Task 4 |
| Authenticated expected policy and no trust elevation | Tasks 4, 5 |
| Reader-first rollout/rollback and Fory handoff | Task 5 |
| English/Korean docs and package lifecycle records | Task 5 |
| Full tests, Ruff, lock/build, metadata, isolated wheels | Task 6 |
| Step 5/6/6-R/7/7-P/7-R/8/9 gates | Task 7 |

No placeholders remain. Public type names, signatures, enum values, error codes,
messages, validation order, package paths, commands, and rollback points are
consistent with the reviewed spec.
