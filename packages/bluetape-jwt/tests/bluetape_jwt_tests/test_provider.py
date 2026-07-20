"""Strict uncached JWS provider contract tests."""

from __future__ import annotations

import json
from base64 import urlsafe_b64decode
from datetime import UTC, datetime, timedelta
from inspect import signature
from typing import get_type_hints

import bluetape.jwt as jwt
import bluetape.jwt._provider as provider_module
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

NOW = datetime(2025, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def rsa_private_pem() -> bytes:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def make_key(algorithm: jwt.JWSAlgorithm, rsa_private_pem: bytes) -> jwt.JWTKey:
    if algorithm.value.startswith("HS"):
        secret_size = int(algorithm.value[2:]) // 8
        return jwt.JWTKey.from_hmac_secret(
            "current-key",
            algorithm,
            b"s" * secret_size,
        )
    return jwt.JWTKey.from_rsa_private(
        "current-key",
        algorithm,
        rsa_private_pem,
    )


def make_profile(**overrides: object) -> jwt.ValidationProfile:
    values = {
        "token_type": "access+jwt",
        "allowed_issuers": frozenset({"issuer"}),
        "accepted_audiences": frozenset({"api"}),
        "required_claims": frozenset({"scope"}),
        "protected_headers": {"tenant": "primary"},
        "clock": lambda: NOW,
    }
    values.update(overrides)
    return jwt.ValidationProfile(**values)


def make_claims(**overrides: object) -> jwt.TokenClaims:
    values = {
        "issuer": "issuer",
        "subject": "subject",
        "audience": ("api",),
        "expires_at": NOW + timedelta(hours=1),
        "issued_at": NOW,
        "jwt_id": "token-id",
        "custom": {"scope": "read", "nested": {"roles": ["reader"]}},
    }
    values.update(overrides)
    return jwt.TokenClaims(**values)


def decode_segment(segment: str) -> object:
    padding = "=" * (-len(segment) % 4)
    return json.loads(urlsafe_b64decode(segment + padding))


@pytest.mark.parametrize("algorithm", list(jwt.JWSAlgorithm))
def test_provider_round_trips_each_algorithm(
    algorithm: jwt.JWSAlgorithm,
    rsa_private_pem: bytes,
) -> None:
    provider_type = getattr(jwt, "JWSProvider", None)
    assert provider_type is not None

    key = make_key(algorithm, rsa_private_pem)
    repository = jwt.InMemoryKeyRepository(active=key)
    provider = provider_type(algorithm, repository, make_profile())
    claims = make_claims()

    token = provider.issue(claims)
    verified = provider.verify(token)
    protected = decode_segment(token.split(".")[0])

    assert protected == {
        "alg": algorithm.value,
        "kid": "current-key",
        "tenant": "primary",
        "typ": "access+jwt",
    }
    assert verified.algorithm is algorithm
    assert verified.kid == "current-key"
    assert verified.token_type == "access+jwt"
    assert verified.issuer == "issuer"
    assert verified.audience == ("api",)
    assert verified.custom == {"scope": "read", "nested": {"roles": ("reader",)}}
    assert claims == make_claims()


def test_verified_headers_are_custom_only(rsa_private_pem: bytes) -> None:
    key = make_key(jwt.JWSAlgorithm.HS256, rsa_private_pem)
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        jwt.InMemoryKeyRepository(active=key),
        make_profile(),
    )

    verified = provider.verify(provider.issue(make_claims()))

    assert verified.headers == {"tenant": "primary"}


def test_provider_surface_binds_policy_at_construction() -> None:
    constructor = signature(jwt.JWSProvider)
    issue = signature(jwt.JWSProvider.issue)
    verify = signature(jwt.JWSProvider.verify)

    assert tuple(constructor.parameters) == (
        "algorithm",
        "repository",
        "validation_profile",
        "cache",
    )
    assert constructor.parameters["cache"].kind.name == "KEYWORD_ONLY"
    assert tuple(issue.parameters) == ("self", "claims")
    assert tuple(verify.parameters) == ("self", "token")
    assert tuple(signature(jwt.TokenProvider.issue).parameters) == ("self", "claims")
    assert tuple(signature(jwt.TokenProvider.verify).parameters) == ("self", "token")
    assert get_type_hints(jwt.TokenProvider.issue)["return"] is str
    assert get_type_hints(jwt.TokenProvider.verify)["return"] is jwt.VerifiedToken


def test_provider_uses_active_and_retired_keys_but_not_revoked_keys(
    rsa_private_pem: bytes,
) -> None:
    old_key = jwt.JWTKey.from_hmac_secret(
        "old-key",
        jwt.JWSAlgorithm.HS256,
        b"o" * 32,
    )
    new_key = jwt.JWTKey.from_hmac_secret(
        "new-key",
        jwt.JWSAlgorithm.HS256,
        b"n" * 32,
    )
    repository = jwt.InMemoryKeyRepository(active=old_key)
    provider = jwt.JWSProvider(jwt.JWSAlgorithm.HS256, repository, make_profile())
    old_token = provider.issue(make_claims(jwt_id="old-token"))

    repository.rotate(new_key)
    assert provider.verify(old_token).kid == "old-key"
    new_token = provider.issue(make_claims(jwt_id="new-token"))
    assert provider.verify(new_token).kid == "new-key"

    repository.revoke("old-key")
    with pytest.raises(jwt.JWTKeyUnavailableError):
        provider.verify(old_token)


