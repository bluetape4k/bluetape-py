"""Eager stdlib-only collection helpers for bluetape-py."""

from collections.abc import Callable, Hashable, Iterable


def _require_callable[F: Callable[..., object]](value: F | object, name: str) -> F:
    if not callable(value):
        raise TypeError(f"{name} must be callable")
    return value


def chunked[T](iterable: Iterable[T], size: int) -> list[list[T]]:
    """Return fixed-size chunks from `iterable`.

    Raises:
        ValueError: If `size` is not greater than zero.
    """
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("size must be an integer")
    if size <= 0:
        raise ValueError("size must be greater than 0")

    chunks: list[list[T]] = []
    current: list[T] = []
    for item in iterable:
        current.append(item)
        if len(current) == size:
            chunks.append(current)
            current = []

    if current:
        chunks.append(current)
    return chunks


def chunk_by[T](iterable: Iterable[T], starts_new: Callable[[T], bool]) -> list[list[T]]:
    """Split `iterable` whenever `starts_new` matches after the first item."""
    split = _require_callable(starts_new, "starts_new")
    chunks: list[list[T]] = []

    for item in iterable:
        if chunks and split(item):
            chunks.append([item])
        elif chunks:
            chunks[-1].append(item)
        else:
            chunks.append([item])

    return chunks


def distinct[T: Hashable](iterable: Iterable[T]) -> list[T]:
    """Return first-seen hashable values while preserving order."""
    seen: set[T] = set()
    result: list[T] = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def distinct_by[T, K: Hashable](iterable: Iterable[T], key: Callable[[T], K]) -> list[T]:
    """Return the first item for each hashable derived key."""
    key_fn = _require_callable(key, "key")
    seen: set[K] = set()
    result: list[T] = []
    for item in iterable:
        derived = key_fn(item)
        if derived not in seen:
            seen.add(derived)
            result.append(item)
    return result


def group_by[T, K: Hashable](iterable: Iterable[T], key: Callable[[T], K]) -> dict[K, list[T]]:
    """Group items by a hashable key."""
    key_fn = _require_callable(key, "key")
    groups: dict[K, list[T]] = {}
    for item in iterable:
        derived = key_fn(item)
        bucket = groups.get(derived)
        if bucket is None:
            bucket = []
            groups[derived] = bucket
        bucket.append(item)
    return groups


def count_by[T, K: Hashable](iterable: Iterable[T], key: Callable[[T], K]) -> dict[K, int]:
    """Count items by a hashable key."""
    key_fn = _require_callable(key, "key")
    counts: dict[K, int] = {}
    for item in iterable:
        derived = key_fn(item)
        counts[derived] = counts.get(derived, 0) + 1
    return counts


def partition[T](
    iterable: Iterable[T],
    predicate: Callable[[T], bool],
) -> tuple[list[T], list[T]]:
    """Split items into matching and non-matching lists."""
    predicate_fn = _require_callable(predicate, "predicate")
    matches: list[T] = []
    misses: list[T] = []
    for item in iterable:
        if predicate_fn(item):
            matches.append(item)
        else:
            misses.append(item)
    return matches, misses


def map_or_raise[T, R](iterable: Iterable[T], mapper: Callable[[T], R]) -> list[R]:
    """Map items eagerly and let mapper exceptions propagate unchanged."""
    mapper_fn = _require_callable(mapper, "mapper")
    return [mapper_fn(item) for item in iterable]


def filter_or_raise[T](iterable: Iterable[T], predicate: Callable[[T], bool]) -> list[T]:
    """Filter items eagerly and let predicate exceptions propagate unchanged."""
    predicate_fn = _require_callable(predicate, "predicate")
    return [item for item in iterable if predicate_fn(item)]


__all__ = [
    "chunk_by",
    "chunked",
    "count_by",
    "distinct",
    "distinct_by",
    "filter_or_raise",
    "group_by",
    "map_or_raise",
    "partition",
]
