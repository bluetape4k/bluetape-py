# Issue #24 Observability Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the opt-in `bluetape-observability` distribution and three fail-safe OpenTelemetry adapters for the existing resilience and Redis observer events without widening the default `bluetape` install or transferring SDK/provider lifecycle ownership to Bluetape.

**Architecture:** The package depends only on `opentelemetry-api` at runtime, keeps domain imports behind `TYPE_CHECKING`, normalizes each event through a closed scalar allowlist before any emission, adds fixed events to the caller-owned current span, and independently records fixed counters/histograms through a constructor-cached `Meter`. The package owns no provider, exporter, span, worker, queue, context propagation, logging bridge, or shutdown lifecycle.

**Tech Stack:** Python 3.13.14, uv workspace/uv_build, OpenTelemetry API/SDK 1.43.x, pytest/pytest-asyncio, Ruff, GitHub Actions, `tracemalloc`, and repository-standard review/lesson gates.

---

## Approved Inputs and Stop Boundary

- Approved spec: `docs/superpowers/specs/2026-07-15-issue-24-observability-design.md`
- Target repository: `bluetape4k/bluetape-py`
- Base/head: `develop` / `feat/issue-24-observability`
- Distribution/import: `bluetape-observability==0.1.0` / `bluetape.observability`
- Runtime dependency: exactly `opentelemetry-api>=1.43,<2`
- Direct focused install only; do not add `bluetape[observability]` or change the default meta dependency.
- This plan authorizes local implementation, tests, documentation, commits, and review evidence after user approval. It does not authorize PR creation, merge, tag, release, publication, workflow dispatch, milestone closure, or destructive cleanup.

## Current-Code Anchors

- `PolicyEvent` and its closed enums live in `packages/bluetape-resilience/src/bluetape/resilience/_core.py`; the observer is an inline callable and ordinary observer errors currently propagate.
- `RedisEvent`, `RedisCoordinationEvent`, and their observer protocols live in `packages/bluetape-cache-redis/src/bluetape/cache/redis/_contracts.py`; sync and async producers share the same observer shapes.
- `packages/bluetape-benchmark/tests/test_benchmark_packaging.py` owns the fail-closed workspace `PUBLISHABLE | PRIVATE` equality proof and must be updated when the workspace member set changes.
- `.github/workflows/ci.yml` owns the generic provider-light test/build path and focused dependency jobs. Observability needs a dedicated job because the SDK is test-only and must not silently skip.
- `docs/release/pypi-preflight.md` is the public/private distribution classifier. `bluetape-observability` is publishable but is not retroactively added to the fixed `v0.1.0` target table.

## Step 3-P Risk Prediction

| Risk | Trigger | Prevention/proof | Rollback boundary |
|---|---|---|---|
| Sensitive or unbounded telemetry | A forged object, future event field, policy name, Redis data, logging context, or arbitrary value reaches the bridge | Closed enum sets, exact scalar checks, signed-64-bit bounds, finite-number checks, whole-event rejection before emission, and forbidden-value sentinel tests | Revert the owning adapter task; retain package scaffold and rerun hostile-input nodes |
| Domain behavior changes on telemetry failure | Current span, counter, histogram, or custom SDK raises | Catch ordinary `Exception` independently at each runtime interaction, propagate `BaseException`, and test later channels after earlier failures | Revert Tasks 2-4 together if shared isolation is wrong; rerun actual producer integration |
| Silent partial adapter setup | Meter acquisition or the second instrument creation fails | Constructor is fail-fast and stores no usable partial instance; setup exceptions are never caught | Revert the owning adapter constructor and rerun exact construction-order tests |
| Default install widens | Root meta metadata gains observability/OTel directly or through an extra | Parse metadata and isolated-wheel install; default wheel must remain core-only and OTel-free | Revert root metadata/lock/CI registration together and regenerate the lock |
| SDK tests silently skip | Generic workspace environment lacks `opentelemetry-sdk` | Dedicated `observability` CI job syncs `--group test`, imports SDK/domain test deps, and runs the SDK marker explicitly | Revert CI task only after restoring equivalent non-skipping evidence |
| Context semantics are overstated | Async, raw thread, executor, detached task, or logging context is assumed to propagate | Test ordinary sync/coroutine current-span attachment only; document unsupported boundaries and no bidirectional log/trace promotion | Revert docs and context test together; do not add implicit propagation |
| Hot-path overhead or retained state exceeds the approved budget | Repeated no-op/SDK calls allocate, retain, lock, queue, or exceed timing gates | Deterministic ownership/allocation tests plus three-run local benchmark evidence; two-of-three timing failures block Step 4-P | Optimize private helpers without changing public names; spec reapproval if budgets must change |
| Publish classifier drifts | New workspace member is omitted from release inventory | Update the single fail-closed classifier test and preflight list; unknown members fail | Revert package registration and classifier in one commit |

Risk gate is required because this change adds a public package, a new external runtime API dependency, synchronous hot-path adapters, privacy/cardinality rules, and setup/runtime failure boundaries.

## Exact Public and Recording Blueprint

The implementation must preserve these exact exports and signatures:

```python
# bluetape/observability/__init__.py
__all__: list[str] = []

# bluetape/observability/resilience.py
__all__ = ["OpenTelemetryPolicyObserver"]

class OpenTelemetryPolicyObserver:
    def __init__(self, *, meter: Meter | None = None) -> None: ...
    def __call__(self, event: PolicyEvent) -> None: ...

# bluetape/observability/redis.py
__all__ = ["OpenTelemetryRedisObserver", "OpenTelemetryRedisCoordinationObserver"]

class OpenTelemetryRedisObserver:
    def __init__(self, *, meter: Meter | None = None) -> None: ...
    def on_event(self, event: RedisEvent) -> None: ...

class OpenTelemetryRedisCoordinationObserver:
    def __init__(self, *, meter: Meter | None = None) -> None: ...
    def on_event(self, event: RedisCoordinationEvent) -> None: ...
```

The ellipses above document signatures only. Production commits may not contain `...`, `pass`, `TODO`, `NotImplementedError`, placeholder branches, or a universal event-dispatch facade.

Use these fixed setup calls and no alternatives:

```python
PACKAGE_VERSION = version("bluetape-observability")

def default_meter() -> Meter:
    return metrics.get_meter("bluetape.observability", PACKAGE_VERSION)

meter.create_counter(
    "bluetape.resilience.policy.events",
    unit="{event}",
    description="Number of observed Bluetape resilience policy events.",
)
meter.create_counter(
    "bluetape.redis.operations",
    unit="{operation}",
    description="Number of observed Bluetape Redis operations.",
)
meter.create_histogram(
    "bluetape.redis.operation.duration",
    unit="s",
    description="Duration of observed Bluetape Redis operations.",
)
meter.create_counter(
    "bluetape.redis.coordination.operations",
    unit="{operation}",
    description="Number of observed Bluetape Redis coordination operations.",
)
meter.create_histogram(
    "bluetape.redis.coordination.duration",
    unit="s",
    description="Duration of observed Bluetape Redis coordination operations.",
)
```

Private `_recording.py` uses only bounded helpers with these semantics:

```python
MAX_INT64 = 2**63 - 1

def closed_value(value: object, allowed: frozenset[str]) -> str:
    raw = value.value
    if type(raw) is not str or raw not in allowed:
        raise ValueError("unsupported enum value")
    return raw

def optional_closed_value(value: object | None, allowed: frozenset[str]) -> str | None:
    return None if value is None else closed_value(value, allowed)

def bounded_int(value: object, *, minimum: int) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INT64:
        raise ValueError("integer outside supported range")
    return value

def optional_bounded_int(value: object | None, *, minimum: int) -> int | None:
    return None if value is None else bounded_int(value, minimum=minimum)

def optional_non_negative_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("unsupported number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError("unsupported number")
    return normalized
```

Normalization catches `Exception` only at the adapter boundary and returns `None`; it validates every consumed field before any OTel interaction. Runtime helpers isolate `get_current_span`, `is_recording`, `add_event`, `Counter.add`, and `Histogram.record` independently and never catch `BaseException`.

Pin these v1 literal allowlists in production constants and tests; do not derive production
acceptance from domain enums at runtime:

```python
POLICY_TYPES = frozenset({"retry", "timeout", "circuit-breaker", "bulkhead"})
POLICY_EVENT_KINDS = frozenset(
    {
        "succeeded", "failed", "retry-scheduled", "timed-out",
        "circuit-transitioned", "admitted", "rejected",
    }
)
POLICY_OUTCOMES = frozenset({"success", "failure", "rejection"})
FAILURE_CATEGORIES = frozenset(
    {"none", "failure", "timeout", "retry-exhausted", "circuit-open", "bulkhead-rejected"}
)
CIRCUIT_STATES = frozenset({"closed", "open", "half-open"})
REDIS_MODES = frozenset({"sync", "async"})
REDIS_OPERATIONS = frozenset(
    {
        "create", "get", "set", "set-if-absent", "delete", "delete-if-value",
        "coordination-snapshot", "publish-if-value", "close",
    }
)
REDIS_OUTCOMES = frozenset({"success", "failure", "cancelled"})
REDIS_ERROR_CODES = frozenset(
    {"closed", "invalid-input", "connection", "timeout", "provider-failure", "invalid-response"}
)
COORDINATION_OPERATIONS = frozenset({"get-or-load"})
COORDINATION_OUTCOMES = frozenset(
    {"loaded", "result-reused", "lease-lost", "timeout", "failure", "cancelled"}
)
COORDINATION_ERROR_CODES = frozenset(
    {
        "attempts-exhausted", "polls-exhausted", "deadline-exceeded", "invalid-artifact",
        "provider-failure", "envelope-failure", "loader-failure",
    }
)
```