def test_provider_rejects_missing_key_and_bad_signature(
    rsa_private_pem: bytes,
) -> None:
    key = make_key(jwt.JWSAlgorithm.HS256, rsa_private_pem)
    repository = jwt.InMemoryKeyRepository(active=key)
    provider = jwt.JWSProvider(jwt.JWSAlgorithm.HS256, repository, make_profile())
    token = provider.issue(make_claims())
    header, payload, signature_segment = token.split(".")
    replacement = "A" if signature_segment[0] != "A" else "B"
    corrupted = replacement + signature_segment[1:]

    with pytest.raises(jwt.JWTSignatureError):
        provider.verify(f"{header}.{payload}.{corrupted}")

    repository.revoke("current-key")
    with pytest.raises(jwt.JWTKeyUnavailableError):
        provider.verify(token)


@pytest.mark.parametrize(
    ("claims", "expected_error"),
    [
        (make_claims(issuer="other"), jwt.JWTClaimError),
        (make_claims(audience=("other",)), jwt.JWTClaimError),
        (make_claims(custom={}), jwt.JWTClaimError),
        (make_claims(expires_at=NOW), jwt.JWTExpiredError),
        (
            make_claims(not_before=NOW + timedelta(seconds=1)),
            jwt.JWTNotYetValidError,
        ),
        (
            make_claims(issued_at=NOW + timedelta(seconds=1)),
            jwt.JWTNotYetValidError,
        ),
    ],
)
def test_provider_maps_profile_failures_to_typed_errors(
    claims: jwt.TokenClaims,
    expected_error: type[jwt.JWTError],
    rsa_private_pem: bytes,
) -> None:
    key = make_key(jwt.JWSAlgorithm.HS256, rsa_private_pem)
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        jwt.InMemoryKeyRepository(active=key),
        make_profile(),
    )

    with pytest.raises(expected_error):
        provider.verify(provider.issue(claims))


class FailingRepository:
    def snapshot(self) -> jwt.KeySnapshot:
        raise RuntimeError("canary-secret")


def test_repository_failure_is_typed_and_redacted() -> None:
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        FailingRepository(),
        make_profile(),
    )

    with pytest.raises(jwt.JWTKeyUnavailableError) as captured:
        provider.verify("e30.e30.c2ln")

    assert "canary-secret" not in str(captured.value)
    assert captured.value.__cause__ is None


def test_dependency_failures_are_typed_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_pem: bytes,
) -> None:
    key = make_key(jwt.JWSAlgorithm.HS256, rsa_private_pem)
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        jwt.InMemoryKeyRepository(active=key),
        make_profile(),
    )
    token = provider.issue(make_claims())

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("canary-secret")

    monkeypatch.setattr(provider_module.jwt, "decode", fail)
    with pytest.raises(jwt.JWTSignatureError) as captured:
        provider.verify(token)
    assert "canary-secret" not in str(captured.value)
    assert captured.value.__cause__ is None

    monkeypatch.setattr(provider_module.jwt, "encode", fail)
    with pytest.raises(jwt.JWTTokenError) as captured:
        provider.issue(make_claims())
    assert "canary-secret" not in str(captured.value)
    assert captured.value.__cause__ is None


def test_verify_captures_one_snapshot_and_one_clock(
    rsa_private_pem: bytes,
) -> None:
    key = make_key(jwt.JWSAlgorithm.HS256, rsa_private_pem)
    repository = RepositorySpy(jwt.InMemoryKeyRepository(active=key))
    clock_calls = 0

    def clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    profile = make_profile(clock=clock)
    provider = jwt.JWSProvider(jwt.JWSAlgorithm.HS256, repository, profile)
    token = provider.issue(make_claims())
    repository.snapshot_calls = 0

    provider.verify(token)

    assert repository.snapshot_calls == 1
    assert clock_calls == 1


def test_shape_preflight_runs_before_snapshot_and_clock() -> None:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    repository = RepositorySpy(jwt.InMemoryKeyRepository(active=key))
    clock_calls = 0

    def clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        repository,
        make_profile(clock=clock),
    )

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify("not-a-compact-token")

    assert repository.snapshot_calls == 0
    assert clock_calls == 0


class RepositorySpy:
    def __init__(self, repository: jwt.InMemoryKeyRepository) -> None:
        self._repository = repository
        self.snapshot_calls = 0

    def snapshot(self) -> jwt.KeySnapshot:
        self.snapshot_calls += 1
        return self._repository.snapshot()
