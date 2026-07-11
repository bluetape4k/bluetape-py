# Issue #46 Apache Fory Adapter Implementation Plan

Date: 2026-07-11
Status: Step 7-R reviewed — P0=0 P1=0; merge approval pending
Scope: `bluetape-serde[fory]`, Python/Go/Rust/Kotlin conformance, CI, and docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, bounded Apache Fory 1.3.0 xlang adapter and prove one
caller-selected schema bidirectionally across Python, Go, Rust, and Kotlin.

**Architecture:** Provider-independent errors remain in `bluetape.serde`, while
the optional provider surface lives in `bluetape.serde.fory` and imports
`pyfory` only when explicitly requested. One generic adapter owns one frozen
registration, a 20-byte `BTFY` envelope, a bounded semaphore in front of a
`ThreadSafeFory` pool, and exact metadata/type/body checks. A separate
conformance tree owns pinned producer CLIs, committed fixtures, the canonical
manifest, and artifact-based CI proof.

**Tech Stack:** CPython 3.13.14; `pyfory==1.3.0`; Python 3.13 generics,
dataclasses, `struct`, and `threading`; Go 1.26.5 with
`github.com/apache/fory/go/fory v1.3.0`; Rust 1.96.1 with `fory = "=1.3.0"`;
Eclipse Temurin 21.0.11+10, Kotlin 2.3.20, KSP 2.3.7, Gradle 9.6.0, and
`fory-kotlin`/`fory-kotlin-ksp` 1.3.0; pytest, Ruff, uv, and actionlint.

---

## Execution Constraints

- Apply `$bluetape-py-patterns` to Python code, tests, public API, packaging,
  and review. Apply `$bluetape-go-patterns` and `$bluetape-rs-patterns` to the
  conformance CLIs before editing those languages.
- Use strict TDD for every Python contract: write the smallest failing test,
  observe the expected failure, implement the minimum behavior, and rerun the
  focused test before broad verification.
- `bluetape-serde`, `bluetape[serde]`, `bluetape[dev]`, and `bluetape[all]`
  remain free of `pyfory`. Only `bluetape-serde[fory]` and `bluetape[fory]`
  install it.
- Fory is CPython 3.13-only at version 1.3.0. Base JSON tests and base-wheel
  smoke tests must continue to pass on CPython 3.14 without the provider.
- Do not expose a registry, default metadata, default adapter, dynamic payload
  dispatch, native/pickle mode, fallback codec, stream API, or nested
  application-class registration.
- Provider tests are synchronous and must use barriers/events rather than
  sleep-based timing. Keep heavy producer builds sequential within each job;
  do not run multiple Gradle invocations against the same project concurrently.
- The approved schema is varint: Python `pyfory.Int64`/`Int32`, plain Go
  `int64`/`int32`, plain Rust `i64`/`i32`, and plain Kotlin `Long`/`Int`.
  Do not add `Fixed*`, `@Fixed`, or `encoding = fixed` annotations.
- The canonical schema uses the same numeric field identities in every
  language: `record_id=1`, `name=2`, `active=3`, and `scores=4`. Use
  `pyfory.field(id=...)`, Go `fory:"id=N"` tags, Rust `#[fory(id = N)]`, and
  Kotlin `@ForyField(id = N)`; field names alone are not the cross-language
  identity contract.
- No README diagram is required: the workspace package topology does not
  change. The feature adds a provider adapter and conformance gate, not a new
  architectural layer.

## Step 3-P Risk Prediction

| Risk | Early signal | Mitigation and proof | Rollback or rerun point |
| --- | --- | --- | --- |
| Provider failure leaks sensitive caller/provider state through chained exceptions, tracebacks, or logs | marker text appears in `__cause__`, `__context__`, traceback locals, or `caplog` | Translate only at fresh public-error boundaries, delete sensitive locals, never parse provider text, and parameterize every gate/failure family | Revert the affected Task 3/4 error path and rerun the full provider failure-isolation subset before any later task |
| Semaphore/pool lifecycle leaks permits or reuses a poisoned runtime | post-failure calls time out, runtime count exceeds the bound, or runtime identity changes unexpectedly | Use `BoundedSemaphore` `try/finally`, public factory instrumentation, `max_concurrency=1` identity proof, and deterministic barriers/events | Revert the concurrency slice to the last green commit and rerun all Task 3/4 concurrency/reuse tests |
| Fory 1.3.0 cross-language metadata differs across implementations | fixture generation is nondeterministic or any peer rejects another producer's bytes | Pin all toolchains/dependencies, align numeric type/field IDs and varint encodings, generate twice in fresh processes, and require both directions | Keep the Python adapter but revert the failing producer task/fixture; do not create the canonical manifest or CI gate until all four peers pass |
| Optional dependency leaks into default/meta extras or unsupported CPython 3.14 | base environment imports `pyfory`, wheel metadata widens existing extras, or 3.14 resolves the provider | Pin the focused extra and CPython 3.13.14, inspect metadata, and test isolated local wheels plus base 3.14 import | Revert pyproject/lock changes and rerun Task 6 from the provider-free baseline |
| Artifact CI passes without proving the downloaded cross-language bytes/verifiers | final job recompiles instead of consuming artifacts, executable modes disappear, or manifest-only edits pass | Upload fixture, canonical producer fragment, deterministic tarred verifier, and checksums; final job downloads and verifies all artifacts | Disable/remove the new workflow, retain local fixture proof, repair Task 11, then rerun `actionlint` and artifact CI |
| Serialization hot path exceeds practical memory/latency despite byte limits | large/small RSS ratio, post-contention growth, or timing evidence regresses unexpectedly | Record isolated subprocess RSS/timing evidence without flaky absolute gates; document that byte bounds are not hard CPU/RSS isolation | Stop rollout, keep the extra opt-in and route disabled, then rerun Task 5/4-P with a narrowed hypothesis |

Risk gate: required because this work combines unsafe-deserialization boundaries,
concurrency/resource ownership, versioned external APIs, cross-language native
toolchains, packaging, and artifact CI. Each risk is assigned to its first
implementing task and blocks dependent tasks when its named signal appears.

