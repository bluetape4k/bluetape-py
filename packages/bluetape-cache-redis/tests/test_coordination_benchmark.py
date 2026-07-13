import asyncio
import sys
from pathlib import Path

import pytest
from bluetape.cache.redis import RedisCommandPolicy, RedisLoadOptions, SyncRedisProvider
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile

BENCHMARKS = Path(__file__).parents[1] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))

from _coordination_matrix import (  # noqa: E402
    FULL,
    SMOKE,
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


def test_full_registry_has_fixed_safety_totals() -> None:
    assert len(FULL.cases) == 12
    assert matrix_totals(FULL, ("sync", "async")) == MatrixTotals(
        results=24, measured_samples=412, operations=409_944, warmups=72
    )
    validate_profile(FULL, ("sync", "async"))


def test_registry_digest_and_seed_are_stable_vectors() -> None:
    assert registry_digest(SMOKE) == (
        "9e114b562ced345d7c7aab9295ab074173475dc192d25784811f38c37dfd3285"
    )
    case = SMOKE.cases[0]
    assert derived_seed(20260712, "smoke", "sync", case, "measurement", 0) == (
        2_577_118_096_661_857_961
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
            "loader_delay_seconds": 0.005,
            "warmups": 1,
            "repetitions": 5,
        },
        metrics={
            "correctness_loader_count": 1,
            "correctness_redis_commands": 4,
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
        active_result_bytes=0,
        completed_result_bytes=1024 if scenario_id == "completed-reuse" else 0,
        overlap_observed=scenario_id == "unrelated-keys",
    )
    assert all(invariants_for(scenario_id, metrics, coordinators=4, keys=4).values())


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
