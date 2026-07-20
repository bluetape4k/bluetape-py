"""Strict JWT signing, verification, and key-rotation contracts."""

from pkgutil import extend_path

from bluetape.jwt._algorithms import JWSAlgorithm
from bluetape.jwt._claims import JSONValue, TokenClaims, VerifiedToken
from bluetape.jwt._errors import (
    JWTCacheError,
    JWTClaimError,
    JWTConfigurationError,
    JWTError,
    JWTExpiredError,
    JWTIssuancePolicyError,
    JWTKeyError,
    JWTKeyStateError,
    JWTKeyUnavailableError,
    JWTMalformedTokenError,
    JWTNotYetValidError,
    JWTSignatureError,
    JWTTokenError,
    JWTUnsupportedTokenError,
)
from bluetape.jwt._keys import JWTKey
from bluetape.jwt._profiles import IssuanceProfile, ValidationProfile
from bluetape.jwt._provider import JWSProvider, TokenProvider
from bluetape.jwt._repository import (
    InMemoryKeyRepository,
    KeyEntry,
    KeyRepository,
    KeySnapshot,
    KeyStatus,
)

__path__ = extend_path(__path__, __name__)

__all__ = [  # noqa: RUF022 - public order is part of the contract
    "JWTError",
    "JWTConfigurationError",
    "JWTKeyError",
    "JWTKeyStateError",
    "JWTKeyUnavailableError",
    "JWTTokenError",
    "JWTMalformedTokenError",
    "JWTUnsupportedTokenError",
    "JWTSignatureError",
    "JWTExpiredError",
    "JWTNotYetValidError",
    "JWTClaimError",
    "JWTIssuancePolicyError",
    "JWTCacheError",
    "JWSAlgorithm",
    "KeyStatus",
    "JSONValue",
    "JWTKey",
    "KeyEntry",
    "KeySnapshot",
    "KeyRepository",
    "InMemoryKeyRepository",
    "TokenClaims",
    "VerifiedToken",
    "IssuanceProfile",
    "ValidationProfile",
    "TokenProvider",
    "JWSProvider",
]
