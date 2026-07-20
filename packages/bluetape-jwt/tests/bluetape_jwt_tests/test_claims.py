"""Immutable JWT claim value tests."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from importlib import import_module
from types import MappingProxyType

import bluetape.jwt as jwt
import pytest
from bluetape.jwt._claims import _claims_from_payload, _claims_to_payload, _freeze_json


def test_custom_claims_are_deeply_frozen() -> None:
    token_claims = getattr(jwt, "TokenClaims", None)
    assert token_claims is not None

    nested = {"roles": ["reader", {"scope": "profile"}]}
    claims = token_claims(custom=nested)
    nested["roles"].append("admin")
    nested["roles"][1]["scope"] = "changed"

    assert claims.custom == {"roles": ("reader", {"scope": "profile"})}


def test_numeric_date_rejects_bool_and_overflow() -> None:
    claims_module = import_module("bluetape.jwt._claims")
    convert = getattr(claims_module, "_numeric_date_to_datetime", None)
    assert callable(convert)

    for invalid in (
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        10**100,
        -(10**100),
    ):
        with pytest.raises(jwt.JWTMalformedTokenError):
            convert(invalid)


def test_claims_normalize_audience_and_datetimes_without_mutating_caller() -> None:
    korean_time = datetime(2025, 1, 1, 9, tzinfo=timezone(timedelta(hours=9)))
    audience = ["api", "admin"]
    claims = jwt.TokenClaims(
        issuer="issuer",
        subject="subject",
        audience=audience,
        expires_at=korean_time,
        jwt_id="identifier",
    )

    audience.append("changed")
    assert claims.audience == ("api", "admin")
    assert claims.expires_at == datetime(2025, 1, 1, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        claims.subject = "changed"


def test_duplicate_audiences_preserve_caller_and_inbound_order() -> None:
    caller = jwt.TokenClaims(audience=["api", "api", "admin"])
    inbound = _claims_from_payload({"aud": ["api", "api", "admin"]})

    assert caller.audience == ("api", "api", "admin")
    assert inbound.audience == ("api", "api", "admin")


@pytest.mark.parametrize("field", ["expires_at", "not_before", "issued_at"])
def test_claims_reject_naive_datetimes(field: str) -> None:
    with pytest.raises(jwt.JWTClaimError):
        jwt.TokenClaims(**{field: datetime(2025, 1, 1)})


@pytest.mark.parametrize(
    "custom",
    [
        {"iss": "shadow"},
        {"": "value"},
        {" spaced ": "value"},
        {1: "value"},
        {"value": b"bytes"},
        {"value": {"set"}},
        {"value": object()},
        {"value": float("nan")},
        {"value": float("inf")},
    ],
)
def test_custom_claims_reject_non_json_or_ambiguous_values(custom: object) -> None:
    with pytest.raises(jwt.JWTClaimError):
        jwt.TokenClaims(custom=custom)


def test_custom_claims_reject_cycles_and_enforce_exact_depth_budget() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(jwt.JWTClaimError):
        jwt.TokenClaims(custom=cyclic)

    at_limit: object = "leaf"
    for _ in range(32):
        at_limit = [at_limit]
    assert _freeze_json(at_limit)

    over_limit: object = [at_limit]
    with pytest.raises(jwt.JWTClaimError):
        _freeze_json(over_limit)


def test_custom_claims_enforce_exact_node_budget() -> None:
    at_limit = _freeze_json([None] * 9_999)
    assert len(at_limit) == 9_999

    with pytest.raises(jwt.JWTClaimError):
        _freeze_json([None] * 10_000)


def test_registered_claim_serialization_uses_integer_numeric_dates() -> None:
    source = {"nested": [1, 2]}
    instant = datetime(2025, 1, 1, 0, 0, 0, 900_000, tzinfo=UTC)
    claims = jwt.TokenClaims(
        issuer="issuer",
        audience="api",
        expires_at=instant,
        custom=source,
    )

    payload = _claims_to_payload(claims)
    payload["nested"].append(3)

    assert type(payload["exp"]) is int
    assert claims.custom == {"nested": (1, 2)}
    assert source == {"nested": [1, 2]}


def test_inbound_payload_conversion_normalizes_and_freezes() -> None:
    payload = {
        "iss": "issuer",
        "aud": "api",
        "iat": 1_735_689_600.5,
        "nested": {"values": [1, 2]},
    }
    claims = _claims_from_payload(payload)
    payload["nested"]["values"].append(3)

    assert claims.audience == ("api",)
    assert claims.issued_at == datetime.fromtimestamp(1_735_689_600.5, tz=UTC)
    assert isinstance(claims.custom, MappingProxyType)
    assert claims.custom == {"nested": {"values": (1, 2)}}


@pytest.mark.parametrize(
    "payload",
    [
        {"aud": []},
        {"aud": ["api", 1]},
        {"iss": 1},
        {"iss": None},
        {"sub": None},
        {"jti": None},
        {"iat": True},
        {"iat": float("nan")},
        {"iat": float("inf")},
        {"iat": float("-inf")},
        {"nested": b"not-json"},
        {"": "invalid"},
    ],
)
def test_inbound_payload_conversion_uses_malformed_token_error(payload: object) -> None:
    with pytest.raises(jwt.JWTMalformedTokenError):
        _claims_from_payload(payload)


def test_verified_token_freezes_custom_and_custom_headers() -> None:
    custom = {"scope": ["read"]}
    headers = {"tenant": "primary"}
    verified = jwt.VerifiedToken(
        kid="current",
        algorithm=jwt.JWSAlgorithm.HS256,
        token_type="access+jwt",
        issuer="issuer",
        subject=None,
        audience=["api"],
        expires_at=None,
        not_before=None,
        issued_at=None,
        jwt_id=None,
        custom=custom,
        headers=headers,
    )
    custom["scope"].append("write")
    headers["tenant"] = "changed"

    assert verified.custom == {"scope": ("read",)}
    assert verified.headers == {"tenant": "primary"}
    with pytest.raises(FrozenInstanceError):
        verified.kid = "changed"


def test_typed_result_helper_preserves_verified_projection() -> None:
    claims_module = import_module("bluetape.jwt._claims")
    convert = getattr(claims_module, "_to_verified_token", None)
    assert callable(convert)
    claims = jwt.TokenClaims(
        issuer="issuer",
        audience=("api",),
        custom={"scope": ["read"]},
    )

    verified = convert(
        claims,
        kid="current",
        algorithm=jwt.JWSAlgorithm.HS256,
        token_type="access+jwt",
        headers={"tenant": "primary"},
    )

    assert verified.custom == {"scope": ("read",)}
    assert verified.headers == {"tenant": "primary"}


@pytest.mark.parametrize("headers", [{"alg": "HS256"}, {"tenant": ""}, {1: "value"}])
def test_verified_token_rejects_reserved_or_invalid_headers(headers: object) -> None:
    with pytest.raises(jwt.JWTClaimError):
        jwt.VerifiedToken(
            kid="current",
            algorithm=jwt.JWSAlgorithm.HS256,
            token_type="access+jwt",
            issuer="issuer",
            subject=None,
            audience=("api",),
            expires_at=None,
            not_before=None,
            issued_at=None,
            jwt_id=None,
            custom={},
            headers=headers,
        )
