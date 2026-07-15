import secrets
import uuid
from collections.abc import Callable
from threading import Lock

from ._entropy import MAX_TIMESTAMP, read_entropy, read_timestamp, require_callback, unix_time_ms
from ._errors import IDOverflowError, InvalidIDError

_CANONICAL_UUID_LENGTH = 36
_RAND_A_MASK = (1 << 12) - 1
_RAND_B_MASK = (1 << 62) - 1


class UUID7Generator:
    """Process-local, thread-safe monotonic UUIDv7 generator."""

    def __init__(
        self,
        *,
        clock: Callable[[], int] = unix_time_ms,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        require_callback(clock, "clock")
        require_callback(random_bytes, "random_bytes")
        self._clock = clock
        self._random_bytes = random_bytes
        self._lock = Lock()
        self._last_ms: int | None = None
        self._counter = 0

    def new(self) -> uuid.UUID:
        observed_ms = read_timestamp(self._clock)
        entropy = read_entropy(self._random_bytes)
        seed = int.from_bytes(entropy[:2], "big") & _RAND_A_MASK
        random_bits = int.from_bytes(entropy[2:], "big") & _RAND_B_MASK

        with self._lock:
            if self._last_ms is None or observed_ms > self._last_ms:
                logical_ms = observed_ms
                counter = seed
            elif self._counter < _RAND_A_MASK:
                logical_ms = self._last_ms
                counter = self._counter + 1
            else:
                logical_ms = self._last_ms + 1
                if logical_ms > MAX_TIMESTAMP:
                    raise IDOverflowError("UUIDv7 timestamp range is exhausted")
                counter = seed

            value = uuid.UUID(
                int=(
                    (logical_ms << 80) | (0x7 << 76) | (counter << 64) | (0b10 << 62) | random_bits
                )
            )
            self._last_ms = logical_ms
            self._counter = counter
            return value


def uuid4() -> uuid.UUID:
    return uuid.uuid4()


def uuid7_timestamp_ms(value: uuid.UUID | str) -> int:
    parsed: uuid.UUID
    if isinstance(value, str):
        if len(value) != _CANONICAL_UUID_LENGTH or value != value.lower():
            raise InvalidIDError("value must be a canonical lowercase UUIDv7 string")
        try:
            parsed = uuid.UUID(value)
        except ValueError as error:
            raise InvalidIDError("value must be a canonical lowercase UUIDv7 string") from error
        if str(parsed) != value:
            raise InvalidIDError("value must be a canonical lowercase UUIDv7 string")
    elif isinstance(value, uuid.UUID):
        parsed = value
    else:
        raise TypeError("value must be a UUID or canonical UUID string")

    if parsed.version != 7 or parsed.variant != uuid.RFC_4122:
        raise InvalidIDError("value must be an RFC UUIDv7")
    return parsed.int >> 80
