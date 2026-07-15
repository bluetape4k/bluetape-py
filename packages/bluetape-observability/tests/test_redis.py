from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from _observability_support import (
    EnumValue,
    RecordingCounter,
    RecordingHistogram,
    RecordingMeter,
    RecordingSpan,
    coordination_event,
    redis_event,
)
from bluetape.cache.redis import (
    AsyncRedisProvider,
    RedisCoordinationErrorCode,
    RedisCoordinationOperation,
    RedisCoordinationOutcome,
    RedisErrorCode,
    RedisMode,
    RedisOperation,
    RedisOutcome,
    RedisProviderError,
    SyncRedisProvider,
)


def observer_with_span(
    monkeypatch: pytest.MonkeyPatch, observer_name: str
) -> tuple[object, RecordingMeter, RecordingSpan]:
    from bluetape.observability import _recording
    from bluetape.observability import redis as module

    span = RecordingSpan()
    monkeypatch.setattr(_recording.trace, "get_current_span", lambda: span)
    meter = RecordingMeter()
    observer = getattr(module, observer_name)(meter=meter)
    return observer, meter, span


def test_provider_maps_exact_metric_and_span_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.observability import _recording

    assert _recording.REDIS_MODES == frozenset(item.value for item in RedisMode)
    assert _recording.REDIS_OPERATIONS == frozenset(item.value for item in RedisOperation)
    assert _recording.REDIS_OUTCOMES == frozenset(item.value for item in RedisOutcome)
    assert _recording.REDIS_ERROR_CODES == frozenset(item.value for item in RedisErrorCode)

    observer, meter, span = observer_with_span(monkeypatch, "OpenTelemetryRedisObserver")
    observer.on_event(redis_event(error_code=EnumValue("timeout")))
    metric = {
        "bluetape.redis.mode": "sync",
        "bluetape.redis.operation": "get",
        "bluetape.redis.outcome": "success",
        "bluetape.redis.error.code": "timeout",
    }
    assert meter.instruments[0].calls == [(1, metric)]
    assert meter.instruments[1].calls == [(0.125, metric)]
    assert span.events == [
        ("bluetape.redis.operation", metric | {"bluetape.redis.elapsed_ns": 125_000_000})
    ]


def test_coordination_maps_exact_metric_and_span_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bluetape.observability import _recording

    assert _recording.COORDINATION_OPERATIONS == frozenset(
        item.value for item in RedisCoordinationOperation
    )
    assert _recording.COORDINATION_OUTCOMES == frozenset(
        item.value for item in RedisCoordinationOutcome
    )
    assert _recording.COORDINATION_ERROR_CODES == frozenset(
        item.value for item in RedisCoordinationErrorCode
    )

    observer, meter, span = observer_with_span(
        monkeypatch, "OpenTelemetryRedisCoordinationObserver"
    )
    observer.on_event(coordination_event(error_code=EnumValue("loader-failure")))
    metric = {
        "bluetape.redis.mode": "async",
        "bluetape.redis.operation": "get-or-load",
        "bluetape.redis.outcome": "loaded",
        "bluetape.redis.error.code": "loader-failure",
        "bluetape.redis.coordination.cleanup_failed": False,
    }
    assert meter.instruments[0].calls == [(1, metric)]
    assert meter.instruments[1].calls == [(0.25, metric)]
    assert span.events == [
        (
            "bluetape.redis.coordination",
            metric
            | {
                "bluetape.redis.coordination.attempts": 1,
                "bluetape.redis.coordination.polls": 0,
                "bluetape.redis.elapsed_ns": 250_000_000,
            },
        )
    ]


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    [
        (redis_event, "mode", EnumValue("unknown")),
        (redis_event, "operation", EnumValue("unknown")),
        (redis_event, "outcome", EnumValue("unknown")),
        (redis_event, "error_code", EnumValue("unknown")),
        (redis_event, "elapsed_ns", -1),
        (coordination_event, "attempts", True),
        (coordination_event, "polls", 2**63),
        (coordination_event, "cleanup_failed", 0),
        (coordination_event, "elapsed_ns", -1),
    ],
)
def test_redis_rejects_invalid_consumed_fields_before_emission(
    monkeypatch: pytest.MonkeyPatch, factory, field: str, value: object
) -> None:
    name = (
        "OpenTelemetryRedisObserver"
        if factory is redis_event
        else "OpenTelemetryRedisCoordinationObserver"
    )
    observer, meter, span = observer_with_span(monkeypatch, name)
    assert observer.on_event(factory(**{field: value})) is None
    assert all(instrument.calls == [] for instrument in meter.instruments)
    assert span.events == []


def test_redis_propagates_process_control_from_consumed_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ProcessControlEvent:
        operation = RedisOperation.GET
        outcome = RedisOutcome.SUCCESS
        error_code = None
        elapsed_ns = 1

        def __init__(self, failure: BaseException) -> None:
            self.failure = failure

        @property
        def mode(self) -> RedisMode:
            raise self.failure

    for failure in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
        observer, meter, span = observer_with_span(monkeypatch, "OpenTelemetryRedisObserver")
        with pytest.raises(type(failure)):
            observer.on_event(ProcessControlEvent(failure))
        assert all(instrument.calls == [] for instrument in meter.instruments)
        assert span.events == []