SDK-backed drift tests compare these constants with the current domain enum literal sets. A
future domain enum addition must fail that sentinel and trigger privacy/cardinality review; it
must never auto-expand the production allowlist.

## Complete Production-Code Blueprint

Implement Task 2's private module with these complete bodies (the pinned constants above live
in the same module):

```python
from __future__ import annotations

import math
from importlib.metadata import version
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Span

type Scalar = str | bool | int | float
type Attributes = dict[str, Scalar]

PACKAGE_VERSION = version("bluetape-observability")
MAX_INT64 = 2**63 - 1


def default_meter() -> Meter:
    return metrics.get_meter("bluetape.observability", PACKAGE_VERSION)


def closed_value(value: object, allowed: frozenset[str]) -> str:
    raw = value.value
    if type(raw) is not str or raw not in allowed:
        raise ValueError("unsupported enum value")
    return raw


def optional_closed_value(value: object | None, allowed: frozenset[str]) -> str | None:
    return None if value is None else closed_value(value, allowed)


def bounded_int(value: object, *, minimum: int) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INT64:
        raise ValueError("integer outside supported range")
    return value


def optional_bounded_int(value: object | None, *, minimum: int) -> int | None:
    return None if value is None else bounded_int(value, minimum=minimum)


def optional_non_negative_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("unsupported number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0:
        raise ValueError("unsupported number")
    return normalized


def exact_bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("unsupported boolean")
    return value


def recording_span() -> Span | None:
    try:
        span = trace.get_current_span()
    except Exception:
        return None
    try:
        return span if span.is_recording() else None
    except Exception:
        return None


def add_span_event(span: Span | None, name: str, attributes: Attributes) -> None:
    if span is None:
        return
    try:
        span.add_event(name, attributes)
    except Exception:
        return


def add_counter(counter: Counter, attributes: Attributes) -> None:
    try:
        counter.add(1, attributes)
    except Exception:
        return


def record_histogram(histogram: Histogram, value: float, attributes: Attributes) -> None:
    try:
        histogram.record(value, attributes)
    except Exception:
        return
```

Implement Task 3's public module atomically; there is no intermediate class with an empty
`__call__`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from bluetape.observability._recording import (
    CIRCUIT_STATES,
    FAILURE_CATEGORIES,
    POLICY_EVENT_KINDS,
    POLICY_OUTCOMES,
    POLICY_TYPES,
    Attributes,
    Scalar,
    add_counter,
    add_span_event,
    closed_value,
    default_meter,
    optional_bounded_int,
    optional_closed_value,
    optional_non_negative_float,
    recording_span,
)

if TYPE_CHECKING:
    from bluetape.resilience import PolicyEvent
    from opentelemetry.metrics import Meter

__all__ = ["OpenTelemetryPolicyObserver"]


def _normalize_policy(event: object) -> tuple[Attributes, tuple[tuple[str, Scalar | None], ...]]:
    policy_type = closed_value(event.policy_type, POLICY_TYPES)
    kind = closed_value(event.kind, POLICY_EVENT_KINDS)
    outcome = optional_closed_value(event.outcome, POLICY_OUTCOMES)
    failure = closed_value(event.failure_category, FAILURE_CATEGORIES)
    attempt = optional_bounded_int(event.attempt, minimum=1)
    delay = optional_non_negative_float(event.delay)
    timeout = optional_non_negative_float(event.timeout)
    state = optional_closed_value(event.state, CIRCUIT_STATES)
    previous_state = optional_closed_value(event.previous_state, CIRCUIT_STATES)
    in_flight = optional_bounded_int(event.in_flight, minimum=0)
    waiters = optional_bounded_int(event.waiters, minimum=0)

    metric: Attributes = {
        "bluetape.resilience.policy.type": policy_type,
        "bluetape.resilience.event.kind": kind,
        "bluetape.resilience.failure.category": failure,
    }
    if outcome is not None:
        metric["bluetape.resilience.outcome"] = outcome
    details = (
        ("bluetape.resilience.attempt", attempt),
        ("bluetape.resilience.delay", delay),
        ("bluetape.resilience.timeout", timeout),
        ("bluetape.resilience.state", state),
        ("bluetape.resilience.previous_state", previous_state),
        ("bluetape.resilience.in_flight", in_flight),
        ("bluetape.resilience.waiters", waiters),
    )
    return metric, details


class OpenTelemetryPolicyObserver:
    __slots__ = ("_counter",)

    def __init__(self, *, meter: Meter | None = None) -> None:
        selected = default_meter() if meter is None else meter
        self._counter = selected.create_counter(
            "bluetape.resilience.policy.events",
            unit="{event}",
            description="Number of observed Bluetape resilience policy events.",
        )

    def __call__(self, event: PolicyEvent) -> None:
        try:
            metric, details = _normalize_policy(event)
        except Exception:
            return
        span = recording_span()
        if span is not None:
            span_attributes = dict(metric)
            for key, value in details:
                if value is not None:
                    span_attributes[key] = value
            add_span_event(span, "bluetape.resilience.policy", span_attributes)
        add_counter(self._counter, metric)
```

Implement Task 4's public module atomically; keep the two normalizers and observer shapes
separate:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from bluetape.observability._recording import (
    COORDINATION_ERROR_CODES,
    COORDINATION_OPERATIONS,
    COORDINATION_OUTCOMES,
    REDIS_ERROR_CODES,
    REDIS_MODES,
    REDIS_OPERATIONS,
    REDIS_OUTCOMES,
    Attributes,
    add_counter,
    add_span_event,
    bounded_int,
    closed_value,
    default_meter,
    exact_bool,
    optional_closed_value,
    record_histogram,
    recording_span,
)

if TYPE_CHECKING:
    from bluetape.cache.redis import RedisCoordinationEvent, RedisEvent
    from opentelemetry.metrics import Meter

__all__ = [  # noqa: RUF022 - public order is an approved compatibility contract
    "OpenTelemetryRedisObserver",
    "OpenTelemetryRedisCoordinationObserver",
]


def _common(
    event: object,
    *,
    operations: frozenset[str],
    outcomes: frozenset[str],
    errors: frozenset[str],
) -> Attributes:
    attributes: Attributes = {
        "bluetape.redis.mode": closed_value(event.mode, REDIS_MODES),
        "bluetape.redis.operation": closed_value(event.operation, operations),
        "bluetape.redis.outcome": closed_value(event.outcome, outcomes),
    }
    error = optional_closed_value(event.error_code, errors)
    if error is not None:
        attributes["bluetape.redis.error.code"] = error
    return attributes


def _normalize_provider(event: object) -> tuple[Attributes, int]:
    metric = _common(
        event, operations=REDIS_OPERATIONS, outcomes=REDIS_OUTCOMES, errors=REDIS_ERROR_CODES
    )
    elapsed_ns = bounded_int(event.elapsed_ns, minimum=0)
    return metric, elapsed_ns


def _normalize_coordination(event: object) -> tuple[Attributes, int, int, int]:
    metric = _common(
        event,
        operations=COORDINATION_OPERATIONS,
        outcomes=COORDINATION_OUTCOMES,
        errors=COORDINATION_ERROR_CODES,
    )
    attempts = bounded_int(event.attempts, minimum=0)
    polls = bounded_int(event.polls, minimum=0)
    cleanup_failed = exact_bool(event.cleanup_failed)
    elapsed_ns = bounded_int(event.elapsed_ns, minimum=0)
    metric["bluetape.redis.coordination.cleanup_failed"] = cleanup_failed
    return metric, attempts, polls, elapsed_ns


class OpenTelemetryRedisObserver:
    __slots__ = ("_counter", "_histogram")

    def __init__(self, *, meter: Meter | None = None) -> None:
        selected = default_meter() if meter is None else meter
        self._counter = selected.create_counter(
            "bluetape.redis.operations",
            unit="{operation}",
            description="Number of observed Bluetape Redis operations.",
        )
        self._histogram = selected.create_histogram(
            "bluetape.redis.operation.duration",
            unit="s",
            description="Duration of observed Bluetape Redis operations.",
        )

    def on_event(self, event: RedisEvent) -> None:
        try:
            metric, elapsed_ns = _normalize_provider(event)
        except Exception:
            return
        span = recording_span()
        if span is not None:
            span_attributes = dict(metric)
            span_attributes["bluetape.redis.elapsed_ns"] = elapsed_ns
            add_span_event(span, "bluetape.redis.operation", span_attributes)
        add_counter(self._counter, metric)
        record_histogram(self._histogram, elapsed_ns / 1_000_000_000, metric)


class OpenTelemetryRedisCoordinationObserver:
    __slots__ = ("_counter", "_histogram")

    def __init__(self, *, meter: Meter | None = None) -> None:
        selected = default_meter() if meter is None else meter
        self._counter = selected.create_counter(
            "bluetape.redis.coordination.operations",
            unit="{operation}",
            description="Number of observed Bluetape Redis coordination operations.",
        )
        self._histogram = selected.create_histogram(
            "bluetape.redis.coordination.duration",
            unit="s",
            description="Duration of observed Bluetape Redis coordination operations.",
        )

    def on_event(self, event: RedisCoordinationEvent) -> None:
        try:
            metric, attempts, polls, elapsed_ns = _normalize_coordination(event)
        except Exception:
            return
        span = recording_span()
        if span is not None:
            span_attributes = dict(metric)
            span_attributes["bluetape.redis.coordination.attempts"] = attempts
            span_attributes["bluetape.redis.coordination.polls"] = polls
            span_attributes["bluetape.redis.elapsed_ns"] = elapsed_ns
            add_span_event(span, "bluetape.redis.coordination", span_attributes)
        add_counter(self._counter, metric)
        record_histogram(self._histogram, elapsed_ns / 1_000_000_000, metric)
```

