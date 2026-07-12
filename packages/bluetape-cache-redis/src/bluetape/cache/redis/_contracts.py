"""Public structural contracts and stable failures for Redis result providers."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from bluetape.serde import PayloadMetadata, SerializedPayload

DEFAULT_MAX_ENCODED_SIZE = 16 * 1024 * 1024
_TOKEN_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._~-")
_ALGORITHM_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_.")


class PayloadCodec[T](Protocol):
    """Encode and decode metadata-bearing payloads under caller-owned policy."""

    def encode(self, value: T) -> SerializedPayload:
        """Encode a value and its caller-owned metadata."""
        ...

    def decode(self, payload: SerializedPayload) -> T:
        """Decode a metadata-bearing payload."""
        ...


class EnvelopeFormat(Protocol):
    """Encode and decode one complete semantic result envelope."""

    @property
    def format_id(self) -> str:
        """Return the stable configuration identifier."""
        ...

    def encode(self, envelope: "ResultEnvelope") -> bytes:
        """Encode one validated envelope."""
        ...

    def decode(self, data: bytes) -> "ResultEnvelope":
        """Decode one complete envelope without fallback."""
        ...


class RedisMode(StrEnum):
    """Provider execution mode."""

    SYNC = "sync"
    ASYNC = "async"


class RedisOperation(StrEnum):
    """Stable Redis provider operation."""

    CREATE = "create"
    GET = "get"
    SET = "set"
    SET_IF_ABSENT = "set-if-absent"
    DELETE = "delete"
    DELETE_IF_VALUE = "delete-if-value"
    CLOSE = "close"


class RedisOutcome(StrEnum):
    """Stable terminal provider outcome."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class RedisErrorCode(StrEnum):
    """Stable machine-readable Redis provider failure."""

    CLOSED = "closed"
    INVALID_INPUT = "invalid-input"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    PROVIDER_FAILURE = "provider-failure"
    INVALID_RESPONSE = "invalid-response"


class EnvelopeErrorCode(StrEnum):
    """Stable machine-readable result-envelope failure."""

    INVALID_INPUT = "invalid-input"
    ENCODED_SIZE_LIMIT = "encoded-size-limit"
    MALFORMED_ENVELOPE = "malformed-envelope"
    UNSUPPORTED_VERSION = "unsupported-version"
    UNSUPPORTED_FORMAT = "unsupported-format"
    UNKNOWN_ALGORITHM = "unknown-algorithm"
    COMPRESSION_FAILURE = "compression-failure"
    PAYLOAD_CODEC_FAILURE = "payload-codec-failure"


def _validate_owner_token(token: object) -> None:
    if type(token) is not str:
        raise TypeError("owner_token must be an exact str")
    if not 1 <= len(token) <= 128 or any(character not in _TOKEN_CHARACTERS for character in token):
        raise ValueError("owner token must be 1..128 allowed ASCII characters")


def _validate_algorithm(algorithm: object) -> None:
    if type(algorithm) is not str:
        raise TypeError("compression_algorithm must be an exact str")
    if not 1 <= len(algorithm) <= 64 or any(
        character not in _ALGORITHM_CHARACTERS for character in algorithm
    ):
        raise ValueError("compression algorithm must be 1..64 allowed ASCII characters")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultEnvelope:
    """Validated versioned result bytes with immutable serialization metadata."""

    version: int
    owner_token: str
    metadata: PayloadMetadata
    compression_algorithm: str
    payload: bytes

    def __post_init__(self) -> None:
        if type(self.version) is not int:
            raise TypeError("version must be an exact int")
        if self.version <= 0:
            raise ValueError("version must be positive")
        _validate_owner_token(self.owner_token)
        if type(self.metadata) is not PayloadMetadata:
            raise TypeError("metadata must be an exact PayloadMetadata")
        _validate_algorithm(self.compression_algorithm)
        if type(self.payload) is not bytes:
            raise TypeError("payload must be exact bytes")


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisEvent:
    """Low-cardinality terminal observation for one provider attempt."""

    mode: RedisMode
    operation: RedisOperation
    outcome: RedisOutcome
    error_code: RedisErrorCode | None
    elapsed_ns: int

    def __post_init__(self) -> None:
        if type(self.mode) is not RedisMode:
            raise TypeError("mode must be an exact RedisMode")
        if type(self.operation) is not RedisOperation:
            raise TypeError("operation must be an exact RedisOperation")
        if type(self.outcome) is not RedisOutcome:
            raise TypeError("outcome must be an exact RedisOutcome")
        if self.error_code is not None and type(self.error_code) is not RedisErrorCode:
            raise TypeError("error_code must be an exact RedisErrorCode or None")
        if type(self.elapsed_ns) is not int:
            raise TypeError("elapsed_ns must be an exact int")
        if self.elapsed_ns < 0:
            raise ValueError("elapsed_ns must be non-negative")


class RedisObserver(Protocol):
    """Receive low-cardinality terminal provider events."""

    def on_event(self, event: RedisEvent) -> None:
        """Observe one terminal provider event."""
        ...


class RedisProviderError(RuntimeError):
    """Report a redacted Redis provider failure with stable fields."""

    def __init__(self, *, operation: RedisOperation, code: RedisErrorCode) -> None:
        if type(operation) is not RedisOperation:
            raise TypeError("operation must be an exact RedisOperation")
        if type(code) is not RedisErrorCode:
            raise TypeError("code must be an exact RedisErrorCode")
        self._operation = operation
        self._code = code
        super().__init__("Redis provider operation failed")

    @property
    def operation(self) -> RedisOperation:
        """Return the failed operation."""
        return self._operation

    @property
    def code(self) -> RedisErrorCode:
        """Return the stable failure code."""
        return self._code


class ProviderClosedError(RedisProviderError):
    """Report local use of a closing or closed provider."""

    def __init__(self, *, operation: RedisOperation) -> None:
        super().__init__(operation=operation, code=RedisErrorCode.CLOSED)
        self.args = ("Redis provider is closed",)


class EnvelopeError(ValueError):
    """Base class for redacted result-envelope failures."""

    _message = "Result envelope operation failed"

    def __init__(self, *, code: EnvelopeErrorCode) -> None:
        if type(code) is not EnvelopeErrorCode:
            raise TypeError("code must be an exact EnvelopeErrorCode")
        self._code = code
        super().__init__(self._message)

    @property
    def code(self) -> EnvelopeErrorCode:
        """Return the stable failure code."""
        return self._code


class EnvelopeSizeError(EnvelopeError):
    """Report an encoded envelope size-limit failure."""

    _message = "Result envelope exceeds the encoded size limit"


class EnvelopeEncodeError(EnvelopeError):
    """Report a redacted envelope encoding failure."""

    _message = "Result envelope encoding failed"


class EnvelopeDecodeError(EnvelopeError):
    """Report a redacted envelope decoding failure."""

    _message = "Result envelope decoding failed"
