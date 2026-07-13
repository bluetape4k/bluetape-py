"""Redis benchmark policy, payload, and report security boundaries."""

import hashlib
import json
import math
from collections.abc import Mapping

import redis
import redis.asyncio as redis_async
from bluetape.cache.redis import (
    BinaryEnvelopeFormat,
    RedisLoadOptions,
    ResultEnvelopeCodec,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile

POLICY_ID = "redis-coordination-benchmark-v1"
MAX_PAYLOAD_BYTES = 15_728_640
MAX_ENCODED_SIZE = 16_777_216

CLIENT_OPTIONS = {
    "decode_responses": False,
    "socket_connect_timeout": 0.1,
    "socket_timeout": 0.1,
    "retry_on_timeout": False,
    "retry_on_error": (),
    "retry": None,
    "max_connections": 128,
}

PARAMETERS = frozenset(
    {
        "case_id",
        "callers",
        "coordinators",
        "keys",
        "payload_bytes",
        "loader_delay_seconds",
        "warmups",
        "repetitions",
    }
)
METRICS = frozenset(
    {
        "correctness_loader_count",
        "correctness_redis_commands",
        "correctness_active_result_bytes",
        "correctness_completed_result_bytes",
        "correctness_overlap_observed",
        "process_high_water_bytes",
    }
)
EXTENSIONS = frozenset(
    {
        "redis_version",
        "redis_image_digest",
        "redis_configuration_profile",
        "coordination_policy_id",
        "coordination_policy_digest",
    }
)


class BenchmarkBytesCodec:
    """Strict raw-bytes codec for ephemeral benchmark payloads."""

    def encode(self, value: bytes) -> SerializedPayload:
        if type(value) is not bytes:
            raise TypeError("benchmark value must be exact bytes")
        if len(value) > MAX_PAYLOAD_BYTES:
            raise ValueError("benchmark payload size mismatch")
        return SerializedPayload(
            metadata=PayloadMetadata(
                format="raw-bytes",
                version=1,
                content_type="application/octet-stream",
                trust_profile=TrustProfile.UNTRUSTED,
            ),
            data=value,
        )

    def decode(self, payload: SerializedPayload) -> bytes:
        if type(payload) is not SerializedPayload:
            raise TypeError("benchmark payload must be exact SerializedPayload")
        metadata = payload.metadata
        if (
            metadata.format != "raw-bytes"
            or metadata.version != 1
            or metadata.content_type != "application/octet-stream"
            or metadata.trust_profile is not TrustProfile.UNTRUSTED
        ):
            raise ValueError("benchmark payload metadata mismatch")
        if len(payload.data) > MAX_PAYLOAD_BYTES:
            raise ValueError("benchmark payload size mismatch")
        return payload.data


def make_sync_client(url: str) -> redis.Redis:
    if type(url) is not str:
        raise TypeError("url must be an exact str")
    return redis.Redis.from_url(url, **CLIENT_OPTIONS)


def make_async_client(url: str) -> redis_async.Redis:
    if type(url) is not str:
        raise TypeError("url must be an exact str")
    return redis_async.Redis.from_url(url, **CLIENT_OPTIONS)


def load_options(namespace: str) -> RedisLoadOptions:
    return RedisLoadOptions(
        namespace=namespace,
        lease_ttl=2.0,
        result_ttl=2.0,
        poll_interval=0.001,
        max_poll_interval=0.01,
        wait_timeout=2.0,
        max_attempts=3,
        max_polls=100,
        redis_io_timeout=0.4,
    )


def build_envelope_codec() -> ResultEnvelopeCodec[bytes]:
    return ResultEnvelopeCodec(
        payload_codec=BenchmarkBytesCodec(),
        envelope_format=BinaryEnvelopeFormat(max_encoded_size=MAX_ENCODED_SIZE),
        max_encoded_size=MAX_ENCODED_SIZE,
    )


def _policy_value() -> dict[str, object]:
    return {
        "client": {
            "decode_responses": False,
            "max_connections": 128,
            "retry": None,
            "retry_on_error": [],
            "retry_on_timeout": False,
            "socket_connect_timeout": 0.1,
            "socket_timeout": 0.1,
        },
        "codec": {
            "compression": None,
            "format": "binary-v1",
            "max_encoded_size": MAX_ENCODED_SIZE,
            "max_payload_bytes": MAX_PAYLOAD_BYTES,
            "readers": [],
        },
        "load_options": {
            "lease_ttl": 2.0,
            "max_attempts": 3,
            "max_poll_interval": 0.01,
            "max_polls": 100,
            "poll_interval": 0.001,
            "redis_io_timeout": 0.4,
            "result_ttl": 2.0,
            "wait_timeout": 2.0,
        },
        "policy_id": POLICY_ID,
    }


def policy_digest() -> str:
    encoded = json.dumps(
        _policy_value(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_scalar(value: object) -> None:
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is str and 0 < len(value) <= 128 and value.isascii() and value.isprintable():
        return
    raise ValueError("Redis benchmark report scalar is invalid")


def _validate_fields(values: Mapping[str, object], expected: frozenset[str], label: str) -> None:
    if set(values) != expected:
        raise ValueError(f"Redis benchmark {label} fields do not match the allowlist")
    for value in values.values():
        _validate_scalar(value)


def validate_redis_report_fields(
    *,
    parameters: Mapping[str, object],
    metrics: Mapping[str, object],
    extensions: Mapping[str, object],
) -> None:
    _validate_fields(parameters, PARAMETERS, "parameter")
    _validate_fields(metrics, METRICS, "metric")
    _validate_fields(extensions, EXTENSIONS, "extension")


__all__ = [
    "MAX_PAYLOAD_BYTES",
    "BenchmarkBytesCodec",
    "build_envelope_codec",
    "load_options",
    "make_async_client",
    "make_sync_client",
    "policy_digest",
    "validate_redis_report_fields",
]