## File Structure

| Path | Responsibility |
| --- | --- |
| `packages/bluetape-serde/src/bluetape/serde/_contracts.py` | Provider-independent Fory codes, fixed messages, and sealed error classes. |
| `packages/bluetape-serde/src/bluetape/serde/__init__.py` | Ordered base exports without importing `pyfory`. |
| `packages/bluetape-serde/src/bluetape/serde/fory.py` | Optional constants, registration/limit values, envelope, bounded pool, encode/decode. |
| `packages/bluetape-serde/tests/test_contracts.py` | Base error enum/class/message/export contract. |
| `packages/bluetape-serde/tests/test_fory.py` | Provider API, envelope, limits, security, concurrency, and failure-isolation tests. |
| `packages/bluetape-serde/tests/test_fory_performance.py` | Non-gating time/allocation/RSS observations. |
| `packages/bluetape-serde/conformance/fory/schema.json` | One canonical semantic schema/value and numeric identifiers. |
| `packages/bluetape-serde/conformance/fory/manifest.json` | Canonical producer runtime/version/path/SHA-256 record. |
| `packages/bluetape-serde/conformance/fory/fixtures/*.bin` | Full `BTFY` envelope fixtures for four producers. |
| `packages/bluetape-serde/conformance/fory/python/conformance_cli.py` | Python generate/verify CLI. |
| `packages/bluetape-serde/conformance/fory/go/` | Go module, lock checksum, and generate/verify CLI. |
| `packages/bluetape-serde/conformance/fory/rust/` | Rust crate, pinned toolchain/lock, and generate/verify CLI. |
| `packages/bluetape-serde/conformance/fory/kotlin/` | Kotlin/KSP Gradle application and pinned wrapper. |
| `packages/bluetape-serde/conformance/fory/verify_manifest.py` | Canonical manifest, SHA, artifact, and semantic verification. |
| `.python-version`, `uv.lock` | Exact Python/provider resolution. |
| `packages/bluetape-serde/pyproject.toml` | Direct `fory` extra. |
| `packages/bluetape/pyproject.toml` | Exact forwarding `fory` extra while `serde`/`dev`/`all` stay JSON-only. |
| `.github/workflows/fory-conformance.yml` | Path-gated four-producer artifact and final bidirectional gate. |
| `README.md`, `README.ko.md`, package READMEs | Install matrix, route-first usage, security, errors, and rollout. |
| `WIP.md`, `CHANGELOG.md`, `docs/package-layout.md` | Issue status and durable package policy. |
| `docs/review/2026-07-11-issue-46-apache-fory-*.md` | TDD, Step 6-R, and PR review evidence. |
| `docs/lessons/2026-07-11-issue-46-apache-fory.md` | Durable implementation/review lessons committed before PR. |

## Spec Coverage Map

| Approved requirement | Plan tasks |
| --- | --- |
| Provider-independent errors and base import isolation | 1, 2, 6 |
| Frozen registration/limits and one-adapter/one-schema API | 2, 3 |
| 20-byte envelope, exact metadata/type/body checks | 3, 4 |
| Bounded concurrency, failure cleanup, public Buffer consumption | 3, 4, 5 |
| CPython 3.13-only extra and thin meta/default installs | 2, 6 |
| Python/Go/Rust/Kotlin deterministic bidirectional fixtures | 7, 8, 9, 10 |
| Artifact-based path-gated CI under exact toolchains | 11 |
| Caller usage, security, rollout, rollback, and observability | 12 |
| Full verification, P0/P1 convergence, lessons, PR, CI, wiki | 13 |

## Task 1: Extend provider-independent error contracts

**Files:**

- Modify: `packages/bluetape-serde/tests/test_contracts.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/_contracts.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/__init__.py`

- [x] **Step 1: Write failing enum, message, class, and export tests**

Extend `ERROR_CASES`, exact enum-value assertions, and ordered public exports
with these six codes and four fixed classes:

```python
FORY_ERROR_CASES = [
    (SerdeErrorCode.SCHEMA_MISMATCH, "Fory schema does not match caller registration"),
    (SerdeErrorCode.TYPE_MISMATCH, "Fory type does not match caller registration"),
    (SerdeErrorCode.FORY_REGISTRATION, "Fory registration failed"),
    (SerdeErrorCode.INVALID_FORY, "payload is not valid Fory"),
    (SerdeErrorCode.FORY_ENCODE, "value cannot be encoded as registered Fory type"),
    (SerdeErrorCode.FORY_CONCURRENCY_LIMIT, "Fory adapter concurrency limit reached"),
]

FIXED_FORY_ERRORS = [
    (SchemaMismatchError, SerdeErrorCode.SCHEMA_MISMATCH),
    (TypeMismatchError, SerdeErrorCode.TYPE_MISMATCH),
    (ForyRegistrationError, SerdeErrorCode.FORY_REGISTRATION),
    (ForyConcurrencyError, SerdeErrorCode.FORY_CONCURRENCY_LIMIT),
]
```

Assert that `MalformedPayloadError` accepts only `INVALID_FORY` in addition to
its current codes, `SerdeEncodeError` accepts only `FORY_ENCODE` in addition to
its current codes, and all fixed classes reject positional/code overrides.

- [x] **Step 2: Run the contract test red**

Run:

```bash
uv run pytest packages/bluetape-serde/tests/test_contracts.py -q
```

Expected: collection/import failure for the new names.

- [x] **Step 3: Implement the exact base contract**

Add enum values/messages, update restricted `allowed_codes`, and implement
fixed constructors equivalent to:

```python
class SchemaMismatchError(SerdeError):
    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.SCHEMA_MISMATCH)


class TypeMismatchError(SerdeError):
    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.TYPE_MISMATCH)


class ForyRegistrationError(SerdeError):
    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.FORY_REGISTRATION)


class ForyConcurrencyError(SerdeError):
    def __init__(self) -> None:
        super().__init__(code=SerdeErrorCode.FORY_CONCURRENCY_LIMIT)
```

