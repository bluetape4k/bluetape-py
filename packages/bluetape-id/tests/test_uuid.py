import inspect
import itertools
import uuid

import pytest
from bluetape.id import (
    IDOverflowError,
    InvalidIDError,
    UUID7Generator,
    uuid4,
    uuid7_timestamp_ms,
)

MAX_TIMESTAMP = (1 << 48) - 1


def entropy(seed: int, random_bits: int) -> bytes:
    return seed.to_bytes(2, "big") + random_bits.to_bytes(8, "big")


def test_uuid4_delegates_to_stdlib_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = uuid.UUID("12345678-1234-4234-9234-123456789abc")
    calls = 0

    def fake_uuid4() -> uuid.UUID:
        nonlocal calls
        calls += 1
        return expected

    monkeypatch.setattr(uuid, "uuid4", fake_uuid4)
    assert uuid4() is expected
    assert calls == 1

    monkeypatch.undo()
    values = {uuid4() for _ in range(128)}
    assert len(values) == 128
    assert all(value.version == 4 and value.variant == uuid.RFC_4122 for value in values)


def test_uuid7_public_signatures_are_exact() -> None:
    constructor = inspect.signature(UUID7Generator)
    assert tuple(constructor.parameters) == ("clock", "random_bytes")
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in constructor.parameters.values()
    )
    assert tuple(inspect.signature(UUID7Generator.new).parameters) == ("self",)
    assert tuple(inspect.signature(uuid4).parameters) == ()
    assert tuple(inspect.signature(uuid7_timestamp_ms).parameters) == ("value",)


def test_uuid7_rfc_vector() -> None:
    timestamp = 0x0123456789AB
    seed = 0x0ABC
    random_bits = 0x0123456789ABCDEF & ((1 << 62) - 1)
    generator = UUID7Generator(
        clock=lambda: timestamp,
        random_bytes=lambda size: entropy(seed, random_bits),
    )

    value = generator.new()
    expected = (timestamp << 80) | (0x7 << 76) | (seed << 64) | (0b10 << 62) | random_bits
    assert value.int == expected
    assert value.version == 7
    assert value.variant == uuid.RFC_4122
    assert uuid7_timestamp_ms(value) == timestamp
    assert uuid7_timestamp_ms(str(value)) == timestamp

    invalid_strings = [
        str(value).upper(),
        str(value).replace("-", ""),
        "{" + str(value) + "}",
        "urn:uuid:" + str(value),
        " " + str(value),
        str(value) + " ",
    ]
    for invalid in invalid_strings:
        with pytest.raises(InvalidIDError):
            uuid7_timestamp_ms(invalid)
    with pytest.raises(InvalidIDError):
        uuid7_timestamp_ms(uuid.uuid4())
    with pytest.raises(TypeError):
        uuid7_timestamp_ms(7)  # type: ignore[arg-type]


def test_uuid7_same_tick_rollback_and_overflow() -> None:
    clocks = iter((10, 10, 9))
    payloads = iter(
        (
            entropy(0xFFE, 1),
            entropy(0x111, 2),
            entropy(0x123, 3),
        )
    )
    generator = UUID7Generator(clock=lambda: next(clocks), random_bytes=lambda size: next(payloads))

    first, second, third = generator.new(), generator.new(), generator.new()
    assert [value.int >> 80 for value in (first, second, third)] == [10, 10, 11]
    assert [(value.int >> 64) & 0xFFF for value in (first, second, third)] == [
        0xFFE,
        0xFFF,
        0x123,
    ]
    assert [value.int & ((1 << 62) - 1) for value in (first, second, third)] == [1, 2, 3]
    assert first.int < second.int < third.int

    overflowing = UUID7Generator(
        clock=lambda: MAX_TIMESTAMP,
        random_bytes=lambda size: entropy(0xFFF, 0),
    )
    overflowing.new()
    with pytest.raises(IDOverflowError):
        overflowing.new()


def test_uuid7_entropy_mapping_and_failure_is_atomic() -> None:
    calls: list[int] = []
    payloads = iter((entropy(0xABC, 5), b"secret", entropy(0x000, 7)))

    def random_bytes(size: int) -> bytes:
        calls.append(size)
        return next(payloads)

    generator = UUID7Generator(clock=lambda: 20, random_bytes=random_bytes)
    first = generator.new()
    with pytest.raises(InvalidIDError) as captured:
        generator.new()
    second = generator.new()

    assert calls == [10, 10, 10]
    assert "secret" not in str(captured.value)
    assert (first.int >> 64) & 0xFFF == 0xABC
    assert (second.int >> 64) & 0xFFF == 0xABD
    assert second.int & ((1 << 62) - 1) == 7

    clock_calls = itertools.count()

    def broken_clock() -> int:
        next(clock_calls)
        raise RuntimeError("clock failed")

    broken = UUID7Generator(clock=broken_clock, random_bytes=lambda size: entropy(0, 0))
    with pytest.raises(RuntimeError, match="clock failed"):
        broken.new()


def test_uuid7_constructor_validates_callbacks_without_invoking_them() -> None:
    called = False

    def callback() -> int:
        nonlocal called
        called = True
        return 1

    UUID7Generator(clock=callback, random_bytes=lambda size: bytes(size))
    assert called is False
    with pytest.raises(TypeError):
        UUID7Generator(clock=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        UUID7Generator(random_bytes=1)  # type: ignore[arg-type]
