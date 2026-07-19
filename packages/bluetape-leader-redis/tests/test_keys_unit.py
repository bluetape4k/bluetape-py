# ruff: noqa: RUF043
from __future__ import annotations

import hashlib
import traceback

import pytest
from bluetape.leader import InvalidLockNameError
from bluetape.leader.redis._keys import _redis_keys, _validated_prefix


def test_identity_uses_exact_utf8_sha256_and_same_slot_without_raw_name() -> None:
    name = "tenant-secret-job"
    digest = hashlib.sha256(name.encode()).hexdigest()

    keys = _redis_keys(name, "bluetape-leader")

    assert keys.lease == f"bluetape-leader:{{{digest}}}:lease"
    assert keys.fence == f"bluetape-leader:{{{digest}}}:fence"
    assert keys.history == f"bluetape-leader:{{{digest}}}:history"
    assert keys.lease.split("}", 1)[0] == keys.fence.split("}", 1)[0]
    assert keys.lease.split("}", 1)[0] == keys.history.split("}", 1)[0]
    assert name not in keys.lease
    assert repr(keys) == "_RedisKeys(<redacted>)"


def test_identity_preserves_nfc_nfd_and_whitespace() -> None:
    assert _redis_keys("é", "p") != _redis_keys("e\u0301", "p")
    assert _redis_keys(" job ", "p") != _redis_keys("job", "p")


@pytest.mark.parametrize("name", ["", " ", "\t\n", "a" * 1025, b"job", True])
def test_identity_rejects_invalid_lock_name(name: object) -> None:
    with pytest.raises(InvalidLockNameError, match="^lock name is invalid$"):
        _redis_keys(name, "p")  # type: ignore[arg-type]


def test_identity_accepts_exact_1024_utf8_bytes() -> None:
    keys = _redis_keys("é" * 512, "p")
    assert keys.lease.endswith(":lease")


def test_identity_rejects_surrogate_without_exposing_original_value() -> None:
    marker = "surrogate-canary-\ud800"

    with pytest.raises(InvalidLockNameError) as caught:
        _redis_keys(marker, "p")

    error = caught.value
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert error.args == ("lock name is invalid",)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert marker not in repr(error)
    assert marker not in rendered


@pytest.mark.parametrize(
    "prefix",
    ["", "a" * 65, "a:b", "a{b", "a b", "한글", b"p", True],
)
def test_identity_rejects_unsafe_prefix(prefix: object) -> None:
    with pytest.raises(ValueError, match="^Redis key prefix is invalid$"):
        _validated_prefix(prefix)  # type: ignore[arg-type]


def test_identity_accepts_ascii_allowlist_boundaries() -> None:
    assert _validated_prefix("A.a_0-9") == "A.a_0-9"
    assert _validated_prefix("a" * 64) == "a" * 64