Re-export only provider-independent contracts from `bluetape.serde`. Do not
import `bluetape.serde.fory` from the base initializer.

- [x] **Step 4: Run focused tests green and commit**

Run the same focused test and expect all cases to pass. Commit:

```text
feat: make Fory failures stable without loading the provider

Constraint: bluetape.serde must import without pyfory
Confidence: high
Scope-risk: narrow
Tested: uv run pytest packages/bluetape-serde/tests/test_contracts.py -q
```

## Task 2: Add the optional provider boundary and frozen configuration

**Files:**

- Modify: `packages/bluetape-serde/pyproject.toml`
- Create: `packages/bluetape-serde/src/bluetape/serde/fory.py`
- Create: `packages/bluetape-serde/tests/test_fory.py`
- Create: `.python-version`
- Modify: `uv.lock`

- [x] **Step 1: Write failing optional-import and value-contract tests**

Under a CPython 3.13 provider environment, test constants and frozen/slotted/
keyword-only values:

```python
assert (FORY_FORMAT, FORY_VERSION, FORY_CONTENT_TYPE) == (
    "apache-fory-xlang",
    1,
    "application/x-apache-fory",
)

registration = ForyRegistration(
    python_type=ConformanceRecord,
    schema_id=0x42544659,
    schema_version=1,
    type_id=1001,
    logical_name="io.bluetape.serde.ConformanceRecord",
)
assert not hasattr(registration, "__dict__")
assert ForyLimits().reference_tracking is False
```

Parametrize exact-type failures (including `bool` for every integer), numeric
lower/upper boundaries, invalid logical names, average-schema count above the
per-type count, concurrency `0/65`, non-finite timeout, timeout outside
`0.001..60.0`, and `reference_tracking=True`.

Exercise the optional-import boundary in isolated subprocesses or with a
scoped import hook. Prove that only a direct `ModuleNotFoundError` whose
`name == "pyfory"` is replaced by the fixed installation guidance. A
transitive `ModuleNotFoundError` naming another module, provider ABI
`ImportError`/`OSError`, and provider initialization failure must retain their
original type and message and must not gain the missing-extra guidance.

- [x] **Step 2: Add the exact dependency and resolve the lock**

Add:

```toml
[project.optional-dependencies]
fory = ["pyfory==1.3.0"]
```

Create `.python-version` with exactly `3.13.14` before resolving or running any
provider-dependent task. Fail fast unless `python --version` under uv reports
`Python 3.13.14`.

Then run:

```bash
uv lock
uv sync --package bluetape-serde --extra fory --python 3.13.14 --locked
```

Expected: CPython 3.13.14 and `pyfory==1.3.0` resolve; no root/default
dependency gains `pyfory`.

- [x] **Step 3: Implement import isolation and immutable values**

At module import, catch only a direct missing provider:

```python
_missing_provider = False
try:
    import pyfory as _pyfory
except ModuleNotFoundError as error:
    if error.name != "pyfory":
        raise
    _missing_provider = True

if _missing_provider:
    raise ModuleNotFoundError(
        "Install bluetape-serde[fory] with CPython 3.13 to use Apache Fory.",
        name="pyfory",
    )
```

Delete the caught exception before the fresh raise. Implement
`ForyRegistration[T]` and `ForyLimits` as frozen, slotted, keyword-only
dataclasses with the exact ranges from the spec. Use a full-match ASCII logical
name check plus explicit leading/trailing/repeated-dot rejection.

- [x] **Step 4: Run provider tests green and commit**

Run:

```bash
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory.py -q
uv lock --check
```

Commit with intent `build: isolate Apache Fory behind its explicit extra` and
record both commands in `Tested:`.

## Task 3: Implement the envelope and serialization path with TDD

**Files:**

- Modify: `packages/bluetape-serde/tests/test_fory.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/fory.py`

- [x] **Step 1: Write failing construction and serialization tests**

Cover exact root type, subclass rejection, trusted metadata, eager registration
failure, fixed configuration, header bytes, IDs, big-endian body length,
round-trip body production, and total output limit. Use this canonical header:

```python
_ENVELOPE = struct.Struct(">4sBBIHII")
expected_header = _ENVELOPE.pack(
    b"BTFY", 1, 0, 0x42544659, 1, 1001, len(body)
)
assert payload.data[:20] == expected_header
```

Inject a provider factory that records constructor kwargs and registration
calls. Assert `xlang=True`, `strict=True`, `ref=False`, `compatible=False`, and
every upstream-supported metadata/depth limit.

- [x] **Step 2: Run serialization tests red**

Run the named serialization subset and expect missing adapter behavior:

```bash
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory.py -q -k 'construct or serialize or output'
```

- [x] **Step 3: Implement eager registration and bounded serialization**

Use a private provider factory so `ThreadSafeFory` never needs a mutable
post-construction registry:

```python
def _new_runtime(self) -> _pyfory.Fory:
    runtime = _pyfory.Fory(**self._provider_config)
    try:
        runtime.register(self.registration.python_type, type_id=self.registration.type_id)
    except (MemoryError, KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        raise _ForyRegistrationFailure from None
    return runtime
```

Call `_new_runtime()` once in the adapter constructor. Translate only
`_ForyRegistrationFailure` to a fresh `ForyRegistrationError` after leaving the
handler and clearing the sentinel. Apply the same translation if a later
`ThreadSafeFory` factory call raises `_ForyRegistrationFailure`; let provider
construction/fatal failures propagate. Discard the successful probe, then construct
`ThreadSafeFory(fory_factory=self._new_runtime)`. Guard every provider call with
`threading.BoundedSemaphore(max_concurrency)` and the configured timeout. After
a successful acquire, every factory, registration callback, encode, decode,
exact-consumption check, and type check must remain inside a `try/finally` whose
`finally` releases the permit.

Validate metadata and `type(value) is python_type` before provider access. Map
ordinary provider encode failure to a fresh `SerdeEncodeError(FORY_ENCODE)`;
never translate fatal exceptions. In the handler retain only the target public
error class and stable code; outside the handler delete `value`, partial body,
provider exception, and related locals before raising the fresh error. Require
exact `bytes`, enforce total
`20 + len(body) <= max_output_size`, and assemble one header plus body.

