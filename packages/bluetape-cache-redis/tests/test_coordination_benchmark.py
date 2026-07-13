import argparse
import asyncio
import json
import signal
import sys
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from bluetape.benchmark import BenchmarkRunIdentity, read_report
from bluetape.cache.redis import (
    RedisCommandPolicy,
    RedisCoordinationSnapshot,
    RedisLoadOptions,
    SyncRedisProvider,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile
from bluetape.testcontainers import StartFailureKind, TestcontainerStartError
from bluetape.testing import eventually, eventually_async

BENCHMARKS = Path(__file__).parents[1] / "benchmarks"
ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(BENCHMARKS))

import _coordination_scenarios as scenario_runtime  # noqa: E402
import _coordination_security as benchmark_security  # noqa: E402
import coordination_benchmark as benchmark_cli  # noqa: E402
from _coordination_matrix import (  # noqa: E402
    FULL,
    SMOKE,
    BenchmarkProfile,
    MatrixTotals,
    derived_seed,
    matrix_totals,
    registry_digest,
    validate_profile,
)
from _coordination_runtime import (  # noqa: E402
    AsyncConvergenceRuntime,
    ChildConfig,
    ChildExecutionError,
    run_sync_case_in_child,
)
from _coordination_scenarios import (  # noqa: E402
    CorrectnessMetrics,
    async_measure_calls,
    invariants_for,
    process_high_water_bytes,
    sync_measure_calls,
)
from _coordination_security import (  # noqa: E402
    MAX_PAYLOAD_BYTES,
    BenchmarkBytesCodec,
    build_envelope_codec,
    load_options,
    make_sync_client,
    policy_digest,
    validate_redis_report_fields,
)
from coordination_benchmark import BenchmarkCliError, exact_int, parser  # noqa: E402


def test_smoke_registry_is_exact() -> None:
    assert [(case.scenario_id, case.case_id, case.repetitions) for case in SMOKE.cases] == [
        ("local-only", "moderate-small-short", 5),
        ("local-hit", "steady-small", 5),
        ("single-coordinator", "moderate-small-short", 5),
        ("multi-coordinator", "moderate-small-short", 5),
        ("completed-reuse", "moderate-small-immediate", 5),
        ("unrelated-keys", "moderate-small-short", 5),
    ]
    assert matrix_totals(SMOKE, ("sync", "async")) == MatrixTotals(
        results=12, measured_samples=60, operations=10_400, warmups=12
    )
    assert all(case.stale_result_bytes == 0 for case in SMOKE.cases)


def test_full_registry_has_fixed_safety_totals() -> None:
    assert len(FULL.cases) == 12
    assert matrix_totals(FULL, ("sync", "async")) == MatrixTotals(
        results=24, measured_samples=412, operations=409_944, warmups=72
    )
    stale_cases = [
        (case.scenario_id, case.case_id, case.stale_result_bytes)
        for case in FULL.cases
        if case.stale_result_bytes
    ]
    assert stale_cases == [("multi-coordinator", "high-medium-short", 65_536)]
    validate_profile(FULL, ("sync", "async"))


def test_registry_digest_and_seed_are_stable_vectors() -> None:
    assert registry_digest(SMOKE) == (
        "fac8eae63c0d6dbeff96cc99827ca1c3d893b53203eb22be1289f85324bfe5e3"
    )
    assert registry_digest(FULL) == (
        "2cc0e4b8700f3678aa51e004acfd966a4fdd363a9b5435459188b039849e5566"
    )
    case = SMOKE.cases[0]
    assert derived_seed(20260712, "smoke", "sync", case, "measurement", 0) == (
        2_577_118_096_661_857_961
    )


def test_stale_result_bytes_requires_an_exact_non_negative_int() -> None:
    case = next(item for item in FULL.cases if item.scenario_id == "multi-coordinator")
    with pytest.raises(TypeError, match="stale_result_bytes must be an exact int"):
        replace(case, stale_result_bytes=True)
    with pytest.raises(ValueError, match="stale_result_bytes must be non-negative"):
        replace(case, stale_result_bytes=-1)


