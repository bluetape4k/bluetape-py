"""Stable, value-free exceptions for JWT security boundaries."""

from __future__ import annotations


class JWTError(Exception):
    """Base class for public bluetape-jwt failures."""

    __slots__ = ()
    _message = "JWT operation failed"

    def __init__(self) -> None:
        super().__init__(self._message)

    def __reduce__(self) -> tuple[type[JWTError], tuple[()]]:
        return type(self), ()


class JWTConfigurationError(JWTError, ValueError):
    """Raised when provider configuration is invalid."""

    __slots__ = ()
    _message = "JWT configuration is invalid"


class JWTKeyError(JWTError):
    """Raised when JWT key material is invalid."""

    __slots__ = ()
    _message = "JWT key is invalid"


class JWTKeyStateError(JWTKeyError):
    """Raised when a key lifecycle transition is invalid."""

    __slots__ = ()
    _message = "JWT key state transition is invalid"


class JWTKeyUnavailableError(JWTKeyError):
    """Raised when a required signing or verification key is unavailable."""

    __slots__ = ()
    _message = "JWT key is unavailable"


class JWTTokenError(JWTError):
    """Base class for rejected JWT tokens."""

    __slots__ = ()
    _message = "JWT token is invalid"


class JWTMalformedTokenError(JWTTokenError):
    """Raised when a JWT cannot be parsed safely."""

    __slots__ = ()
    _message = "JWT token is malformed"


class JWTUnsupportedTokenError(JWTTokenError):
    """Raised when a JWT uses an unsupported feature."""

    __slots__ = ()
    _message = "JWT token is unsupported"


class JWTSignatureError(JWTTokenError):
    """Raised when JWS signature verification fails."""

    __slots__ = ()
    _message = "JWT signature verification failed"


class JWTExpiredError(JWTTokenError):
    """Raised when a JWT is expired."""

    __slots__ = ()
    _message = "JWT token is expired"


class JWTNotYetValidError(JWTTokenError):
    """Raised when a JWT is not yet valid."""

    __slots__ = ()
    _message = "JWT token is not yet valid"


class JWTClaimError(JWTTokenError):
    """Raised when a JWT claim is missing or invalid."""

    __slots__ = ()
    _message = "JWT claim is invalid"


class JWTIssuancePolicyError(JWTError, ValueError):
    """Raised when claims violate the configured issuance policy."""

    __slots__ = ()
    _message = "JWT issuance policy is invalid"


class JWTCacheError(JWTError):
    """Raised when the optional verified-token cache fails."""

    __slots__ = ()
    _message = "JWT cache operation failed"