Test that encode failures disclose neither a caller marker nor provider
message, have no `__cause__`/`__context__`, expose no sensitive traceback
locals, and emit no library log records.

- [x] **Step 4: Verify serialization green and commit**

Run the focused subset, then the whole provider test file. Commit with intent
`feat: encode registered Fory values behind a bounded pool`.

## Task 4: Implement strict deserialization and failure isolation with TDD

**Files:**

- Modify: `packages/bluetape-serde/tests/test_fory.py`
- Modify: `packages/bluetape-serde/src/bluetape/serde/fory.py`

- [x] **Step 1: Write the ordered decode-gate tests**

Add named tests for:

- actual and expected metadata created independently but both `UNTRUSTED`, only
  actual metadata `UNTRUSTED`, and only expected metadata `UNTRUSTED`, all
  rejected with `TrustProfileMismatchError` before provider access;
- a caller policy fixture proving the expected metadata is never derived or
  copied from `payload.metadata`;
- total input over limit; header shorter than 20 bytes; wrong magic;
- envelope version, unknown flags, schema ID/version, type ID, and body length;
- empty/truncated/foreign body, Fory body with root OOB bit `0x02`, and valid
  root plus trailing byte;
- Fory root header with an unknown bit such as `0x04`, and a body whose xlang
  bit is disabled, both normalized to `INVALID_FORY` without provider-text
  matching;
- built-in root, subclass result, and exact registered result type;
- provider depth/type-metadata/schema-history `ValueError` mapping to
  `INVALID_FORY` without parsing provider text;
- provider error messages, payload markers, values, and traceback locals absent
  from fresh public errors;
- no library log records for import, encode, or decode failures;
- `MemoryError`, `KeyboardInterrupt`, and `SystemExit` propagated unchanged.

Use a spy factory to assert the provider is untouched for every envelope gate.

- [x] **Step 2: Run decode tests red**

```bash
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory.py -q -k 'deserialize or malformed or mismatch or trailing or out_of_band'
```

Expected: missing decode behavior.

- [x] **Step 3: Implement the ordered decode path**

Unpack only after metadata/input/header checks:

```python
magic, envelope_version, flags, schema_id, schema_version, type_id, body_length = (
    _ENVELOPE.unpack_from(data)
)
```

Reject mismatches in the spec order. Reject a zero-length body before reading
its first byte, then reject `body[0] & 0x02` before provider decode. Pass
`memoryview(data)[20:]` to public `_pyfory.Buffer`, call public
`ThreadSafeFory.deserialize(buffer)`, and require
`buffer.get_reader_index() == body_length`. Map every ordinary provider parse
or configured-limit exception to `MalformedPayloadError(INVALID_FORY)` and
require `type(result) is python_type`.

For every translated error, store only `(error class, stable code)`, leave the
provider handler, delete payload/body/result/provider locals, and raise a new
public error with no cause/context. Never use provider message matching.

Apply the same fresh-error boundary to every metadata/trust/input/header/schema/
type/body-length/OOB pre-provider rejection and semaphore-acquisition timeout:
internal helpers return only an error specification, then the public operation
deletes `value`, `payload`, `data`, body views, and other sensitive locals before
raising. Parameterize all pre-provider error families and
`ForyConcurrencyError` to prove caller markers are absent from library traceback
locals and that `__cause__`, `__context__`, and library log records are empty.

- [x] **Step 4: Add deterministic concurrency and reuse tests**

Use `threading.Barrier`, `threading.Event`, and `ThreadPoolExecutor` to prove:

- no more than `max_concurrency` pooled provider runtimes are created,
  excluding the discarded eager probe;
- a fifth blocked operation times out with `ForyConcurrencyError`;
- construction/registration failures never enter the pool;
- after the eager probe succeeds, a deterministic first lazy registration
  failure maps to `ForyRegistrationError`, does not pool that runtime, releases
  the semaphore permit, and allows the next factory attempt and operation to
  succeed;
- ordinary encode/decode failures return the provider-reset runtime, and the
  same pool remains usable for a subsequent valid operation;
- every construction, registration, encode, decode, exact-consumption, and
  type-check failure releases its semaphore permit, proven by completing
  `max_concurrency` subsequent valid calls without timeout;
- caller values are not mixed between concurrent operations.

Assert runtime creation count through the public
`ThreadSafeFory(fory_factory=counting_factory)` seam; never inspect `_pool`.
Count the discarded eager probe separately: retained pooled runtimes must be at
most `max_concurrency`, while total successful constructions may be at most
`max_concurrency + 1` including the probe.
For the failed-runtime reuse case, set `max_concurrency=1`, record runtime
identity in the public factory seam and provider method spy, and prove the exact
same reset instance handles the ordinary failure and subsequent success.

- [x] **Step 5: Run provider tests green and commit**

```bash
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory.py -q
```

Commit with intent `feat: reject untrusted Fory envelopes before reconstruction`.

## Task 5: Prove allocation and performance behavior without flaky gates

**Files:**

- Create: `packages/bluetape-serde/tests/test_fory_performance.py`
- Create: `docs/review/2026-07-11-issue-46-apache-fory-tdd-evidence.md`

- [x] **Step 1: Add non-absolute smoke measurements**

Measure 1000 warm serializations/deserializations with `timeit`, small/large
payload `tracemalloc` peaks, encoded sizes, and post-contention runtime reuse.
Run each native RSS high-water scenario (small, large, and post-contention) in
its own bounded subprocess using
`resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`; normalize Linux KiB and
macOS byte units before recording comparable byte values.

Assertions are structural only: correct results, output bounds, one adapter
construction reused across operations, and retained runtime count at or below
`max_concurrency`. Record timing/RSS as evidence; do not assert absolute
latency or RSS values.

- [x] **Step 2: Run and record evidence**

```bash
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory_performance.py -q -s
```

Write the command, environment, encoded sizes, ratios, and RSS observations to
the TDD evidence artifact. Commit with intent
`test: preserve bounded Fory allocation evidence`.

