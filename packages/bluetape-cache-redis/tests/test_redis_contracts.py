"""Redis provider public contract tests."""

from dataclasses import FrozenInstanceError, replace
from typing import get_type_hints

import pytest
from bluetape.cache.redis import (
    MAX_COORDINATION_MARKER_SIZE,
    EnvelopeDecodeError,
    EnvelopeEncodeError,
    EnvelopeError,
    EnvelopeErrorCode,
    EnvelopeFormat,
    EnvelopeSizeError,
    PayloadCodec,
    ProviderClosedError,
    RedisCommandPolicy,
    RedisCoordinationError,
    RedisCoordinationErrorCode,
    RedisCoordinationEvent,
    RedisCoordinationOperation,
    RedisCoordinationOutcome,
    RedisCoordinationSnapshot,
    RedisCoordinationTimeoutError,
    RedisErrorCode,
    RedisEvent,
    RedisLoadOptions,
    RedisMode,
    RedisOperation,
    RedisOutcome,
    RedisProviderError,
    ResultEnvelope,
)
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile


@pytest.fixture
def metadata() -> PayloadMetadata:
    return PayloadMetadata(
        format="json",
        version=1,
        content_type="application/json",
        trust_profile=TrustProfile.UNTRUSTED,
    )


def test_public_exports_are_ordered_and_exact() -> None:
    import bluetape.cache.redis as redis_api

    assert redis_api.__all__ == [
        "DEFAULT_MAX_ENCODED_SIZE",
        "PayloadCodec",
        "EnvelopeFormat",
        "ResultEnvelope",
        "RedisMode",
        "RedisOperation",
        "RedisOutcome",
        "RedisErrorCode",
        "EnvelopeErrorCode",
        "RedisEvent",
        "RedisObserver",
        "RedisProviderError",
        "ProviderClosedError",
        "EnvelopeError",
        "EnvelopeSizeError",
        "EnvelopeEncodeError",
        "EnvelopeDecodeError",
        "BinaryEnvelopeFormat",
        "JsonEnvelopeFormat",
        "ResultEnvelopeCodec",
        "SyncRedisProvider",
        "AsyncRedisProvider",
        "RedisCommandPolicy",
        "ResultEnvelopeMatch",
        "MAX_COORDINATION_MARKER_SIZE",
        "RedisCoordinationSnapshot",
        "RedisCoordinationOperation",
        "RedisCoordinationOutcome",
        "RedisCoordinationErrorCode",
        "RedisCoordinationEvent",
        "RedisCoordinationObserver",
        "RedisCoordinationError",
        "RedisCoordinationTimeoutError",
        "RedisLoadOptions",
        "SyncRedisLoadCoordinator",
    ]


def test_payload_codec_and_envelope_format_are_structural_protocols() -> None:
    assert PayloadCodec._is_protocol is True
    assert EnvelopeFormat._is_protocol is True
    assert not getattr(PayloadCodec, "_is_runtime_protocol", False)
    assert not getattr(EnvelopeFormat, "_is_runtime_protocol", False)
    assert get_type_hints(PayloadCodec.encode)["return"] is SerializedPayload
    assert get_type_hints(EnvelopeFormat.encode)["return"] is bytes
    assert get_type_hints(EnvelopeFormat.decode)["return"] is ResultEnvelope