def test_redis_never_reads_forbidden_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    observer, meter, span = observer_with_span(monkeypatch, "OpenTelemetryRedisObserver")

    class PrivateEvent:
        mode = EnumValue("sync")
        operation = EnumValue("get")
        outcome = EnumValue("success")
        error_code = None
        elapsed_ns = 1

        @property
        def key(self) -> bytes:
            raise AssertionError("key was read")

        @property
        def value(self) -> bytes:
            raise AssertionError("value was read")

        def __repr__(self) -> str:
            raise AssertionError("repr was read")

    observer.on_event(PrivateEvent())
    assert [len(instrument.calls) for instrument in meter.instruments] == [1, 1]
    assert len(span.events) == 1


def test_redis_runtime_channels_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    from bluetape.observability import _recording
    from bluetape.observability.redis import OpenTelemetryRedisObserver

    meter = RecordingMeter()
    observer = OpenTelemetryRedisObserver(meter=meter)
    counter, histogram = meter.instruments
    assert isinstance(counter, RecordingCounter)
    assert isinstance(histogram, RecordingHistogram)

    monkeypatch.setattr(
        _recording.trace,
        "get_current_span",
        lambda: RecordingSpan(add_failure=RuntimeError("span")),
    )
    counter.failure = RuntimeError("counter")
    observer.on_event(redis_event())
    assert histogram.calls == [
        (
            0.125,
            {
                "bluetape.redis.mode": "sync",
                "bluetape.redis.operation": "get",
                "bluetape.redis.outcome": "success",
            },
        )
    ]
    counter.failure = None
    observer.on_event(redis_event())
    assert len(counter.calls) == 1
    assert len(histogram.calls) == 2

    for instrument in (counter, histogram):
        for failure in (KeyboardInterrupt(), SystemExit(), GeneratorExit()):
            instrument.failure = failure
            with pytest.raises(type(failure)):
                observer.on_event(redis_event())
        instrument.failure = None


async def test_actual_sync_and_async_provider_behavior_is_preserved() -> None:
    from bluetape.observability.redis import (
        OpenTelemetryRedisCoordinationObserver,
        OpenTelemetryRedisObserver,
    )

    options = {
        "decode_responses": False,
        "socket_connect_timeout": 0.1,
        "socket_timeout": 0.2,
        "retry_on_timeout": False,
        "retry_on_error": [],
    }

    class SyncClient:
        def __init__(self, failure: BaseException | None = None) -> None:
            self.connection_pool = SimpleNamespace(connection_kwargs=options)
            self.failure = failure

        def get(self, _key: str) -> bytes:
            if self.failure is not None:
                raise self.failure
            return b"value"

    class AsyncClient:
        def __init__(self, failure: BaseException | None = None) -> None:
            self.connection_pool = SimpleNamespace(connection_kwargs=options)
            self.failure = failure

        async def get(self, _key: str) -> bytes:
            if self.failure is not None:
                raise self.failure
            return b"value"

    sync_meter = RecordingMeter()
    async_meter = RecordingMeter()
    sync_control = SyncRedisProvider(SyncClient())  # type: ignore[arg-type]
    sync_observed = SyncRedisProvider(  # type: ignore[arg-type]
        SyncClient(), observer=OpenTelemetryRedisObserver(meter=sync_meter)
    )
    async_control = AsyncRedisProvider(AsyncClient())  # type: ignore[arg-type]
    async_observed = AsyncRedisProvider(  # type: ignore[arg-type]
        AsyncClient(), observer=OpenTelemetryRedisObserver(meter=async_meter)
    )

    assert sync_control.get("key") == sync_observed.get("key") == b"value"
    assert await async_control.get("key") == await async_observed.get("key") == b"value"

    control_failure = RuntimeError("control")
    observed_failure = RuntimeError("observed")
    sync_control = SyncRedisProvider(SyncClient(control_failure))  # type: ignore[arg-type]
    sync_observed = SyncRedisProvider(  # type: ignore[arg-type]
        SyncClient(observed_failure), observer=OpenTelemetryRedisObserver(meter=sync_meter)
    )
    with pytest.raises(RedisProviderError) as control_error:
        sync_control.get("key")
    with pytest.raises(RedisProviderError) as observed_error:
        sync_observed.get("key")
    assert (control_error.value.operation, control_error.value.code) == (
        observed_error.value.operation,
        observed_error.value.code,
    )
    assert control_error.value.__cause__ is control_failure
    assert observed_error.value.__cause__ is observed_failure

    async_control = AsyncRedisProvider(  # type: ignore[arg-type]
        AsyncClient(asyncio.CancelledError())
    )
    async_observed = AsyncRedisProvider(  # type: ignore[arg-type]
        AsyncClient(asyncio.CancelledError()),
        observer=OpenTelemetryRedisObserver(meter=async_meter),
    )
    with pytest.raises(asyncio.CancelledError):
        await async_control.get("key")
    with pytest.raises(asyncio.CancelledError):
        await async_observed.get("key")

    coordination_meter = RecordingMeter()
    OpenTelemetryRedisCoordinationObserver(meter=coordination_meter).on_event(
        SimpleNamespace(
            mode=RedisMode.ASYNC,
            operation=RedisCoordinationOperation.GET_OR_LOAD,
            outcome=RedisCoordinationOutcome.CANCELLED,
            error_code=None,
            attempts=1,
            polls=2,
            cleanup_failed=False,
            elapsed_ns=3,
        )
    )
    assert (
        sum(
            len(instrument.calls)
            for instrument in sync_meter.instruments
            if isinstance(instrument, RecordingCounter)
        )
        == 2
    )
    assert (
        sum(
            len(instrument.calls)
            for instrument in async_meter.instruments
            if isinstance(instrument, RecordingCounter)
        )
        == 2
    )
    assert len(coordination_meter.instruments[0].calls) == 1