Formatting may wrap the `_common` signature, but implementation must remain behaviorally exact.
Tests/fakes may use smaller helpers; production behavior may not omit or widen any branch above.

Use this complete API-only test-support module before writing adapter tests:

```python
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True, slots=True)
class EnumValue:
    value: object


class RecordingCounter:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.calls: list[tuple[int, dict[str, object]]] = []
        self.failure = failure
        self._lock = Lock()

    def add(self, amount: int, attributes: dict[str, object]) -> None:
        if self.failure is not None:
            raise self.failure
        with self._lock:
            self.calls.append((amount, dict(attributes)))


class RecordingHistogram:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.calls: list[tuple[float, dict[str, object]]] = []
        self.failure = failure
        self._lock = Lock()

    def record(self, amount: float, attributes: dict[str, object]) -> None:
        if self.failure is not None:
            raise self.failure
        with self._lock:
            self.calls.append((amount, dict(attributes)))


class RecordingMeter:
    def __init__(self, *, fail_at: int | None = None, failure: BaseException | None = None) -> None:
        self.calls: list[tuple[str, str, str, str]] = []
        self.instruments: list[RecordingCounter | RecordingHistogram] = []
        self.fail_at = fail_at
        self.failure = failure or RuntimeError("instrument setup")

    def _create(self, kind: str, name: str, unit: str, description: str):
        self.calls.append((kind, name, unit, description))
        if self.fail_at == len(self.calls):
            raise self.failure
        instrument = RecordingCounter() if kind == "counter" else RecordingHistogram()
        self.instruments.append(instrument)
        return instrument

    def create_counter(self, name: str, unit: str = "", description: str = ""):
        return self._create("counter", name, unit, description)

    def create_histogram(self, name: str, unit: str = "", description: str = ""):
        return self._create("histogram", name, unit, description)


class RecordingSpan:
    def __init__(
        self,
        *,
        recording: bool = True,
        is_recording_failure: BaseException | None = None,
        add_failure: BaseException | None = None,
    ) -> None:
        self.recording = recording
        self.is_recording_failure = is_recording_failure
        self.add_failure = add_failure
        self.events: list[tuple[str, dict[str, object]]] = []

    def is_recording(self) -> bool:
        if self.is_recording_failure is not None:
            raise self.is_recording_failure
        return self.recording

    def add_event(self, name: str, attributes: dict[str, object]) -> None:
        if self.add_failure is not None:
            raise self.add_failure
        self.events.append((name, dict(attributes)))


def policy_event(**overrides: Any) -> SimpleNamespace:
    values = {
        "policy_name": "must-never-be-read",
        "policy_type": EnumValue("retry"),
        "kind": EnumValue("succeeded"),
        "outcome": EnumValue("success"),
        "failure_category": EnumValue("none"),
        "attempt": 1,
        "delay": None,
        "timeout": None,
        "state": None,
        "previous_state": None,
        "in_flight": None,
        "waiters": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def redis_event(**overrides: Any) -> SimpleNamespace:
    values = {
        "mode": EnumValue("sync"),
        "operation": EnumValue("get"),
        "outcome": EnumValue("success"),
        "error_code": None,
        "elapsed_ns": 125_000_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def coordination_event(**overrides: Any) -> SimpleNamespace:
    values = {
        "mode": EnumValue("async"),
        "operation": EnumValue("get-or-load"),
        "outcome": EnumValue("loaded"),
        "error_code": None,
        "attempts": 1,
        "polls": 0,
        "cleanup_failed": False,
        "elapsed_ns": 250_000_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)
```

`Lock` above is deliberately test-owned and is used only for the application-owned executor
stress fixture; production ownership scans exclude `tests/_support.py`. Tests that need a
raising forbidden property or weak reference define a one-purpose local class at that node.

## Mandatory TDD Micro-Cycle

For every named behavior in Tasks 2-6:

- [ ] Add one deterministic test or one small parameterized family.
- [ ] Run its exact node ID and confirm RED is the intended missing contract/assertion, not collection, lock, interpreter, Docker, or network failure.
- [ ] Implement the smallest owning behavior.
- [ ] Re-run the exact node ID and then the owning test file; both must be GREEN.
- [ ] Record the RED/GREEN command and result for the final TDD evidence artifact; never reconstruct evidence from memory.

Each row below is one required 2-5 minute micro-cycle. Add the named test, run the exact
node, observe the stated RED, implement only the owning transition, and rerun the same node.
Parameterized cases stay under the stable parent node ID.

## Stable TDD Node Registry

| Task | Exact pytest node ID | Intended RED before implementation |
|---|---|---|
| 1 | `packages/bluetape-observability/tests/test_packaging.py::test_distribution_has_exact_metadata` | focused `pyproject.toml` missing |
| 1 | `packages/bluetape-observability/tests/test_packaging.py::test_workspace_registers_focused_distribution_once` | root dependency/source/member missing |
| 1 | `packages/bluetape-observability/tests/test_packaging.py::test_meta_distribution_has_no_observability_reference` | focused boundary not yet provable |
| 1 | `packages/bluetape-benchmark/tests/test_benchmark_packaging.py::test_every_workspace_distribution_is_publishable_or_private` | new publishable member unclassified |
| 2 | `packages/bluetape-observability/tests/test_recording.py::test_default_meter_uses_installed_distribution_scope` | `_recording`/`default_meter` missing |
| 2 | `packages/bluetape-observability/tests/test_recording.py::test_closed_values_are_exact_and_pinned` | scalar helpers missing |
| 2 | `packages/bluetape-observability/tests/test_recording.py::test_numeric_normalization_enforces_exact_bounds` | scalar helpers missing |
| 2 | `packages/bluetape-observability/tests/test_recording.py::test_current_span_steps_isolate_exception` | span helper missing |
| 2 | `packages/bluetape-observability/tests/test_recording.py::test_recording_calls_isolate_exception_and_propagate_base_exception` | signal wrappers missing |
| 3 | `packages/bluetape-observability/tests/test_public_api.py::test_policy_public_contract_and_setup` | resilience module/class missing |
| 3 | `packages/bluetape-observability/tests/test_resilience.py::test_policy_maps_exact_metric_and_span_attributes` | callable mapping missing |
| 3 | `packages/bluetape-observability/tests/test_resilience.py::test_policy_rejects_invalid_consumed_fields_before_emission` | closed normalization missing |
| 3 | `packages/bluetape-observability/tests/test_resilience.py::test_policy_never_reads_forbidden_fields` | privacy behavior missing |
| 3 | `packages/bluetape-observability/tests/test_resilience.py::test_policy_runtime_channels_are_independent` | runtime isolation missing |
| 3 | `packages/bluetape-observability/tests/test_resilience.py::test_policy_actual_retry_behavior_is_preserved` | domain integration missing |
| 4 | `packages/bluetape-observability/tests/test_public_api.py::test_redis_public_contract_and_setup` | Redis module/classes missing |
| 4 | `packages/bluetape-observability/tests/test_redis.py::test_provider_maps_exact_metric_and_span_attributes` | provider mapping missing |
| 4 | `packages/bluetape-observability/tests/test_redis.py::test_coordination_maps_exact_metric_and_span_attributes` | coordination mapping missing |
| 4 | `packages/bluetape-observability/tests/test_redis.py::test_redis_rejects_invalid_consumed_fields_before_emission` | closed normalization missing |
| 4 | `packages/bluetape-observability/tests/test_redis.py::test_redis_never_reads_forbidden_fields` | privacy behavior missing |
| 4 | `packages/bluetape-observability/tests/test_redis.py::test_redis_runtime_channels_are_independent` | counter/histogram isolation missing |
| 4 | `packages/bluetape-observability/tests/test_redis.py::test_actual_sync_and_async_provider_behavior_is_preserved` | protocol integration missing |
| 5 | `packages/bluetape-observability/tests/test_sdk_integration.py::test_sdk_records_exact_metrics_for_all_adapters` | SDK aggregation proof missing |
| 5 | `packages/bluetape-observability/tests/test_sdk_integration.py::test_sdk_adds_events_only_to_current_span` | current-span proof missing |
| 5 | `packages/bluetape-observability/tests/test_sdk_integration.py::test_same_adapter_isolates_concurrent_coroutine_contexts` | concurrent context proof missing |
| 5 | `packages/bluetape-observability/tests/test_sdk_integration.py::test_thread_pool_metrics_do_not_claim_context_propagation` | thread-boundary proof missing |
| 6 | `packages/bluetape-observability/tests/test_performance_contract.py::test_each_adapter_releases_event_reference` | retention proof missing |
| 6 | `packages/bluetape-observability/tests/test_performance_contract.py::test_each_adapter_retains_at_most_64_kib` | allocation proof missing |
| 6 | `packages/bluetape-observability/tests/test_performance_contract.py::test_package_owns_no_runtime_resource` | ownership proof missing |
| 6 | `packages/bluetape-observability/tests/test_performance_contract.py::test_benchmark_modes_repeat_without_resource_leak` | benchmark lifecycle proof missing |
| 7 | `packages/bluetape-observability/tests/test_readme_examples.py::test_package_readme_examples_are_source_equivalent` | locale snippets/docs missing |
| 7 | `packages/bluetape-observability/tests/test_readme_examples.py::test_api_only_example_executes_without_sdk` | API-only example missing |
| 7 | `packages/bluetape-observability/tests/test_readme_examples.py::test_composition_examples_pin_order_and_failure_policy` | migration guidance missing |
| 7 | `packages/bluetape-observability/tests/test_logging_separation.py::test_log_context_baggage_and_trace_ids_remain_separate` | executable separation proof missing |
| 7 | `packages/bluetape-observability/tests/test_packaging.py::test_ci_and_wheel_verifier_own_focused_gates` | CI/script registration missing |

