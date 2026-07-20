"""Hostile-input tests for the strict JWS boundary."""

from __future__ import annotations

import json
import tracemalloc
from base64 import urlsafe_b64encode
from datetime import UTC, datetime

import bluetape.jwt as jwt
import pytest
from joserfc import jws

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def encode_segment(value: object) -> str:
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def encode_raw_segment(value: str) -> str:
    return urlsafe_b64encode(value.encode("utf-8")).rstrip(b"=").decode("ascii")


def compact_token(header: object, payload: object, signature: str = "c2ln") -> str:
    return f"{encode_segment(header)}.{encode_segment(payload)}.{signature}"


def make_provider() -> tuple[jwt.JWSProvider, jwt.JWTKey]:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    profile = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        protected_headers={"tenant": "primary"},
        clock=lambda: NOW,
    )
    return (
        jwt.JWSProvider(
            jwt.JWSAlgorithm.HS256,
            jwt.InMemoryKeyRepository(active=key),
            profile,
        ),
        key,
    )


def sign_payload(
    provider: jwt.JWSProvider,
    key: jwt.JWTKey,
    payload: bytes | str,
) -> str:
    return jws.serialize_compact(
        {
            "alg": "HS256",
            "kid": "current-key",
            "typ": "access+jwt",
            "tenant": "primary",
        },
        payload,
        key._provider_key,
        algorithms=["HS256"],
        registry=provider._registry,
    )


class RepositorySpy:
    def __init__(self, repository: jwt.InMemoryKeyRepository) -> None:
        self._repository = repository
        self.snapshot_calls = 0

    def snapshot(self) -> jwt.KeySnapshot:
        self.snapshot_calls += 1
        return self._repository.snapshot()


def test_algorithm_mismatch_fails_before_key_resolution() -> None:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    repository = RepositorySpy(jwt.InMemoryKeyRepository(active=key))
    profile = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        protected_headers={"tenant": "primary"},
        clock=lambda: NOW,
    )
    provider = jwt.JWSProvider(jwt.JWSAlgorithm.HS256, repository, profile)
    mismatch = compact_token(
        {
            "alg": "RS256",
            "kid": "missing-key",
            "typ": "access+jwt",
            "tenant": "primary",
        },
        {"iss": "issuer", "aud": ["api"]},
    )

    with pytest.raises(jwt.JWTUnsupportedTokenError):
        provider.verify(mismatch)

    protected = encode_raw_segment(
        '{"alg":"RS256","alg":"HS256","kid":"missing-key","typ":"access+jwt","tenant":"primary"}'
    )
    token = f"{protected}.{encode_segment({'iss': 'issuer', 'aud': ['api']})}.c2ln"

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify(token)

    assert repository.snapshot_calls == 2


def test_oversized_token_is_rejected_before_allocating_a_utf8_copy() -> None:
    provider, _ = make_provider()
    oversized = "a" * (8 * 1024 * 1024)

    tracemalloc.start()
    try:
        with pytest.raises(jwt.JWTMalformedTokenError):
            provider.verify(oversized)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < 1024 * 1024


def test_key_family_mismatch_is_rejected_before_signature() -> None:
    hmac_key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    profile = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        protected_headers={"tenant": "primary"},
        clock=lambda: NOW,
    )
    provider = jwt.JWSProvider(
        jwt.JWSAlgorithm.RS256,
        jwt.InMemoryKeyRepository(active=hmac_key),
        profile,
    )
    token = compact_token(
        {
            "alg": "RS256",
            "kid": "current-key",
            "typ": "access+jwt",
            "tenant": "primary",
        },
        {"iss": "issuer", "aud": ["api"]},
    )

    with pytest.raises(jwt.JWTUnsupportedTokenError):
        provider.verify(token)


@pytest.mark.parametrize("algorithm", list(jwt.JWSAlgorithm))
def test_every_algorithm_rejects_header_mismatch_before_key_lookup(
    algorithm: jwt.JWSAlgorithm,
) -> None:
    mismatch = "RS256" if algorithm is jwt.JWSAlgorithm.HS256 else "HS256"
    profile = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        protected_headers={"tenant": "primary"},
        clock=lambda: NOW,
    )
    provider = jwt.JWSProvider(
        algorithm,
        jwt.InMemoryKeyRepository(),
        profile,
    )
    token = compact_token(
        {
            "alg": mismatch,
            "kid": "missing-key",
            "typ": "access+jwt",
            "tenant": "primary",
        },
        {"iss": "issuer", "aud": ["api"]},
    )

    with pytest.raises(jwt.JWTUnsupportedTokenError):
        provider.verify(token)


