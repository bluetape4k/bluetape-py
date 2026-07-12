from bluetape.cache.redis import ResultEnvelope
from bluetape.serde import PayloadMetadata, TrustProfile


def sample_metadata(*, content_type: str | None = "application/json") -> PayloadMetadata:
    return PayloadMetadata(
        format="json",
        version=1,
        content_type=content_type,
        trust_profile=TrustProfile.UNTRUSTED,
    )


def sample_envelope(
    *, payload: bytes = b"value", content_type: str | None = "application/json"
) -> ResultEnvelope:
    return ResultEnvelope(
        version=1,
        owner_token="owner-42",
        metadata=sample_metadata(content_type=content_type),
        compression_algorithm="identity",
        payload=payload,
    )