The test body for each registry node must use these concrete inputs and GREEN assertions:

| Node suffix | Fixture/input | Required GREEN assertions |
|---|---|---|
| `distribution_has_exact_metadata` | parse focused TOML | exact name/version/Python/runtime dependency/test group/build module; no extras |
| `workspace_registers_focused_distribution_once` | parse root TOML/lock | dependency/source/member count is one; lock resolves OTel API in approved range |
| `meta_distribution_has_no_observability_reference` | parse meta TOML | default is core-only; no extra/dev/all observability or OTel entry |
| `every_workspace_distribution_is_publishable_or_private` | glob package TOMLs + preflight | equality/disjointness; observability publishable but absent from v0.1.0 target table |
| `default_meter_uses_installed_distribution_scope` | monkeypatch `metrics.get_meter`; sentinel meter | call exactly `("bluetape.observability", version(...))`; exact sentinel returned |
| `closed_values_are_exact_and_pinned` | allowed/unknown/raising `EnumValue` | exact allowed string returned; unknown/raising ordinary error reaches adapter rejection path; process-control exception propagates |
| `numeric_normalization_enforces_exact_bounds` | `True`, `-1`, `0`, `2**63-1`, `2**63`, NaN/inf | exact positive/non-negative boundaries accepted; bool/out-of-range/non-finite rejected |
| `current_span_steps_isolate_exception` | monkeypatched current span plus raising `RecordingSpan` | ordinary lookup/check failure returns no span; `BaseException` propagates |
| `recording_calls_isolate_exception_and_propagate_base_exception` | raising span/counter/histogram fakes | ordinary error returns; each process-control exception propagates at its exact call |
| `policy_public_contract_and_setup` | `inspect.signature`, `RecordingMeter` fail positions | exact `__all__`/annotations/keyword-only signature/counter descriptor; setup fails fast; new construction retries from call one |
| `policy_maps_exact_metric_and_span_attributes` | `policy_event` parameterized over pinned literals/optionals | exact event name/counter `1`/metric allowlist/span-only detail/omitted `None`; no duration |
| `policy_rejects_invalid_consumed_fields_before_emission` | one invalid consumed field per case | call returns `None`; span/counter logs remain empty; `BaseException` case propagates |
| `policy_never_reads_forbidden_fields` | local event whose `policy_name` and repr raise | valid metric/span emitted; raising fields untouched; sentinel absent from logs |
| `policy_runtime_channels_are_independent` | ordinary failure at lookup/check/add/counter | counter attempted after trace ordinary failures; counter failure does not escape; next event retries |
| `policy_actual_retry_behavior_is_preserved` | real success and exhausted `Retry` events | success result/exhausted error identity matches no-observer control; telemetry ordinary failures do not replace them |
| `redis_public_contract_and_setup` | signatures plus meter fail positions 1/2 for each class | exact exports/signatures/descriptors/order; fail-fast/no partial instance; clean new construction |
| `provider_maps_exact_metric_and_span_attributes` | `redis_event` all pinned literals, elapsed 125ms | exact provider event/counter/histogram 0.125s and allowlisted attrs only |
| `coordination_maps_exact_metric_and_span_attributes` | `coordination_event` all pinned literals | exact coordination event/counter/histogram 0.25s; cleanup metric attr; attempts/polls span-only |
| `redis_rejects_invalid_consumed_fields_before_emission` | unknown enums, bool/negative/int64 overflow, raising consumed property | no span/counter/histogram call for entire event; process-control exception propagates |
| `redis_never_reads_forbidden_fields` | local valid event with raising key/value/namespace/error/repr | signals emit exact allowlist and never access sentinel fields |
| `redis_runtime_channels_are_independent` | ordinary failure at every trace/counter/histogram call | later ordinary channels still attempted in order; next event retries; each `BaseException` propagates |
| `actual_sync_and_async_provider_behavior_is_preserved` | existing deterministic fake Redis clients + same adapter | sync/async return/error/cancellation matches recording-only controls; no Docker/network |
| `sdk_records_exact_metrics_for_all_adapters` | local reader/provider and real domain events | exact metric descriptors/data-point values/attributes; application teardown once |
| `sdk_adds_events_only_to_current_span` | local tracer/exporter, nested/sequential scopes | exact events attach only to current scope; no child span and no stale-span reuse |
| `same_adapter_isolates_concurrent_coroutine_contexts` | two task scopes with distinct spans/events | each exported span has only its own event/attributes; no cross-contamination |
| `thread_pool_metrics_do_not_claim_context_propagation` | context-managed executor + thread-safe meter fake | exact metric multiset/count; no trace assertion; all worker threads joined |
| `each_adapter_releases_event_reference` | weak-referenceable local event per adapter | weakref is dead after caller delete/GC; adapter slots hold instruments only |
| `each_adapter_retains_at_most_64_kib` | warmed 100k adapter vs empty-callback runs | isolated snapshot delta `<=64 KiB` independently for all three adapters |
| `package_owns_no_runtime_resource` | AST/source scan + before/after thread/task sets | no production lock/thread/task/queue/executor/registry/lifecycle method; sets reconcile |
| `benchmark_modes_repeat_without_resource_leak` | two subprocess executions per mode | valid JSON schema/sample counts; API uses no SDK; SDK teardown summaries; no residual process resource |
| `package_readme_examples_are_source_equivalent` | marker extraction from EN/KO | every named code block is byte-identical and compiles |
| `api_only_example_executes_without_sdk` | clean README wheel venv | exact snippet exits 0; SDK absent before/after; `uv pip check` passes |
| `composition_examples_pin_order_and_failure_policy` | execute callable/object examples with ordered recorders/failure | exact chosen order and failure behavior; replacement warning/restore path present in both locales |
| `log_context_baggage_and_trace_ids_remain_separate` | active baggage/log context/non-recording span + recording fakes/caplog | exact telemetry excludes log/baggage; log record excludes trace/span IDs; forbidden imports absent |
| `ci_and_wheel_verifier_own_focused_gates` | read CI/script/root markers | dedicated API/SDK/JUnit gates, strict markers, hash sync, temp cleanup, JSON summary, default/focused/README probes all present |

Run a node exactly as:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  '<node-id-from-table>' -q
```

Task 1 nodes run from the root environment before the package can be selected. Task 7's
`observability_workspace` node runs after the exact full-workspace sync. Expected RED may not
be an unrelated collection/environment error.

## Task 1: Register and isolate the focused distribution

**Complexity:** Medium  
**Depends on:** Approved plan only  
**Write scope:** Package scaffold, workspace metadata, lock, packaging tests  
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-observability/pyproject.toml`
- Create: `packages/bluetape-observability/README.md`
- Create: `packages/bluetape-observability/src/bluetape/observability/__init__.py`
- Create: `packages/bluetape-observability/tests/test_packaging.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`
- Modify: `docs/release/pypi-preflight.md`
- Inspect and modify only if its public-distribution enumeration is inconsistent: `docs/release/release-guide.md`

- [ ] Create `test_packaging.py` RED assertions for name/version/Python, exact runtime/test dependencies, `uv_build` module name, root dependency/source/member registration exactly once, no distribution extras, no meta default/extra/dev/all reference, no root convenience `bluetape/__init__.py`, and nested namespace importability.
- [ ] Extend the benchmark classifier RED set with `bluetape-observability`; assert every workspace distribution equals `PUBLISHABLE | PRIVATE`, the sets remain disjoint, and the preflight document names every member. Assert observability is absent from the historical `v0.1.0` target table.
- [ ] Run:

```bash
uv run pytest \
  packages/bluetape-observability/tests/test_packaging.py \
  packages/bluetape-benchmark/tests/test_benchmark_packaging.py -q
```

Expected RED: the focused metadata/directory and classifier registration do not exist.

- [ ] Add this exact focused metadata:

```toml
[project]
name = "bluetape-observability"
version = "0.1.0"
description = "OpenTelemetry adapters for Bluetape resilience and Redis observer events."
readme = "README.md"
requires-python = ">=3.13"
dependencies = ["opentelemetry-api>=1.43,<2"]

[dependency-groups]
test = [
    "bluetape-cache-redis==0.1.0",
    "bluetape-resilience==0.1.0",
    "opentelemetry-sdk>=1.43,<2",
    "pytest>=8.4.0",
    "pytest-asyncio>=1.1.0",
]

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.observability"
```

- [ ] Register `bluetape-observability==0.1.0` in root development dependencies, workspace sources, and members. Do not edit `packages/bluetape/pyproject.toml` except to repair a test-proven accidental reference. Update the publishable classifier and preflight list while preserving publication HOLD.
- [ ] Add the empty root `__all__` and a minimal focused README containing the direct-install/API-only ownership boundary so `uv_build` can resolve the declared readme. Task 7 expands it and adds the Korean twin. Run `uv lock`, then run the two packaging test files. Expected GREEN.
- [ ] Run `uv build --package bluetape-observability` and inspect wheel `METADATA`: exactly one runtime requirement range for `opentelemetry-api`, with test-group dependencies absent from `Requires-Dist`.
- [ ] Commit with Lore trailers:

```bash
git add pyproject.toml uv.lock docs/release packages/bluetape-benchmark/tests/test_benchmark_packaging.py packages/bluetape-observability
git commit -m "Establish an isolated observability package boundary" \
  -m "Constraint: The default bluetape distribution must remain core-only." \
  -m "Rejected: A root observability extra | Direct focused installation was approved." \
  -m "Confidence: high" -m "Scope-risk: moderate" \
  -m "Tested: Packaging classifier tests and focused wheel metadata build." \
  -m "Not-tested: Adapter runtime behavior is owned by later tasks."
```

