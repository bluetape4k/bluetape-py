"""Strict synchronous JWS provider bound to one repository and policy."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from typing import Any, ClassVar, Protocol

from bluetape.jwt._algorithms import JWSAlgorithm
from bluetape.jwt._cache import VerifiedTokenCacheOptions, _VerifiedTokenCache
from bluetape.jwt._claims import (
    TokenClaims,
    VerifiedToken,
    _claims_from_payload,
    _claims_to_payload,
    _to_verified_token,
)
from bluetape.jwt._errors import (
    JWTConfigurationError,
    JWTError,
    JWTKeyUnavailableError,
    JWTMalformedTokenError,
    JWTSignatureError,
    JWTTokenError,
    JWTUnsupportedTokenError,
)
from bluetape.jwt._profiles import (
    ValidationProfile,
    _capture_reference_time,
    _validate_claims,
)
from bluetape.jwt._repository import KeyRepository, KeySnapshot, KeyStatus
from joserfc import jwt
from joserfc.errors import BadSignatureError, DecodeError, InvalidPayloadError, JoseError
from joserfc.jws import JWSRegistry
from joserfc.registry import HeaderParameter

_MAX_TOKEN_BYTES = 16_384
_MAX_PROTECTED_HEADER_BYTES = 512
_BASE64URL_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError
        result[name] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError


class _StrictJSONDecoder(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["object_pairs_hook"] = _strict_object
        kwargs["parse_constant"] = _reject_json_constant
        super().__init__(*args, **kwargs)


class _RestrictedJWSRegistry(JWSRegistry):
    default_header_registry: ClassVar[dict[str, HeaderParameter]] = {
        name: JWSRegistry.default_header_registry[name] for name in ("alg", "kid", "typ")
    }


class TokenProvider(Protocol):
    """Minimal composable synchronous token provider contract."""

    def issue(self, claims: TokenClaims) -> str: ...

    def verify(self, token: str) -> VerifiedToken: ...


class JWSProvider:
    """Issue and verify compact JWS tokens under one immutable policy."""

    __slots__ = ("_algorithm", "_cache", "_profile", "_registry", "_repository")

    def __init__(
        self,
        algorithm: JWSAlgorithm,
        repository: KeyRepository,
        validation_profile: ValidationProfile,
        *,
        cache: VerifiedTokenCacheOptions | None = None,
    ) -> None:
        if (
            type(algorithm) is not JWSAlgorithm
            or not callable(getattr(repository, "snapshot", None))
            or type(validation_profile) is not ValidationProfile
            or (cache is not None and type(cache) is not VerifiedTokenCacheOptions)
        ):
            raise JWTConfigurationError() from None
        custom_headers = {
            name: HeaderParameter("Application protected header", "str")
            for name in validation_profile.protected_headers
        }
        self._algorithm = algorithm
        self._repository = repository
        self._profile = validation_profile
        self._cache = None if cache is None else _VerifiedTokenCache(cache)
        self._registry = _RestrictedJWSRegistry(
            header_registry=custom_headers,
            algorithms=[algorithm.value],
            strict_check_header=True,
        )

    def issue(self, claims: TokenClaims) -> str:
        """Sign caller-owned immutable claims with the current active key."""
        snapshot = self._snapshot()
        entry = snapshot.active
        if (
            entry is None
            or entry.status is not KeyStatus.ACTIVE
            or entry.key is None
            or entry.key.algorithm is not self._algorithm
            or not entry.key.can_sign
        ):
            raise JWTKeyUnavailableError() from None
        header = {
            "alg": self._algorithm.value,
            "kid": entry.key.kid,
            "typ": self._profile.token_type,
            **self._profile.protected_headers,
        }
        try:
            return jwt.encode(
                header,
                _claims_to_payload(claims),
                entry.key._provider_key,
                algorithms=[self._algorithm.value],
                registry=self._registry,
                default_type=None,
            )
        except JWTError:
            raise
        except Exception:
            raise JWTTokenError() from None

    def verify(self, token: str) -> VerifiedToken:
        """Verify one compact token and return a frozen public projection."""
        segments = self._validate_token_shape(token)
        snapshot = self._snapshot()
        now = _capture_reference_time(self._profile)
        if self._cache is not None:
            cached = self._cache.get(token, self._profile, snapshot)
            if cached is not None:
                self._validate_cached(cached, now=now)
                return cached
        header = self._read_header(segments[0])
        entry = snapshot.entries.get(header["kid"])
        if (
            entry is None
            or entry.status not in {KeyStatus.ACTIVE, KeyStatus.RETIRED}
            or entry.key is None
        ):
            raise JWTKeyUnavailableError() from None
        if entry.key.algorithm is not self._algorithm:
            raise JWTUnsupportedTokenError() from None

        try:
            decoded = jwt.decode(
                token,
                entry.key._provider_key,
                algorithms=[self._algorithm.value],
                registry=self._registry,
                decoder_cls=_StrictJSONDecoder,
            )
        except BadSignatureError:
            raise JWTSignatureError() from None
        except (DecodeError, InvalidPayloadError):
            raise JWTMalformedTokenError() from None
        except JoseError:
            raise JWTUnsupportedTokenError() from None
        except Exception:
            raise JWTSignatureError() from None

        if type(decoded.header) is not dict or decoded.header != header:
            raise JWTMalformedTokenError() from None

        claims = _claims_from_payload(decoded.claims)
        custom_headers = {name: header[name] for name in self._profile.protected_headers}
        _validate_claims(
            claims,
            self._profile,
            token_type=header["typ"],
            protected_headers=custom_headers,
            now=now,
        )
        verified = _to_verified_token(
            claims,
            kid=entry.key.kid,
            algorithm=self._algorithm,
            token_type=header["typ"],
            headers=custom_headers,
        )
        if self._cache is not None:
            live_epoch = self._live_epoch()
            if live_epoch is not None:
                self._cache.set(
                    token,
                    self._profile,
                    snapshot,
                    verified,
                    now=now,
                    live_epoch=live_epoch,
                )
        return verified

    def _validate_cached(self, value: VerifiedToken, *, now: datetime) -> None:
        claims = TokenClaims(
            issuer=value.issuer,
            subject=value.subject,
            audience=value.audience,
            expires_at=value.expires_at,
            not_before=value.not_before,
            issued_at=value.issued_at,
            jwt_id=value.jwt_id,
            custom=value.custom,
        )
        _validate_claims(
            claims,
            self._profile,
            token_type=value.token_type,
            protected_headers=value.headers,
            now=now,
        )

    def _live_epoch(self) -> int | None:
        try:
            snapshot = self._repository.snapshot()
        except Exception:
            return None
        return snapshot.epoch if type(snapshot) is KeySnapshot else None

    def _snapshot(self) -> KeySnapshot:
        try:
            snapshot = self._repository.snapshot()
        except JWTError:
            raise
        except Exception:
            raise JWTKeyUnavailableError() from None
        if type(snapshot) is not KeySnapshot:
            raise JWTKeyUnavailableError() from None
        return snapshot

    def _validate_token_shape(self, token: object) -> tuple[str, str, str]:
        if type(token) is not str or len(token) > _MAX_TOKEN_BYTES:
            raise JWTMalformedTokenError() from None
        try:
            if len(token.encode("utf-8")) > _MAX_TOKEN_BYTES:
                raise ValueError
            segments = token.split(".")
            if (
                len(segments) != 3
                or any(not segment for segment in segments)
                or any(_BASE64URL_SEGMENT.fullmatch(segment) is None for segment in segments)
            ):
                raise ValueError
        except (UnicodeError, ValueError):
            raise JWTMalformedTokenError() from None
        return segments[0], segments[1], segments[2]

    def _read_header(self, encoded: str) -> dict[str, str]:
        try:
            padding = "=" * (-len(encoded) % 4)
            raw = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
            if len(raw) > _MAX_PROTECTED_HEADER_BYTES:
                raise ValueError
            header = json.loads(raw.decode("utf-8"), cls=_StrictJSONDecoder)
        except (UnicodeError, ValueError):
            raise JWTMalformedTokenError() from None
        if type(header) is not dict:
            raise JWTMalformedTokenError() from None
        expected = {
            "alg": self._algorithm.value,
            "typ": self._profile.token_type,
            **self._profile.protected_headers,
        }
        allowed = {"alg", "kid", "typ", *self._profile.protected_headers}
        if (
            set(header) != allowed
            or any(type(header.get(name)) is not str for name in allowed)
            or any(header.get(name) != value for name, value in expected.items())
        ):
            raise JWTUnsupportedTokenError() from None
        kid = header["kid"]
        try:
            encoded_kid = kid.encode("utf-8")
        except UnicodeError:
            raise JWTUnsupportedTokenError() from None
        if not kid or kid != kid.strip() or "\x00" in kid or len(encoded_kid) > 128:
            raise JWTUnsupportedTokenError() from None
        return header
