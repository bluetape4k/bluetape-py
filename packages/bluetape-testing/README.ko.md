# bluetape-testing

[English](README.md) | 한국어

Python-native bluetape package를 위한 internal-first pytest helper입니다.

안정적인 public subset은 `bluetape.testing`에서 import합니다.

## Public API 정책

`bluetape-testing`은 이 workspace를 위한 internal-first package로 시작합니다. 아래에 문서화한 helper만 작고 안정적인 public subset입니다. 여러 package에서 사용되고 명확한 user-facing contract가 생길 때까지 향후 fixture helper는 private으로 유지할 수 있습니다.

```python
from bluetape.testing import eventually

eventually(lambda: cache.get("ready"), timeout=2.0, interval=0.01)
```

`pytest-asyncio`로 test를 실행하면 async probe도 지원합니다.

```python
from bluetape.testing import eventually_async

value = await eventually_async(fetch_state, timeout=2.0)
```

## 계약

- `eventually(probe, timeout=..., interval=...)`은 probe가 `None` 또는 `False`가 아닌 value를 반환할 때까지 polling합니다.
- `eventually_async(...)`는 awaitable probe에 같은 contract를 적용합니다.
- `timeout`과 `interval`은 0보다 커야 합니다.
- 정해진 시간 안에 조건이 충족되지 않으면 helper가 `AssertionError`를 발생시킵니다.
- 이 package는 `pytest`에 의존하며, 그 dependency는 `bluetape-core` 또는 default `bluetape` install로 유출되지 않습니다.
