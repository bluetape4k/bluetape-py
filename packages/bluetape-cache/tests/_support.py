"""Deterministic test support for bluetape-cache."""


class FakeClock:
    """Return a caller-controlled monotonic nanosecond value."""

    def __init__(self, now_ns: int = 0) -> None:
        self.now_ns = now_ns

    def __call__(self) -> int:
        return self.now_ns
