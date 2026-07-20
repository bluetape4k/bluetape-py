from __future__ import annotations

import traceback
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import Any

import pytest
from bluetape.jwt import JWSAlgorithm, JWTKey, JWTKeyError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jws
from joserfc.jwk import RSAKey


@pytest.fixture(scope="module")
def rsa_material() -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    encrypted_private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"correct-password"),
    )
    public_pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    dependency_key = RSAKey.import_key(private_pem)
    return {
        "private_pem": private_pem,
        "encrypted_private_pem": encrypted_private_pem,
        "public_pem": public_pem,
        "private_jwk": dependency_key.as_dict(private=True),
        "public_jwk": dependency_key.as_dict(private=False),
    }


@pytest.fixture(scope="module")
def weak_rsa_material() -> dict[str, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    return {
        "private_pem": private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        "public_pem": private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    }


@pytest.mark.parametrize(
    ("algorithm", "minimum_bytes"),
    [
        (JWSAlgorithm.HS256, 32),
        (JWSAlgorithm.HS384, 48),
        (JWSAlgorithm.HS512, 64),
    ],
)
def test_hmac_strength_exact_minimum_and_one_byte_short(
    algorithm: JWSAlgorithm,
    minimum_bytes: int,
) -> None:
    key = JWTKey.from_hmac_secret("hmac-key", algorithm, b"s" * minimum_bytes)

    assert key.kid == "hmac-key"
    assert key.algorithm is algorithm
    assert key.can_sign is True

    with pytest.raises(JWTKeyError):
        JWTKey.from_hmac_secret("hmac-key", algorithm, b"s" * (minimum_bytes - 1))


def test_hmac_rejects_wrong_family_material_and_public_export() -> None:
    with pytest.raises(JWTKeyError):
        JWTKey.from_hmac_secret("hmac-key", JWSAlgorithm.RS256, b"s" * 32)

    with pytest.raises(JWTKeyError):
        JWTKey.from_hmac_secret("hmac-key", JWSAlgorithm.HS256, "s" * 32)  # type: ignore[arg-type]

    key = JWTKey.from_hmac_secret("hmac-key", JWSAlgorithm.HS256, b"s" * 32)
    with pytest.raises(JWTKeyError):
        key.public_jwk()


@pytest.mark.parametrize("algorithm", [JWSAlgorithm.RS256, JWSAlgorithm.PS512])
def test_rsa_private_and_public_pem_imports(
    algorithm: JWSAlgorithm,
    rsa_material: dict[str, Any],
) -> None:
    private_key = JWTKey.from_rsa_private(
        "rsa-key",
        algorithm,
        rsa_material["private_pem"],
    )
    public_key = JWTKey.from_rsa_public(
        "rsa-key",
        algorithm,
        rsa_material["public_pem"],
    )

    assert private_key.can_sign is True
    assert public_key.can_sign is False
    assert private_key.algorithm is algorithm
    assert public_key.algorithm is algorithm


def test_rsa_private_and_public_jwk_round_trip_and_verification(
    rsa_material: dict[str, Any],
) -> None:
    private_jwk = {
        **rsa_material["private_jwk"],
        "kid": "rsa-key",
        "alg": "RS256",
        "use": "sig",
        "key_ops": ["sign", "verify"],
    }
    private_key = JWTKey.from_rsa_private(
        "rsa-key",
        JWSAlgorithm.RS256,
        private_jwk,
    )
    public_jwk = private_key.public_jwk()
    public_key = JWTKey.from_rsa_public(
        "rsa-key",
        JWSAlgorithm.RS256,
        public_jwk,
    )

    signer = RSAKey.import_key(rsa_material["private_pem"])
    verifier = RSAKey.import_key(dict(public_key.public_jwk()))
    compact = jws.serialize_compact(
        {"alg": "RS256", "kid": "rsa-key"},
        b"verified payload",
        signer,
        algorithms=["RS256"],
    )

    assert public_key.can_sign is False
    assert jws.deserialize_compact(compact, verifier, algorithms=["RS256"]).payload == (
        b"verified payload"
    )


def test_rsa_private_password_handling(rsa_material: dict[str, Any]) -> None:
    key = JWTKey.from_rsa_private(
        "rsa-key",
        JWSAlgorithm.RS256,
        rsa_material["encrypted_private_pem"],
        password=b"correct-password",
    )

    assert key.can_sign is True

    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_private(
            "rsa-key",
            JWSAlgorithm.RS256,
            rsa_material["encrypted_private_pem"],
            password=b"wrong-password",
        )

    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_private(
            "rsa-key",
            JWSAlgorithm.RS256,
            rsa_material["private_pem"],
            password="wrong-type",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("algorithm", [JWSAlgorithm.RS256, JWSAlgorithm.PS256])
def test_weak_rsa_is_rejected_for_private_and_public_factories(
    algorithm: JWSAlgorithm,
    weak_rsa_material: dict[str, bytes],
) -> None:
    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_private(
            "weak-key",
            algorithm,
            weak_rsa_material["private_pem"],
        )

    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_public(
            "weak-key",
            algorithm,
            weak_rsa_material["public_pem"],
        )


def test_rsa_rejects_family_confusion_capability_confusion_and_invalid_material(
    rsa_material: dict[str, Any],
) -> None:
    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_private(
            "rsa-key",
            JWSAlgorithm.HS256,
            rsa_material["private_pem"],
        )

    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_public(
            "rsa-key",
            JWSAlgorithm.HS256,
            rsa_material["public_pem"],
        )

    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_private(
            "rsa-key",
            JWSAlgorithm.RS256,
            rsa_material["public_pem"],
        )

    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_public(
            "rsa-key",
            JWSAlgorithm.RS256,
            rsa_material["private_pem"],
        )

    for material in (b"not-a-key", "not-a-key", 123, {"kty": "RSA"}):
        with pytest.raises(JWTKeyError):
            JWTKey.from_rsa_private(
                "rsa-key",
                JWSAlgorithm.RS256,
                material,  # type: ignore[arg-type]
            )


@pytest.mark.parametrize(
    "kid",
    ["", " ", " leading", "trailing ", "nul\x00kid", "k" * 129, 7],
)
def test_kid_is_strictly_validated(kid: Any) -> None:
    with pytest.raises(JWTKeyError):
        JWTKey.from_hmac_secret(kid, JWSAlgorithm.HS256, b"s" * 32)


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"kid": "rsa-key"},
        {"alg": "RS256"},
        {"use": "sig"},
        {"key_ops": ["sign"]},
        {"key_ops": ["sign", "verify"]},
        {
            "kid": "rsa-key",
            "alg": "RS256",
            "use": "sig",
            "key_ops": ["sign", "verify"],
        },
    ],
)
def test_private_jwk_accepts_only_compatible_metadata(
    metadata: dict[str, Any],
    rsa_material: dict[str, Any],
) -> None:
    key = JWTKey.from_rsa_private(
        "rsa-key",
        JWSAlgorithm.RS256,
        {**rsa_material["private_jwk"], **metadata},
    )

    assert key.can_sign is True