Rollback/rerun: revert package metadata, root registration, classifier, preflight, and lock together; rerun `uv lock` and both classifier tests.

## Task 2: Implement bounded private recording primitives

**Complexity:** High  
**Depends on:** Task 1 package imports/builds  
**Write scope:** Private OTel helpers, bounded normalizers, and API-only recording fakes  
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-observability/src/bluetape/observability/_recording.py`
- Create: `packages/bluetape-observability/tests/_support.py`
- Create: `packages/bluetape-observability/tests/test_recording.py`

- [ ] Add RED tests for exact default `get_meter` arguments, every bounded scalar helper, current-span lookup/recording checks, independent span/counter/histogram runtime wrappers, and ordinary `Exception` isolation versus `BaseException` propagation. Public classes do not exist in this task; their constructor/signature/instrument setup tests and complete behavior are added atomically in Tasks 3 and 4.
- [ ] In `_support.py`, implement small recording fakes: `EnumValue`, `RecordingMeter`, `RecordingCounter`, `RecordingHistogram`, `RecordingSpan`, and raising variants. They must expose ordered call logs and never import SDK/domain packages.
- [ ] Add RED tests for all normalization primitives: closed values, optional values, bool rejection, signed-64-bit boundaries, positive attempt, non-negative counts, finite non-negative floats, raising `.value`, and `BaseException` propagation. Parameterize representative `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` across normalization and default meter acquisition; constructor instrument positions belong to the atomic public-class tests in Tasks 3 and 4.
- [ ] Implement `_recording.py` with `PACKAGE_VERSION`, `default_meter`, the exact bounded helpers above, and independent runtime helpers. Use `from __future__ import annotations`; import OTel API only. Do not add logging, callbacks, global provider setters, locks, registries, tasks, queues, caches, or mutable health fields.
- [ ] Add a source assertion that `_recording.py` imports only stdlib and OpenTelemetry API modules and owns no domain, SDK, logging, baggage, provider, exporter, worker, queue, or lifecycle import.
- [ ] Run:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  packages/bluetape-observability/tests/test_recording.py -q
uv run ruff check packages/bluetape-observability
uv run ruff format --check packages/bluetape-observability
```

Expected: all pass; raw `typing.get_type_hints()` without explicit globals is neither called nor promised.

- [ ] Commit:

```bash
git add packages/bluetape-observability
git commit -m "Bound telemetry setup and runtime recording behavior" \
  -m "Constraint: Setup errors are wiring failures while per-event failures must not alter domain calls." \
  -m "Rejected: Mutable health callbacks | They transfer diagnostics ownership to the bridge." \
  -m "Confidence: high" -m "Scope-risk: moderate" \
  -m "Directive: Keep every OTel runtime interaction independently isolated." \
  -m "Tested: Default meter scope, bounded normalizers, isolated recording calls, and API-only imports." \
  -m "Not-tested: Public adapters and domain-specific mappings are owned by Tasks 3 and 4."
```

Rollback/rerun: revert Task 2 as one unit; package metadata remains valid. Rerun Task 1 packaging tests plus `test_recording.py`.

## Task 3: Map resilience events through the callable adapter

**Complexity:** High  
**Depends on:** Task 2 bounded private helpers  
**Write scope:** Resilience mapping, callable behavior, privacy/failure tests  
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-observability/src/bluetape/observability/resilience.py`
- Create: `packages/bluetape-observability/tests/test_public_api.py`
- Create: `packages/bluetape-observability/tests/test_resilience.py`
- Modify as test support requires: `packages/bluetape-observability/tests/_support.py`

- [ ] Add RED public-contract/setup tests for exact resilience `__all__`, keyword-only constructor, postponed `PolicyEvent` annotation, no runtime domain import, injected-meter identity, exact counter construction, fail-fast setup, clean retry after ordinary setup failure, and setup `BaseException` propagation. Implement the complete class and mapping in this task; do not commit a constructor with placeholder/no-op `__call__`.
- [ ] Add RED success tests using structural fixtures for every pinned enum literal and optional field. Add a drift sentinel comparing the pinned v1 literal sets with the current domain enum sets; future domain additions must fail for explicit review and must not auto-expand production constants. Assert span event `bluetape.resilience.policy`, counter amount `1`, exact shared metric attributes, exact span-only fields, omitted `None`, and no duration metric.
- [ ] Add a hostile `policy_name` property that raises and prove the adapter never reads it. Add sentinel secrets in unconsumed fields/repr and assert they never reach call logs.
- [ ] Add whole-event rejection RED tests for missing fields, unsupported enum values, strings masquerading as enums, bool/count confusion, attempt `0`, negative/out-of-range counts, NaN/infinity, and property access raising `Exception`. Assert zero span/counter calls.
- [ ] Implement one private resilience normalizer that validates all consumed fields before requesting the current span. Use the exact closed value sets from `_core.py`; future enum values remain rejected until reviewed.
- [ ] Implement `__call__` in this fixed order: normalize; resolve recording span; attempt span event; independently attempt counter. Each runtime call catches `Exception` only. Return `None` on every accepted/rejected ordinary path.
- [ ] Add runtime isolation tests: span lookup failure still attempts counter; `is_recording` failure still attempts counter; `add_event` failure still attempts counter; counter failure does not escape; the next event retries. Parameterize representative `BaseException` injection separately at normalization, `get_current_span`, `is_recording`, `add_event`, and `Counter.add`; each propagates immediately and prevents only work that is sequenced after that uncaught process-control exception.
- [ ] Import actual `PolicyEvent` and all enum types only in tests and prove a real `Retry` success and failure retain their results/errors while telemetry fakes raise ordinary exceptions.
- [ ] Run focused nodes after each micro-cycle, then:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  packages/bluetape-observability/tests/test_public_api.py \
  packages/bluetape-observability/tests/test_resilience.py -q
```

Expected: all mapping, privacy, malformed-input, actual-producer, and isolation tests pass.

- [ ] Commit:

```bash
git add packages/bluetape-observability
git commit -m "Bridge resilience events without exposing caller identity" \
  -m "Constraint: Policy names and arbitrary event data cannot become telemetry attributes." \
  -m "Rejected: Synthetic operation spans | The terminal observer does not own operation timing." \
  -m "Confidence: high" -m "Scope-risk: moderate" \
  -m "Directive: New PolicyEvent fields remain ignored until explicitly allowlisted." \
  -m "Tested: Exact mapping, hostile inputs, runtime isolation, and real Retry behavior." \
  -m "Not-tested: Redis mappings are owned by Task 4."
```

Rollback/rerun: reverting Task 3 removes the resilience public module/class entirely. Rerun Task 2 plus Task 1 packaging tests and do not retain any downstream Task 5-8 claim.

## Task 4: Map Redis provider and coordination events

**Complexity:** High  
**Depends on:** Tasks 2-3 bounded helpers and first public module  
**Write scope:** Both Redis mappings, `on_event` behavior, privacy/failure tests  
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-observability/src/bluetape/observability/redis.py`
- Modify: `packages/bluetape-observability/tests/test_public_api.py`
- Create: `packages/bluetape-observability/tests/test_redis.py`
- Modify as test support requires: `packages/bluetape-observability/tests/_support.py`

- [ ] Extend RED public-contract/setup tests for exact Redis `__all__`, both keyword-only constructors, postponed event annotations, no runtime domain import, injected-meter identity, exact counter/histogram construction order, fail-fast setup at each instrument, clean retry after ordinary setup failure, and setup `BaseException` propagation. Implement both complete classes and mappings in this task; do not commit placeholder/no-op `on_event` methods.
- [ ] Add RED provider tests for exact `mode/operation/outcome/error.code` attributes, span-only exact `elapsed_ns`, counter `1`, histogram seconds `elapsed_ns / 1_000_000_000`, fixed event/instrument names, and omitted absent error code.
- [ ] Add RED coordination tests for the same shared fields plus metric/span `cleanup_failed`, span-only `attempts/polls/elapsed_ns`, counter `1`, and duration conversion.
- [ ] Exercise every pinned provider/coordination literal and add drift sentinels comparing the pinned v1 sets with current domain enum sets. Reject unknown consumed enum values, negative/bool/greater-than-int64 numeric values, non-bool cleanup, and missing/raising consumed properties before any signal call. For payload/key/namespace/error-message/future unconsumed fields, use raising-property and repr sentinels to prove they are never read while an otherwise valid event still emits only the allowlisted attributes.
- [ ] Implement separate provider and coordination normalizers; do not introduce runtime dispatch on event class. Normalize all fields once before any OTel interaction.
- [ ] Implement each `on_event` in this order: normalize; resolve recording span; attempt span event; attempt counter; attempt histogram. A failed counter must not suppress histogram; a failed span must not suppress either metric; ordinary failures retry on the next event.
- [ ] Parameterize representative `BaseException` propagation separately at normalization, `get_current_span`, `is_recording`, `add_event`, counter, and histogram. Add actual sync and async Redis provider event integration without Docker by using deterministic fake Redis clients already patterned in `packages/bluetape-cache-redis/tests`; prove provider outcomes are unchanged when the adapter's ordinary telemetry `Exception` calls fail.
- [ ] Add actual `RedisCoordinationEvent` protocol compatibility directly; do not require Testcontainers because the adapter consumes the public terminal event rather than Redis transport behavior.
- [ ] Add a source/subprocess assertion after both modules exist: domain imports occur only under `TYPE_CHECKING`; API-only import of both modules leaves domain/SDK modules absent from `sys.modules`; root `bluetape.observability.__all__` remains empty.
- [ ] Run:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  packages/bluetape-observability/tests/test_public_api.py \
  packages/bluetape-observability/tests/test_redis.py -q
```

Expected: both adapters pass exact mapping, conversion, isolation, actual-event, sync, and async cases.

- [ ] Commit:

