# bluetape-logging

Stdlib `logging` and `contextvars` helpers for Python-native bluetape packages.

Import from `bluetape.logging`.

## Public API

`bluetape-logging` does not replace Python's logging framework. It provides
small helpers that keep context caller-owned and context-local.

```python
import logging

from bluetape.logging import ContextLogFilter, log_context, redact

logger = logging.getLogger("orders")
logger.addFilter(ContextLogFilter())

with log_context(trace_id="trace-1", tenant="blue"):
    logger.info("order accepted")

safe_fields = redact({"Authorization": "secret", "tenant": "blue"}, keys={"authorization"})
```

## Contract

- `log_context(**values)` merges values into the current `contextvars` context
  and restores the previous context when the block exits.
- `log_context(override=False, **values)` rejects duplicate keys with
  `KeyError` instead of replacing an existing context value.
- `get_log_context()` returns a shallow copy so callers cannot mutate internal
  context state.
- `ContextLogFilter` adds current context fields to each `logging.LogRecord`.
- `redact(values, keys=...)` returns a copy and matches sensitive keys
  case-insensitively by default.

The package is stdlib-only at runtime.
