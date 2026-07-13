from bluetape.cache.redis import ResultEnvelope
from bluetape.serde import PayloadMetadata, TrustProfile

COORDINATION_SNAPSHOT_SCRIPT = """
local marker_exists = redis.call('exists', KEYS[1])
local marker_length = redis.call('strlen', KEYS[1])
local marker_value = redis.call('getrange', KEYS[1], 0, ARGV[1] - 1)
if string.sub(marker_value, 1, 7) == 'active:' then
  return {marker_exists, marker_length, marker_value, 0, 0, ''}
end
local result_exists = redis.call('exists', KEYS[2])
local result_length = redis.call('strlen', KEYS[2])
local result_value = redis.call('getrange', KEYS[2], 0, ARGV[2] - 1)
return {marker_exists, marker_length, marker_value, result_exists, result_length, result_value}
""".strip()

PUBLISH_IF_VALUE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  redis.call('set', KEYS[2], ARGV[2], 'PX', ARGV[3])
  redis.call('set', KEYS[1], ARGV[4], 'PX', ARGV[3])
  return 1
end
return 0
""".strip()


def bounded_command_options() -> dict[str, object]:
    return {
        "decode_responses": False,
        "socket_connect_timeout": 0.1,
        "socket_timeout": 0.2,
        "retry_on_timeout": False,
        "retry_on_error": [],
    }


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