```bash
git add packages/bluetape-observability
git commit -m "Bridge Redis events through fixed low-cardinality signals" \
  -m "Constraint: Measurements may not become metric dimensions and Redis data may never be promoted." \
  -m "Rejected: One universal observer | Redis and resilience expose different public observer shapes." \
  -m "Confidence: high" -m "Scope-risk: moderate" \
  -m "Directive: Keep counter and histogram failures independent." \
  -m "Tested: Provider/coordination mappings, actual events, sync/async paths, and hostile input." \
  -m "Not-tested: Real SDK aggregation and span export are owned by Task 5."
```

Rollback/rerun: revert Task 4 without changing resilience. Rerun public API/recording tests and all Redis adapter nodes.

## Task 5: Prove real SDK measurements and current-context semantics

**Complexity:** High  
**Depends on:** Tasks 3-4 mappings complete  
**Write scope:** Local SDK integration, metric extraction, sync/async context, default scope proof  
**Pattern skill:** `$bluetape-py-patterns`, `$test-driven-development`

**Files:**

- Create: `packages/bluetape-observability/tests/test_sdk_integration.py`
- Modify: `packages/bluetape-observability/tests/_support.py`
- Modify: `pyproject.toml` only to register marker `observability_sdk`

- [ ] Mark every SDK test `pytest.mark.observability_sdk`. Keep ordinary SDK imports inside selected fixtures/tests; do not use `pytest.importorskip` and do not import SDK during module collection. The generic gate explicitly deselects this marker after proving SDK absence. The focused command first proves SDK/domain imports, selects only this marker with `--strict-markers`, writes JUnit XML, and fails if selected tests are zero or any test is skipped/failed/errored.
- [ ] Add `yield` fixtures for `InMemoryMetricReader`/local `MeterProvider` and tracer/exporter state plus a helper that flattens `MetricsData.resource_metrics[*].scope_metrics[*].metrics` by name. Use `shutdown_on_exit=False`; in `finally`, shut down tracer then meter provider exactly once and assert teardown remains correct when the test body raises.
- [ ] For all three adapters, assert real SDK metric name/type/unit/description, data-point attributes, counter value, histogram count/sum, and absence of forbidden dimensions.
- [ ] Use local `TracerProvider(shutdown_on_exit=False)`, `SimpleSpanProcessor`, and `InMemorySpanExporter`; activate spans with `trace.use_span` or `start_as_current_span` without setting the global provider. Assert exact span-event names/attributes and no synthetic child span.
- [ ] Reuse one adapter across nested and sequential sync/async span scopes; every event must attach only to the span current at invocation and no event may leak to a closed/stale span. Run concurrent coroutines with the same adapter and distinct active spans/attributes; assert context isolation and zero cross-call contamination. Assert no promise for raw thread/executor/detached/process propagation.
- [ ] Run an application-owned `ThreadPoolExecutor` stress case with the same adapter and a thread-safe injected recording meter. Bound ownership with `with ThreadPoolExecutor(...) as executor`, use no active span in worker threads, assert the expected metric call count/attribute multiset, and verify worker threads are joined after context exit. Explicitly treat trace-context propagation across raw threads as unsupported rather than expected.
- [ ] Patch `opentelemetry.metrics.get_meter` before constructing a default adapter and assert one call with `("bluetape.observability", importlib.metadata.version("bluetape-observability"))`. Assert construction/calls never invoke `set_meter_provider` or `set_tracer_provider`.
- [ ] Use actual `PolicyEvent`, `RedisEvent`, and `RedisCoordinationEvent` objects to prove protocol compatibility against the local SDK.
- [ ] Run:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 \
  python -c "import opentelemetry.sdk, bluetape.resilience, bluetape.cache.redis"
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  --strict-markers -m observability_sdk -rs \
  packages/bluetape-observability/tests/test_sdk_integration.py \
  --junitxml=.omx/issue24-observability-sdk.xml -q
uv run python -c 'import xml.etree.ElementTree as E; r=E.parse(".omx/issue24-observability-sdk.xml").getroot(); s=[r] if r.tag.endswith("testsuite") else list(r.findall("testsuite")); assert sum(int(x.attrib.get("tests", 0)) for x in s) > 0 and all(sum(int(x.attrib.get(k, 0)) for x in s) == 0 for k in ("failures", "errors", "skipped"))'
```

Expected: non-zero SDK test collection, every selected SDK test passes, `skipped=0`, and no global provider mutation occurs. A failed prerequisite import or any selected skip is a focused-gate failure.

- [ ] Commit:

```bash
git add pyproject.toml packages/bluetape-observability
git commit -m "Prove observability adapters against caller-owned SDK state" \
  -m "Constraint: Applications own providers, readers, processors, exporters, and shutdown." \
  -m "Rejected: Global provider setup in tests | It hides ownership and makes test order observable." \
  -m "Confidence: high" -m "Scope-risk: narrow" \
  -m "Tested: Real metrics, span events, default scope, actual events, and sync/async current context." \
  -m "Not-tested: Unsupported propagation boundaries remain documented non-goals."
```

Rollback/rerun: revert SDK tests/marker only if runtime adapter tests remain green; any adapter fix discovered here reopens its owning Task 3 or 4.

## Task 6: Enforce performance, allocation, and owned-resource budgets

**Complexity:** High  
**Depends on:** Tasks 3-5 behavior fixed  
**Write scope:** Deterministic resource tests, reproducible benchmark, Step 4-P evidence  
**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Create: `packages/bluetape-observability/tests/test_performance_contract.py`
- Create: `packages/bluetape-observability/benchmarks/observer_overhead.py`
- Create during final evidence task: `docs/review/2026-07-15-issue-24-observability-performance.md`

- [ ] Add a deterministic source/runtime ownership test proving production modules create no `threading`/`asyncio` lock, thread, task, queue, executor, weak/global registry, event list, or close/flush/shutdown method. Compare thread/task sets around two consecutive API-only runs. Keep SDK-owned provider/exporter resources in a separate assertion category and verify their application-owned teardown rather than attributing them to the package.
- [ ] Parameterize a `tracemalloc` retained-allocation test over all three adapters independently: construct/warm, collect, snapshot, run exactly 100,000 API-only calls, collect, snapshot, and compare with an equivalently warmed 100,000-call empty-observer baseline in isolated snapshots. Assert each adapter's incremental retained size is at most 64 KiB; avoid asserting peak temporary allocation.
- [ ] Pass a weak-referenceable structural event sentinel through each adapter, delete the caller reference, collect, and prove the event is immediately collectible. Assert adapter state contains only constructor-cached instruments and no event, span, attribute mapping, or context reference.
- [ ] Implement the benchmark CLI with fixed seedless structural events, warmup outside measurement, an empty-callback baseline, `perf_counter_ns`, exact per-run sample counts, and compact JSON. `--runs 3` is exactly the three-run evidence set. Retain raw baseline and adapter median/p95 values and compute bounded incremental values as `max(0, adapter_quantile - baseline_quantile)` for each quantile.
- [ ] For `--mode api`, use fresh warmed API-only state per adapter/run with the default no-op meter and a non-recording current span; never construct SDK providers/readers/exporters in this mode. For `--mode sdk`, create fresh application-owned SDK provider/reader/exporter state per adapter/run, activate one recording span for measured adapter samples, and tear down/reset all SDK state in `finally` before the next run. Record the span limit and exported event count so bounded SDK retention cannot contaminate later runs; run the corresponding baseline with equivalent mode-specific fixture setup. A deterministic subprocess test invokes each complete mode twice and asserts no additional thread/task remains.
- [ ] Run deterministic tests:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  packages/bluetape-observability/tests/test_performance_contract.py -q
```

- [ ] Run exactly one command per mode; each command performs and reports the three evidence runs selected by `--runs 3`:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 python \
  packages/bluetape-observability/benchmarks/observer_overhead.py --mode api --runs 3 --calls 100000
uv run --package bluetape-observability --group test --python 3.13.14 python \
  packages/bluetape-observability/benchmarks/observer_overhead.py --mode sdk --runs 3 --calls 100000
```

Acceptance per adapter: API/no recording span median `<=25 us`, p95 `<=75 us`; local SDK median `<=150 us`, p95 `<=500 us`. If a budget fails in two of three same-environment runs, stop Step 4-P, optimize private code, and repeat; changing the budget requires spec reapproval.

- [ ] Commit code/tests, but defer measured evidence text to Task 8:

```bash
git add packages/bluetape-observability
git commit -m "Bound adapter overhead and forbid owned telemetry resources" \
  -m "Constraint: Inline observers must remain allocation-bounded and resource-free." \
  -m "Rejected: CI timing thresholds | Shared runners cannot provide stable latency evidence." \
  -m "Confidence: medium" -m "Scope-risk: narrow" \
  -m "Directive: Keep timing evidence local while allocation and ownership stay deterministic CI gates." \
  -m "Tested: Retained allocation, task/thread ownership, and three-run API/SDK benchmarks." \
  -m "Not-tested: Exporter network latency is application-owned."
