from __future__ import annotations

import copy
import pickle
import traceback

import bluetape.jwt as jwt
import pytest

ERROR_MESSAGES = [
    ("JWTError", "JWT operation failed"),
    ("JWTConfigurationError", "JWT configuration is invalid"),
    ("JWTKeyError", "JWT key is invalid"),
    ("JWTKeyStateError", "JWT key state transition is invalid"),
    ("JWTKeyUnavailableError", "JWT key is unavailable"),
    ("JWTTokenError", "JWT token is invalid"),
    ("JWTMalformedTokenError", "JWT token is malformed"),
    ("JWTUnsupportedTokenError", "JWT token is unsupported"),
    ("JWTSignatureError", "JWT signature verification failed"),
    ("JWTExpiredError", "JWT token is expired"),
    ("JWTNotYetValidError", "JWT token is not yet valid"),
    ("JWTClaimError", "JWT claim is invalid"),
    ("JWTIssuancePolicyError", "JWT issuance policy is invalid"),
    ("JWTCacheError", "JWT cache operation failed"),
]


@pytest.mark.parametrize(("error_name", "message"), ERROR_MESSAGES)
def test_public_errors_survive_safe_reconstruction(error_name: str, message: str) -> None:
    canary = "private-key-token-claim-canary"
    error_type = getattr(jwt, error_name)
    error = error_type()

    restored_errors = [copy.copy(error), pickle.loads(pickle.dumps(error))]

    for restored in restored_errors:
        assert type(restored) is error_type
        assert str(restored) == message
        assert restored.args == (message,)
        assert canary not in str(restored)
        assert canary not in repr(restored)


def test_public_errors_are_redacted() -> None:
    canary = "private-key-token-claim-canary"

    for error_name, message in ERROR_MESSAGES:
        error_type = getattr(jwt, error_name)
        error = error_type()

        assert str(error) == message
        assert repr(error) == f"{error_name}({message!r})"
        assert error.args == (message,)
        assert canary not in str(error)
        assert canary not in repr(error)

        with pytest.raises(TypeError):
            error_type(canary)

        try:
            try:
                raise RuntimeError(canary)
            except RuntimeError:
                raise error_type() from None
        except error_type as translated:
            rendered = "".join(traceback.format_exception(translated))
            assert translated.__cause__ is None
            assert translated.__suppress_context__ is True
            assert canary not in rendered


def test_error_hierarchy_is_exact() -> None:
    assert jwt.JWTError.__bases__ == (Exception,)
    assert jwt.JWTConfigurationError.__bases__ == (jwt.JWTError, ValueError)
    assert jwt.JWTKeyError.__bases__ == (jwt.JWTError,)
    assert jwt.JWTKeyStateError.__bases__ == (jwt.JWTKeyError,)
    assert jwt.JWTKeyUnavailableError.__bases__ == (jwt.JWTKeyError,)
    assert jwt.JWTTokenError.__bases__ == (jwt.JWTError,)
    assert jwt.JWTMalformedTokenError.__bases__ == (jwt.JWTTokenError,)
    assert jwt.JWTUnsupportedTokenError.__bases__ == (jwt.JWTTokenError,)
    assert jwt.JWTSignatureError.__bases__ == (jwt.JWTTokenError,)
    assert jwt.JWTExpiredError.__bases__ == (jwt.JWTTokenError,)
    assert jwt.JWTNotYetValidError.__bases__ == (jwt.JWTTokenError,)
    assert jwt.JWTClaimError.__bases__ == (jwt.JWTTokenError,)
    assert jwt.JWTIssuancePolicyError.__bases__ == (jwt.JWTError, ValueError)
    assert jwt.JWTCacheError.__bases__ == (jwt.JWTError,)
