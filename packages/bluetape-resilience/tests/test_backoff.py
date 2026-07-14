"""Deterministic backoff contract tests."""

import math
from dataclasses import FrozenInstanceError

import bluetape.resilience as resilience
import pytest
from bluetape.resilience import Backoff, constant_backoff, exponential_backoff


def test_backoff_public_exports_precede_shared_values() -> None:
    names = {"Backoff", "constant_backoff", "exponential_backoff"}
    assert [name for name in resilience.__all__ if name in names] == [
        "Backoff",
        "constant_backoff",
        "exponential_backoff",
    ]


def test_backoff_protocol_is_runtime_checkable() -> None:
    assert isinstance(constant_backoff(), Backoff)
    assert isinstance(lambda attempt: float(attempt), Backoff)


def test_constant_backoff_is_immutable_and_attempt_independent() -> None:
    backoff = constant_backoff(0.25)
    assert backoff(1) == 0.25
    assert backoff(99) == 0.25
    with pytest.raises(FrozenInstanceError):
        backoff.delay = 1.0


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        ("1", TypeError),
        (-1, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
    ],
)
def test_constant_backoff_rejects_invalid_delay(value: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        constant_backoff(value)


def test_backoff_requires_positive_non_bool_failed_attempt() -> None:
    for attempt in (0, -1):
        with pytest.raises(ValueError):
            constant_backoff()(attempt)
    for attempt in (True, 1.0, "1"):
        with pytest.raises(TypeError):
            constant_backoff()(attempt)


def test_exponential_backoff_uses_one_based_failed_attempt() -> None:
    backoff = exponential_backoff(initial_delay=0.5, multiplier=3)
    assert [backoff(attempt) for attempt in (1, 2, 3)] == [0.5, 1.5, 4.5]


def test_exponential_backoff_caps_before_bounded_jitter() -> None:
    low = exponential_backoff(
        initial_delay=2,
        multiplier=3,
        max_delay=5,
        jitter=0.2,
        random_source=lambda: 0.0,
    )
    high = exponential_backoff(
        initial_delay=2,
        multiplier=3,
        max_delay=5,
        jitter=0.2,
        random_source=lambda: 1.0,
    )
    assert low(3) == 4.0
    assert high(3) == pytest.approx(6.0)


@pytest.mark.parametrize("jitter", [0.0, 1.0])
def test_exponential_backoff_accepts_jitter_boundaries(jitter: float) -> None:
    backoff = exponential_backoff(initial_delay=1, jitter=jitter, random_source=lambda: 0.5)
    assert backoff(1) == 1.0


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"initial_delay": True}, TypeError),
        ({"initial_delay": 0}, ValueError),
        ({"initial_delay": math.inf}, ValueError),
        ({"initial_delay": 1, "multiplier": 0}, ValueError),
        ({"initial_delay": 1, "max_delay": 0}, ValueError),
        ({"initial_delay": 1, "jitter": -0.1}, ValueError),
        ({"initial_delay": 1, "jitter": 1.1}, ValueError),
        ({"initial_delay": 1, "random_source": None}, TypeError),
    ],
)
def test_exponential_backoff_rejects_invalid_configuration(
    kwargs: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        exponential_backoff(**kwargs)


@pytest.mark.parametrize("value", [math.nan, math.inf, -0.1, 1.1, True])
def test_exponential_backoff_rejects_invalid_random_output(value: object) -> None:
    backoff = exponential_backoff(initial_delay=1, jitter=0.5, random_source=lambda: value)
    with pytest.raises((TypeError, ValueError)):
        backoff(1)


def test_exponential_backoff_does_not_invoke_random_source_at_construction() -> None:
    invoked = False

    def random_source() -> float:
        nonlocal invoked
        invoked = True
        return 0.5

    backoff = exponential_backoff(initial_delay=1, jitter=0.5, random_source=random_source)
    assert not invoked
    assert backoff(1) == 1
    assert invoked