def test_stale_result_fixture_is_bounded_and_requires_multiple_coordinators() -> None:
    case = next(
        item
        for item in FULL.cases
        if item.scenario_id == "multi-coordinator" and item.case_id == "high-medium-short"
    )
    oversized = replace(case, stale_result_bytes=16_777_217)
    with pytest.raises(ValueError, match="stale result ceiling"):
        validate_profile(
            BenchmarkProfile(profile_id="oversized", cases=(oversized,), wall_timeout_seconds=900),
            ("sync",),
        )
    single = replace(
        case,
        scenario_id="single-coordinator",
        coordinators=1,
        stale_result_bytes=1,
    )
    with pytest.raises(ValueError, match="stale result fixture requires multi-coordinator"):
        validate_profile(
            BenchmarkProfile(profile_id="single", cases=(single,), wall_timeout_seconds=900),
            ("sync",),
        )


def test_fixed_policy_matches_provider_discovery() -> None:
    client = make_sync_client("redis://localhost:6379/0")
    provider = SyncRedisProvider(client)
    try:
        assert provider.command_policy == RedisCommandPolicy(
            connect_timeout=0.1, socket_timeout=0.1
        )
        assert load_options("safe:namespace") == RedisLoadOptions(
            namespace="safe:namespace",
            lease_ttl=2.0,
            result_ttl=2.0,
            poll_interval=0.001,
            max_poll_interval=0.01,
            wait_timeout=2.0,
            max_attempts=3,
            max_polls=100,
            redis_io_timeout=0.4,
        )
    finally:
        provider.close()
        client.close()


def payload(
    *,
    data: bytes = b"value",
    trust_profile: TrustProfile = TrustProfile.UNTRUSTED,
) -> SerializedPayload:
    return SerializedPayload(
        metadata=PayloadMetadata(
            format="raw-bytes",
            version=1,
            content_type="application/octet-stream",
            trust_profile=trust_profile,
        ),
        data=data,
    )


def test_bytes_codec_round_trip_and_envelope_bound() -> None:
    codec = BenchmarkBytesCodec()
    assert codec.decode(codec.encode(b"value")) == b"value"
    envelope = build_envelope_codec()
    assert envelope.max_encoded_size == 16_777_216
    match = envelope.decode_matching(
        envelope.encode("a" * 32, b"value"), expected_owner_token="a" * 32
    )
    assert match is not None and match.value == b"value"


def test_bytes_codec_rejects_trusted_or_oversized_payload() -> None:
    codec = BenchmarkBytesCodec()
    with pytest.raises(ValueError, match="benchmark payload metadata mismatch"):
        codec.decode(payload(trust_profile=TrustProfile.TRUSTED_INTERNAL))
    with pytest.raises(ValueError, match="benchmark payload size mismatch"):
        codec.decode(payload(data=b"x" * (MAX_PAYLOAD_BYTES + 1)))


def test_policy_digest_is_stable() -> None:
    assert policy_digest() == "7e7c46760f9c9d04c82f63972e8f7e0ab304710e725b759cb0606d1955bae8ad"