@pytest.mark.parametrize(
    "metadata",
    [
        {"kid": "wrong-key"},
        {"alg": "PS256"},
        {"use": "enc"},
        {"key_ops": []},
        {"key_ops": ["verify"]},
        {"key_ops": ["sign", "encrypt"]},
        {"key_ops": ["sign", "unknown"]},
        {"key_ops": ["sign", "sign"]},
        {"kid": 1},
        {"alg": ["RS256"]},
        {"use": True},
        {"key_ops": "sign"},
    ],
)
def test_private_jwk_rejects_conflicting_or_invalid_metadata(
    metadata: dict[str, Any],
    rsa_material: dict[str, Any],
) -> None:
    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_private(
            "rsa-key",
            JWSAlgorithm.RS256,
            {**rsa_material["private_jwk"], **metadata},
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"kid": "rsa-key"},
        {"alg": "RS256"},
        {"use": "sig"},
        {"key_ops": ["verify"]},
        {
            "kid": "rsa-key",
            "alg": "RS256",
            "use": "sig",
            "key_ops": ["verify"],
        },
    ],
)
def test_public_jwk_accepts_only_verification_metadata(
    metadata: dict[str, Any],
    rsa_material: dict[str, Any],
) -> None:
    key = JWTKey.from_rsa_public(
        "rsa-key",
        JWSAlgorithm.RS256,
        {**rsa_material["public_jwk"], **metadata},
    )

    assert key.can_sign is False


