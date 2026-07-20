"""Logging ownership and public dependency boundary tests."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import bluetape.jwt as jwt
import pytest

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def test_import_and_construction_do_not_change_global_logging_state() -> None:
    script = """
import json
import logging

root = logging.getLogger()
before = (tuple(root.handlers), root.level, root.disabled)

import bluetape.jwt as jwt

key = jwt.JWTKey.from_hmac_secret(
    "current-key", jwt.JWSAlgorithm.HS256, b"s" * 32
)
repository = jwt.InMemoryKeyRepository(active=key)
profile = jwt.ValidationProfile(
    token_type="access+jwt",
    allowed_issuers=frozenset({"issuer"}),
    accepted_audiences=frozenset({"api"}),
)
jwt.JWSProvider(
    jwt.JWSAlgorithm.HS256,
    repository,
    profile,
    cache=jwt.VerifiedTokenCacheOptions(
        default_ttl=__import__("datetime").timedelta(seconds=1),
        max_size=1,
    ),
)

after = (tuple(root.handlers), root.level, root.disabled)
owned = []
for name in ("bluetape.jwt._repository", "bluetape.jwt._cache"):
    logger = logging.getLogger(name)
    owned.append((tuple(logger.handlers), logger.level, logger.disabled, logger.propagate))
print(json.dumps({
    "root_unchanged": before == after,
    "owned_default": owned == [
        ((), logging.NOTSET, False, True),
        ((), logging.NOTSET, False, True),
    ],
}))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "root_unchanged": True,
        "owned_default": True,
    }
    assert completed.stderr == ""


def test_success_cache_hit_and_invalid_token_emit_no_package_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        jwt.InMemoryKeyRepository(active=key),
        jwt.ValidationProfile(
            token_type="access+jwt",
            allowed_issuers=frozenset({"issuer"}),
            accepted_audiences=frozenset({"api"}),
            clock=lambda: NOW,
        ),
        cache=jwt.VerifiedTokenCacheOptions(timedelta(minutes=1), 2),
    )
    claims = jwt.TokenClaims(issuer="issuer", audience=("api",))
    caplog.set_level(logging.DEBUG, logger="bluetape.jwt")

    token = provider.issue(claims)
    provider.verify(token)
    provider.verify(token)
    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify("invalid-token")

    assert caplog.records == []


def test_public_graph_does_not_export_dependencies_or_private_helpers() -> None:
    assert "TTLCache" not in jwt.__all__
    assert "joserfc" not in jwt.__all__
    assert all(not name.startswith("_") for name in jwt.__all__)
    assert not hasattr(jwt, "TTLCache")
    assert not hasattr(jwt, "joserfc")

    for name in jwt.__all__:
        value = getattr(jwt, name)
        module = getattr(value, "__module__", "")
        assert not module.startswith(("joserfc", "bluetape.cache"))
