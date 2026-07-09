# bluetape-testing

Internal-first pytest helpers for Python-native bluetape packages.

Import the stable public subset from `bluetape.testing`.

## Public API Policy

`bluetape-testing` starts as an internal-first package for this workspace. The
documented helpers below are the small stable public subset. Future fixture
helpers can stay private until they are used by multiple packages and have a
clear user-facing contract.

```python
from bluetape.testing import eventually

eventually(lambda: cache.get("ready"), timeout=2.0, interval=0.01)
```

Async probes are supported when tests run with `pytest-asyncio`:

```python
from bluetape.testing import eventually_async

value = await eventually_async(fetch_state, timeout=2.0)
```

## Contract

- `eventually(probe, timeout=..., interval=...)` polls until the probe returns
  any value except `None` or `False`.
- `eventually_async(...)` applies the same contract to awaitable probes.
- `timeout` and `interval` must be greater than zero.
- The helpers raise `AssertionError` when the condition is not satisfied in
  time.
- The package depends on `pytest`; that dependency does not leak into
  `bluetape-core` or the default `bluetape` install.