def test_redis_report_field_vocabulary_is_fail_closed() -> None:
    validate_redis_report_fields(
        parameters={
            "case_id": "moderate-small-short",
            "callers": 8,
            "coordinators": 4,
            "keys": 1,
            "payload_bytes": 1024,
            "stale_result_bytes": 0,
            "loader_delay_seconds": 0.005,
            "warmups": 1,
            "repetitions": 5,
        },
        metrics={
            "correctness_loader_count": 1,
            "correctness_redis_commands": 4,
            "correctness_active_snapshot_count": 2,
            "correctness_active_result_bytes": 0,
            "correctness_completed_result_bytes": 1024,
            "correctness_overlap_observed": True,
            "process_high_water_bytes": None,
        },
        extensions={
            "redis_version": "8.0.1",
            "redis_image_digest": "sha256:" + "a" * 64,
            "redis_configuration_profile": "ephemeral-default",
            "coordination_policy_id": "redis-coordination-benchmark-v1",
            "coordination_policy_digest": policy_digest(),
        },
    )
    with pytest.raises(ValueError):
        validate_redis_report_fields(
            parameters={"case_id": "small", "redis_url": "SECRET"},
            metrics={},
            extensions={},
        )
    assert benchmark_security.PARAMETERS == frozenset(
        {
            "case_id",
            "callers",
            "coordinators",
            "keys",
            "payload_bytes",
            "stale_result_bytes",
            "loader_delay_seconds",
            "warmups",
            "repetitions",
        }
    )
    assert benchmark_security.METRICS == frozenset(
        {
            "correctness_loader_count",
            "correctness_redis_commands",
            "correctness_active_snapshot_count",
            "correctness_active_result_bytes",
            "correctness_completed_result_bytes",
            "correctness_overlap_observed",
            "process_high_water_bytes",
        }
    )


def test_sync_measurement_verifies_after_stopping_clock() -> None:
    events: list[str] = []

    def call() -> bytes:
        events.append("call")
        return b"value"

    def verify(values: tuple[bytes, ...]) -> None:
        events.append("verify")
        assert values == (b"value",) * 4

    elapsed = sync_measure_calls((call,) * 4, timeout=1.0, verify=verify)
    assert elapsed > 0
    assert events[-1] == "verify"


@pytest.mark.asyncio
async def test_async_measurement_verifies_after_task_convergence() -> None:
    events: list[str] = []

    async def call() -> bytes:
        events.append("call")
        return b"value"

    def verify(values: tuple[bytes, ...]) -> None:
        events.append("verify")
        assert values == (b"value",) * 4

    elapsed = await async_measure_calls((call,) * 4, timeout=1.0, verify=verify)
    assert elapsed > 0
    assert events[-1] == "verify"


@pytest.mark.parametrize(
    ("scenario_id", "loader_count"),
    [
        ("local-only", 4),
        ("local-hit", 0),
        ("single-coordinator", 1),
        ("multi-coordinator", 1),
        ("completed-reuse", 0),
        ("unrelated-keys", 4),
    ],
)
def test_every_scenario_has_exact_correctness_invariants(
    scenario_id: str, loader_count: int
) -> None:
    metrics = CorrectnessMetrics(
        loader_count=loader_count,
        redis_commands=0,
        active_snapshot_count=0,
        active_result_bytes=0,
        completed_result_bytes=1024 if scenario_id == "completed-reuse" else 0,
        overlap_observed=scenario_id == "unrelated-keys",
    )
    assert all(invariants_for(scenario_id, metrics, coordinators=4, keys=4).values())


def _snapshot(marker: bytes | None, result: bytes | None) -> RedisCoordinationSnapshot:
    return RedisCoordinationSnapshot(
        marker=marker,
        result=result,
        marker_oversized=False,
        result_oversized=False,
    )


def test_recorder_classifies_active_and_completed_result_bytes() -> None:
    recorder = scenario_runtime._Recorder(active_snapshot_target=2)
    snapshots = (
        _snapshot(b"active:owner-a", b"abc"),
        _snapshot(b"active:owner-b", b"12345"),
        _snapshot(b"active:owner-c", None),
        _snapshot(b"completed:owner-a", b"1234567"),
        _snapshot(None, b"ignored"),
    )

    for snapshot in snapshots:
        recorder.snapshot(snapshot)

    assert recorder.commands == 5
    assert recorder.active_snapshot_count == 3
    assert recorder.active_result_bytes == 8
    assert recorder.completed_result_bytes == 7
    assert snapshots[0] == _snapshot(b"active:owner-a", b"abc")


def test_recorder_ignores_result_bytes_for_non_matching_markers() -> None:
    recorder = scenario_runtime._Recorder(active_snapshot_target=2)
    recorder.snapshot(_snapshot(b"invalid-marker", b"ignored"))

    assert recorder.commands == 1
    assert recorder.active_snapshot_count == 0
    assert recorder.active_result_bytes == 0
    assert recorder.completed_result_bytes == 0