## Task 6: Complete packaging and wheel compatibility gates

**Files:**

- Modify: `packages/bluetape/pyproject.toml`
- Modify: `packages/bluetape-serde/tests/test_fory.py`
- Create: `packages/bluetape-serde/tests/test_fory_packaging.py`
- Modify: `uv.lock`

- [x] **Step 1: Add the forwarding extra without widening existing extras**

Add only:

```toml
fory = ["bluetape-serde[fory]==0.1.0"]
```

Keep `serde`, `dev`, and `all` entries exactly unchanged. Reassert that the
`.python-version` created in Task 2 is still exactly `3.13.14`.

- [x] **Step 2: Add subprocess/wheel tests**

Build focused `bluetape-serde` and `bluetape` wheels, then verify:

1. CPython 3.13 base wheel imports `bluetape.serde` and cannot import
   `bluetape.serde.fory` without the fixed missing-extra message.
2. CPython 3.13 wheel with `[fory]` imports and round-trips the canonical value.
3. CPython 3.14 base wheel installs/imports JSON successfully.
4. CPython 3.14 installation of the same local wheel with `[fory]` fails
   dependency resolution because `pyfory==1.3.0` has no compatible artifact.
5. `bluetape[serde]`, `[dev]`, and `[all]` metadata omit `pyfory`; only
   `bluetape[fory]` forwards the provider extra.
6. Build both local project wheels into one temporary wheelhouse, download the
   exact CPython 3.13.14 `pyfory==1.3.0` wheel and its locked transitive wheels
   into that wheelhouse, then create a seeded isolated environment and install
   `"bluetape[fory]"` with `--no-index --find-links "$wheelhouse"`. Prove the
   installed meta extra resolves the local `bluetape-serde` wheel and performs
   the canonical round-trip without contacting PyPI during installation.

- [x] **Step 3: Run packaging checks and commit**

```bash
uv lock --check
uv build --package bluetape-serde
uv build --package bluetape
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory_packaging.py -q
```

Commit with intent `build: forward Fory only through its explicit extras`.

## Task 7: Build the canonical Python conformance fixture

**Files:**

- Create: `packages/bluetape-serde/conformance/fory/schema.json`
- Create: `packages/bluetape-serde/conformance/fory/python/conformance_cli.py`
- Create: `packages/bluetape-serde/conformance/fory/verify_manifest.py`
- Create: `packages/bluetape-serde/conformance/fory/fixtures/python.bin`

- [x] **Step 1: Commit the exact schema source**

Use sorted canonical JSON with these values:

```json
{
  "application_type_id": 1001,
  "expected": {
    "active": true,
    "name": "blue",
    "record_id": 7,
    "scores": [1, 2, 3]
  },
  "fields": [
    {"id": 1, "name": "record_id", "type": "int64-varint"},
    {"id": 2, "name": "name", "type": "string"},
    {"id": 3, "name": "active", "type": "bool"},
    {"id": 4, "name": "scores", "type": "list<int32-varint>"}
  ],
  "fory_type_id": 1001,
  "logical_name": "io.bluetape.serde.ConformanceRecord",
  "schema_id": 1112819289,
  "schema_version": 1
}
```

Define the Python record with aligned field IDs and varint types:

```python
@dataclass
class ConformanceRecord:
    record_id: pyfory.Int64 = pyfory.field(id=1)
    name: str = pyfory.field(id=2)
    active: bool = pyfory.field(id=3)
    scores: list[pyfory.Int32] = pyfory.field(id=4)
```

`pyfory.Int64`/`Int32` are `VARINT64`/`VARINT32` in v1.3.0.

- [x] **Step 2: Implement Python `generate` and `verify` commands**

`generate OUTPUT` serializes through `ForyAdapter` and atomically writes the
full envelope. `verify INPUT` constructs an independent expected metadata value,
decodes, checks the exact dataclass value, and exits nonzero on trailing bytes,
wrong IDs, or semantic mismatch.

- [x] **Step 3: Implement canonical manifest verification**

`verify_manifest.py` accepts four producer paths plus manifest path, recomputes
SHA-256, validates sorted JSON/schema/toolchain/dependency fields, compares each
artifact byte-for-byte with the corresponding producer fixture, and invokes the Python
verifier for Go/Rust/Kotlin artifacts. Build and unit-test the validator here
with temporary complete inputs; do not create the canonical four-producer
manifest before all producer fixtures exist. `--write` is allowed only for
intentional fixture regeneration; ordinary CI verification writes temporary
outputs only.

- [x] **Step 4: Prove fresh-process determinism and commit**

Generate twice under `LC_ALL=C.UTF-8 TZ=UTC` into two temporary files, compare
them, then intentionally write only the canonical Python fixture. Commit with
intent `test: anchor Fory conformance in a canonical Python fixture`.

```bash
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
LC_ALL=C.UTF-8 TZ=UTC uv run --package bluetape-serde --extra fory --python 3.13.14 python python/conformance_cli.py generate "$tmpdir/python.first"
LC_ALL=C.UTF-8 TZ=UTC uv run --package bluetape-serde --extra fory --python 3.13.14 python python/conformance_cli.py generate "$tmpdir/python.second"
cmp "$tmpdir/python.first" "$tmpdir/python.second"
uv run --package bluetape-serde --extra fory --python 3.13.14 python python/conformance_cli.py verify "$tmpdir/python.first"
```

## Task 8: Add the Go producer and consumer

**Files:**

- Create: `packages/bluetape-serde/conformance/fory/go/go.mod`
- Create: `packages/bluetape-serde/conformance/fory/go/go.sum`
- Create: `packages/bluetape-serde/conformance/fory/go/main.go`
- Create: `packages/bluetape-serde/conformance/fory/fixtures/go.bin`

- [x] **Step 1: Pin and implement the Go CLI**

Pin `go 1.26.5` and `github.com/apache/fory/go/fory v1.3.0`. Use plain varint
fields—no fixed tags:

