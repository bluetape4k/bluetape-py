"""Deterministic immutable backoff strategies."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from bluetape.resilience._core import (
    _finite_non_negative,
    _finite_positive,
    _positive_int,
    _validate_callable,
)


@runtime_checkable
class Backoff(Protocol):
    def __call__(self, failed_attempt: int, /) -> float: ...


@dataclass(frozen=True, slots=True)
class _ConstantBackoff:
    delay: float

    def __call__(self, failed_attempt: int, /) -> float:
        _positive_int(failed_attempt, "failed_attempt")
        return self.delay


@dataclass(frozen=True, slots=True)
class _ExponentialBackoff:
    initial_delay: float
    multiplier: float
    max_delay: float | None
    jitter: float
    random_source: Callable[[], float]

    def __call__(self, failed_attempt: int, /) -> float:
        attempt = _positive_int(failed_attempt, "failed_attempt")
        try:
            base = self.initial_delay * self.multiplier ** (attempt - 1)
        except OverflowError:
            base = float("inf")
        if self.max_delay is not None:
            base = min(base, self.max_delay)
        if self.jitter == 0:
            return _finite_non_negative(base, "backoff result")
        random_value = self.random_source()
        if isinstance(random_value, bool) or not isinstance(random_value, (int, float)):
            raise TypeError("random_source result must be a finite number in the range 0..1")
        random_result = float(random_value)
        if not 0 <= random_result <= 1:
            raise ValueError("random_source result must be a finite number in the range 0..1")
        factor = 1 - self.jitter + (2 * self.jitter * random_result)
        return _finite_non_negative(base * factor, "backoff result")


def constant_backoff(delay: float = 0, /) -> Backoff:
    return _ConstantBackoff(_finite_non_negative(delay, "delay"))


def exponential_backoff(
    *,
    initial_delay: float,
    multiplier: float = 2,
    max_delay: float | None = None,
    jitter: float = 0,
    random_source: Callable[[], float] = random.random,
) -> Backoff:
    initial = _finite_positive(initial_delay, "initial_delay")
    factor = _finite_positive(multiplier, "multiplier")
    maximum = None if max_delay is None else _finite_positive(max_delay, "max_delay")
    jitter_value = _finite_non_negative(jitter, "jitter")
    if jitter_value > 1:
        raise ValueError("jitter must be in the range 0..1")
    source = _validate_callable(random_source, "random_source")
    return _ExponentialBackoff(initial, factor, maximum, jitter_value, source)