def test_sync_active_snapshot_gate_releases_at_exact_boundary() -> None:
    recorder = scenario_runtime._Recorder(active_snapshot_target=2)
    released = threading.Event()

    def wait_for_gate() -> None:
        recorder.wait_for_active_snapshots(timeout=0.5)
        released.set()

    waiter = threading.Thread(target=wait_for_gate, daemon=True)
    waiter.start()
    recorder.snapshot(_snapshot(b"active:owner-a", None))
    assert released.is_set() is False
    recorder.snapshot(_snapshot(b"active:owner-b", None))

    assert eventually(released.is_set, timeout=0.5, interval=0.001) is True
    waiter.join(timeout=0.5)
    assert waiter.is_alive() is False


@pytest.mark.asyncio
async def test_async_active_snapshot_gate_is_bound_to_the_running_loop() -> None:
    recorder = scenario_runtime._Recorder(active_snapshot_target=2)
    released = asyncio.Event()

    async def wait_for_gate() -> None:
        await recorder.wait_for_active_snapshots_async(timeout=0.5)
        released.set()

    waiter = asyncio.create_task(wait_for_gate())
    await asyncio.sleep(0)
    recorder.snapshot(_snapshot(b"active:owner-a", None))
    assert released.is_set() is False
    recorder.snapshot(_snapshot(b"active:owner-b", None))

    async def probe() -> bool:
        return released.is_set()

    assert await eventually_async(probe, timeout=0.5, interval=0.001) is True
    await waiter


def test_sync_loader_overlap_gate_is_deterministic_at_zero_delay() -> None:
    loader = scenario_runtime._SyncLoader(b"", 0.0, overlap_target=2)

    values: tuple[bytes, ...] = ()

    def verify(completed: tuple[bytes, ...]) -> None:
        nonlocal values
        values = completed

    sync_measure_calls((lambda: loader("key"),) * 4, timeout=0.5, verify=verify)

    assert values == (b"",) * 4
    assert loader.count == 4
    assert loader.overlap is True


@pytest.mark.asyncio
async def test_async_loader_overlap_gate_is_deterministic_at_zero_delay() -> None:
    loader = scenario_runtime._AsyncLoader(b"", 0.0, overlap_target=2)

    async def call() -> bytes:
        return await loader("key")

    values: tuple[bytes, ...] = ()

    def verify(completed: tuple[bytes, ...]) -> None:
        nonlocal values
        values = completed

    await async_measure_calls((call,) * 4, timeout=0.5, verify=verify)

    assert values == (b"",) * 4
    assert loader.count == 4
    assert loader.overlap is True


def test_active_snapshot_gate_timeout_has_stable_category() -> None:
    recorder = scenario_runtime._Recorder(active_snapshot_target=2)
    with pytest.raises(scenario_runtime.BenchmarkScenarioError, match="active-snapshot-gate"):
        recorder.wait_for_active_snapshots(timeout=0.001)


def test_stale_result_seed_uses_derived_isolated_key_and_result_ttl() -> None:
    case = next(
        item
        for item in FULL.cases
        if item.scenario_id == "multi-coordinator" and item.case_id == "high-medium-short"
    )
    calls: list[tuple[str, bytes, float]] = []

    class Provider:
        def set(self, key: str, value: bytes, *, ttl: float) -> None:
            calls.append((key, value, ttl))

    namespace = scenario_runtime._namespace("full", "sync", case, "correctness", 0, 20260713)
    warmup_namespace = scenario_runtime._namespace("full", "sync", case, "warmup", 0, 20260713)
    next_warmup_namespace = scenario_runtime._namespace("full", "sync", case, "warmup", 1, 20260713)
    scenario_runtime._seed_sync_stale_result(
        case,
        [Provider()],  # type: ignore[list-item]
        namespace,
    )

    assert calls == [
        (
            scenario_runtime._stale_result_key(namespace),
            b"s" * 65_536,
            load_options(namespace).result_ttl,
        )
    ]
    assert len({namespace, warmup_namespace, next_warmup_namespace}) == 3
    assert scenario_runtime._stale_result_key(namespace) != scenario_runtime._stale_result_key(
        warmup_namespace
    )