```go
type ConformanceRecord struct {
    RecordID int64   `fory:"id=1"`
    Name     string  `fory:"id=2"`
    Active   bool    `fory:"id=3"`
    Scores   []int32 `fory:"id=4"`
}

f := fory.New(
    fory.WithXlang(true),
    fory.WithTrackRef(false),
    fory.WithCompatible(false),
    fory.WithMaxDepth(64),
    fory.WithMaxTypeFields(256),
    fory.WithMaxTypeMetaBytes(4096),
    fory.WithMaxSchemaVersionsPerType(8),
    fory.WithMaxAverageSchemaVersionsPerType(2),
)
if err := f.RegisterStruct(ConformanceRecord{}, uint32(1001)); err != nil {
    return err
}
```

`generate OUTPUT` calls `Serialize(&value)`, copies the reusable returned slice,
adds the exact 20-byte envelope with `encoding/binary.BigEndian`, and writes it.
`verify INPUT` validates/strips the envelope and calls
`Deserialize(body, &result)` before exact semantic comparison.

- [x] **Step 2: Prove both directions and commit**

```bash
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
LC_ALL=C.UTF-8 TZ=UTC go run . generate "$tmpdir/go.first"
LC_ALL=C.UTF-8 TZ=UTC go run . generate "$tmpdir/go.second"
cmp "$tmpdir/go.first" "$tmpdir/go.second"
go run . verify ../fixtures/python.bin
uv run --package bluetape-serde --extra fory --python 3.13.14 python ../python/conformance_cli.py verify "$tmpdir/go.first"
```

Promote the verified first output to `fixtures/go.bin`. Use temporary partial
metadata only for local checks; do not create or update the canonical manifest
yet. Commit with intent `test: prove Go Fory exchange against Python`.

## Task 9: Add the Rust producer and consumer

**Files:**

- Create: `packages/bluetape-serde/conformance/fory/rust/Cargo.toml`
- Create: `packages/bluetape-serde/conformance/fory/rust/Cargo.lock`
- Create: `packages/bluetape-serde/conformance/fory/rust/rust-toolchain.toml`
- Create: `packages/bluetape-serde/conformance/fory/rust/src/main.rs`
- Create: `packages/bluetape-serde/conformance/fory/fixtures/rust.bin`

- [x] **Step 1: Pin and implement the Rust CLI**

Use edition 2021, `rust-version = "1.96.1"`, and
`fory = { version = "=1.3.0", default-features = false }`. Use the approved
varint fields without fixed annotations:

```rust
#[derive(ForyStruct, Debug, PartialEq)]
#[fory(evolving = false)]
struct ConformanceRecord {
    #[fory(id = 1)]
    record_id: i64,
    #[fory(id = 2)]
    name: String,
    #[fory(id = 3)]
    active: bool,
    #[fory(id = 4)]
    scores: Vec<i32>,
}

let mut fory = Fory::builder()
    .xlang(true)
    .compatible(false)
    .track_ref(false)
    .build();
fory.register::<ConformanceRecord>(1001)?;
```

`generate` uses `serialize_to`; `verify` uses `Reader::new(body)`,
`deserialize_from`, and `reader.get_cursor() == body.len()` so release builds
reject trailing bytes. Build/validate the outer envelope separately.

- [x] **Step 2: Prove both directions and commit**

Run two fresh processes, compare their outputs, and verify both directions:

```bash
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
LC_ALL=C.UTF-8 TZ=UTC cargo run --locked --release -- generate "$tmpdir/rust.first"
LC_ALL=C.UTF-8 TZ=UTC cargo run --locked --release -- generate "$tmpdir/rust.second"
cmp "$tmpdir/rust.first" "$tmpdir/rust.second"
cargo run --locked --release -- verify ../fixtures/python.bin
uv run --package bluetape-serde --extra fory --python 3.13.14 python ../python/conformance_cli.py verify "$tmpdir/rust.first"
```

Update only the canonical Rust fixture and commit with intent
`test: prove Rust Fory exchange against Python`.

## Task 10: Add the Kotlin producer and consumer

**Files:**

- Create: `packages/bluetape-serde/conformance/fory/kotlin/settings.gradle.kts`
- Create: `packages/bluetape-serde/conformance/fory/kotlin/build.gradle.kts`
- Create: `packages/bluetape-serde/conformance/fory/kotlin/gradle/wrapper/*`
- Create: `packages/bluetape-serde/conformance/fory/kotlin/gradle.lockfile`
- Create: `packages/bluetape-serde/conformance/fory/kotlin/gradlew`
- Create: `packages/bluetape-serde/conformance/fory/kotlin/src/main/kotlin/io/bluetape/serde/conformance/ConformanceCli.kt`
- Create: `packages/bluetape-serde/conformance/fory/fixtures/kotlin.bin`
- Create: `packages/bluetape-serde/conformance/fory/manifest.json`

- [x] **Step 1: Pin Gradle, Kotlin, KSP, JDK, and Fory**

Use Kotlin `2.3.20`, KSP `2.3.7`, Java toolchain 21,
`fory-kotlin:1.3.0`, and `fory-kotlin-ksp:1.3.0`. The Gradle 9.6.0 wrapper must
contain:

```properties
distributionSha256Sum=bbaeb2fef8710818cf0e261201dab964c572f92b942812df0c3620d62a529a01
```

Verify the wrapper JAR SHA-256 is
`497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7`.
Enable `dependencyLocking { lockAllConfigurations() }`, generate
`gradle.lockfile` with `./gradlew dependencies --write-locks`, and require
ordinary builds to use the committed lock without rewriting it.

- [x] **Step 2: Implement the generated serializer and CLI**

Use plain varint `Long`/`Int`; do not use `@Fixed`:

```kotlin
@ForyStruct
data class ConformanceRecord(
    @ForyField(id = 1) val recordId: Long,
    @ForyField(id = 2) val name: String,
    @ForyField(id = 3) val active: Boolean,
    @ForyField(id = 4) val scores: List<Int>,
)

val fory = ForyKotlin.builder()
    .withXlang(true)
    .withCompatible(false)
    .requireClassRegistration(true)
    .withRefTracking(false)
    .withMaxDepth(64)
    .withMaxTypeFields(256)
    .withMaxTypeMetaBytes(4096)
    .withMaxSchemaVersionsPerType(8)
    .withMaxAverageSchemaVersionsPerType(2)
    .build()
    .also { it.register<ConformanceRecord>(1001L) }
```

