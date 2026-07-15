import json
import uuid

import pytest
from bluetape.id import UUID7Generator, parse_ulid


def test_values_use_stdlib_or_primitive_serialization_only() -> None:
    value = UUID7Generator(clock=lambda: 1, random_bytes=lambda size: bytes(size)).new()
    with pytest.raises(TypeError):
        json.dumps(value)
    assert json.loads(json.dumps(parse_ulid("00000000000000000000000000"))) == (
        "00000000000000000000000000"
    )
    assert isinstance(value, uuid.UUID)
