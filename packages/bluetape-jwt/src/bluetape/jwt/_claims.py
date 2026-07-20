"""Immutable typed JWT claims and strict payload conversion helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import NoReturn

from bluetape.jwt._algorithms import JWSAlgorithm
from bluetape.jwt._errors import JWTClaimError, JWTMalformedTokenError

_MAX_JSON_DEPTH = 32
_MAX_JSON_NODES = 10_000
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

type JSONValue = None | bool | int | float | str | tuple[JSONValue, ...] | Mapping[str, JSONValue]


def _raise_claim_error() -> NoReturn:
    raise JWTClaimError() from None


def _raise_malformed_token_error() -> NoReturn:
    raise JWTMalformedTokenError() from None


def _freeze_json(value: object, *, inbound: bool = False) -> JSONValue:
    """Defensively freeze one bounded JSON value without exposing its contents."""
    nodes = [0]
    active: set[int] = set()

    def reject() -> NoReturn:
        if inbound:
            _raise_malformed_token_error()
        _raise_claim_error()

    def freeze(item: object, depth: int) -> JSONValue:
        nodes[0] += 1
        if nodes[0] > _MAX_JSON_NODES or depth > _MAX_JSON_DEPTH:
            reject()
        if item is None or type(item) in {bool, int, str}:
            return item
        if type(item) is float:
            if not math.isfinite(item):
                reject()
            return item
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in active:
                reject()
            active.add(identity)
            try:
                snapshot = dict(item)
                copied: dict[str, JSONValue] = {}
                for key, nested in snapshot.items():
                    if type(key) is not str or not key or key != key.strip() or "\x00" in key:
                        reject()
                    copied[key] = freeze(nested, depth + 1)
            except (JWTClaimError, JWTMalformedTokenError):
                raise
            except Exception:
                reject()
            finally:
                active.discard(identity)
            return MappingProxyType(copied)
        if type(item) in {list, tuple}:
            identity = id(item)
            if identity in active:
                reject()
            active.add(identity)
            try:
                snapshot = tuple(item)
                copied_sequence = tuple(freeze(nested, depth + 1) for nested in snapshot)
            except (JWTClaimError, JWTMalformedTokenError):
                raise
            except Exception:
                reject()
            finally:
                active.discard(identity)
            return copied_sequence
        reject()

    return freeze(value, 0)


def _numeric_date_to_datetime(value: object) -> datetime:
    """Convert one strict inbound NumericDate to an aware UTC datetime."""
    if type(value) not in {int, float}:
        _raise_malformed_token_error()
    if type(value) is float and not math.isfinite(value):
        _raise_malformed_token_error()
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError):
        _raise_malformed_token_error()


def _validate_string(value: object, *, inbound: bool = False) -> str:
    if type(value) is not str or not value or value != value.strip() or "\x00" in value:
        if inbound:
            _raise_malformed_token_error()
        _raise_claim_error()
    return value


def _normalize_audience(
    value: object,
    *,
    inbound: bool = False,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if type(value) is str:
        values: tuple[object, ...] = (value,)
    elif type(value) in {tuple, list}:
        values = tuple(value)
    else:
        if inbound:
            _raise_malformed_token_error()
        _raise_claim_error()
    if not values and not allow_empty:
        if inbound:
            _raise_malformed_token_error()
        _raise_claim_error()
    normalized = tuple(_validate_string(item, inbound=inbound) for item in values)
    return normalized


def _normalize_datetime(value: object) -> datetime:
    if type(value) is not datetime:
        _raise_claim_error()
    try:
        offset = value.utcoffset()
        if offset is None:
            _raise_claim_error()
        return value.astimezone(UTC)
    except JWTClaimError:
        raise
    except Exception:
        _raise_claim_error()


def _datetime_to_numeric_date(value: datetime) -> int:
    try:
        timestamp = value.timestamp()
    except (OverflowError, OSError, ValueError):
        _raise_claim_error()
    if not math.isfinite(timestamp):
        _raise_claim_error()
    return math.floor(timestamp)


def _thaw_json(value: JSONValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(nested) for key, nested in value.items()}
    if type(value) is tuple:
        return [_thaw_json(nested) for nested in value]
    return value


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Caller-owned registered and custom claims captured immutably."""

    issuer: str | None = None
    subject: str | None = None
    audience: tuple[str, ...] = ()
    expires_at: datetime | None = None
    not_before: datetime | None = None
    issued_at: datetime | None = None
    jwt_id: str | None = None
    custom: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("issuer", "subject", "jwt_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _validate_string(value))
        object.__setattr__(self, "audience", _normalize_audience(self.audience))
        for field_name in ("expires_at", "not_before", "issued_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _normalize_datetime(value))
        if not isinstance(self.custom, Mapping):
            _raise_claim_error()
        try:
            custom = dict(self.custom)
        except Exception:
            _raise_claim_error()
        if _REGISTERED_CLAIMS.intersection(custom):
            _raise_claim_error()
        frozen = _freeze_json(custom)
        object.__setattr__(self, "custom", frozen)


@dataclass(frozen=True, slots=True)
class VerifiedToken:
    """Fully verified immutable token projection returned to callers."""

    kid: str
    algorithm: JWSAlgorithm
    token_type: str
    issuer: str
    subject: str | None
    audience: tuple[str, ...]
    expires_at: datetime | None
    not_before: datetime | None
    issued_at: datetime | None
    jwt_id: str | None
    custom: Mapping[str, JSONValue]
    headers: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kid", _validate_string(self.kid))
        if type(self.algorithm) is not JWSAlgorithm:
            _raise_claim_error()
        object.__setattr__(self, "token_type", _validate_string(self.token_type))
        object.__setattr__(self, "issuer", _validate_string(self.issuer))
        if self.subject is not None:
            object.__setattr__(self, "subject", _validate_string(self.subject))
        object.__setattr__(
            self,
            "audience",
            _normalize_audience(self.audience, allow_empty=False),
        )
        for field_name in ("expires_at", "not_before", "issued_at"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _normalize_datetime(value))
        if self.jwt_id is not None:
            object.__setattr__(self, "jwt_id", _validate_string(self.jwt_id))
        if not isinstance(self.custom, Mapping):
            _raise_claim_error()
        try:
            custom = dict(self.custom)
        except Exception:
            _raise_claim_error()
        if _REGISTERED_CLAIMS.intersection(custom):
            _raise_claim_error()
        object.__setattr__(self, "custom", _freeze_json(custom))
        object.__setattr__(self, "headers", _freeze_headers(self.headers))


def _freeze_headers(headers: object) -> Mapping[str, str]:
    if not isinstance(headers, Mapping):
        _raise_claim_error()
    try:
        copied = dict(headers)
    except Exception:
        _raise_claim_error()
    frozen: dict[str, str] = {}
    for name, value in copied.items():
        validated_name = _validate_string(name)
        if validated_name in _RESERVED_HEADERS:
            _raise_claim_error()
        frozen[validated_name] = _validate_string(value)
    return MappingProxyType(frozen)


def _claims_to_payload(claims: TokenClaims) -> dict[str, object]:
    """Serialize immutable caller claims without mutating caller-owned values."""
    if type(claims) is not TokenClaims:
        _raise_claim_error()
    payload = {key: _thaw_json(value) for key, value in claims.custom.items()}
    if claims.issuer is not None:
        payload["iss"] = claims.issuer
    if claims.subject is not None:
        payload["sub"] = claims.subject
    if claims.audience:
        payload["aud"] = list(claims.audience)
    if claims.expires_at is not None:
        payload["exp"] = _datetime_to_numeric_date(claims.expires_at)
    if claims.not_before is not None:
        payload["nbf"] = _datetime_to_numeric_date(claims.not_before)
    if claims.issued_at is not None:
        payload["iat"] = _datetime_to_numeric_date(claims.issued_at)
    if claims.jwt_id is not None:
        payload["jti"] = claims.jwt_id
    return payload


def _claims_from_payload(payload: object) -> TokenClaims:
    """Convert one strict signed payload into immutable typed claims."""
    if not isinstance(payload, Mapping):
        _raise_malformed_token_error()
    try:
        copied = dict(payload)
    except Exception:
        _raise_malformed_token_error()
    if any(
        type(name) is not str or not name or name != name.strip() or "\x00" in name
        for name in copied
    ):
        _raise_malformed_token_error()

    def optional_string(name: str) -> str | None:
        if name not in copied:
            return None
        return _validate_string(copied[name], inbound=True)

    audience: tuple[str, ...] = ()
    if "aud" in copied:
        audience = _normalize_audience(copied["aud"], inbound=True, allow_empty=False)
    temporal: dict[str, datetime | None] = {}
    temporal_fields = (
        ("exp", "expires_at"),
        ("nbf", "not_before"),
        ("iat", "issued_at"),
    )
    for claim_name, field_name in temporal_fields:
        temporal[field_name] = (
            _numeric_date_to_datetime(copied[claim_name]) if claim_name in copied else None
        )
    custom = {key: value for key, value in copied.items() if key not in _REGISTERED_CLAIMS}
    frozen_custom = _freeze_json(custom, inbound=True)
    try:
        return TokenClaims(
            issuer=optional_string("iss"),
            subject=optional_string("sub"),
            audience=audience,
            expires_at=temporal["expires_at"],
            not_before=temporal["not_before"],
            issued_at=temporal["issued_at"],
            jwt_id=optional_string("jti"),
            custom=frozen_custom,
        )
    except JWTClaimError:
        _raise_malformed_token_error()


def _to_verified_token(
    claims: TokenClaims,
    *,
    kid: str,
    algorithm: JWSAlgorithm,
    token_type: str,
    headers: Mapping[str, str],
) -> VerifiedToken:
    """Project validated typed claims into the public verified result value."""
    if type(claims) is not TokenClaims or claims.issuer is None or not claims.audience:
        _raise_claim_error()
    return VerifiedToken(
        kid=kid,
        algorithm=algorithm,
        token_type=token_type,
        issuer=claims.issuer,
        subject=claims.subject,
        audience=claims.audience,
        expires_at=claims.expires_at,
        not_before=claims.not_before,
        issued_at=claims.issued_at,
        jwt_id=claims.jwt_id,
        custom=claims.custom,
        headers=headers,
    )