def test_duplicate_payload_name_is_rejected() -> None:
    provider, key = make_provider()
    token = sign_payload(
        provider,
        key,
        '{"iss":"issuer","iss":"issuer","aud":["api"]}',
    )

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify(token)


@pytest.mark.parametrize(
    "token",
    [
        None,
        b"e30.e30.c2ln",
        "e30.e30",
        "e30.e30.c2ln.extra",
        ".e30.c2ln",
        "e30..c2ln",
        "e30.e30.",
        "e$0.e30.c2ln",
        "a" * 16_385,
    ],
)
def test_malformed_compact_shape_is_rejected(token: object) -> None:
    provider, _ = make_provider()

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify(token)


@pytest.mark.parametrize(
    "raw_header",
    [
        b"\xff",
        b"not-json",
        b'{"alg":NaN,"kid":"current-key","typ":"access+jwt","tenant":"primary"}',
        b"[]",
        b'{"alg":"HS256","alg":"HS256","kid":"current-key","typ":"access+jwt","tenant":"primary"}',
        json.dumps({"padding": "x" * 513}).encode("utf-8"),
    ],
)
def test_malformed_protected_header_is_rejected(raw_header: bytes) -> None:
    provider, _ = make_provider()
    protected = urlsafe_b64encode(raw_header).rstrip(b"=").decode("ascii")

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify(f"{protected}.e30.c2ln")


@pytest.mark.parametrize(
    "header",
    [
        {"alg": "none", "kid": "current-key", "typ": "access+jwt", "tenant": "primary"},
        {"alg": "RS256", "kid": "current-key", "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "kid": "", "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "kid": " key", "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "kid": "key\x00", "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "kid": 1, "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "kid": "k" * 129, "typ": "access+jwt", "tenant": "primary"},
        {"alg": "HS256", "kid": "current-key", "typ": "other", "tenant": "primary"},
        {"alg": "HS256", "kid": "current-key", "typ": "access+jwt", "tenant": "other"},
        {
            "alg": "HS256",
            "kid": "current-key",
            "typ": "access+jwt",
            "tenant": "primary",
            "crit": ["unknown"],
        },
        {
            "alg": "HS256",
            "kid": "current-key",
            "typ": "access+jwt",
            "tenant": "primary",
            "unapproved": "value",
        },
        *[
            {
                "alg": "HS256",
                "kid": "current-key",
                "typ": "access+jwt",
                "tenant": "primary",
                name: "remote",
            }
            for name in ("jku", "jwk", "x5u", "x5c", "zip")
        ],
    ],
)
def test_unsupported_headers_fail_before_key_lookup(header: object) -> None:
    key = jwt.JWTKey.from_hmac_secret(
        "current-key",
        jwt.JWSAlgorithm.HS256,
        b"s" * 32,
    )
    repository = RepositorySpy(jwt.InMemoryKeyRepository(active=key))
    profile = jwt.ValidationProfile(
        token_type="access+jwt",
        allowed_issuers=frozenset({"issuer"}),
        accepted_audiences=frozenset({"api"}),
        protected_headers={"tenant": "primary"},
        clock=lambda: NOW,
    )
    provider = jwt.JWSProvider(jwt.JWSAlgorithm.HS256, repository, profile)

    with pytest.raises(jwt.JWTUnsupportedTokenError):
        provider.verify(compact_token(header, {"iss": "issuer", "aud": ["api"]}))

    assert repository.snapshot_calls == 1


@pytest.mark.parametrize("payload", ["[]", '"value"', "null"])
def test_non_object_payload_is_rejected(payload: str) -> None:
    provider, key = make_provider()

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify(sign_payload(provider, key, payload))


@pytest.mark.parametrize("payload", [b"\xff", b"not-json"])
def test_invalid_payload_encoding_is_rejected(payload: bytes) -> None:
    provider, key = make_provider()

    with pytest.raises(jwt.JWTMalformedTokenError):
        provider.verify(sign_payload(provider, key, payload))


def test_unknown_key_is_unavailable_before_signature_verification() -> None:
    provider, _ = make_provider()
    token = compact_token(
        {
            "alg": "HS256",
            "kid": "missing-key",
            "typ": "access+jwt",
            "tenant": "primary",
        },
        {"iss": "issuer", "aud": ["api"]},
    )

    with pytest.raises(jwt.JWTKeyUnavailableError):
        provider.verify(token)
