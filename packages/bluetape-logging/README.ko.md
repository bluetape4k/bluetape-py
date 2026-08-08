# bluetape-logging

[English](README.md) | 한국어

Python-native bluetape package를 위한 표준 라이브러리 `logging` 및 `contextvars` helper입니다.

`bluetape.logging`에서 import합니다.

## Public API

`bluetape-logging`은 Python logging framework를 대체하지 않습니다. context를 caller-owned 및 context-local로 유지하는 작은 helper를 제공합니다.

```python
import logging

from bluetape.logging import ContextLogFilter, log_context, redact

logger = logging.getLogger("orders")
logger.addFilter(ContextLogFilter())

with log_context(trace_id="trace-1", tenant="blue"):
    logger.info("order accepted")

safe_fields = redact({"Authorization": "secret", "tenant": "blue"}, keys={"authorization"})
```

## 계약

- `log_context(**values)`는 현재 `contextvars` context에 value를 병합하고 block이 종료되면 이전 context를 복원합니다.
- `log_context(override=False, **values)`는 기존 context value를 대체하지 않고 중복 key에 `KeyError`를 발생시킵니다.
- `get_log_context()`는 shallow copy를 반환하므로 caller가 내부 context state를 변경할 수 없습니다.
- `ContextLogFilter`는 현재 context field를 각 `logging.LogRecord`에 추가합니다.
- `redact(values, keys=...)`는 copy를 반환하며 기본적으로 sensitive key를 case-insensitive하게 비교합니다.

이 package는 runtime에서 표준 라이브러리만 사용합니다.
