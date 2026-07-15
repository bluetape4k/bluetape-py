import secrets
from collections.abc import Callable
from threading import Lock

from ._entropy import read_entropy, read_timestamp, require_callback, unix_time_ms
from ._errors import IDOverflowError, InvalidIDError

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {character: index for index, character in enumerate(_ALPHABET)}
_MAX_RANDOMNESS = (1 << 80) - 1
_ULID_LENGTH = 26


def _encode(timestamp: int, randomness: int) -> str:
    value = (timestamp << 80) | randomness
    output = ["0"] * _ULID_LENGTH
    for index in range(_ULID_LENGTH - 1, -1, -1):
        output[index] = _ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(output)


def _decode(value: str) -> int:
    decoded = 0
    for character in value:
        try:
            digit = _DECODE[character]
        except KeyError as error:
            raise InvalidIDError("value must be a canonical ULID") from error
        decoded = (decoded << 5) | digit
    if decoded >= 1 << 128:
        raise InvalidIDError("value exceeds the canonical ULID range")
    return decoded


class ULIDGenerator:
    """Random ULID generator with caller-owned clock and entropy callbacks."""

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

    def new(self) -> str:
        timestamp = read_timestamp(self._clock)
        randomness = int.from_bytes(read_entropy(self._random_bytes), "big")
        return _encode(timestamp, randomness)


class MonotonicULIDGenerator:
    """Process-local monotonic ULID generator ordered by state-lock acquisition."""

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
        self._randomness = 0

    def new(self) -> str:
        observed_ms = read_timestamp(self._clock)
        entropy = read_entropy(self._random_bytes)
        fresh_randomness = int.from_bytes(entropy, "big")

        with self._lock:
            if self._last_ms is None or observed_ms > self._last_ms:
                logical_ms = observed_ms
                randomness = fresh_randomness
            else:
                logical_ms = self._last_ms
                if self._randomness == _MAX_RANDOMNESS:
                    raise IDOverflowError("monotonic ULID randomness is exhausted")
                randomness = self._randomness + 1

            value = _encode(logical_ms, randomness)
            self._last_ms = logical_ms
            self._randomness = randomness
            return value


def parse_ulid(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    if len(value) != _ULID_LENGTH:
        raise InvalidIDError("value must contain exactly 26 ULID characters")
    _decode(value)
    return value


def ulid_timestamp_ms(value: str) -> int:
    return _decode(parse_ulid(value)) >> 80