def test_sync_stale_seed_precedes_measurement_clock(monkeypatch) -> None:
    case = next(
        item
        for item in FULL.cases
        if item.scenario_id == "multi-coordinator" and item.case_id == "high-medium-short"
    )
    events: list[str] = []

    class Coordinator:
        def __init__(self, cache, provider, codec, *, options) -> None:
            del cache, provider, codec, options

        def get_or_load(self, key: str, loader) -> bytes:
            return loader(key)

    def seed(*_args) -> None:
        events.append("seed")

    def measure(calls, *, timeout, verify) -> int:
        del timeout
        events.append("clock")
        values = tuple(call() for call in calls)
        verify(values)
        return 1

    monkeypatch.setattr(scenario_runtime, "SyncRedisLoadCoordinator", Coordinator)
    monkeypatch.setattr(scenario_runtime, "_seed_sync_stale_result", seed)
    monkeypatch.setattr(scenario_runtime, "sync_measure_calls", measure)

    result = scenario_runtime._sync_repetition(
        case,
        [object()] * case.coordinators,  # type: ignore[list-item]
        "benchmark:sync",
        b"value",
        lambda _key: b"value",
        timeout=1.0,
    )
    assert result == 1
    assert events[:2] == ["seed", "clock"]


@pytest.mark.asyncio
async def test_async_stale_seed_precedes_measurement_clock(monkeypatch) -> None:
    case = next(
        item
        for item in FULL.cases
        if item.scenario_id == "multi-coordinator" and item.case_id == "high-medium-short"
    )
    events: list[str] = []

    class Coordinator:
        def __init__(self, cache, provider, codec, *, options) -> None:
            del cache, provider, codec, options

        async def get_or_load(self, key: str, loader) -> bytes:
            return await loader(key)

    async def seed(*_args) -> None:
        events.append("seed")

    async def measure(calls, *, timeout, verify) -> int:
        del timeout
        events.append("clock")
        values = tuple([await call() for call in calls])
        verify(values)
        return 1

    async def loader(_key: str) -> bytes:
        return b"value"

    monkeypatch.setattr(scenario_runtime, "AsyncRedisLoadCoordinator", Coordinator)
    monkeypatch.setattr(scenario_runtime, "_seed_async_stale_result", seed)
    monkeypatch.setattr(scenario_runtime, "async_measure_calls", measure)

    result = await scenario_runtime._async_repetition(
        case,
        [object()] * case.coordinators,  # type: ignore[list-item]
        "benchmark:async",
        b"value",
        loader,
        timeout=1.0,
    )
    assert result == 1
    assert events[:2] == ["seed", "clock"]


def test_recording_provider_does_not_count_fixture_set(monkeypatch) -> None:
    recorder = scenario_runtime._Recorder(active_snapshot_target=2)
    provider = object.__new__(scenario_runtime._RecordingSyncProvider)
    provider._recorder = recorder
    monkeypatch.setattr(SyncRedisProvider, "set", lambda *_args, **_kwargs: None)

    provider.set("result-key", b"stale", ttl=2.0)

    assert recorder.commands == 0


def test_stale_result_invariant_requires_two_active_snapshots() -> None:
    metrics = CorrectnessMetrics(
        loader_count=1,
        redis_commands=4,
        active_snapshot_count=1,
        active_result_bytes=65_536,
        completed_result_bytes=0,
        overlap_observed=False,
    )
    failed = invariants_for(
        "multi-coordinator",
        metrics,
        coordinators=8,
        keys=1,
        stale_result_bytes=65_536,
    )
    assert failed["multiple_active_snapshots"] is False

    passed = invariants_for(
        "multi-coordinator",
        replace(metrics, active_snapshot_count=2),
        coordinators=8,
        keys=1,
        stale_result_bytes=65_536,
    )
    assert passed["multiple_active_snapshots"] is True


