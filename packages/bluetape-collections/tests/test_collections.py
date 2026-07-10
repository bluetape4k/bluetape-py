import pytest
from bluetape.collections import (
    __all__,
    chunk_by,
    chunked,
    count_by,
    distinct,
    distinct_by,
    filter_or_raise,
    group_by,
    map_or_raise,
    partition,
)


def _raising_iterable():
    raise AssertionError("iterable should not be consumed")
    yield


def test_all_exports_public_helpers() -> None:
    assert set(__all__) == {
        "chunk_by",
        "chunked",
        "count_by",
        "distinct",
        "distinct_by",
        "filter_or_raise",
        "group_by",
        "map_or_raise",
        "partition",
    }


def test_chunked_splits_iterable_and_preserves_input_container() -> None:
    values = [1, 2, 3, 4, 5]

    result = chunked(values, 2)
    result[0].append(99)

    assert result == [[1, 2, 99], [3, 4], [5]]
    assert values == [1, 2, 3, 4, 5]
    assert chunked((value for value in range(5)), 2) == [[0, 1], [2, 3], [4]]
    assert chunked([], 2) == []


@pytest.mark.parametrize("size", [0, -1])
def test_chunked_rejects_non_positive_size(size: int) -> None:
    with pytest.raises(ValueError, match="size must be greater than 0"):
        chunked([1, 2, 3], size)


@pytest.mark.parametrize("size", [1.5, float("nan"), "2"])
def test_chunked_rejects_non_integral_size_before_consuming_iterable(size: object) -> None:
    with pytest.raises(TypeError, match="size must be an integer"):
        chunked(_raising_iterable(), size)  # type: ignore[arg-type]


def test_chunk_by_splits_after_first_matching_item() -> None:
    values = ["api-1", "api-2", "job-1", "job-2", "api-3"]

    result = chunk_by(values, lambda value: value in {"job-1", "api-3"})

    assert result == [["api-1", "api-2"], ["job-1", "job-2"], ["api-3"]]
    assert values == ["api-1", "api-2", "job-1", "job-2", "api-3"]
    assert chunk_by([], lambda _: True) == []


def test_distinct_preserves_first_seen_order() -> None:
    assert distinct(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert distinct([]) == []


def test_distinct_rejects_unhashable_values() -> None:
    with pytest.raises(TypeError):
        distinct([[1], [1]])


def test_distinct_by_preserves_first_item_per_hashable_key() -> None:
    values = ["alpha", "alps", "beta", "bravo", "charlie"]

    result = distinct_by(values, lambda value: value[0])

    assert result == ["alpha", "beta", "charlie"]
    assert values == ["alpha", "alps", "beta", "bravo", "charlie"]


def test_distinct_by_rejects_unhashable_keys() -> None:
    with pytest.raises(TypeError):
        distinct_by(["a"], lambda value: [value])


def test_group_by_and_count_by_build_new_containers() -> None:
    values = ["ant", "ape", "bee", "bat", "cat"]

    groups = group_by(values, lambda value: value[0])
    counts = count_by(values, lambda value: value[0])
    groups["a"].append("added")

    assert groups == {
        "a": ["ant", "ape", "added"],
        "b": ["bee", "bat"],
        "c": ["cat"],
    }
    assert counts == {"a": 2, "b": 2, "c": 1}
    assert values == ["ant", "ape", "bee", "bat", "cat"]


def test_partition_splits_matches_and_misses_without_mutating_input() -> None:
    values = [1, 2, 3, 4, 5]

    even, odd = partition(values, lambda value: value % 2 == 0)
    even.append(10)

    assert even == [2, 4, 10]
    assert odd == [1, 3, 5]
    assert values == [1, 2, 3, 4, 5]


def test_map_or_raise_returns_eager_list_and_propagates_mapper_errors() -> None:
    assert map_or_raise([1, 2, 3], lambda value: value * 2) == [2, 4, 6]

    def mapper(value: int) -> int:
        if value == 2:
            raise RuntimeError("boom")
        return value

    with pytest.raises(RuntimeError, match="boom"):
        map_or_raise([1, 2, 3], mapper)


def test_filter_or_raise_returns_eager_list_and_propagates_predicate_errors() -> None:
    assert filter_or_raise([1, 2, 3, 4], lambda value: value % 2 == 0) == [2, 4]

    def predicate(value: int) -> bool:
        if value == 3:
            raise RuntimeError("boom")
        return True

    with pytest.raises(RuntimeError, match="boom"):
        filter_or_raise([1, 2, 3], predicate)


@pytest.mark.parametrize(
    ("helper", "args"),
    [
        (chunk_by, ([1], None)),
        (distinct_by, ([1], None)),
        (group_by, ([1], None)),
        (count_by, ([1], None)),
        (partition, ([1], None)),
        (map_or_raise, ([1], None)),
        (filter_or_raise, ([1], None)),
        (chunk_by, ([1], "not callable")),
        (distinct_by, ([1], "not callable")),
        (group_by, ([1], "not callable")),
        (count_by, ([1], "not callable")),
        (partition, ([1], "not callable")),
        (map_or_raise, ([1], "not callable")),
        (filter_or_raise, ([1], "not callable")),
    ],
)
def test_callable_arguments_must_be_callable(helper, args) -> None:
    with pytest.raises(TypeError, match="must be callable"):
        helper(*args)
