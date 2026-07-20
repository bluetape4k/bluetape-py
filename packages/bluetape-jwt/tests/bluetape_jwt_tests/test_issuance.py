"""Composable issuance-policy decorator contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import bluetape.jwt as jwt
import pytest

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def make_claims(**overrides: object) -> jwt.TokenClaims:
    values = {
        "issuer": "issuer",
        "subject": "subject",
        "audience": ("api",),
        "custom": {"scope": "read", "nested": {"roles": ["reader"]}},
    }
    values.update(overrides)
    return jwt.TokenClaims(**values)


class RecordingProvider:
    def __init__(self) -> None:
        self.issued: list[jwt.TokenClaims] = []
        self.verified: list[str] = []
        self.verified_result = object()

    def issue(self, claims: jwt.TokenClaims) -> str:
        self.issued.append(claims)
        return "signed-token"

    def verify(self, token: str) -> object:
        self.verified.append(token)
        return self.verified_result


def test_decorator_transforms_a_copy_and_delegates_verify_unchanged() -> None:
    recording = RecordingProvider()
    clock_calls = 0

    def clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    profile = jwt.IssuanceProfile(default_ttl=timedelta(hours=1), clock=clock)
    provider_type = getattr(jwt, "IssuanceProfileProvider", None)
    assert provider_type is not None
    provider = provider_type(recording, profile)
    original = make_claims()

    assert provider.issue(original) == "signed-token"
    assert original == make_claims()
    assert recording.issued == [make_claims(issued_at=NOW, expires_at=NOW + timedelta(hours=1))]
    assert recording.issued[0] is not original
    assert clock_calls == 1

    assert provider.verify("opaque-token") is recording.verified_result
    assert recording.verified == ["opaque-token"]


def test_explicit_issued_at_and_expiration_are_preserved() -> None:
    recording = RecordingProvider()
    explicit_iat = NOW - timedelta(hours=1)
    explicit_exp = NOW + timedelta(hours=1)
    clock_calls = 0

    def clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    provider = jwt.IssuanceProfileProvider(
        recording,
        jwt.IssuanceProfile(
            default_ttl=timedelta(minutes=5),
            max_ttl=timedelta(hours=2),
            clock=clock,
        ),
    )

    provider.issue(make_claims(issued_at=explicit_iat, expires_at=explicit_exp))

    assert recording.issued[0].issued_at == explicit_iat
    assert recording.issued[0].expires_at == explicit_exp
    assert clock_calls == 1


def test_default_ttl_uses_effective_time_without_emitting_issued_at() -> None:
    recording = RecordingProvider()
    provider = jwt.IssuanceProfileProvider(
        recording,
        jwt.IssuanceProfile(
            default_ttl=timedelta(days=7),
            add_issued_at=False,
            clock=lambda: NOW,
        ),
    )

    provider.issue(make_claims())

    assert recording.issued[0].issued_at is None
    assert recording.issued[0].expires_at == NOW + timedelta(days=7)


def test_default_ttl_uses_caller_issued_at_as_effective_time() -> None:
    recording = RecordingProvider()
    issued_at = NOW - timedelta(minutes=30)
    provider = jwt.IssuanceProfileProvider(
        recording,
        jwt.IssuanceProfile(
            default_ttl=timedelta(hours=1),
            clock=lambda: NOW,
        ),
    )

    provider.issue(make_claims(issued_at=issued_at))

    assert recording.issued[0].issued_at == issued_at
    assert recording.issued[0].expires_at == issued_at + timedelta(hours=1)


@pytest.mark.parametrize("add_issued_at", [False, True])
def test_no_default_ttl_never_invents_an_expiration(add_issued_at: bool) -> None:
    recording = RecordingProvider()
    provider = jwt.IssuanceProfileProvider(
        recording,
        jwt.IssuanceProfile(
            default_ttl=None,
            add_issued_at=add_issued_at,
            clock=lambda: NOW,
        ),
    )

    provider.issue(make_claims())

    assert recording.issued[0].expires_at is None
    expected_iat = NOW if add_issued_at else None
    assert recording.issued[0].issued_at == expected_iat


@pytest.mark.parametrize(
    "claims",
    [
        make_claims(expires_at=NOW),
        make_claims(expires_at=NOW - timedelta(seconds=1)),
        make_claims(
            not_before=NOW + timedelta(minutes=1),
            expires_at=NOW + timedelta(minutes=1),
        ),
        make_claims(expires_at=NOW + timedelta(hours=2)),
    ],
)
def test_invalid_ordering_or_excessive_lifetime_is_rejected(
    claims: jwt.TokenClaims,
) -> None:
    provider = jwt.IssuanceProfileProvider(
        RecordingProvider(),
        jwt.IssuanceProfile(
            default_ttl=None,
            max_ttl=timedelta(hours=1),
            add_issued_at=False,
            clock=lambda: NOW,
        ),
    )

    with pytest.raises(jwt.JWTIssuancePolicyError):
        provider.issue(claims)


def test_explicit_issued_at_controls_maximum_lifetime() -> None:
    recording = RecordingProvider()
    provider = jwt.IssuanceProfileProvider(
        recording,
        jwt.IssuanceProfile(
            max_ttl=timedelta(hours=2),
            clock=lambda: NOW,
        ),
    )
    issued_at = NOW - timedelta(hours=1)

    provider.issue(
        make_claims(
            issued_at=issued_at,
            expires_at=issued_at + timedelta(hours=2),
        )
    )

    assert recording.issued[0].issued_at == issued_at
    assert recording.issued[0].expires_at == issued_at + timedelta(hours=2)


def test_decorator_references_are_frozen() -> None:
    provider = jwt.IssuanceProfileProvider(
        RecordingProvider(),
        jwt.IssuanceProfile(clock=lambda: NOW),
    )

    with pytest.raises(FrozenInstanceError):
        provider.profile = jwt.IssuanceProfile()


def test_clock_failure_is_redacted_before_delegation() -> None:
    recording = RecordingProvider()

    def clock() -> datetime:
        raise RuntimeError("canary-secret")

    provider = jwt.IssuanceProfileProvider(
        recording,
        jwt.IssuanceProfile(clock=clock),
    )

    with pytest.raises(jwt.JWTConfigurationError) as captured:
        provider.issue(make_claims())

    assert recording.issued == []
    assert "canary-secret" not in str(captured.value)
    assert captured.value.__cause__ is None


class ReversibleEnvelope:
    def __init__(self, provider: jwt.TokenProvider) -> None:
        self._provider = provider

    def issue(self, claims: jwt.TokenClaims) -> str:
        return f"envelope:{self._provider.issue(claims)}"

    def verify(self, token: str) -> jwt.VerifiedToken:
        if not token.startswith("envelope:"):
            raise jwt.JWTMalformedTokenError() from None
        return self._provider.verify(token.removeprefix("envelope:"))


def test_issuance_decorator_composes_with_reversible_outer_provider() -> None:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    validation = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        required_claims=frozenset({"scope"}),
        clock=lambda: NOW,
    )
    signer = jwt.JWSProvider(
        jwt.JWSAlgorithm.HS256,
        jwt.InMemoryKeyRepository(active=key),
        validation,
    )
    issuance = jwt.IssuanceProfileProvider(
        signer,
        jwt.IssuanceProfile(default_ttl=timedelta(hours=1), clock=lambda: NOW),
    )
    provider = ReversibleEnvelope(issuance)

    token = provider.issue(make_claims())
    verified = provider.verify(token)

    assert token.startswith("envelope:")
    assert verified.issuer == "issuer"
    assert verified.expires_at == NOW + timedelta(hours=1)
