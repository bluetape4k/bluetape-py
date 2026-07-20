"""Immutable JWT issuance and validation policy values."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import NoReturn

from bluetape.jwt._claims import TokenClaims
from bluetape.jwt._errors import (
    JWTClaimError,
    JWTConfigurationError,
    JWTExpiredError,
    JWTNotYetValidError,
    JWTUnsupportedTokenError,
)

_REGISTERED_CLAIMS = frozenset({"iss", "sub", "aud", "exp", "nbf", "iat", "jti"})
_RESERVED_HEADERS = frozenset(
    {
        "alg",
        "kid",
        "typ",
        "crit",
        "jku",
        "jwk",
        "x5u",
        "x5c",
        "x5t",
        "x5t#S256",
        "cty",
        "b64",
        "zip",
    }
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _raise_configuration_error() -> NoReturn:
    raise JWTConfigurationError() from None


def _validate_name(value: object) -> str:
    if type(value) is not str or not value or value != value.strip() or "\x00" in value:
        _raise_configuration_error()
    return value


def _normalize_string_set(value: object, *, nonempty: bool) -> frozenset[str]:
    if type(value) is str or not isinstance(value, Iterable):
        _raise_configuration_error()
    try:
        copied = tuple(value)
    except Exception:
        _raise_configuration_error()
    normalized = frozenset(_validate_name(item) for item in copied)
    if nonempty and not normalized:
        _raise_configuration_error()
    return normalized


def _validate_duration(
    value: object,
    *,
    optional: bool,
    allow_zero: bool,
) -> timedelta | None:
    if value is None and optional:
        return None
    if type(value) is not timedelta:
        _raise_configuration_error()
    if value < timedelta(0) or (not allow_zero and value == timedelta(0)):
        _raise_configuration_error()
    return value


def _duration_microseconds(value: timedelta) -> int:
    return ((value.days * 86_400 + value.seconds) * 1_000_000) + value.microseconds


@dataclass(frozen=True, slots=True)
class IssuanceProfile:
    """Constructor-only policy for the optional issuance decorator."""

    default_ttl: timedelta | None = None
    max_ttl: timedelta | None = None
    add_issued_at: bool = True
    clock: Callable[[], datetime] = field(default=_utc_now, repr=False, compare=False)

    def __post_init__(self) -> None:
        default_ttl = _validate_duration(self.default_ttl, optional=True, allow_zero=False)
        max_ttl = _validate_duration(self.max_ttl, optional=True, allow_zero=False)
        if default_ttl is not None and max_ttl is not None and default_ttl > max_ttl:
            _raise_configuration_error()
        if type(self.add_issued_at) is not bool or not callable(self.clock):
            _raise_configuration_error()
        object.__setattr__(self, "default_ttl", default_ttl)
        object.__setattr__(self, "max_ttl", max_ttl)


@dataclass(frozen=True, slots=True)
class ValidationProfile:
    """One immutable validation policy bound to a provider."""

    token_type: str
    allowed_issuers: frozenset[str]
    accepted_audiences: frozenset[str]
    required_claims: frozenset[str] = frozenset()
    protected_headers: Mapping[str, str] = field(default_factory=dict)
    clock_skew: timedelta = timedelta(0)
    max_token_age: timedelta | None = None
    clock: Callable[[], datetime] = field(default=_utc_now, repr=False, compare=False)
    _fingerprint: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        token_type = _validate_name(self.token_type)
        issuers = _normalize_string_set(self.allowed_issuers, nonempty=True)
        audiences = _normalize_string_set(self.accepted_audiences, nonempty=True)
        required = _normalize_string_set(self.required_claims, nonempty=False)
        required = required.union({"iss", "aud"})
        clock_skew = _validate_duration(self.clock_skew, optional=False, allow_zero=True)
        max_token_age = _validate_duration(
            self.max_token_age,
            optional=True,
            allow_zero=False,
        )
        if max_token_age is not None:
            required = required.union({"iat"})
        if not callable(self.clock):
            _raise_configuration_error()
        headers = _normalize_headers(self.protected_headers)

        object.__setattr__(self, "token_type", token_type)
        object.__setattr__(self, "allowed_issuers", issuers)
        object.__setattr__(self, "accepted_audiences", audiences)
        object.__setattr__(self, "required_claims", required)
        object.__setattr__(self, "protected_headers", headers)
        object.__setattr__(self, "clock_skew", clock_skew)
        object.__setattr__(self, "max_token_age", max_token_age)
        object.__setattr__(self, "_fingerprint", _policy_fingerprint(self))

    @property
    def fingerprint(self) -> str:
        """Return a deterministic SHA-256 digest of non-secret policy fields."""
        return self._fingerprint


def _normalize_headers(value: object) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        _raise_configuration_error()
    try:
        copied = dict(value)
    except Exception:
        _raise_configuration_error()
    normalized: dict[str, str] = {}
    for name, expected in copied.items():
        validated_name = _validate_name(name)
        if validated_name in _RESERVED_HEADERS:
            _raise_configuration_error()
        normalized[validated_name] = _validate_name(expected)
    return MappingProxyType(normalized)


def _policy_fingerprint(profile: ValidationProfile) -> str:
    policy = {
        "accepted_audiences": sorted(profile.accepted_audiences),
        "allowed_issuers": sorted(profile.allowed_issuers),
        "clock_skew_us": _duration_microseconds(profile.clock_skew),
        "max_token_age_us": (
            None if profile.max_token_age is None else _duration_microseconds(profile.max_token_age)
        ),
        "protected_headers": sorted(profile.protected_headers.items()),
        "required_claims": sorted(profile.required_claims),
        "token_type": profile.token_type,
    }
    encoded = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _capture_reference_time(profile: ValidationProfile) -> datetime:
    """Capture and normalize the injected clock exactly once."""
    try:
        now = profile.clock()
        if type(now) is not datetime or now.utcoffset() is None:
            _raise_configuration_error()
        return now.astimezone(UTC)
    except JWTConfigurationError:
        raise
    except Exception:
        _raise_configuration_error()


def _present_claims(claims: TokenClaims) -> frozenset[str]:
    present = frozenset(claims.custom)
    field_names = {
        "iss": claims.issuer,
        "sub": claims.subject,
        "aud": claims.audience if claims.audience else None,
        "exp": claims.expires_at,
        "nbf": claims.not_before,
        "iat": claims.issued_at,
        "jti": claims.jwt_id,
    }
    return present.union(name for name, value in field_names.items() if value is not None)


def _validate_temporal_claims(
    claims: TokenClaims,
    profile: ValidationProfile,
    *,
    now: datetime,
) -> None:
    if claims.expires_at is not None and now - claims.expires_at >= profile.clock_skew:
        raise JWTExpiredError() from None
    if claims.not_before is not None and claims.not_before - now > profile.clock_skew:
        raise JWTNotYetValidError() from None
    if claims.issued_at is not None and claims.issued_at - now > profile.clock_skew:
        raise JWTNotYetValidError() from None
    if (
        claims.expires_at is not None
        and claims.not_before is not None
        and claims.expires_at <= claims.not_before
    ):
        raise JWTClaimError() from None
    if profile.max_token_age is not None:
        if claims.issued_at is None:
            raise JWTClaimError() from None
        token_age = now - claims.issued_at
        if (
            token_age > profile.max_token_age
            and token_age - profile.max_token_age > profile.clock_skew
        ):
            raise JWTExpiredError() from None


def _validate_claims(
    claims: TokenClaims,
    profile: ValidationProfile,
    *,
    token_type: str,
    protected_headers: Mapping[str, str],
    now: datetime,
) -> None:
    """Validate all policy and temporal rules against one caller-captured time."""
    if type(claims) is not TokenClaims or type(profile) is not ValidationProfile:
        raise JWTClaimError() from None
    try:
        normalized_now = now.astimezone(UTC)
    except Exception:
        raise JWTClaimError() from None
    if type(now) is not datetime or now.utcoffset() is None:
        raise JWTClaimError() from None
    try:
        headers = dict(protected_headers)
    except Exception:
        raise JWTUnsupportedTokenError() from None
    if token_type != profile.token_type or headers != dict(profile.protected_headers):
        raise JWTUnsupportedTokenError() from None
    if not profile.required_claims.issubset(_present_claims(claims)):
        raise JWTClaimError() from None
    if claims.issuer not in profile.allowed_issuers:
        raise JWTClaimError() from None
    if not profile.accepted_audiences.intersection(claims.audience):
        raise JWTClaimError() from None
    _validate_temporal_claims(claims, profile, now=normalized_now)