```

Rollback/rerun: benchmark/test-only corrections remain isolated. Runtime optimization reopens the owning adapter tests and SDK integration.

## Task 7: Synchronize bilingual docs, CI, and release inventory

**Complexity:** High  
**Depends on:** Tasks 1-6 final install/API/failure shape  
**Write scope:** README locale pairs, executable examples, workspace docs, CI ownership  
**Pattern skill:** `$bluetape-maintenance`, `$bluetape-py-patterns`

**Files:**

- Modify: `packages/bluetape-observability/README.md`
- Create: `packages/bluetape-observability/README.ko.md`
- Create: `packages/bluetape-observability/tests/test_readme_examples.py`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `docs/package-layout.md`
- Modify: `WIP.md`
- Modify: `CHANGELOG.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` to register `observability_workspace`
- Modify: `packages/bluetape-observability/tests/test_packaging.py`
- Create: `packages/bluetape-observability/tests/test_logging_separation.py`
- Create: `scripts/verify-observability-wheels.sh`
- Modify only if a test proves a public inventory omission: `docs/release/release-guide.md`

- [ ] Write RED documentation tests before prose. Require direct `pip install bluetape-observability`, no root extra, English/Korean switch directly under each title, exact three adapter and signal names, privacy/cardinality exclusions, fail-fast setup vs isolated runtime behavior, API-only no-op, SDK/application ownership, sync/async current-context limits, no fan-out/replacement warning, rollback, and no automatic log-context/baggage/trace-ID promotion in either direction.
- [ ] Add a source-equivalent EN/KO prerequisite matrix: `bluetape-observability + bluetape-resilience` for policy observation, `bluetape-observability + bluetape-cache-redis` for Redis provider/coordination observation, and all three only when both domains are used. Explain that domain packages are deliberately not runtime dependencies of the bridge, so callers install the domain they actually own.
- [ ] Add marked source-identical snippets to both package READMEs. `api-only-example` constructs/calls all adapters without configuring SDK. `sdk-example` creates local application-owned meter/tracer providers/readers/exporter, injects a meter, wires both Redis adapter types, records/shuts down explicitly, and states production exporter selection/shutdown are application-owned.
- [ ] Execute/compile both locale copies in `test_readme_examples.py`; patch network/domain producers with deterministic public events. Assert the marked snippets are byte-for-byte identical across locales. Keep the SDK example in the focused SDK lane, but run the exact extracted API-only snippet again through the clean wheel-installed venv described below and assert `opentelemetry.sdk` is absent before and after execution.
- [ ] Add source-identical caller-owned composition examples for both observer shapes. The resilience example composes callables in an explicit documented order; the Redis example provides an object with `on_event`. Each states its chosen fail-stop/continue policy, proves that assigning only the OTel adapter replaces the prior observer, and leaves alternate ordering/failure handling to the caller rather than the package.
- [ ] Mark `test_logging_separation.py` as `observability_workspace` and run it only after full workspace sync. Activate OTel baggage and `bluetape.logging.log_context`, pass valid events through all adapters with recording fakes, and assert the exact telemetry attributes contain neither baggage nor log-context values. Capture a stdlib log record inside an active span and assert no trace/span ID appears without application logging configuration. Source-check production modules for `opentelemetry.baggage` and `bluetape.logging` imports.
- [ ] Update root README locale tables, direct install/smoke commands, package-document links, milestone text, and core-only default statement in lockstep. Do not add observability to `packages/bluetape/pyproject.toml` or its extras tables.
- [ ] Pin failure/operations guidance in both package locale files with section-level parity assertions: no mutable health or diagnostic callback exists; constructor failures are application wiring failures; per-event ordinary telemetry failures are isolated; SDK/exporter delivery health is diagnosed through application-owned OTel configuration; raw threads, `run_in_executor`, detached/background tasks, processes, remote transports, and callbacks after context end have no implicit propagation guarantee. Rollback removes the adapter and restores any prior observer/composite without data/schema migration.
- [ ] Update package layout, WIP issue #24 state, changelog user-facing behavior, and any enumerating release inventory. Do not claim merge, release, or PyPI availability.
- [ ] Add a dedicated `observability` CI job with Python 3.13.14:

```yaml
- name: Sync observability test dependencies
  run: >-
    uv sync --package bluetape-observability --group test
    --python 3.13.14 --locked
- name: Prove focused SDK and domain dependencies
  run: >-
    uv run --package bluetape-observability --group test --python 3.13.14
    python -c "import opentelemetry.sdk, bluetape.resilience, bluetape.cache.redis"
- name: Test observability contracts
  run: >-
    uv run --package bluetape-observability --group test --python 3.13.14 pytest
    --strict-markers -m "not observability_sdk and not observability_workspace"
    packages/bluetape-observability/tests -rs -q
- name: Test observability SDK contracts without skips
  run: |
    uv run --package bluetape-observability --group test --python 3.13.14 pytest \
      --strict-markers -m observability_sdk packages/bluetape-observability/tests \
      --junitxml="$RUNNER_TEMP/observability-sdk.xml" -rs -q
    uv run python -c 'import os, xml.etree.ElementTree as E; r=E.parse(os.environ["RUNNER_TEMP"] + "/observability-sdk.xml").getroot(); s=[r] if r.tag.endswith("testsuite") else list(r.findall("testsuite")); assert sum(int(x.attrib.get("tests", 0)) for x in s) > 0 and all(sum(int(x.attrib.get(k, 0)) for x in s) == 0 for k in ("failures", "errors", "skipped"))'
```

- [ ] Extend generic base-workspace proof with `find_spec("opentelemetry.sdk") is None`; API presence is expected because the root workspace aggregates the focused package for development. Register `observability_sdk` and `observability_workspace` markers. The generic pytest command uses `--strict-markers -m "not testcontainers and not native_compression and not observability_sdk" -rs`, so the SDK lane is deterministically deselected. Extend the isolated default `bluetape` wheel proof so both `opentelemetry` and `bluetape.observability` are absent.
- [ ] Implement `scripts/verify-observability-wheels.sh` as the single reusable focused/default isolation gate. Use `set -euo pipefail`, `mktemp -d`, and `trap 'rm -rf "$tmp_dir"' EXIT`; build core/meta/observability with `--out-dir "$tmp_dir/dist"`; assert exactly one wheel exists for each expected distribution before installation; run `uv export --locked --package bluetape-observability --no-dev --no-emit-local -o "$tmp_dir/requirements.txt"`; create the interpreter with `uv venv "$tmp_dir/focused" --python 3.13.14`; run `uv pip sync --python "$tmp_dir/focused/bin/python" --require-hashes "$tmp_dir/requirements.txt"`; install the built observability wheel with `--no-deps`; and run `uv pip check`. Never read repository-root `dist/`.
- [ ] In the same script, execute probes with the venv `python -I` from the temporary directory. Assert `opentelemetry-api` equals the `uv.lock` version; imported OTel/observability module origins are under the temporary venv; SDK/domain modules are absent; both public modules construct/call with structural events; and wheel metadata has only the approved runtime requirement. In a second clean venv install core/meta wheels with `--no-index --find-links`, run `uv pip check`, and prove observability/OTel cannot resolve.
- [ ] Add a third clean README-example venv. Run `uv export --locked --package bluetape-observability --no-dev --no-emit-local -o "$tmp_dir/observability-requirements.txt"` and `uv export --locked --package bluetape-cache-redis --no-dev --no-emit-local -o "$tmp_dir/redis-requirements.txt"`; create it with `uv venv "$tmp_dir/readme" --python 3.13.14`; then run `uv pip sync --python "$tmp_dir/readme/bin/python" --require-hashes "$tmp_dir/observability-requirements.txt" "$tmp_dir/redis-requirements.txt"`. Build/install only the local resilience, cache, compression, serde, cache-redis, and observability wheels with `--no-deps`; run `uv pip check`; assert SDK absence; extract the exact `api-only-example` from the English README into the temporary directory; and execute it with `python -I`. Latest-range compatibility, if run, is a separate non-blocking probe.
- [ ] Before cleanup, make the script print one stable compact JSON summary containing every built wheel filename/SHA256, per-distribution wheel count, installed OTel API version, focused/default/README venv module origins, and each probe verdict. Call this exact script from the dedicated CI job after focused tests and from Task 8 local verification; do not duplicate shell fragments in workflow YAML. Task 8 preserves this stdout verbatim before the temporary directory is removed.
- [ ] Run:

```bash
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  packages/bluetape-observability/tests/test_readme_examples.py \
  packages/bluetape-observability/tests/test_packaging.py -q
uv sync --all-packages --all-extras --python 3.13.14 --locked
uv run pytest --strict-markers \
  packages/bluetape-observability/tests/test_logging_separation.py -rs -q
scripts/verify-observability-wheels.sh
actionlint
git diff --check
```

Expected: bilingual snippets execute, all inventory/isolation assertions pass, and workflow syntax is valid.

- [ ] Commit:

```bash
git add .github README.md README.ko.md CHANGELOG.md WIP.md docs pyproject.toml \
  packages/bluetape-observability scripts/verify-observability-wheels.sh
git commit -m "Document and continuously verify observability ownership" \
  -m "Constraint: The focused package is source-workspace available while publication remains on hold." \
  -m "Rejected: A meta-package extra | It would obscure the approved direct-install boundary." \
  -m "Confidence: high" -m "Scope-risk: moderate" \
  -m "Directive: Keep English and Korean examples source-equivalent and executable." \
  -m "Tested: README examples, package inventories, isolated installs, and actionlint." \
  -m "Not-tested: Publication and production exporter delivery remain out of scope."
