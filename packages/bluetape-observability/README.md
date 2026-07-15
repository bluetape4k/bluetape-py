# bluetape-observability

English | [한국어](README.ko.md)

Opt-in OpenTelemetry API adapters for Bluetape resilience and Redis observer events.

## Responsibility map

The bridge keeps bounded signal recording separate from the application-owned
OpenTelemetry runtime and exporter lifecycle.

![bluetape-observability responsibility map](../../docs/images/readme-diagrams/bluetape-observability-architecture.png)

[Open the editable SVG](../../docs/images/readme-diagrams/bluetape-observability-architecture.svg)

## Install and prerequisites

```bash
pip install bluetape-observability
```

There is no root extra. Install the focused bridge and only the domain packages the
application uses:

| Use | Direct distributions |
|---|---|
| Policy events | `bluetape-observability + bluetape-resilience` |
| Redis provider and coordination events | `bluetape-observability + bluetape-cache-redis` |
| Both domains | `bluetape-observability + bluetape-resilience + bluetape-cache-redis` |

Domain packages are deliberately test-only dependencies of this bridge. Applications own and
install their domain packages directly.

## Public adapters and fixed signals

- `OpenTelemetryPolicyObserver` records `bluetape.resilience.policy.events`.
- `OpenTelemetryRedisObserver` records `bluetape.redis.operations` and duration.
- `OpenTelemetryRedisCoordinationObserver` records
  `bluetape.redis.coordination.operations` and duration.

Only pinned low-cardinality enum values, bounded counts, booleans, and durations are consumed.
Policy names, Redis keys/values/namespaces, exception messages, arbitrary attributes, log
context, baggage, and trace ID values are never promoted automatically.

## API-only example

The OpenTelemetry API no-op path works without configuring an SDK.

<!-- api-only-example:start -->
```python
from bluetape.cache.redis import (
    RedisCoordinationEvent,
    RedisCoordinationOperation,
    RedisCoordinationOutcome,
    RedisEvent,
    RedisMode,
    RedisOperation,
    RedisOutcome,
)
from bluetape.observability.redis import (
    OpenTelemetryRedisCoordinationObserver,
    OpenTelemetryRedisObserver,
)
from bluetape.observability.resilience import OpenTelemetryPolicyObserver
from bluetape.resilience import (
    EventKind,
    FailureCategory,
    PolicyEvent,
    PolicyOutcome,
    PolicyType,
)

OpenTelemetryPolicyObserver()(
    PolicyEvent(
        policy_name="orders",
        policy_type=PolicyType.RETRY,
        kind=EventKind.SUCCEEDED,
        outcome=PolicyOutcome.SUCCESS,
        failure_category=FailureCategory.NONE,
        attempt=1,
        delay=None,
        timeout=None,
        state=None,
        previous_state=None,
        in_flight=None,
        waiters=None,
    )
)
OpenTelemetryRedisObserver().on_event(
    RedisEvent(
        mode=RedisMode.SYNC,
        operation=RedisOperation.GET,
        outcome=RedisOutcome.SUCCESS,
        error_code=None,
        elapsed_ns=1,
    )
)
OpenTelemetryRedisCoordinationObserver().on_event(
    RedisCoordinationEvent(
        mode=RedisMode.ASYNC,
        operation=RedisCoordinationOperation.GET_OR_LOAD,
        outcome=RedisCoordinationOutcome.LOADED,
        error_code=None,
        attempts=1,
        polls=0,
        cleanup_failed=False,
        elapsed_ns=1,
    )
)
```
<!-- api-only-example:end -->

## Application-owned SDK example

Production exporter selection, provider configuration, flushing, and shutdown are
application-owned.

<!-- sdk-example:start -->
```python
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bluetape.cache.redis import RedisEvent, RedisMode, RedisOperation, RedisOutcome
from bluetape.observability.redis import OpenTelemetryRedisObserver

reader = InMemoryMetricReader()
meter_provider = MeterProvider(metric_readers=[reader], shutdown_on_exit=False)
exporter = InMemorySpanExporter()
tracer_provider = TracerProvider(shutdown_on_exit=False)
tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
observer = OpenTelemetryRedisObserver(meter=meter_provider.get_meter("orders"))
tracer = tracer_provider.get_tracer("orders")
shutdown_order = []
try:
    with tracer.start_as_current_span("redis-get"):
        observer.on_event(
            RedisEvent(
                mode=RedisMode.SYNC,
                operation=RedisOperation.GET,
                outcome=RedisOutcome.SUCCESS,
                error_code=None,
                elapsed_ns=1,
            )
        )
finally:
    tracer_provider.shutdown()
    shutdown_order.append("tracer")
    meter_provider.shutdown()
    shutdown_order.append("meter")
```
<!-- sdk-example:end -->

## Caller-owned composition

Each producer accepts one observer. Assigning only the OTel adapter replaces the previous observer.
A caller-owned composite makes order and failure policy explicit.

This resilience example is `fail-stop`: the first failure stops later callbacks.

<!-- resilience-composition:start -->
```python
calls = []

def audit(event):
    calls.append("audit")

def otel(event):
    calls.append("otel")

def compose(*observers):
    def observe(event):
        for observer in observers:
            observer(event)
    return observe

compose(audit, otel)(object())
```
<!-- resilience-composition:end -->

This Redis example is `fail-continue`: it keeps later callbacks running and leaves diagnosis to
the application.

<!-- redis-composition:start -->
```python
calls = []

class Composite:
    def __init__(self, *observers):
        self.observers = observers

    def on_event(self, event):
        for observer in self.observers:
            try:
                observer.on_event(event)
            except Exception:
                continue

class Recorder:
    def __init__(self, name):
        self.name = name

    def on_event(self, event):
        calls.append(self.name)

Composite(Recorder("audit"), Recorder("otel")).on_event(object())
```
<!-- redis-composition:end -->

Alternate ordering and failure handling remain caller decisions.

## Failure, context, and diagnostics

Construction is fail-fast: meter lookup or instrument creation errors are application wiring
failures. Per-event ordinary OpenTelemetry errors are isolated independently so domain results
are preserved; process-control `BaseException` values still propagate. The package exposes
no mutable health state and no diagnostic callback. SDK/exporter delivery health belongs to the
application-owned OpenTelemetry configuration.

Current span lookup follows normal synchronous and coroutine `contextvars` behavior. There is no
implicit propagation guarantee for raw threads, `run_in_executor`, detached or background tasks,
processes, remote transports, or callbacks after a context ends. The package does not promote
log context or baggage into telemetry and does not add trace ID or span ID fields to logs.

## rollback

Rollback removes the adapter from the producer and restores the prior observer or caller-owned
composite. No data or schema migration is required.
