# bluetape-core

[English](README.md) | 한국어

Python-native bluetape package를 위한 표준 라이브러리 전용 foundation helper입니다.

`bluetape.core`에서 import합니다.

## Public API

`bluetape-core`는 `0.1.0`에서 의도적으로 작게 유지합니다. 성공 시 caller의 원래 value를 반환하고 잘못된 입력에는 명시적 exception을 발생시키는 재사용 가능한 validation guard를 소유합니다.

```python
from bluetape.core import require_instance, require_not_blank, require_not_empty

name = require_not_blank("orders", "service_name")
tags = require_not_empty(["api"], "tags")
tenant = require_instance("blue", str, "tenant")
```

## 계약

- `require_not_none(value, name)`은 `value is None`일 때 `ValueError`를 발생시킵니다.
- `require_not_blank(value, name)`은 blank string에 `ValueError`를 발생시키고 원래 string을 변경 없이 반환합니다.
- `require_not_empty(value, name)`은 비어 있는 sized value에 `ValueError`를 발생시킵니다.
- `require_instance(value, expected_type, name)`은 value가 기대한 runtime type과 일치하지 않을 때 `TypeError`를 발생시킵니다.

이 package에는 runtime dependency가 없습니다.
