"""Immutable JWT key wrappers with strict family and strength gates."""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from bluetape.jwt._algorithms import JWSAlgorithm
from bluetape.jwt._errors import JWTKeyError
from joserfc.errors import SecurityWarning
from joserfc.jwk import OctKey, RSAKey

_HMAC_ALGORITHMS = frozenset({JWSAlgorithm.HS256, JWSAlgorithm.HS384, JWSAlgorithm.HS512})
_RSA_ALGORITHMS = frozenset(
    {
        JWSAlgorithm.RS256,
        JWSAlgorithm.RS384,
        JWSAlgorithm.RS512,
        JWSAlgorithm.PS256,
        JWSAlgorithm.PS384,
        JWSAlgorithm.PS512,
    }
)
_PRIVATE_RSA_FIELDS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})


def _raise_key_error() -> None:
    raise JWTKeyError() from None


def _validate_kid(kid: object) -> str:
    if type(kid) is not str:
        _raise_key_error()
    try:
        encoded = kid.encode("utf-8")
    except UnicodeError:
        _raise_key_error()
    if not kid or kid != kid.strip() or "\x00" in kid or len(encoded) > 128:
        _raise_key_error()
    return kid


def _validate_algorithm(
    algorithm: object,
    allowed: frozenset[JWSAlgorithm],
) -> JWSAlgorithm:
    if not isinstance(algorithm, JWSAlgorithm) or algorithm not in allowed:
        _raise_key_error()
    return algorithm


def _copy_rsa_material(
    material: object,
    *,
    kid: str,
    algorithm: JWSAlgorithm,
    private: bool,
) -> str | bytes | dict[str, Any]:
    if isinstance(material, (str, bytes)):
        return material
    if not isinstance(material, Mapping):
        _raise_key_error()
    try:
        copied = dict(material)
    except Exception:
        _raise_key_error()
    if any(type(name) is not str for name in copied):
        _raise_key_error()
    _validate_jwk_metadata(copied, kid=kid, algorithm=algorithm, private=private)
    return copied


def _validate_jwk_metadata(
    jwk: Mapping[str, Any],
    *,
    kid: str,
    algorithm: JWSAlgorithm,
    private: bool,
) -> None:
    if "kty" in jwk and (type(jwk["kty"]) is not str or jwk["kty"] != "RSA"):
        _raise_key_error()
    if "kid" in jwk and (type(jwk["kid"]) is not str or jwk["kid"] != kid):
        _raise_key_error()
    if "alg" in jwk and (type(jwk["alg"]) is not str or jwk["alg"] != algorithm.value):
        _raise_key_error()
    if "use" in jwk and (type(jwk["use"]) is not str or jwk["use"] != "sig"):
        _raise_key_error()
    if "key_ops" not in jwk:
        return

    operations = jwk["key_ops"]
    if type(operations) is not list or any(type(item) is not str for item in operations):
        _raise_key_error()
    operation_set = set(operations)
    if len(operation_set) != len(operations):
        _raise_key_error()
    if private:
        if "sign" not in operation_set or not operation_set <= {"sign", "verify"}:
            _raise_key_error()
    elif operation_set != {"verify"}:
        _raise_key_error()


def _import_rsa_key(
    material: str | bytes | dict[str, Any],
    *,
    password: bytes | None,
) -> RSAKey:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SecurityWarning)
            key = RSAKey.import_key(material, password=password)
    except Exception:
        _raise_key_error()
    if key.public_key.key_size < 2048:
        _raise_key_error()
    return key


