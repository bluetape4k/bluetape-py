"""Public structural contracts and stable failures for Redis result providers."""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from bluetape.serde import PayloadMetadata, SerializedPayload

DEFAULT_MAX_ENCODED_SIZE = 16 * 1024 * 1024
MAX_COORDINATION_MARKER_SIZE = 138
_MAX_COORDINATION_DURATION = 3600.0
_MIN_POLL_INTERVAL = 0.001
_MAX_POLL_BUDGET = 10_000
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
    COORDINATION_SNAPSHOT = "coordination-snapshot"
    PUBLISH_IF_VALUE = "publish-if-value"
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


class RedisCoordinationOperation(StrEnum):
    """Stable public load-coordination operation."""

    GET_OR_LOAD = "get-or-load"


class RedisCoordinationOutcome(StrEnum):
    """Stable terminal outcome for one cache-owned distributed flight."""

    LOADED = "loaded"
    RESULT_REUSED = "result-reused"
    LEASE_LOST = "lease-lost"
    TIMEOUT = "timeout"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class RedisCoordinationErrorCode(StrEnum):
    """Stable machine-readable load-coordination failure."""

    ATTEMPTS_EXHAUSTED = "attempts-exhausted"
    POLLS_EXHAUSTED = "polls-exhausted"
    DEADLINE_EXCEEDED = "deadline-exceeded"
    INVALID_ARTIFACT = "invalid-artifact"
    PROVIDER_FAILURE = "provider-failure"
    ENVELOPE_FAILURE = "envelope-failure"
    LOADER_FAILURE = "loader-failure"
    CLEANUP_FAILURE = "cleanup-failure"


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
class ResultEnvelopeMatch[T]:
    """Distinguish a matching decoded value from an owner-token mismatch."""

    value: T


def _finite_positive(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a real number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisCommandPolicy:
    """Finite no-retry command bounds inspected from a Redis connection pool."""

    connect_timeout: float
    socket_timeout: float
    max_retries: int = 0

    def __post_init__(self) -> None:
        _finite_positive(self.connect_timeout, field="connect_timeout")
        _finite_positive(self.socket_timeout, field="socket_timeout")
        if type(self.max_retries) is not int:
            raise TypeError("max_retries must be an exact int")
        if self.max_retries != 0:
            raise ValueError("max_retries must be zero")

    @property
    def max_command_time(self) -> float:
        """Return the maximum connect plus socket duration."""
        return float(self.connect_timeout) + float(self.socket_timeout)


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisCoordinationSnapshot:
    """Bounded atomic marker/result snapshot returned by a provider."""

    marker: bytes | None
    result: bytes | None
    marker_oversized: bool
    result_oversized: bool

    def __post_init__(self) -> None:
        if self.marker is not None and type(self.marker) is not bytes:
            raise TypeError("marker must be exact bytes or None")
        if self.result is not None and type(self.result) is not bytes:
            raise TypeError("result must be exact bytes or None")
        if type(self.marker_oversized) is not bool:
            raise TypeError("marker_oversized must be an exact bool")
        if type(self.result_oversized) is not bool:
            raise TypeError("result_oversized must be an exact bool")


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisLoadOptions:
    """Exact bounded settings for Redis-backed load coordination."""

    namespace: str
    lease_ttl: float = 5.0
    result_ttl: float = 1.0
    poll_interval: float = 0.01
    max_poll_interval: float = 0.25
    wait_timeout: float = 10.0
    max_attempts: int = 3
    max_polls: int = 100
    redis_io_timeout: float = 1.0

    def __post_init__(self) -> None:
        if type(self.namespace) is not str:
            raise TypeError("namespace must be an exact str")
        encoded = self.namespace.encode("utf-8")
        if (
            not self.namespace
            or self.namespace != self.namespace.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in self.namespace)
            or not 1 <= len(encoded) <= 256
        ):
            raise ValueError(
                "namespace must be 1..256 UTF-8 bytes without surrounding whitespace "
                "or control characters"
            )

        durations = {
            "lease_ttl": self.lease_ttl,
            "result_ttl": self.result_ttl,
            "poll_interval": self.poll_interval,
            "max_poll_interval": self.max_poll_interval,
            "wait_timeout": self.wait_timeout,
            "redis_io_timeout": self.redis_io_timeout,
        }
        normalized = {
            field: _finite_positive(value, field=field) for field, value in durations.items()
        }
        if any(value > _MAX_COORDINATION_DURATION for value in normalized.values()):
            raise ValueError("coordination durations must not exceed 3600 seconds")
        if normalized["poll_interval"] < _MIN_POLL_INTERVAL:
            raise ValueError("poll_interval is below the minimum")
        if normalized["poll_interval"] > normalized["max_poll_interval"]:
            raise ValueError("poll_interval must not exceed max_poll_interval")
        if normalized["max_poll_interval"] > normalized["wait_timeout"]:
            raise ValueError("max_poll_interval must not exceed wait_timeout")
        if normalized["max_poll_interval"] > normalized["result_ttl"]:
            raise ValueError("max_poll_interval must not exceed result_ttl")
        for field, value, maximum in (
            ("max_attempts", self.max_attempts, 100),
            ("max_polls", self.max_polls, _MAX_POLL_BUDGET),
        ):
            if type(value) is not int:
                raise TypeError(f"{field} must be an exact int")
            if not 1 <= value <= maximum:
                raise ValueError(f"{field} is outside its supported range")


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