def test_result_envelope_is_frozen_slotted_and_validated(metadata: PayloadMetadata) -> None:
    envelope = ResultEnvelope(
        version=1,
        owner_token="owner-42",
        metadata=metadata,
        compression_algorithm="identity",
        payload=b"value",
    )

    assert not hasattr(envelope, "__dict__")
    with pytest.raises(FrozenInstanceError):
        envelope.payload = b"other"  # type: ignore[misc]
    with pytest.raises(ValueError, match="owner token"):
        replace(envelope, owner_token="")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", True, "version"),
        ("owner_token", b"owner", "owner_token"),
        ("metadata", object(), "metadata"),
        ("compression_algorithm", b"identity", "compression_algorithm"),
        ("payload", bytearray(), "payload"),
    ],
)
def test_result_envelope_rejects_non_exact_field_types(
    metadata: PayloadMetadata, field: str, value: object, message: str
) -> None:
    values: dict[str, object] = {
        "version": 1,
        "owner_token": "owner-42",
        "metadata": metadata,
        "compression_algorithm": "identity",
        "payload": b"",
    }
    values[field] = value

    with pytest.raises(TypeError, match=message):
        ResultEnvelope(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("token", [" owner", "owner ", "owner/token", "한글", "x" * 129])
def test_result_envelope_rejects_invalid_owner_tokens(
    metadata: PayloadMetadata, token: str
) -> None:
    with pytest.raises(ValueError, match="owner token"):
        ResultEnvelope(
            version=1,
            owner_token=token,
            metadata=metadata,
            compression_algorithm="identity",
            payload=b"",
        )


def test_stable_enum_values_are_exact() -> None:
    assert [item.value for item in RedisMode] == ["sync", "async"]
    assert [item.value for item in RedisOperation] == [
        "create",
        "get",
        "set",
        "set-if-absent",
        "delete",
        "delete-if-value",
        "coordination-snapshot",
        "publish-if-value",
        "close",
    ]
    assert [item.value for item in RedisOutcome] == ["success", "failure", "cancelled"]
    assert [item.value for item in RedisErrorCode] == [
        "closed",
        "invalid-input",
        "connection",
        "timeout",
        "provider-failure",
        "invalid-response",
    ]
    assert [item.value for item in EnvelopeErrorCode] == [
        "invalid-input",
        "encoded-size-limit",
        "malformed-envelope",
        "unsupported-version",
        "unsupported-format",
        "unknown-algorithm",
        "compression-failure",
        "payload-codec-failure",
    ]


def test_redis_event_is_frozen_slotted_and_low_cardinality() -> None:
    event = RedisEvent(
        mode=RedisMode.SYNC,
        operation=RedisOperation.GET,
        outcome=RedisOutcome.SUCCESS,
        error_code=None,
        elapsed_ns=7,
    )
    assert not hasattr(event, "__dict__")
    assert tuple(event.__slots__) == (
        "mode",
        "operation",
        "outcome",
        "error_code",
        "elapsed_ns",
    )


def test_redis_provider_errors_use_static_redacted_messages() -> None:
    error = RedisProviderError(
        operation=RedisOperation.GET,
        code=RedisErrorCode.PROVIDER_FAILURE,
    )
    assert str(error) == "Redis provider operation failed"
    assert repr(error) == "RedisProviderError('Redis provider operation failed')"
    assert error.operation is RedisOperation.GET
    assert error.code is RedisErrorCode.PROVIDER_FAILURE

    closed = ProviderClosedError(operation=RedisOperation.SET)
    assert str(closed) == "Redis provider is closed"
    assert closed.code is RedisErrorCode.CLOSED


@pytest.mark.parametrize(
    ("error_type", "code"),
    [
        (EnvelopeSizeError, EnvelopeErrorCode.ENCODED_SIZE_LIMIT),
        (EnvelopeEncodeError, EnvelopeErrorCode.PAYLOAD_CODEC_FAILURE),
        (EnvelopeDecodeError, EnvelopeErrorCode.MALFORMED_ENVELOPE),
    ],
)
def test_envelope_errors_expose_only_stable_codes(
    error_type: type[EnvelopeError], code: EnvelopeErrorCode
) -> None:
    error = error_type(code=code)
    assert error.code is code
    assert code.value not in repr(error)
    assert "envelope" in str(error).lower()


def test_redis_command_policy_is_exact_immutable_and_bounded() -> None:
    policy = RedisCommandPolicy(connect_timeout=0.25, socket_timeout=0.75)
    assert policy.max_command_time == 1.0
    assert policy.max_retries == 0
    assert not hasattr(policy, "__dict__")
    with pytest.raises(FrozenInstanceError):
        policy.socket_timeout = 1.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        RedisCommandPolicy(connect_timeout=True, socket_timeout=1.0)
    with pytest.raises(ValueError):
        RedisCommandPolicy(connect_timeout=1.0, socket_timeout=1.0, max_retries=1)


def test_coordination_snapshot_is_bounded_immutable_data() -> None:
    snapshot = RedisCoordinationSnapshot(
        marker=b"active:owner",
        result=None,
        marker_oversized=False,
        result_oversized=False,
    )
    assert MAX_COORDINATION_MARKER_SIZE == 138
    assert not hasattr(snapshot, "__dict__")
    with pytest.raises(TypeError):
        replace(snapshot, marker_oversized=1)


def test_coordination_enums_are_stable_and_ordered() -> None:
    assert [item.value for item in RedisCoordinationOperation] == ["get-or-load"]
    assert [item.value for item in RedisCoordinationOutcome] == [
        "loaded",
        "result-reused",
        "lease-lost",
        "timeout",
        "failure",
        "cancelled",
    ]
    assert [item.value for item in RedisCoordinationErrorCode] == [
        "attempts-exhausted",
        "polls-exhausted",
        "deadline-exceeded",
        "invalid-artifact",
        "provider-failure",
        "envelope-failure",
        "loader-failure",
        "cleanup-failure",
    ]


def test_coordination_event_and_errors_are_exact_and_redacted() -> None:
    event = RedisCoordinationEvent(
        mode=RedisMode.SYNC,
        operation=RedisCoordinationOperation.GET_OR_LOAD,
        outcome=RedisCoordinationOutcome.LOADED,
        error_code=None,
        attempts=1,
        polls=0,
        cleanup_failed=False,
        elapsed_ns=7,
    )
    assert not hasattr(event, "__dict__")
    with pytest.raises(ValueError):
        replace(event, polls=-1)
    with pytest.raises(TypeError):
        replace(event, cleanup_failed=0)

    failure = RedisCoordinationError(code=RedisCoordinationErrorCode.PROVIDER_FAILURE)
    assert str(failure) == "Redis load coordination failed"
    assert failure.code is RedisCoordinationErrorCode.PROVIDER_FAILURE
    timeout = RedisCoordinationTimeoutError(code=RedisCoordinationErrorCode.DEADLINE_EXCEEDED)
    assert str(timeout) == "Redis load coordination timed out"
    with pytest.raises(ValueError):
        RedisCoordinationTimeoutError(code=RedisCoordinationErrorCode.PROVIDER_FAILURE)


def test_load_options_validate_exact_bounds_and_relationships() -> None:
    options = RedisLoadOptions(namespace="orders:prod:tenant-a:order-v3")
    assert options.lease_ttl == 5.0
    assert options.result_ttl == 1.0
    assert options.max_attempts == 3
    assert options.max_polls == 100
    assert not hasattr(options, "__dict__")

    with pytest.raises(TypeError):
        replace(options, max_polls=True)
    with pytest.raises(ValueError):
        replace(options, namespace=" ")
    with pytest.raises(ValueError):
        replace(options, namespace="가" * 86)
    with pytest.raises(ValueError):
        replace(options, poll_interval=0.000_9)
    with pytest.raises(ValueError):
        replace(options, max_poll_interval=options.result_ttl + 0.001)
    with pytest.raises(ValueError):
        replace(options, redis_io_timeout=3600.1)