def test_process_high_water_is_nullable_or_positive() -> None:
    value = process_high_water_bytes()
    assert value is None or value > 0


def _non_converging_child(sender, config) -> None:
    del sender, config
    while True:
        pass


def test_sync_timeout_terminates_spawned_child() -> None:
    config = ChildConfig(
        redis_url="redis://127.0.0.1:1/0",
        profile_id="smoke",
        scenario_id="local-only",
        case_id="moderate-small-short",
        seed=1,
    )
    with pytest.raises(ChildExecutionError) as raised:
        run_sync_case_in_child(
            config,
            wall_timeout_seconds=0.05,
            cleanup_timeout=0.01,
            terminate_timeout=0.5,
            kill_timeout=0.5,
            _target=_non_converging_child,
        )
    assert raised.value.category == "live-worker"
    assert raised.value.events[0] == "abort"
    assert raised.value.events[-1] == "join"


@pytest.mark.asyncio
async def test_repeated_cancellation_reuses_one_shielded_cleanup() -> None:
    operation_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    cleanup_release = asyncio.Event()

    async def operation() -> None:
        operation_started.set()
        await asyncio.Event().wait()

    async def cleanup() -> None:
        cleanup_started.set()
        await cleanup_release.wait()

    runtime = AsyncConvergenceRuntime(operation, cleanup=cleanup)
    task = asyncio.create_task(runtime.run())
    await operation_started.wait()
    task.cancel()
    await cleanup_started.wait()
    task.cancel()
    cleanup_release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runtime.cleanup_task_creations == 1
    assert runtime.pending_owned_tasks == ()


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_replace_first_cancellation() -> None:
    started = asyncio.Event()

    async def operation() -> None:
        started.set()
        await asyncio.Event().wait()

    async def cleanup() -> None:
        raise RuntimeError("SECRET_SENTINEL")

    runtime = AsyncConvergenceRuntime(operation, cleanup=cleanup)
    task = asyncio.create_task(runtime.run())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runtime.cleanup_failed is True


@pytest.mark.asyncio
async def test_partial_async_resource_failure_closes_every_client(monkeypatch) -> None:
    clients = []

    class Client:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.closed = False

        async def ping(self) -> None:
            if self.fail:
                raise RuntimeError("redis failed")

        async def aclose(self) -> None:
            self.closed = True

    def client_factory(_url: str):
        client = Client(fail=len(clients) == 1)
        clients.append(client)
        return client

    monkeypatch.setattr(scenario_runtime, "make_async_client", client_factory)
    with pytest.raises(RuntimeError, match="redis failed"):
        await scenario_runtime._async_resources("redis://private", 2, recorder=None)
    assert len(clients) == 2
    assert all(client.closed for client in clients)


@pytest.mark.asyncio
async def test_async_client_factory_failure_closes_prior_clients(monkeypatch) -> None:
    class Client:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    first = Client()
    calls = 0

    def client_factory(_url: str):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("factory failed")
        return first

    monkeypatch.setattr(scenario_runtime, "make_async_client", client_factory)
    with pytest.raises(RuntimeError, match="factory failed"):
        await scenario_runtime._async_resources("redis://private", 2, recorder=None)
    assert first.closed is True


def test_sync_client_factory_failure_closes_prior_clients(monkeypatch) -> None:
    class Client:
        closed = False

        def close(self) -> None:
            self.closed = True

    first = Client()
    calls = 0

    def client_factory(_url: str):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("factory failed")
        return first

    monkeypatch.setattr(scenario_runtime, "make_sync_client", client_factory)
    with pytest.raises(RuntimeError, match="factory failed"):
        scenario_runtime._sync_resources("redis://private", 2, recorder=None)
    assert first.closed is True


@pytest.mark.asyncio
async def test_async_acquisition_cleanup_signal_overrides_primary_failure(monkeypatch) -> None:
    class Client:
        async def ping(self) -> None:
            raise RuntimeError("ping failed")

        async def aclose(self) -> None:
            raise benchmark_cli._SignalInterrupt(signal.SIGINT)

    monkeypatch.setattr(scenario_runtime, "make_async_client", lambda _url: Client())
    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        await scenario_runtime._async_resources("redis://private", 1, recorder=None)
    assert raised.value.signum == signal.SIGINT