git ls-files --error-unmatch pyproject.toml scripts/verify-observability-wheels.sh
```

Rollback/rerun: revert docs/CI together only if the prior runtime commits stay green; rerun package docs/packaging tests plus `actionlint`.

## Task 8: Complete validation, six-lens review, lesson, and exact-head evidence

**Complexity:** High  
**Depends on:** Tasks 1-7 complete and individually green  
**Write scope:** Findings-driven fixes plus durable TDD/performance/review/verifier/lesson artifacts  
**Pattern skill:** `$verification-before-completion`, `$requesting-code-review`, `$bluetape-workflow`

**Files:**

- Create: `docs/review/2026-07-15-issue-24-observability-tdd-evidence.md`
- Create: `docs/review/2026-07-15-issue-24-observability-performance.md`
- Create: `docs/review/2026-07-15-issue-24-observability-implementation-review.md`
- Create: `docs/review/2026-07-15-issue-24-observability-verifier.md`
- Create: `docs/lessons/2026-07-15-issue-24-observability.md`
- Modify only as findings require: files owned by Tasks 1-7

- [ ] Record actual RED/GREEN node IDs, commands, results, and owning commits. Do not claim a RED transition without captured evidence.
- [ ] Record Step 4-P benchmark JSON and environment; summarize per-adapter three-run median/p95 and the two-of-three verdict. Record deterministic retained-allocation and zero-owned-resource evidence separately.
- [ ] Run the focused gate:

```bash
uv sync --package bluetape-observability --group test --python 3.13.14 --locked
uv run --package bluetape-observability --group test --python 3.13.14 \
  python -c "import opentelemetry.sdk, bluetape.resilience, bluetape.cache.redis"
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  --strict-markers -m "not observability_sdk and not observability_workspace" \
  packages/bluetape-observability/tests -rs -q
uv run --package bluetape-observability --group test --python 3.13.14 pytest \
  --strict-markers -m observability_sdk packages/bluetape-observability/tests \
  --junitxml=.omx/issue24-observability-sdk.xml -rs -q
uv run python -c 'import xml.etree.ElementTree as E; r=E.parse(".omx/issue24-observability-sdk.xml").getroot(); s=[r] if r.tag.endswith("testsuite") else list(r.findall("testsuite")); assert sum(int(x.attrib.get("tests", 0)) for x in s) > 0 and all(sum(int(x.attrib.get(k, 0)) for x in s) == 0 for k in ("failures", "errors", "skipped"))'
uv run ruff check packages/bluetape-observability
uv run ruff format --check packages/bluetape-observability
uv build --package bluetape-observability
```

- [ ] Run the full workspace gate from a fresh exact sync:

```bash
uv sync --all-packages --all-extras --python 3.13.14 --locked
uv run python -c 'import importlib.util; assert importlib.util.find_spec("opentelemetry.sdk") is None'
uv run pytest --strict-markers \
  -m "not testcontainers and not native_compression and not observability_sdk" -rs
uv run ruff check .
uv run ruff format --check .
uv build --all-packages
scripts/verify-observability-wheels.sh
actionlint
git diff --check
```

Expected: all commands exit 0. The focused prerequisite imports succeed, selected SDK tests all pass with `skipped=0`, and the generic full suite deterministically deselects the SDK marker after proving SDK absence while running the workspace logging-separation test. Preserve `-rs` output and selected/deselected counts in evidence; any focused skip is a failure.

- [ ] Run `scripts/verify-observability-wheels.sh` fresh and record artifact hashes/counts and its module-origin proof; do not substitute source-tree imports or unconstrained dependency resolution.
- [ ] Run six independent implementation reviews: performance, stability, security/privacy, operator/ops, developer/API, and user/caller. Repair every P0/P1 in its owning task, rerun targeted tests, then rerun both focused and full gates. Record final integrated `P0=0 P1=0`.
- [ ] Verify all acceptance criteria and DoD lines against exact files/commands. Mark Testcontainers, external collector/exporter, publication, tag, release, and workflow dispatch as evidence-backed N/A; do not execute them.
- [ ] Write the mandatory Type A lesson covering focused dependency isolation, fail-safe normalization before emission, current-span ownership, independent runtime failure isolation, SDK-only test gating, and cardinality/privacy review.
- [ ] Commit evidence and lesson:

```bash
git add docs/review docs/lessons
git commit -m "Preserve observability delivery evidence and lessons" \
  -m "Constraint: Type A delivery requires exact-head validation, six-lens convergence, and a durable lesson." \
  -m "Confidence: high" -m "Scope-risk: narrow" \
  -m "Directive: Re-run focused and full gates after any later implementation change." \
  -m "Tested: Focused/full suites, Ruff, builds, actionlint, wheel isolation, performance, and reviews." \
  -m "Not-tested: PR CI and publication require later explicit workflow authority."
```

- [ ] After the evidence/lesson commit, capture `final_head=$(git rev-parse HEAD)`, rerun the complete focused gate, full gate, and wheel script exactly as written above against that clean HEAD, and make no further edits. Any failure enters the repair/commit/rerun loop and produces a new `final_head`; pre-repair evidence cannot be reused.
- [ ] Confirm `repo-status` is clean, `git diff --check` passes, `git rev-parse HEAD` still equals `final_head`, and `repo-log`/`git log --oneline origin/develop..HEAD` contains only issue #24 commits. Report that exact final HEAD plus the post-commit gate outputs and stop.

Rollback/rerun: any P0/P1 or validation failure reopens its owning task and invalidates later exact-head evidence. Apply the smallest repair in a separate Lore commit, rerun targeted plus focused/full gates, and regenerate evidence against the new HEAD.

## Forward Rollback Matrix

Rollback is always a history-preserving forward operation. Never use `git reset --hard`,
`git checkout --`, or rewrite already reviewed commits. Use `git revert` in reverse dependency
order, then make any lock/document reconciliation as a new Lore commit.

| Failed/removed task | Revert/invalidate first | Required reconciliation and rerun |
|---|---|---|
| Task 7 docs/CI | Task 8 evidence/lesson, then Task 7 | `actionlint`, docs tests, focused/full gates, wheel script; regenerate exact-head evidence |
| Task 6 performance contract | Task 8 evidence, then Task 6 | Owning adapter/SDK tests, allocation/ownership checks, both benchmark commands; regenerate performance evidence |
| Task 5 SDK/context proof | Tasks 8 -> 7 CI claims -> 6 benchmark -> 5 | Targeted adapter tests, focused/full gates, wheel script; remove invalid SDK claims before new evidence |
| Task 4 Redis adapters | Tasks 8 -> 7 docs/CI -> 6 -> 5 -> 4 | Redis targeted tests, all public/recording tests, focused/full gates, wheel script; regenerate all downstream evidence |
| Task 3 resilience adapter | Tasks 8 -> 7 docs/CI -> 6 -> 5 -> 3 | Resilience targeted tests, all public/recording tests, focused/full gates, wheel script; regenerate all downstream evidence |
| Task 2 shared recording/setup | Tasks 8 -> 7 -> 6 -> 5 -> 4 -> 3 -> 2 | Public/setup tests, all adapter tests, focused/full gates, wheel script; no downstream claim survives |
| Task 1 distribution boundary | Tasks 8 down through 2, then Task 1 | Revert package/root/classifier/preflight together, run `uv lock`, classifier tests, full workspace gate, default-wheel proof; discard all issue #24 exact-head evidence |

After any rollback, `repo-status` must be clean, the new forward history must be reviewed, and
no prior exact-head review/CI claim may be reused for the new HEAD.

## Spec Coverage Map

| Approved requirement / DoD | Plan tasks |
|---|---|
| Focused package, Python/version/runtime/test dependency boundary, no extras/default widening | 1, 7, 8 |
| Exact exports, signatures, versioned default meter, injected meter, fail-fast construction | 2, 5 |
| Fixed resilience span/counter mapping and privacy exclusions | 3, 5 |
| Fixed Redis provider/coordination span/counter/histogram mapping and duration conversion | 4, 5 |
| Whole-event fail-safe normalization, closed enums, exact scalar/range checks, no partial emission | 2-4 |
| Independent runtime `Exception` isolation, retry-next-event, `BaseException` propagation | 2-4 |
| No providers/exporters/spans/logging bridge/background resources/global mutation | 2, 5, 6 |
| API-only import/no-op and no runtime domain/SDK dependencies | 1, 2, 7, 8 |
| Real local SDK metrics/spans and actual domain event compatibility | 3-5 |
| Ordinary sync/async current context and unsupported propagation boundaries | 4, 5, 7 |
| Performance latency, retained allocation, no locks/threads/tasks/queues/retention | 6, 8 |
| Bilingual package/root docs, executable examples, fan-out replacement warning, logging separation | 7 |
| Workspace/lock/layout/WIP/changelog/CI/release classifier synchronization | 1, 7, 8 |
| TDD evidence, six-lens P0/P1 convergence, Type A lesson, exact-head report | 8 |

## Planned Commit Sequence

1. `Establish an isolated observability package boundary`
2. `Bound telemetry setup and runtime recording behavior`
3. `Bridge resilience events without exposing caller identity`
4. `Bridge Redis events through fixed low-cardinality signals`
5. `Prove observability adapters against caller-owned SDK state`
6. `Bound adapter overhead and forbid owned telemetry resources`
7. `Document and continuously verify observability ownership`
8. `Preserve observability delivery evidence and lessons`

Corrective review commits remain separate, Lore-compliant decisions; do not rewrite reviewed history merely to make the sequence appear shorter.

## Plan Self-Review

- Every spec acceptance criterion and DoD item maps to at least one concrete task.
- Dependencies are forward-only: registration -> primitives -> domain mappings -> real SDK -> performance -> docs/CI -> final evidence.
- No later artifact is required by an earlier task; evidence files are intentionally deferred until commands exist.
- Tests cover success, absent/edge values, malformed/hostile fields, setup failure, runtime failure independence, sync/async context, actual domain events, lifecycle/ownership, allocation, packaging, and SDK capability.
- Exact commands distinguish focused SDK-installed proof from the generic full-suite environment.
- English/Korean package and root documentation, changelog, WIP, package layout, CI, and publish classification are explicit.
- No placeholder production code, extra dependency, global provider mutation, release side effect, PR, merge, or publication is authorized.

## Stop Condition

Planning closes only after six independent Step 3-R plan reviews and main integration record `P0=0 P1=0`, the reviewed plan and plan-review artifact are committed, and the user approves execution. Implementation closes later only after Task 8 exact-head evidence. PR creation and merge remain separate future gates; auto-merge is forbidden.
