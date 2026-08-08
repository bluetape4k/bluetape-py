# bluetape-collections

[English](README.md) | 한국어

backend Python code를 위한 표준 라이브러리 전용 eager collection helper입니다.

`bluetape-collections`는 이 workspace에서 source 형태로 사용할 수 있습니다. `bluetape-py`의 PyPI publication은 보류 중이므로 `pip install bluetape-collections`와 `pip install "bluetape[collections]"`는 현재 registry에서 사용할 수 있는 명령이 아니라 publication 이후의 install shape를 설명합니다.

## 로컬 사용

```bash
uv sync --all-packages
```

```python
from bluetape.collections import chunked, group_by

chunks = chunked(range(5), 2)
by_initial = group_by(["ant", "ape", "bee"], lambda value: value[0])
```

`chunks`는 `[[0, 1], [2, 3], [4]]`이고, `by_initial`은 `{"a": ["ant", "ape"], "b": ["bee"]}`입니다.

## Helper

| Helper | 동작 |
|---|---|
| `chunked(iterable, size)` | 고정 크기의 `list[list[T]]` chunk를 반환합니다. 정수가 아닌 `size`와 boolean `size`는 `TypeError`, `size <= 0`은 `ValueError`를 발생시킵니다. |
| `chunk_by(iterable, starts_new)` | 첫 item 이후 `starts_new(item)`이 true일 때 새 chunk를 시작합니다. |
| `distinct(iterable)` | 처음 관찰한 순서를 유지하는 hashable value 목록을 반환합니다. |
| `distinct_by(iterable, key)` | 파생된 hashable key마다 첫 item을 유지합니다. |
| `group_by(iterable, key)` | `dict[K, list[T]]`를 반환합니다. |
| `count_by(iterable, key)` | `dict[K, int]`를 반환합니다. |
| `partition(iterable, predicate)` | `(matches, misses)` 목록을 반환합니다. |
| `map_or_raise(iterable, mapper)` | eager mapped list를 반환하며 mapper exception을 변경하지 않고 전파합니다. |
| `filter_or_raise(iterable, predicate)` | eager filtered list를 반환하며 predicate exception을 변경하지 않고 전파합니다. |

모든 helper는 입력 iterable을 한 번 소비하고 새 container를 반환합니다. caller-owned list나 mapping을 변경하지 않습니다.

## Error-aware transform

`map_or_raise`와 `filter_or_raise`는 이름으로 import할 수 있는 eager helper와 구체적인 list를 사용하면서 callable error를 caller에게 노출하려는 call site를 위한 것입니다.

```python
from bluetape.collections import filter_or_raise, map_or_raise

ids = map_or_raise(["1", "2"], int)
active = filter_or_raise(ids, lambda value: value > 1)
```

mapper 또는 predicate의 exception을 감싸거나 변환하거나 억제하지 않습니다. 짧은 일회성 logic에는 native Python comprehension이 더 명확할 수 있습니다.

```python
ids = [int(value) for value in ["1", "2"]]
active = [value for value in ids if value > 1]
```

## Sibling 호환성

이 package는 `bluetape-go/collections`에서 영감을 받았지만 Python-native name과 eager container contract를 유지합니다.

| bluetape-go 개념 | Python helper |
|---|---|
| `Chunk` | `chunked` |
| `ChunkBy` | `chunk_by` |
| `Distinct` | `distinct` |
| `DistinctBy` | `distinct_by` |
| `GroupBy` | `group_by` |
| `CountBy` | `count_by` |
| `MapErr` | `map_or_raise` |
| `FilterErr` | `filter_or_raise` |

## 지원하지 않는 항목

- 이 package에는 async helper가 없습니다.
- lazy pipeline API를 제공하지 않습니다.
- Go/Kotlin parity data structure를 제공하지 않습니다.
- hashable이 아닌 `distinct` value를 지원하지 않습니다. 대신 hashable derived key와 함께 `distinct_by`를 사용합니다.
- 이 PR에서는 PyPI publication을 수행하지 않습니다.
