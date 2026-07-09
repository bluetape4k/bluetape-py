# bluetape-core

Stdlib-only foundation helpers for Python-native bluetape packages.

Import from `bluetape.core`.

## Public API

`bluetape-core` is intentionally small in `0.1.0`. It owns reusable validation
guards that return the original caller value on success and raise explicit
exceptions on invalid input.

```python
from bluetape.core import require_instance, require_not_blank, require_not_empty

name = require_not_blank("orders", "service_name")
tags = require_not_empty(["api"], "tags")
tenant = require_instance("blue", str, "tenant")
```

## Contract

- `require_not_none(value, name)` raises `ValueError` when `value is None`.
- `require_not_blank(value, name)` raises `ValueError` for blank strings and
  returns the original string unchanged.
- `require_not_empty(value, name)` raises `ValueError` for empty sized values.
- `require_instance(value, expected_type, name)` raises `TypeError` when the
  value does not match the expected runtime type.

The package has no runtime dependencies.
