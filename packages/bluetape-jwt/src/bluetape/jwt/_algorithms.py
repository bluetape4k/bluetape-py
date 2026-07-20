"""Approved JWS algorithms and internal key-family policy."""

from enum import StrEnum


class _AlgorithmFamily(StrEnum):
    HMAC = "hmac"
    RSA = "rsa"


class JWSAlgorithm(StrEnum):
    """JWS algorithms accepted by bluetape-jwt providers."""

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"
    PS256 = "PS256"
    PS384 = "PS384"
    PS512 = "PS512"

    @property
    def _family(self) -> _AlgorithmFamily:
        if self.name.startswith("HS"):
            return _AlgorithmFamily.HMAC
        return _AlgorithmFamily.RSA

    @property
    def _minimum_key_bits(self) -> int:
        if self._family is _AlgorithmFamily.HMAC:
            return int(self.name[2:])
        return 2048