@dataclass(frozen=True, slots=True, kw_only=True)
class RedisCoordinationEvent:
    """Low-cardinality terminal observation for one distributed flight."""

    mode: RedisMode
    operation: RedisCoordinationOperation
    outcome: RedisCoordinationOutcome
    error_code: RedisCoordinationErrorCode | None
    attempts: int
    polls: int
    cleanup_failed: bool
    elapsed_ns: int

    def __post_init__(self) -> None:
        if type(self.mode) is not RedisMode:
            raise TypeError("mode must be an exact RedisMode")
        if type(self.operation) is not RedisCoordinationOperation:
            raise TypeError("operation must be an exact RedisCoordinationOperation")
        if type(self.outcome) is not RedisCoordinationOutcome:
            raise TypeError("outcome must be an exact RedisCoordinationOutcome")
        if self.error_code is not None and type(self.error_code) is not RedisCoordinationErrorCode:
            raise TypeError("error_code must be an exact RedisCoordinationErrorCode or None")
        for field, value in (
            ("attempts", self.attempts),
            ("polls", self.polls),
            ("elapsed_ns", self.elapsed_ns),
        ):
            if type(value) is not int:
                raise TypeError(f"{field} must be an exact int")
            if value < 0:
                raise ValueError(f"{field} must be non-negative")
        if type(self.cleanup_failed) is not bool:
            raise TypeError("cleanup_failed must be an exact bool")


class RedisObserver(Protocol):
    """Receive low-cardinality terminal provider events."""

    def on_event(self, event: RedisEvent) -> None:
        """Observe one terminal provider event."""
        ...


class RedisCoordinationObserver(Protocol):
    """Receive one redacted terminal event per distributed flight."""

    def on_event(self, event: RedisCoordinationEvent) -> None:
        """Observe a terminal load-coordination event."""
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


class RedisCoordinationError(RuntimeError):
    """Report a redacted load-coordination failure."""

    def __init__(self, *, code: RedisCoordinationErrorCode) -> None:
        if type(code) is not RedisCoordinationErrorCode:
            raise TypeError("code must be an exact RedisCoordinationErrorCode")
        self._code = code
        super().__init__("Redis load coordination failed")

    @property
    def code(self) -> RedisCoordinationErrorCode:
        """Return the stable failure code."""
        return self._code


class RedisCoordinationTimeoutError(RedisCoordinationError):
    """Report exhaustion of a bounded coordination wait."""

    def __init__(self, *, code: RedisCoordinationErrorCode) -> None:
        if type(code) is not RedisCoordinationErrorCode:
            raise TypeError("code must be an exact RedisCoordinationErrorCode")
        if code not in {
            RedisCoordinationErrorCode.ATTEMPTS_EXHAUSTED,
            RedisCoordinationErrorCode.POLLS_EXHAUSTED,
            RedisCoordinationErrorCode.DEADLINE_EXCEEDED,
        }:
            raise ValueError("timeout error requires a timeout code")
        super().__init__(code=code)
        self.args = ("Redis load coordination timed out",)
