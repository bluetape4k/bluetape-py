from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import bluetape.id as id_module
from bluetape.id import MonotonicULIDGenerator, UUID7Generator


def test_monotonic_ulid_shared_instance_is_lock_ordered() -> None:
    workers = 16
    barrier = Barrier(workers)

    def clock() -> int:
        barrier.wait(timeout=5)
        return 100

    generator = MonotonicULIDGenerator(clock=clock, random_bytes=lambda size: bytes(size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        values = list(executor.map(lambda _: generator.new(), range(workers)))

    assert len(set(values)) == workers
    assert sorted(values) == [f"0000000034{index:016X}" for index in range(workers)]


def test_module_convenience_concurrency_contracts(monkeypatch) -> None:
    workers = 16
    uuid_generator = UUID7Generator(clock=lambda: 200, random_bytes=lambda size: bytes(size))
    monotonic_ulid = MonotonicULIDGenerator(
        clock=lambda: 200, random_bytes=lambda size: bytes(size)
    )
    monkeypatch.setattr(id_module, "_UUID7_GENERATOR", uuid_generator)
    monkeypatch.setattr(id_module, "_ULID_GENERATOR", monotonic_ulid)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        uuid_values = list(executor.map(lambda _: id_module.uuid7(), range(workers)))
        ulid_values = list(executor.map(lambda _: id_module.ulid(), range(workers)))

    assert len(set(uuid_values)) == workers
    assert len(set(ulid_values)) == workers
    assert [(value.int >> 64) & 0xFFF for value in sorted(uuid_values)] == list(range(workers))
    assert sorted(ulid_values) == [f"0000000068{index:016X}" for index in range(workers)]


def test_callbacks_execute_before_state_lock() -> None:
    barrier = Barrier(2)

    def clock() -> int:
        barrier.wait(timeout=5)
        return 300

    generator = UUID7Generator(clock=clock, random_bytes=lambda size: bytes(size))
    with ThreadPoolExecutor(max_workers=2) as executor:
        values = list(executor.map(lambda _: generator.new(), range(2)))

    assert values[0] != values[1]