def test_sync_acquisition_cleanup_signal_overrides_primary_failure(monkeypatch) -> None:
    class Client:
        def ping(self) -> None:
            raise RuntimeError("ping failed")

        def close(self) -> None:
            raise benchmark_cli._SignalInterrupt(signal.SIGTERM)

    monkeypatch.setattr(scenario_runtime, "make_sync_client", lambda _url: Client())
    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        scenario_runtime._sync_resources("redis://private", 1, recorder=None)
    assert raised.value.signum == signal.SIGTERM


@pytest.mark.asyncio
async def test_async_cleanup_closes_clients_after_provider_failure() -> None:
    class Provider:
        async def aclose(self) -> None:
            raise RuntimeError("provider close failed")

    class Client:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    client = Client()
    with pytest.raises(RuntimeError, match="provider close failed"):
        await scenario_runtime._close_async([client], [Provider()])  # type: ignore[list-item]
    assert client.closed is True


@pytest.mark.asyncio
async def test_async_cleanup_failure_preserves_primary_cancellation() -> None:
    class Provider:
        async def aclose(self) -> None:
            raise RuntimeError("provider close failed")

    primary = asyncio.CancelledError()
    await scenario_runtime._close_async_preserving(
        [],
        [Provider()],
        primary,  # type: ignore[list-item]
    )
    assert primary.__notes__ == ["benchmark resource cleanup also failed"]


@pytest.mark.asyncio
async def test_signal_during_scenario_cleanup_overrides_prior_failure() -> None:
    class Provider:
        async def aclose(self) -> None:
            raise benchmark_cli._SignalInterrupt(signal.SIGTERM)

    primary = RuntimeError("provider failed")
    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        await scenario_runtime._close_async_preserving(
            [],
            [Provider()],
            primary,  # type: ignore[list-item]
        )
    assert raised.value.signum == signal.SIGTERM


@pytest.mark.asyncio
async def test_later_async_cleanup_signal_overrides_earlier_close_failure() -> None:
    class FailedProvider:
        async def aclose(self) -> None:
            raise RuntimeError("close failed")

    class InterruptedProvider:
        async def aclose(self) -> None:
            raise benchmark_cli._SignalInterrupt(signal.SIGINT)

    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        await scenario_runtime._close_async(
            [],
            [FailedProvider(), InterruptedProvider()],  # type: ignore[list-item]
        )
    assert raised.value.signum == signal.SIGINT


def test_later_sync_cleanup_signal_overrides_earlier_close_failure() -> None:
    class FailedProvider:
        def close(self) -> None:
            raise RuntimeError("close failed")

    class InterruptedProvider:
        def close(self) -> None:
            raise benchmark_cli._SignalInterrupt(signal.SIGTERM)

    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        scenario_runtime._close_sync(
            [],
            [FailedProvider(), InterruptedProvider()],  # type: ignore[list-item]
        )
    assert raised.value.signum == signal.SIGTERM


def test_cli_requires_seed_and_complete_pair_fields() -> None:
    with pytest.raises(BenchmarkCliError) as raised:
        parser().parse_args(["--profile", "smoke", "--output", "-"])
    assert raised.value.category == "input-invalid"
    arguments = parser().parse_args(
        [
            "--profile",
            "full",
            "--output",
            "-",
            "--seed",
            "1",
            "--role",
            "baseline",
        ]
    )
    assert arguments.runner_id is None