`generate` wraps `fory.serialize(expected)` in the envelope. `verify` validates
and strips the envelope, calls typed `deserialize(body,
ConformanceRecord::class.java)`, and compares the exact value.

- [x] **Step 3: Prove both directions and commit**

Fail unless `$JAVA_HOME/bin/java -version` reports Temurin `21.0.11+10`, then
run two no-daemon processes with a fixed environment and distinct outputs:

```bash
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
LC_ALL=C.UTF-8 TZ=UTC ./gradlew --no-daemon run --args="generate $tmpdir/kotlin.first"
LC_ALL=C.UTF-8 TZ=UTC ./gradlew --no-daemon run --args="generate $tmpdir/kotlin.second"
cmp "$tmpdir/kotlin.first" "$tmpdir/kotlin.second"
LC_ALL=C.UTF-8 TZ=UTC ./gradlew --no-daemon run --args='verify ../fixtures/python.bin'
uv run --package bluetape-serde --extra fory --python 3.13.14 python ../python/conformance_cli.py verify "$tmpdir/kotlin.first"
```

Promote the verified fixture. Now that all four producer fixtures exist,
generate the canonical sorted manifest, run `verify_manifest.py` across all four
paths, and sign off its hashes/toolchain/dependency fields. Commit with intent
`test: prove Kotlin Fory exchange against Python`.

## Task 11: Add the artifact-based conformance workflow

**Files:**

- Create: `.github/workflows/fory-conformance.yml`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Add a path-gated least-privilege workflow**

Set `permissions: contents: read`; `pull_request` targeting `develop`;
`push.branches: [develop]`; and exact path filters covering `.python-version`,
`uv.lock`, serde source/tests/conformance, both serde and meta-package metadata,
and this workflow, plus:

