import inspect

import bluetape.id as id_module
import pytest
from bluetape.id import (
    IDOverflowError,
    InvalidIDError,
    MonotonicULIDGenerator,
    ULIDGenerator,
    parse_ulid,
    ulid,
    ulid_timestamp_ms,
)


def test_random_ulid_and_module_convenience_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = iter((bytes(10), b"\xff" * 10))
    generator = ULIDGenerator(clock=lambda: 1234, random_bytes=lambda size: next(payloads))

    first = generator.new()
    second = generator.new()
    assert first == "000000016J0000000000000000"
    assert second == "000000016JZZZZZZZZZZZZZZZZ"
    assert first < second
    assert ulid_timestamp_ms(first) == 1234

    monkeypatch.setattr(id_module, "_ULID_GENERATOR", generator)
    monkeypatch.setattr(generator, "new", lambda: first)
    assert ulid() == first


def test_ulid_canonical_boundaries() -> None:
    minimum = "00000000000000000000000000"
    maximum = "7ZZZZZZZZZZZZZZZZZZZZZZZZZ"
    assert parse_ulid(minimum) == minimum
    assert parse_ulid(maximum) == maximum
    assert ulid_timestamp_ms(minimum) == 0
    assert ulid_timestamp_ms(maximum) == (1 << 48) - 1

    for invalid in (
        "8" + "0" * 25,
        "0" * 25,
        "0" * 27,
        "0" * 25 + "I",
        "0" * 25 + "L",
        "0" * 25 + "O",
        "0" * 25 + "U",
        "0" * 25 + "a",
        " " + "0" * 26,
        "0" * 26 + " ",
    ):
        with pytest.raises(InvalidIDError):
            parse_ulid(invalid)
    with pytest.raises(TypeError):
        parse_ulid(1)  # type: ignore[arg-type]


def test_monotonic_ulid_same_tick_rollback_and_overflow() -> None:
    clocks = iter((5, 5, 4))
    payloads = iter((bytes(10), b"\x11" * 10, b"\x22" * 10))
    generator = MonotonicULIDGenerator(
        clock=lambda: next(clocks),
        random_bytes=lambda size: next(payloads),
    )
    values = [generator.new(), generator.new(), generator.new()]
    assert values == sorted(values)
    assert [ulid_timestamp_ms(value) for value in values] == [5, 5, 5]

    overflowing = MonotonicULIDGenerator(
        clock=lambda: 1,
        random_bytes=lambda size: b"\xff" * size,
    )
    overflowing.new()
    with pytest.raises(IDOverflowError):
        overflowing.new()


def test_ulid_entropy_and_signature_contracts() -> None:
    sizes: list[int] = []

    def short_entropy(size: int) -> bytes:
        sizes.append(size)
        return b"payload"

    generator = ULIDGenerator(clock=lambda: 0, random_bytes=short_entropy)
    with pytest.raises(InvalidIDError) as captured:
        generator.new()
    assert sizes == [10]
    assert "payload" not in str(captured.value)

    assert tuple(inspect.signature(ULIDGenerator.new).parameters) == ("self",)
    assert tuple(inspect.signature(MonotonicULIDGenerator.new).parameters) == ("self",)
    assert tuple(inspect.signature(parse_ulid).parameters) == ("value",)
    assert tuple(inspect.signature(ulid_timestamp_ms).parameters) == ("value",)
