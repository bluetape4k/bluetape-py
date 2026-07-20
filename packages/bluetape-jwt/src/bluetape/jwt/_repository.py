"""Atomic immutable key repository and lifecycle transitions."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from types import MappingProxyType
from typing import Protocol

from bluetape.jwt._algorithms import JWSAlgorithm
from bluetape.jwt._errors import JWTConfigurationError, JWTKeyStateError
from bluetape.jwt._keys import JWTKey

logger = logging.getLogger(__name__)

_LOG_MESSAGE = "JWT key repository mutation"


def _raise_configuration_error() -> None:
    raise JWTConfigurationError() from None


def _raise_key_state_error() -> None:
    raise JWTKeyStateError() from None


def _validate_kid(kid: object) -> str:
    if type(kid) is not str:
        _raise_configuration_error()
    try:
        encoded = kid.encode("utf-8")
    except UnicodeError:
        _raise_configuration_error()
    if not kid or kid != kid.strip() or "\x00" in kid or len(encoded) > 128:
        _raise_configuration_error()
    return kid


def _validate_key(key: object) -> JWTKey:
    if type(key) is not JWTKey:
        _raise_configuration_error()
    return key


class KeyStatus(StrEnum):
    """Repository-owned lifecycle status for JWT key material."""

    ACTIVE = "active"
    RETIRED = "retired"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class KeyEntry:
    """One immutable repository-owned key lifecycle entry."""

    status: KeyStatus
    key: JWTKey | None

    def __post_init__(self) -> None:
        if type(self.status) is not KeyStatus:
            _raise_key_state_error()
        if self.status is KeyStatus.REVOKED:
            if self.key is not None:
                _raise_key_state_error()
        elif type(self.key) is not JWTKey:
            _raise_key_state_error()


@dataclass(frozen=True, slots=True)
class KeySnapshot:
    """Immutable point-in-time view of a repository state."""

    entries: Mapping[str, KeyEntry]
    epoch: int

    def __post_init__(self) -> None:
        if type(self.epoch) is not int or self.epoch < 0:
            _raise_configuration_error()
        if not isinstance(self.entries, Mapping):
            _raise_configuration_error()
        try:
            copied = dict(self.entries)
        except Exception:
            _raise_configuration_error()

        active_count = 0
        for kid, entry in copied.items():
            validated_kid = _validate_kid(kid)
            if type(entry) is not KeyEntry:
                _raise_configuration_error()
            if entry.key is not None and entry.key.kid != validated_kid:
                _raise_configuration_error()
            if entry.status is KeyStatus.ACTIVE:
                active_count += 1
        if active_count > 1:
            _raise_configuration_error()
        object.__setattr__(self, "entries", MappingProxyType(copied))

    @property
    def active(self) -> KeyEntry | None:
        """Return the active entry, if the snapshot has one."""
        return next(
            (entry for entry in self.entries.values() if entry.status is KeyStatus.ACTIVE),
            None,
        )


class KeyRepository(Protocol):
    """Synchronous repository contract used by JWT providers."""

    def snapshot(self) -> KeySnapshot: ...

    def add_verification_key(self, key: JWTKey) -> KeySnapshot: ...

    def rotate(self, key: JWTKey) -> KeySnapshot: ...

    def retire(self, kid: str) -> KeySnapshot: ...

    def revoke(self, kid: str) -> KeySnapshot: ...


def _freeze_snapshot(entries: dict[str, KeyEntry], epoch: int) -> KeySnapshot:
    return KeySnapshot(entries, epoch)


class InMemoryKeyRepository:
    """Thread-safe repository that publishes complete immutable snapshots."""

    def __init__(
        self,
        *,
        active: JWTKey | None = None,
        verification_keys: Iterable[JWTKey] = (),
    ) -> None:
        entries: dict[str, KeyEntry] = {}
        algorithm: JWSAlgorithm | None = None

        if active is not None:
            active_key = _validate_key(active)
            if not active_key.can_sign:
                _raise_key_state_error()
            algorithm = active_key.algorithm
            entries[active_key.kid] = KeyEntry(KeyStatus.ACTIVE, active_key)

        try:
            candidates = tuple(verification_keys)
        except Exception:
            _raise_configuration_error()
        for candidate in candidates:
            key = _validate_key(candidate)
            if key.kid in entries:
                _raise_key_state_error()
            if algorithm is None:
                algorithm = key.algorithm
            elif key.algorithm is not algorithm:
                _raise_configuration_error()
            entries[key.kid] = KeyEntry(KeyStatus.RETIRED, key)

        self._lock = RLock()
        self._algorithm = algorithm
        self._snapshot = _freeze_snapshot(entries, 0)

    def snapshot(self) -> KeySnapshot:
        """Capture one complete immutable repository state."""
        with self._lock:
            return self._snapshot

    def add_verification_key(self, key: JWTKey) -> KeySnapshot:
        """Install new compatible verification material as retired."""
        return self._mutate_key("add_verification_key", key, active=False)

    def rotate(self, key: JWTKey) -> KeySnapshot:
        """Publish a new active key while retaining the old key for verification."""
        return self._mutate_key("rotate", key, active=True)

    def retire(self, kid: str) -> KeySnapshot:
        """Retire the current active key without selecting a replacement."""
        return self._mutate_identifier("retire", kid)

    def revoke(self, kid: str) -> KeySnapshot:
        """Remove usable material and preserve its identifier as a tombstone."""
        return self._mutate_identifier("revoke", kid)

    def _mutate_key(
        self,
        operation: str,
        candidate: object,
        *,
        active: bool,
    ) -> KeySnapshot:
        try:
            with self._lock:
                key = _validate_key(candidate)
                if active and not key.can_sign:
                    _raise_key_state_error()
                if key.kid in self._snapshot.entries:
                    _raise_key_state_error()
                if self._algorithm is not None and key.algorithm is not self._algorithm:
                    _raise_configuration_error()

                entries = dict(self._snapshot.entries)
                if active:
                    for kid, entry in tuple(entries.items()):
                        if entry.status is KeyStatus.ACTIVE:
                            entries[kid] = KeyEntry(KeyStatus.RETIRED, entry.key)
                status = KeyStatus.ACTIVE if active else KeyStatus.RETIRED
                entries[key.kid] = KeyEntry(status, key)
                published = _freeze_snapshot(entries, self._snapshot.epoch + 1)
                self._snapshot = published
                if self._algorithm is None:
                    self._algorithm = key.algorithm
        except (JWTConfigurationError, JWTKeyStateError) as error:
            self._log_failure(operation, error)
            raise error from None

        self._log_success(operation)
        return published

    def _mutate_identifier(self, operation: str, candidate: object) -> KeySnapshot:
        try:
            with self._lock:
                kid = _validate_kid(candidate)
                entry = self._snapshot.entries.get(kid)
                if entry is None:
                    _raise_key_state_error()
                if operation == "retire":
                    if entry.status is not KeyStatus.ACTIVE:
                        _raise_key_state_error()
                    replacement = KeyEntry(KeyStatus.RETIRED, entry.key)
                else:
                    if entry.status is KeyStatus.REVOKED:
                        _raise_key_state_error()
                    replacement = KeyEntry(KeyStatus.REVOKED, None)

                entries = dict(self._snapshot.entries)
                entries[kid] = replacement
                published = _freeze_snapshot(entries, self._snapshot.epoch + 1)
                self._snapshot = published
        except (JWTConfigurationError, JWTKeyStateError) as error:
            self._log_failure(operation, error)
            raise error from None

        self._log_success(operation)
        return published

    @staticmethod
    def _log_success(operation: str) -> None:
        logger.info(
            _LOG_MESSAGE,
            extra={
                "event": "jwt_key_repository_mutation",
                "operation": operation,
                "outcome": "success",
                "error_category": "none",
            },
        )

    @staticmethod
    def _log_failure(
        operation: str,
        error: JWTConfigurationError | JWTKeyStateError,
    ) -> None:
        category = "configuration" if type(error) is JWTConfigurationError else "key_state"
        logger.warning(
            _LOG_MESSAGE,
            extra={
                "event": "jwt_key_repository_mutation",
                "operation": operation,
                "outcome": "failure",
                "error_category": category,
            },
        )