@pytest.mark.parametrize(
    "metadata",
    [
        {"kid": "wrong-key"},
        {"alg": "PS256"},
        {"use": "enc"},
        {"key_ops": []},
        {"key_ops": ["sign"]},
        {"key_ops": ["verify", "decrypt"]},
        {"key_ops": ["unknown"]},
        {"key_ops": ["verify", "verify"]},
        {"kid": []},
        {"alg": 1},
        {"use": ["sig"]},
        {"key_ops": {"verify"}},
    ],
)
def test_public_jwk_rejects_conflicting_or_invalid_metadata(
    metadata: dict[str, Any],
    rsa_material: dict[str, Any],
) -> None:
    with pytest.raises(JWTKeyError):
        JWTKey.from_rsa_public(
            "rsa-key",
            JWSAlgorithm.RS256,
            {**rsa_material["public_jwk"], **metadata},
        )


def test_rsa_jwk_rejects_invalid_mapping_keys_and_key_type(
    rsa_material: dict[str, Any],
) -> None:
    for jwk in (
        {**rsa_material["public_jwk"], "kty": "oct"},
        {**rsa_material["public_jwk"], 7: "invalid"},
    ):
        with pytest.raises(JWTKeyError):
            JWTKey.from_rsa_public(
                "rsa-key",
                JWSAlgorithm.RS256,
                jwk,  # type: ignore[arg-type]
            )


def test_public_jwk_is_fresh_immutable_and_public_only(
    rsa_material: dict[str, Any],
) -> None:
    key = JWTKey.from_rsa_private(
        "rsa-key",
        JWSAlgorithm.PS384,
        rsa_material["private_pem"],
    )

    first = key.public_jwk()
    second = key.public_jwk()

    assert isinstance(first, MappingProxyType)
    assert first is not second
    assert set(first) == {"kty", "kid", "alg", "n", "e"}
    assert first["kty"] == "RSA"
    assert first["kid"] == "rsa-key"
    assert first["alg"] == "PS384"
    assert not set(first).intersection({"d", "p", "q", "dp", "dq", "qi", "oth"})

    with pytest.raises(TypeError):
        first["kid"] = "changed"  # type: ignore[index]


def test_key_is_immutable_identity_based_unhashable_and_redacted() -> None:
    canary = b"private-key-canary-" + b"s" * 32
    first = JWTKey.from_hmac_secret("safe-id", JWSAlgorithm.HS256, canary)
    second = JWTKey.from_hmac_secret("safe-id", JWSAlgorithm.HS256, canary)

    assert first is not second
    assert first != second
    with pytest.raises(TypeError):
        hash(first)
    with pytest.raises(FrozenInstanceError):
        first._kid = "changed"  # type: ignore[misc]

    rendered = f"{first!s} {first!r}"
    assert canary.decode() not in rendered
    assert "safe-id" not in rendered


def test_direct_construction_cannot_bypass_factory_validation() -> None:
    with pytest.raises(TypeError, match="factory method"):
        JWTKey()

    with pytest.raises(TypeError):
        JWTKey("unsafe", JWSAlgorithm.HS256, True, object())  # type: ignore[call-arg]


def test_dependency_failures_do_not_leak_key_material() -> None:
    canary = "PRIVATE-PEM-JWK-PASSWORD-CANARY"

    try:
        JWTKey.from_rsa_private(
            "safe-id",
            JWSAlgorithm.RS256,
            canary.encode(),
            password=canary.encode(),
        )
    except JWTKeyError as error:
        rendered = "".join(traceback.format_exception(error))
        assert str(error) == "JWT key is invalid"
        assert repr(error) == "JWTKeyError('JWT key is invalid')"
        assert error.__cause__ is None
        assert error.__suppress_context__ is True
        assert canary not in rendered
    else:
        pytest.fail("invalid RSA material was accepted")