```yaml
concurrency:
  group: fory-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Pin actions by full SHA:

```text
actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd
astral-sh/setup-uv@94527f2e458b27549849d47d273a16bec83a01e9
actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
actions/setup-go@924ae3a1cded613372ab5595356fb5720e22ba16
actions/setup-java@0f481fcb613427c0f801b606911222b5b6f3083a
actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830
gradle/actions/setup-gradle@4c125117fe7c5aed11272ec4213f602f012f89f2
actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0
```

- [x] **Step 2: Implement four producer jobs**

Use timeouts Python 10, Go 10, Rust 15, Kotlin 20 minutes. Install the exact
toolchain, print/fail on version drift, generate twice in separate processes,
compare temporary outputs, verify the opposite Python direction, and upload
the four exact artifact names `fory-${{ github.sha }}-python`,
`fory-${{ github.sha }}-go`, `fory-${{ github.sha }}-rust`, and
`fory-${{ github.sha }}-kotlin` with `retention-days: 7`.

The Go artifact also contains its Linux verifier binary, the Rust artifact its
release verifier binary, and the Kotlin artifact its `installDist` application.
Package each runnable verifier/distribution in a deterministic tar archive
before upload so executable modes survive the GitHub artifact boundary, emit a
SHA-256 file for each archive, and verify the checksum before extraction. This
lets the final job rerun consumers against the downloaded Python artifact
without recompiling all three languages.

Each producer job also emits and uploads one canonical machine-readable
manifest fragment containing producer name, observed runtime/toolchain version,
exact Fory dependency version, artifact-relative path, size, and SHA-256. The
final job must validate all four fragments against the committed canonical
manifest; console version output is diagnostic, not evidence.

Cache keys include runner OS, exact toolchain, Fory 1.3.0, and exact lock/build
hash inputs: Python `uv.lock`; Go `go.mod` and `go.sum`; Rust `Cargo.toml`,
`Cargo.lock`, and `rust-toolchain.toml`; Kotlin `settings.gradle.kts`,
`build.gradle.kts`, `gradle.lockfile`,
`gradle/wrapper/gradle-wrapper.properties`, and the wrapper JAR checksum.
Do not use broad restore-key prefixes across toolchain or lock changes. Restored
caches are accelerators only; locked resolution and explicit version checks
remain authoritative on every run.

- [x] **Step 3: Implement the final conformance job**

Use `needs: [python, go, rust, kotlin]`, timeout 15 minutes, set up CPython
3.13.14 and Temurin 21.0.11+10, and download the
four commit-SHA artifacts. Recompute hashes, byte-compare committed fixtures,
validate archive checksums before extracting the executable verifiers,
validate all producer fragments against the canonical manifest, have Python
verify downloaded Go/Rust/Kotlin,
and run the extracted Go/Rust/Kotlin verifier distributions against the
downloaded Python artifact. Assert the extracted Go/Rust binaries and Kotlin
launcher retain executable mode before invoking them.
Changing only `manifest.json` must fail.

- [x] **Step 4: Keep base CI provider-free, then run cheap fixture gates**

In the normal CPython 3.13.14 job, first assert `pyfory` is absent after the
ordinary workspace sync. Then explicitly sync `bluetape-serde[fory]`, verify
every committed fixture SHA/size against the canonical manifest, and have the
Python consumer decode all four fixtures. Keep compiler-heavy Go/Rust/Kotlin
generation in the path-gated conformance workflow. Then run:

```bash
actionlint
git diff --check
```

Commit with intent `ci: require four-language Fory artifact proof`.

## Task 12: Update user and project documentation

**Files:**

- Modify: `packages/bluetape-serde/README.md`
- Modify: `packages/bluetape/README.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/package-layout.md`

- [x] **Step 1: Document install and caller-owned routing**

Add the exact source, local-wheel, and future PyPI commands; CPython 3.13-only
provider boundary; base/serde/dev/all/fory matrix; and the complete independent
producer/consumer metadata example from the approved spec.

Define application ownership of `(schema_id, schema_version, type_id)`: one
version-controlled application manifest owns the tuple across all producers and
consumers, IDs are unique within that application's routing domain, and every
allocation/change requires compatibility review. Include the smallest complete
manifest example with logical name, Python type, tuple, route ID, and active
reader/writer versions.

Add install troubleshooting that distinguishes the fixed direct-missing-extra
message from transitive module, ABI `ImportError`/`OSError`, and provider
initialization failures. For the latter, instruct callers to verify exact
CPython `3.13.14`, the `pyfory==1.3.0` wheel tag/ABI and lock, recreate the
environment once, and escalate the original unchanged error instead of looping
on extra reinstallation.

- [x] **Step 2: Document security, errors, and operations**

Document trusted-internal-only use, exact root/schema/type checks, no nested
application classes, no payload-selected adapter, no fallback, resource-limit
scope, stable error actions, route-first rollout, canary thresholds, route ID
observability, write-stop rollback, and reader drain.

Define the observability boundary exactly. Allow only `operation`, stable error
code, envelope byte count, success/failure, latency, and fixed low-cardinality
route ID. Prohibit payload/body/value, provider exception text or traceback,
caller-supplied schema/type names, and unbounded/high-cardinality labels. When
route ID is unavailable, emit only the fixed safe fields to a distinct
metric/log stream owned by each versioned route; never combine versioned routes
in one unattributed aggregate or substitute payload-derived identity.

State that byte/depth/type-metadata/schema-history limits are acceptance bounds,
not CPU or RSS ceilings, and provider encode may allocate before the adapter can
reject oversized output. Applications needing hard CPU/RSS containment must run
Fory in a separately resource-limited process.

Make canary/rollback actionable: deployment owners set the observation window
and error/latency thresholds before activation; threshold breach automatically
stops Fory writes; the previous codec remains on a separate route with no codec
mixing; and Fory readers remain deployed until queue/cache TTL drain evidence is
complete.

State the fixed-schema migration rule: a field or type change creates a new
registration tuple and versioned route; deploy readers first, run old/new
adapters concurrently through the drain window, switch writers only after the
new read path is healthy, and retire the old route after evidence-backed drain.
Update package public-API/error tables and every fixed export/error-code count
for the new Fory contracts.

- [x] **Step 3: Update project status in both root locales**

Mark Issue #46 implemented in the source workspace but still subject to the
PyPI publication hold. Keep `README.md` and `README.ko.md` semantically aligned;
update package layout and changelog with the explicit extra and conformance gate.

- [x] **Step 4: Verify docs and commit**

Compare every command/API name against source, run `git diff --check`, and
commit with intent `docs: define safe Fory adoption and rollback`.

## Task 13: Run full verification, reviews, lessons, PR, and knowledge capture

**Files:**

- Create: `docs/review/2026-07-11-issue-46-apache-fory-code-review.md`
- Create: `docs/lessons/2026-07-11-issue-46-apache-fory.md`
- Update: `docs/superpowers/plans/2026-07-11-issue-46-apache-fory-implementation-plan.md`

- [x] **Step 1: Run focused and full local gates**

```bash
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_contracts.py packages/bluetape-serde/tests/test_fory.py packages/bluetape-serde/tests/test_fory_packaging.py -q
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest packages/bluetape-serde/tests/test_fory_performance.py -q -s
uv run --package bluetape-serde --extra fory --python 3.13.14 pytest
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
actionlint
git diff --check
git status --short
```

Run every Go/Rust/Kotlin fresh-process generation and bidirectional verifier,
then `verify_manifest.py` across all committed fixtures. Confirm `git status`
contains only the intentional tracked change set and no generated `.first`,
`.second`, build, wheelhouse, or verifier artifacts.

- [x] **Step 2: Run Step 5/6 verification and Step 6-R convergence**

Verify every spec DoD and plan checkbox with fresh evidence. Run six independent
performance, stability, security, operator, developer/API, and caller/user
reviews plus main-session integration. Fix and rerun affected lanes until
`P0=0 P1=0`; record P2/P3 decisions without expanding scope.

- [x] **Step 3: Commit lessons before PR**

Record root cause, varint annotation correction, provider exception-boundary
decision, public Buffer exact-consumption evidence, bounded-pool proof,
cross-language fixture results, review misses, and future guards. Commit with
intent `docs: preserve Apache Fory integration lessons`.

- [x] **Step 4: Create and verify the PR**

Push the feature branch, create an English PR assigned to `debop`, set milestone
`0.2.0`, copy relevant labels, and end the body with `## DoD Status`. Verify the
stored body, actual PR diff, formal Step 7-R review, and CI. Do not merge; deliver
the Step 9 DoD report and request user merge approval.

- [x] **Step 5: Preserve research and knowledge**

Write a copyright-safe Korean research note in
`/Users/debop/work/bluetape4k/bluetape4k-wiki/research/2026-07-11-apache-fory-1-3-xlang.md`
with official URLs, retrieval notes, varint mapping, install constraints, and
bluetape-py implications. Validate with `git diff --check`, `gno update`,
`gno embed --collection bluetape4k-wiki`, and representative `gno search`;
commit/push the wiki artifact as the durable research record.

## Plan Definition of Done

- [x] Every approved spec requirement maps to a task above.
- [x] The base serde contract imports and tests without `pyfory`.
- [x] The explicit provider extra passes all contract/security/concurrency tests on CPython 3.13.14.
- [x] CPython 3.14 base install succeeds and provider-extra resolution fails explicitly.
- [x] Python, Go, Rust, and Kotlin committed fixtures regenerate deterministically.
- [x] Bidirectional artifact verification passes under exact toolchain/dependency pins.
- [x] Ruff, full pytest, all-package build, actionlint, and diff checks pass.
- [x] README locale set, package docs, WIP, changelog, layout, review, and lessons are current.
- [x] Step 6-R and Step 7-R finish with P0=0 and P1=0.
- [x] PR/CI evidence is complete and merge remains user-approved only.
- [x] External research is preserved and indexed in `bluetape4k-wiki`.