def test_main_parse_failure_emits_one_exact_redacted_record(capsys) -> None:
    assert benchmark_cli.main(["--profile", "smoke", "--output", "-"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    prefix = "bluetape-benchmark-error "
    assert captured.err.startswith(prefix)
    assert json.loads(captured.err.removeprefix(prefix)) == {
        "case_id": None,
        "category": "input-invalid",
        "code": "BTBENCH_INPUT_INVALID",
        "mode": None,
        "phase": None,
        "repetition": None,
        "scenario_id": None,
    }


@pytest.mark.parametrize("value", ["+1", "01", "1.0", " 1", "1 "])
def test_exact_int_rejects_noncanonical_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        exact_int(value)


def test_cli_diagnostic_has_only_fixed_safe_fields() -> None:
    error = BenchmarkCliError("provider-failed", mode="sync", scenario_id="local-hit")
    assert str(error) == "provider-failed"
    assert error.code == "BTBENCH_PROVIDER_FAILED"
    assert error.exit_code == 3


@pytest.mark.parametrize(
    ("kind", "category"),
    [
        (StartFailureKind.RUNTIME_UNAVAILABLE, "docker-unavailable"),
        (StartFailureKind.IMAGE_PULL, "redis-startup"),
        (StartFailureKind.READINESS_TIMEOUT, "redis-startup"),
        (StartFailureKind.WRAPPER_FAILURE, "redis-startup"),
    ],
)
def test_startup_failure_kind_has_stable_category(kind, category: str) -> None:
    class Server:
        def start(self) -> None:
            raise TestcontainerStartError(kind, "redis:8")

    with pytest.raises(BenchmarkCliError) as raised:
        benchmark_cli._start_server(Server())  # type: ignore[arg-type]
    assert raised.value.category == category
    assert raised.value.exit_code == 5


def test_cleanup_failure_preserves_primary_error() -> None:
    class Server:
        def close(self) -> None:
            raise RuntimeError("SECRET_SENTINEL")

    primary = BenchmarkCliError("provider-failed")
    benchmark_cli._close_server(Server(), primary)  # type: ignore[arg-type]
    assert primary.__notes__ == ["benchmark cleanup also failed"]
    with pytest.raises(BenchmarkCliError) as raised:
        benchmark_cli._close_server(Server(), None)  # type: ignore[arg-type]
    assert raised.value.category == "cleanup-failed"
    assert raised.value.exit_code == 3


def test_first_signal_during_server_cleanup_retries_then_preserves_signal() -> None:
    class Server:
        calls = 0

        def close(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise benchmark_cli._SignalInterrupt(signal.SIGINT)

    server = Server()
    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        benchmark_cli._close_server(server, None)  # type: ignore[arg-type]
    assert raised.value.signum == signal.SIGINT
    assert server.calls == 2


def test_first_signal_wins_when_server_cleanup_retry_fails() -> None:
    class Server:
        calls = 0

        def close(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise benchmark_cli._SignalInterrupt(signal.SIGINT)
            raise RuntimeError("cleanup failed")

    server = Server()
    with pytest.raises(benchmark_cli._SignalInterrupt) as raised:
        benchmark_cli._close_server(server, None)  # type: ignore[arg-type]
    assert raised.value.signum == signal.SIGINT
    assert raised.value.__notes__ == ["benchmark cleanup also failed"]
    assert server.calls == 2


def test_main_redacts_unexpected_internal_failure(monkeypatch, capsys) -> None:
    def fail(_arguments) -> None:
        raise RuntimeError("SECRET_SENTINEL")

    monkeypatch.setattr(benchmark_cli, "preflight", fail)
    result = benchmark_cli.main(["--profile", "smoke", "--output", "-", "--seed", "1"])
    captured = capsys.readouterr()
    assert result == 3
    assert captured.out == ""
    assert captured.err.startswith("bluetape-benchmark-error ")
    assert "SECRET_SENTINEL" not in captured.err
    assert '"phase":null' in captured.err


def test_checked_issue_65_artifact_is_clean_smoke_report() -> None:
    report = read_report(ROOT / "docs/review/artifacts/issue-65-redis-coordination-benchmark.json")
    assert report.schema_version == 1
    assert report.profile == "smoke"
    assert report.environment.source_dirty is False
    assert report.run == BenchmarkRunIdentity(mode_order=("sync", "async"))
    assert len(report.scenarios) == 12
    assert report.production_capacity_claim is False
