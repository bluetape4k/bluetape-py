"""Non-gating real-Redis load-coordination latency and command evidence."""

import json
import platform
import statistics
import sys
import threading
from dataclasses import asdict
from time import perf_counter_ns

import redis
from bluetape.cache import TTLCache
from bluetape.cache.redis import (
    RedisLoadOptions,
    ResultEnvelopeCodec,
    SyncRedisLoadCoordinator,
    SyncRedisProvider,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile
from bluetape.testcontainers import RedisServer

CALLERS = 64
COORDINATORS = 8
COLD_REPETITIONS = 10
LOCAL_REPETITIONS = 1_000
LOCAL_WARMUPS = 100


class BytesCodec:
    def encode(self, value: bytes) -> SerializedPayload:
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="bytes",
                version=1,
                content_type="application/octet-stream",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=value,
        )

    def decode(self, payload: SerializedPayload) -> bytes:
        return payload.data


class Recorder:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.total = 0
        self.acquisitions = 0

    def record(self) -> None:
        with self.condition:
            self.total += 1
            self.condition.notify_all()

    def record_acquisition(self) -> None:
        with self.condition:
            self.total += 1
            self.acquisitions += 1
            self.condition.notify_all()

    def wait_for_acquisitions(self, target: int) -> None:
        with self.condition:
            assert self.condition.wait_for(lambda: self.acquisitions >= target, timeout=5)


class RecordingProvider(SyncRedisProvider):
    def __init__(self, client: redis.Redis, recorder: Recorder) -> None:
        super().__init__(client)
        self.recorder = recorder

    def set_if_absent(self, key: str, value: bytes, *, ttl: float) -> bool:
        self.recorder.record_acquisition()
        return super().set_if_absent(key, value, ttl=ttl)

    def coordination_snapshot(
        self, marker_key, result_key, *, max_marker_size=138, max_result_size
    ):
        self.recorder.record()
        return super().coordination_snapshot(
            marker_key,
            result_key,
            max_marker_size=max_marker_size,
            max_result_size=max_result_size,
        )

    def publish_if_value(self, condition_key, expected_value, **kwargs):
        self.recorder.record()
        return super().publish_if_value(condition_key, expected_value, **kwargs)


def main() -> None:
    """Print one machine-readable benchmark sample without capacity claims."""
    with RedisServer() as server:
        clients = [
            redis.Redis.from_url(
                server.url,
                decode_responses=False,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
                retry_on_timeout=False,
            )
            for _ in range(COORDINATORS)
        ]
        recorder = Recorder()
        providers = [RecordingProvider(client, recorder) for client in clients]
        caches = [TTLCache[str, bytes](default_ttl=60, max_size=100) for _ in providers]
        codec = ResultEnvelopeCodec(payload_codec=BytesCodec())
        coordination_options = RedisLoadOptions(
            namespace="benchmark:test:value-v1",
            lease_ttl=2.0,
            result_ttl=2.0,
            poll_interval=0.001,
            max_poll_interval=0.01,
            wait_timeout=2.0,
            redis_io_timeout=0.4,
        )
        coordinators = [
            SyncRedisLoadCoordinator(cache, provider, codec, options=coordination_options)
            for cache, provider in zip(caches, providers, strict=True)
        ]
        loader_count = 0
        loader_lock = threading.Lock()

        try:
            caches[0].set("local", b"value")
            for _ in range(LOCAL_WARMUPS):
                assert coordinators[0].get_or_load("local", lambda _: b"unused") == b"value"
            local_timings = []
            for _ in range(LOCAL_REPETITIONS):
                started = perf_counter_ns()
                assert coordinators[0].get_or_load("local", lambda _: b"unused") == b"value"
                local_timings.append(perf_counter_ns() - started)

            cold_timings = []
            for iteration in range(COLD_REPETITIONS):
                key = f"cold-{iteration}"
                start_barrier = threading.Barrier(CALLERS)
                owner_release = threading.Event()
                results: list[bytes] = []

                def loader(_: str, release: threading.Event = owner_release) -> bytes:
                    nonlocal loader_count
                    with loader_lock:
                        loader_count += 1
                    assert release.wait(5)
                    return b"value"

                def call(
                    index: int,
                    barrier: threading.Barrier = start_barrier,
                    values: list[bytes] = results,
                    logical_key: str = key,
                    load=loader,
                ) -> None:
                    barrier.wait()
                    values.append(coordinators[index % COORDINATORS].get_or_load(logical_key, load))

                threads = [threading.Thread(target=call, args=(index,)) for index in range(CALLERS)]
                acquisition_target = recorder.acquisitions + COORDINATORS
                started = perf_counter_ns()
                for thread in threads:
                    thread.start()
                recorder.wait_for_acquisitions(acquisition_target)
                owner_release.set()
                for thread in threads:
                    thread.join(10)
                cold_timings.append(perf_counter_ns() - started)
                assert results == [b"value"] * CALLERS

            print(
                json.dumps(
                    {
                        "commands_per_caller": recorder.total / (CALLERS * COLD_REPETITIONS),
                        "contended_cold_burst_median_ns": int(statistics.median(cold_timings)),
                        "loader_count": loader_count,
                        "local_hit_median_ns": int(statistics.median(local_timings)),
                        "metadata": {
                            "callers": CALLERS,
                            "cold_repetitions": COLD_REPETITIONS,
                            "coordinators": COORDINATORS,
                            "local_repetitions": LOCAL_REPETITIONS,
                            "options": asdict(coordination_options),
                            "payload_bytes": len(b"value"),
                            "platform": platform.platform(),
                            "python": sys.version.split()[0],
                            "production_capacity_claim": False,
                        },
                        "redis_commands": recorder.total,
                    },
                    sort_keys=True,
                )
            )
        finally:
            for provider in providers:
                provider.close()
            for client in clients:
                client.close()


if __name__ == "__main__":
    main()
