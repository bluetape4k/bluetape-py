"""Immutable JWT issuance and validation policy tests."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import bluetape.jwt as jwt
import pytest
from bluetape.jwt._profiles import _validate_claims


def test_validation_profile_fingerprint_is_stable() -> None:
    profile_type = getattr(jwt, "ValidationProfile", None)
    assert profile_type is not None

    first = profile_type(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer-b", "issuer-a"}),
        accepted_audiences=frozenset({"audience-b", "audience-a"}),
        required_claims=frozenset({"scope"}),
        protected_headers={"tenant": "primary", "version": "1"},
        clock=lambda: datetime(2025, 1, 1, tzinfo=UTC),
    )
    second = profile_type(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer-a", "issuer-b"}),
        accepted_audiences=frozenset({"audience-a", "audience-b"}),
        required_claims=frozenset({"scope"}),
        protected_headers={"version": "1", "tenant": "primary"},
        clock=lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )

    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_issuance_profile_validates_configuration_without_calling_clock() -> None:
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return datetime.now(UTC)

    profile = jwt.IssuanceProfile(default_ttl=None, max_ttl=None, clock=clock)
    assert profile.default_ttl is None
    assert calls == 0

    with pytest.raises(FrozenInstanceError):
        profile.default_ttl = timedelta(days=1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_ttl": timedelta(0)},
        {"default_ttl": timedelta(seconds=-1)},
        {"max_ttl": timedelta(0)},
        {"max_ttl": timedelta(seconds=-1)},
        {"default_ttl": timedelta(seconds=2), "max_ttl": timedelta(seconds=1)},
        {"add_issued_at": 1},
        {"clock": None},
    ],
)
def test_issuance_profile_rejects_invalid_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(jwt.JWTConfigurationError):
        jwt.IssuanceProfile(**kwargs)


def test_validation_profile_freezes_policy_and_adds_mandatory_claims() -> None:
    issuers = {"issuer"}
    audiences = {"api"}
    required = {"scope"}
    headers = {"tenant": "primary"}
    profile = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=issuers,
        accepted_audiences=audiences,
        required_claims=required,
        protected_headers=headers,
        max_token_age=timedelta(hours=1),
    )
    issuers.add("changed")
    audiences.add("changed")
    required.add("changed")
    headers["tenant"] = "changed"

    assert profile.allowed_issuers == frozenset({"issuer"})
    assert profile.accepted_audiences == frozenset({"api"})
    assert profile.required_claims == frozenset({"iss", "aud", "iat", "scope"})
    assert isinstance(profile.protected_headers, MappingProxyType)
    assert profile.protected_headers == {"tenant": "primary"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"token_type": ""},
        {"token_type": " access+jwt "},
        {"allowed_issuers": frozenset()},
        {"allowed_issuers": frozenset({""})},
        {"accepted_audiences": frozenset()},
        {"accepted_audiences": frozenset({1})},
        {"required_claims": frozenset({" bad "})},
        {"protected_headers": {"alg": "HS256"}},
        {"protected_headers": {"tenant": ""}},
        {"clock_skew": timedelta(seconds=-1)},
        {"max_token_age": timedelta(0)},
        {"clock": None},
    ],
)
def test_validation_profile_rejects_invalid_configuration(kwargs: dict[str, object]) -> None:
    values = {
        "token_type": "access+jwt",
        "allowed_issuers": frozenset({"issuer"}),
        "accepted_audiences": frozenset({"api"}),
    }
    values.update(kwargs)
    with pytest.raises(jwt.JWTConfigurationError):
        jwt.ValidationProfile(**values)


def test_validation_profile_constructor_does_not_call_clock() -> None:
    def clock() -> datetime:
        raise AssertionError("constructor called clock")

    jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        clock=clock,
    )


def make_profile(**overrides: object) -> jwt.ValidationProfile:
    values = {
        "token_type": "access+jwt",
        "allowed_issuers": frozenset({"issuer"}),
        "accepted_audiences": frozenset({"api"}),
        "required_claims": frozenset({"scope"}),
        "protected_headers": {"tenant": "primary"},
    }
    values.update(overrides)
    return jwt.ValidationProfile(**values)


def make_claims(**overrides: object) -> jwt.TokenClaims:
    values = {
        "issuer": "issuer",
        "audience": ("api",),
        "issued_at": datetime(2025, 1, 1, tzinfo=UTC),
        "custom": {"scope": "read"},
    }
    values.update(overrides)
    return jwt.TokenClaims(**values)


def test_same_reference_time_validation_accepts_exact_policy() -> None:
    now = datetime(2025, 1, 1, 0, 30, tzinfo=UTC)
    profile = make_profile(max_token_age=timedelta(hours=1))
    _validate_claims(
        make_claims(expires_at=now + timedelta(seconds=1)),
        profile,
        token_type="access+jwt",
        protected_headers={"tenant": "primary"},
        now=now,
    )


@pytest.mark.parametrize(
    ("claims", "error"),
    [
        (make_claims(issuer="other"), jwt.JWTClaimError),
        (make_claims(audience=("other",)), jwt.JWTClaimError),
        (make_claims(custom={}), jwt.JWTClaimError),
        (make_claims(expires_at=datetime(2025, 1, 1, tzinfo=UTC)), jwt.JWTExpiredError),
        (
            make_claims(not_before=datetime(2025, 1, 1, 0, 0, 1, tzinfo=UTC)),
            jwt.JWTNotYetValidError,
        ),
        (
            make_claims(issued_at=datetime(2025, 1, 1, 0, 0, 1, tzinfo=UTC)),
            jwt.JWTNotYetValidError,
        ),
    ],
)
def test_same_reference_time_validation_rejects_claim_violations(
    claims: jwt.TokenClaims,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        _validate_claims(
            claims,
            make_profile(),
            token_type="access+jwt",
            protected_headers={"tenant": "primary"},
            now=datetime(2025, 1, 1, tzinfo=UTC),
        )


def test_same_reference_time_validation_applies_skew_and_max_age() -> None:
    now = datetime(2025, 1, 1, 1, tzinfo=UTC)
    profile = make_profile(
        clock_skew=timedelta(seconds=5),
        max_token_age=timedelta(hours=1),
    )
    _validate_claims(
        make_claims(
            not_before=now + timedelta(seconds=4),
            issued_at=now - timedelta(hours=1, seconds=4),
        ),
        profile,
        token_type="access+jwt",
        protected_headers={"tenant": "primary"},
        now=now,
    )
    with pytest.raises(jwt.JWTExpiredError):
        _validate_claims(
            make_claims(issued_at=now - timedelta(hours=1, seconds=6)),
            profile,
            token_type="access+jwt",
            protected_headers={"tenant": "primary"},
            now=now,
        )


def test_temporal_validation_never_overflows_with_accepted_durations() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    unlimited_skew = make_profile(clock_skew=timedelta.max)
    _validate_claims(
        make_claims(expires_at=now - timedelta(seconds=1)),
        unlimited_skew,
        token_type="access+jwt",
        protected_headers={"tenant": "primary"},
        now=now,
    )

    huge_max_age = make_profile(
        clock_skew=timedelta(microseconds=1),
        max_token_age=timedelta.max,
    )
    _validate_claims(
        make_claims(issued_at=datetime.min.replace(tzinfo=UTC)),
        huge_max_age,
        token_type="access+jwt",
        protected_headers={"tenant": "primary"},
        now=now,
    )


def test_same_reference_time_validation_rejects_exp_not_after_nbf() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    with pytest.raises(jwt.JWTClaimError):
        _validate_claims(
            make_claims(
                expires_at=now + timedelta(seconds=1),
                not_before=now + timedelta(seconds=1),
            ),
            make_profile(clock_skew=timedelta(seconds=2)),
            token_type="access+jwt",
            protected_headers={"tenant": "primary"},
            now=now,
        )


@pytest.mark.parametrize(
    ("token_type", "headers"),
    [
        ("other+jwt", {"tenant": "primary"}),
        ("access+jwt", {}),
        ("access+jwt", {"tenant": "other"}),
        ("access+jwt", {"tenant": "primary", "extra": "value"}),
    ],
)
def test_same_reference_time_validation_rejects_header_policy(
    token_type: str,
    headers: dict[str, str],
) -> None:
    with pytest.raises(jwt.JWTUnsupportedTokenError):
        _validate_claims(
            make_claims(),
            make_profile(),
            token_type=token_type,
            protected_headers=headers,
            now=datetime(2025, 1, 1, tzinfo=UTC),
        )