@dataclass(frozen=True, slots=True, eq=False, repr=False, init=False)
class JWTKey:
    """Opaque, identity-based JWT key material selected for one algorithm."""

    __hash__ = None

    _kid: str
    _algorithm: JWSAlgorithm
    _can_sign: bool
    _provider_key: OctKey | RSAKey

    def __init__(self) -> None:
        """Reject construction that bypasses the validated factories."""
        raise TypeError("JWTKey must be created by a factory method")

    @classmethod
    def _create(
        cls,
        kid: str,
        algorithm: JWSAlgorithm,
        can_sign: bool,
        provider_key: OctKey | RSAKey,
    ) -> JWTKey:
        key = object.__new__(cls)
        object.__setattr__(key, "_kid", kid)
        object.__setattr__(key, "_algorithm", algorithm)
        object.__setattr__(key, "_can_sign", can_sign)
        object.__setattr__(key, "_provider_key", provider_key)
        return key

    @classmethod
    def from_hmac_secret(
        cls,
        kid: str,
        algorithm: JWSAlgorithm,
        secret: bytes,
    ) -> JWTKey:
        """Copy and import an HMAC secret that meets the selected strength."""
        validated_kid = _validate_kid(kid)
        validated_algorithm = _validate_algorithm(algorithm, _HMAC_ALGORITHMS)
        if type(secret) is not bytes:
            _raise_key_error()
        secret_copy = bytes(secret)
        if len(secret_copy) * 8 < validated_algorithm._minimum_key_bits:
            _raise_key_error()
        try:
            provider_key = OctKey.import_key(secret_copy)
        except Exception:
            _raise_key_error()
        return cls._create(validated_kid, validated_algorithm, True, provider_key)

    @classmethod
    def from_rsa_private(
        cls,
        kid: str,
        algorithm: JWSAlgorithm,
        material: str | bytes | Mapping[str, object],
        *,
        password: bytes | None = None,
    ) -> JWTKey:
        """Import private RSA material for signing and verification."""
        validated_kid = _validate_kid(kid)
        validated_algorithm = _validate_algorithm(algorithm, _RSA_ALGORITHMS)
        if password is not None and type(password) is not bytes:
            _raise_key_error()
        copied_material = _copy_rsa_material(
            material,
            kid=validated_kid,
            algorithm=validated_algorithm,
            private=True,
        )
        if isinstance(copied_material, dict) and password is not None:
            _raise_key_error()
        provider_key = _import_rsa_key(copied_material, password=password)
        if not provider_key.is_private:
            _raise_key_error()
        return cls._create(validated_kid, validated_algorithm, True, provider_key)

    @classmethod
    def from_rsa_public(
        cls,
        kid: str,
        algorithm: JWSAlgorithm,
        material: str | bytes | Mapping[str, object],
    ) -> JWTKey:
        """Import public-only RSA material for verification."""
        validated_kid = _validate_kid(kid)
        validated_algorithm = _validate_algorithm(algorithm, _RSA_ALGORITHMS)
        copied_material = _copy_rsa_material(
            material,
            kid=validated_kid,
            algorithm=validated_algorithm,
            private=False,
        )
        provider_key = _import_rsa_key(copied_material, password=None)
        if provider_key.is_private:
            _raise_key_error()
        return cls._create(validated_kid, validated_algorithm, False, provider_key)

    @property
    def kid(self) -> str:
        """Return the validated key identifier."""
        return self._kid

    @property
    def algorithm(self) -> JWSAlgorithm:
        """Return the one algorithm selected for this key."""
        return self._algorithm

    @property
    def can_sign(self) -> bool:
        """Return whether this wrapper contains signing material."""
        return self._can_sign

    def public_jwk(self) -> Mapping[str, str]:
        """Return a fresh immutable RSA public JWK projection."""
        if not isinstance(self._provider_key, RSAKey):
            _raise_key_error()
        try:
            public = self._provider_key.as_dict(private=False)
            projection = {
                "kty": "RSA",
                "kid": self._kid,
                "alg": self._algorithm.value,
                "n": public["n"],
                "e": public["e"],
            }
        except Exception:
            _raise_key_error()
        if not all(type(value) is str for value in projection.values()):
            _raise_key_error()
        if _PRIVATE_RSA_FIELDS.intersection(projection):
            _raise_key_error()
        return cast(Mapping[str, str], MappingProxyType(projection))
