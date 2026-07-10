# bluetape-collections

Stdlib-only eager collection helpers for backend Python code.

`bluetape-collections` is available from this workspace in source form. PyPI
publication for `bluetape-py` is still on hold, so `pip install
bluetape-collections` and `pip install "bluetape[collections]"` describe the
intended post-publication install shape, not current registry availability.

## Local Usage

```bash
uv sync --all-packages
```

```python
from bluetape.collections import chunked, group_by

chunks = chunked(range(5), 2)
by_initial = group_by(["ant", "ape", "bee"], lambda value: value[0])
```

`chunks` is `[[0, 1], [2, 3], [4]]`, and `by_initial` is
`{"a": ["ant", "ape"], "b": ["bee"]}`.

## Helpers

| Helper | Behavior |
|---|---|
| `chunked(iterable, size)` | Return fixed-size `list[list[T]]` chunks; non-integer `size` raises `TypeError`; `size <= 0` raises `ValueError`. |
| `chunk_by(iterable, starts_new)` | Start a new chunk when `starts_new(item)` is true after the first item. |
| `distinct(iterable)` | Preserve first-seen order for hashable values. |
| `distinct_by(iterable, key)` | Preserve the first item for each hashable derived key. |
| `group_by(iterable, key)` | Return `dict[K, list[T]]`. |
| `count_by(iterable, key)` | Return `dict[K, int]`. |
| `partition(iterable, predicate)` | Return `(matches, misses)` lists. |
| `map_or_raise(iterable, mapper)` | Return an eager mapped list and propagate mapper exceptions unchanged. |
| `filter_or_raise(iterable, predicate)` | Return an eager filtered list and propagate predicate exceptions unchanged. |

All helpers consume the input iterable once and return new containers. They do
not mutate caller-owned lists or mappings.

## Error-Aware Transforms

`map_or_raise` and `filter_or_raise` are for call sites that want named,
importable eager helpers returning concrete lists while keeping callable errors
visible to the caller.

```python
from bluetape.collections import filter_or_raise, map_or_raise

ids = map_or_raise(["1", "2"], int)
active = filter_or_raise(ids, lambda value: value > 1)
```

They do not wrap, translate, or suppress exceptions from the mapper or
predicate. For short one-off logic, native Python comprehensions are often
clearer:

```python
ids = [int(value) for value in ["1", "2"]]
active = [value for value in ids if value > 1]
```

## Sibling Compatibility

The package is inspired by `bluetape-go/collections`, but keeps Python-native
names and eager container contracts.

| bluetape-go concept | Python helper |
|---|---|
| `Chunk` | `chunked` |
| `ChunkBy` | `chunk_by` |
| `Distinct` | `distinct` |
| `DistinctBy` | `distinct_by` |
| `GroupBy` | `group_by` |
| `CountBy` | `count_by` |
| `MapErr` | `map_or_raise` |
| `FilterErr` | `filter_or_raise` |

## Unsupported

- No async helpers in this package.
- No lazy pipeline API.
- No Go/Kotlin parity data structures.
- No unhashable `distinct` values. Use `distinct_by` with a hashable derived
  key instead.
- No PyPI publication in this PR.
