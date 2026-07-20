"""Caller-preserving issuance policy decorator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NoReturn

from bluetape.jwt._claims import TokenClaims, VerifiedToken
from bluetape.jwt._errors import JWTConfigurationError, JWTIssuancePolicyError
from bluetape.jwt._profiles import IssuanceProfile
from bluetape.jwt._provider import TokenProvider


def _raise_issuance_policy_error() -> NoReturn:
    raise JWTIssuancePolicyError() from None


def _capture_issuance_time(profile: IssuanceProfile) -> datetime:
    try:
        now = profile.clock()
        if type(now) is not datetime or now.utcoffset() is None:
            raise JWTConfigurationError() from None
        return now.astimezone(UTC)
    except JWTConfigurationError:
        raise
    except Exception:
        raise JWTConfigurationError() from None


def _apply_issuance_profile(
    claims: TokenClaims,
    profile: IssuanceProfile,
    *,
    now: datetime,
) -> TokenClaims:
    """Return a new claims value with only configured temporal defaults applied."""
    if type(claims) is not TokenClaims or type(profile) is not IssuanceProfile:
        _raise_issuance_policy_error()
    try:
        if type(now) is not datetime or now.utcoffset() is None:
            _raise_issuance_policy_error()
        reference_time = now.astimezone(UTC)
        effective_time = claims.issued_at or reference_time
        issued_at = claims.issued_at
        if issued_at is None and profile.add_issued_at:
            issued_at = reference_time

        expires_at = claims.expires_at
        if expires_at is None and profile.default_ttl is not None:
            expires_at = effective_time + profile.default_ttl

        if expires_at is not None:
            if expires_at <= effective_time:
                _raise_issuance_policy_error()
            if claims.not_before is not None and expires_at <= claims.not_before:
                _raise_issuance_policy_error()
            if profile.max_ttl is not None and expires_at - effective_time > profile.max_ttl:
                _raise_issuance_policy_error()

        return TokenClaims(
            issuer=claims.issuer,
            subject=claims.subject,
            audience=claims.audience,
            expires_at=expires_at,
            not_before=claims.not_before,
            issued_at=issued_at,
            jwt_id=claims.jwt_id,
            custom=claims.custom,
        )
    except JWTIssuancePolicyError:
        raise
    except Exception:
        _raise_issuance_policy_error()


@dataclass(frozen=True, slots=True)
class IssuanceProfileProvider:
    """Apply immutable issuance defaults before delegating to another provider."""

    provider: TokenProvider
    profile: IssuanceProfile

    def __post_init__(self) -> None:
        if (
            not callable(getattr(self.provider, "issue", None))
            or not callable(getattr(self.provider, "verify", None))
            or type(self.profile) is not IssuanceProfile
        ):
            raise JWTConfigurationError() from None

    def issue(self, claims: TokenClaims) -> str:
        """Apply one issuance policy using one captured clock value."""
        now = _capture_issuance_time(self.profile)
        transformed = _apply_issuance_profile(claims, self.profile, now=now)
        return self.provider.issue(transformed)

    def verify(self, token: str) -> VerifiedToken:
        """Delegate verification without changing the token or result."""
        return self.provider.verify(token)
