from dataclasses import FrozenInstanceError, replace
from typing import get_type_hints

import pytest
from bluetape.cache.redis import (
    EnvelopeDecodeError,
    EnvelopeEncodeError,
    EnvelopeError,
    EnvelopeErrorCode,
    EnvelopeFormat,
    EnvelopeSizeError,
    PayloadCodec,
    ProviderClosedError,
    RedisErrorCode,
    RedisEvent,
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
