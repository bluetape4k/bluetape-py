import time
from collections.abc import Callable

from ._errors import IDOverflowError, InvalidIDError

MAX_TIMESTAMP = (1 << 48) - 1


def unix_time_ms() -> int:
    return time.time_ns() // 1_000_000


def require_callback(value: object, name: str) -> None:
    if not callable(value):
        raise TypeError(f"{name} must be callable")


def read_timestamp(clock: Callable[[], int]) -> int:
    value = clock()
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("clock result must be an integer")
    if not 0 <= value <= MAX_TIMESTAMP:
        raise IDOverflowError("clock result exceeds the 48-bit timestamp range")
    return value


def read_entropy(random_bytes: Callable[[int], bytes]) -> bytes:
    value = random_bytes(10)
    if not isinstance(value, bytes):
        raise TypeError("entropy result must be bytes")
    if len(value) != 10:
        raise InvalidIDError("entropy result must contain exactly 10 bytes")
    return value
