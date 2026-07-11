"""Apache Fory contracts for authenticated internal serialization."""

from __future__ import annotations

import math
import re
import struct
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ._contracts import (
    ContentTypeMismatchError,
    FormatMismatchError,
    ForyConcurrencyError,
    ForyRegistrationError,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SchemaMismatchError,
    SerdeEncodeError,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfile,
    TrustProfileMismatchError,
    TypeMismatchError,
    UnsupportedVersionError,
)

_missing_provider = False
try:
    import pyfory as _pyfory
except ModuleNotFoundError as error:
    if error.name != "pyfory":
        raise
    _missing_provider = True

if _missing_provider:
    raise ModuleNotFoundError(
        "Install bluetape-serde[fory] with CPython 3.13 to use Apache Fory.",
        name="pyfory",
    )


FORY_FORMAT = "apache-fory-xlang"
FORY_VERSION = 1
FORY_CONTENT_TYPE = "application/x-apache-fory"

__all__ = [
    "FORY_CONTENT_TYPE",
    "FORY_FORMAT",
    "FORY_VERSION",
    "ForyAdapter",
    "ForyLimits",
    "ForyRegistration",
]

_LOGICAL_NAME = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", re.ASCII)
_ENVELOPE = struct.Struct(">4sBBIHII")
_FATAL_EXCEPTIONS = (MemoryError, KeyboardInterrupt, SystemExit)


class _ForyRegistrationFailureError(Exception):
    pass


def _require_exact_int(name: str, value: object, minimum: int, maximum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact int")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in {minimum}..{maximum}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ForyRegistration[T]:
    """Bind one Python root type to a caller-owned Fory schema identity."""

    python_type: type[T]
    schema_id: int
    schema_version: int
    type_id: int
    logical_name: str

    def __post_init__(self) -> None:
        if type(self.python_type) is not type:
            raise TypeError("python_type must be an exact type")
        _require_exact_int("schema_id", self.schema_id, 1, 0xFFFFFFFF)
        _require_exact_int("schema_version", self.schema_version, 1, 0xFFFF)
        _require_exact_int("type_id", self.type_id, 1, 0xFFFFFFFE)
        if type(self.logical_name) is not str:
            raise TypeError("logical_name must be an exact str")
        if (
            not 1 <= len(self.logical_name) <= 128
            or _LOGICAL_NAME.fullmatch(self.logical_name) is None
        ):
            raise ValueError("logical_name must be a bounded ASCII dotted name")


@dataclass(frozen=True, slots=True, kw_only=True)
class ForyLimits:
    """Bound Apache Fory resource use and runtime-pool concurrency."""

    max_input_size: int = 16 * 1024 * 1024
    max_output_size: int = 16 * 1024 * 1024
    max_depth: int = 64
    max_type_fields: int = 256
    max_type_meta_bytes: int = 4096
    max_schema_versions_per_type: int = 8
    max_average_schema_versions_per_type: int = 2
    max_concurrency: int = 4
    acquire_timeout_seconds: float = 5.0
    reference_tracking: bool = False

    def __post_init__(self) -> None:
        _require_exact_int("max_input_size", self.max_input_size, 20, 1024**3)
        _require_exact_int("max_output_size", self.max_output_size, 20, 1024**3)
        _require_exact_int("max_depth", self.max_depth, 1, 256)
        _require_exact_int("max_type_fields", self.max_type_fields, 1, 65_535)
        _require_exact_int("max_type_meta_bytes", self.max_type_meta_bytes, 1, 16 * 1024 * 1024)
        _require_exact_int(
            "max_schema_versions_per_type",
            self.max_schema_versions_per_type,
            1,
            65_535,
        )
        _require_exact_int(
            "max_average_schema_versions_per_type",
            self.max_average_schema_versions_per_type,
            1,
            65_535,
        )
        if self.max_average_schema_versions_per_type > self.max_schema_versions_per_type:
            raise ValueError(
                "max_average_schema_versions_per_type must not exceed max_schema_versions_per_type"
            )
        _require_exact_int("max_concurrency", self.max_concurrency, 1, 64)
        if type(self.acquire_timeout_seconds) is not float:
            raise TypeError("acquire_timeout_seconds must be an exact float")
        if not math.isfinite(self.acquire_timeout_seconds) or not (
            0.001 <= self.acquire_timeout_seconds <= 60.0
        ):
            raise ValueError("acquire_timeout_seconds must be in 0.001..60.0")
        if type(self.reference_tracking) is not bool:
            raise TypeError("reference_tracking must be an exact bool")
        if self.reference_tracking:
            raise ValueError("reference_tracking must be False")


_ErrorSpec = tuple[type[Exception], SerdeErrorCode | str | None]


def _new_error(spec: _ErrorSpec) -> Exception:
    error_type, detail = spec
    if error_type is TypeError:
        return TypeError(detail)
    if error_type in {MalformedPayloadError, PayloadLimitError, SerdeEncodeError}:
        return error_type(code=detail)
    return error_type()


def _metadata_error(metadata: object) -> _ErrorSpec | None:
    if type(metadata) is not PayloadMetadata:
        return (TypeError, "metadata must be an exact PayloadMetadata")
    if metadata.format != FORY_FORMAT:
        return (FormatMismatchError, None)
    if metadata.version != FORY_VERSION:
        return (UnsupportedVersionError, None)
    if metadata.content_type != FORY_CONTENT_TYPE:
        return (ContentTypeMismatchError, None)
    if metadata.trust_profile is not TrustProfile.TRUSTED_INTERNAL:
        return (TrustProfileMismatchError, None)
    return None


class ForyAdapter[T]:
    """Serialize one statically registered root type with bounded Fory runtimes."""

    __slots__ = (
        "_pool",
        "_provider_config",
        "_semaphore",
        "limits",
        "registration",
    )

    def __init__(
        self,
        *,
        registration: ForyRegistration[T],
        limits: ForyLimits | None = None,
    ) -> None:
        if type(registration) is not ForyRegistration:
            raise TypeError("registration must be an exact ForyRegistration")
        if limits is not None and type(limits) is not ForyLimits:
            raise TypeError("limits must be an exact ForyLimits or None")
        self.registration = registration
        self.limits = limits or ForyLimits()
        self._provider_config = MappingProxyType(
            {
                "xlang": True,
                "strict": True,
                "ref": False,
                "compatible": False,
                "max_depth": self.limits.max_depth,
                "max_type_fields": self.limits.max_type_fields,
                "max_type_meta_bytes": self.limits.max_type_meta_bytes,
                "max_schema_versions_per_type": self.limits.max_schema_versions_per_type,
                "max_average_schema_versions_per_type": (
                    self.limits.max_average_schema_versions_per_type
                ),
            }
        )
        self._semaphore = threading.BoundedSemaphore(self.limits.max_concurrency)

        registration_failed = False
        try:
            self._new_runtime()
        except _ForyRegistrationFailureError:
            registration_failed = True
        if registration_failed:
            raise ForyRegistrationError

        self._pool = _pyfory.ThreadSafeFory(fory_factory=self._new_runtime)

    def _new_runtime(self) -> Any:
        runtime = _pyfory.Fory(**self._provider_config)
        registration_failed = False
        try:
            runtime.register(
                self.registration.python_type,
                type_id=self.registration.type_id,
            )
        except _FATAL_EXCEPTIONS:
            raise
        except Exception:
            registration_failed = True
        if registration_failed:
            raise _ForyRegistrationFailureError
        return runtime

    def serialize(
        self,
        value: T,
        *,
        metadata: PayloadMetadata,
    ) -> SerializedPayload:
        """Serialize an exact registered root under trusted caller metadata."""
        payload, error_spec = self._try_serialize(value, metadata)
        del value, metadata
        if error_spec is not None:
            raise _new_error(error_spec)
        if payload is None:  # pragma: no cover - internal completeness invariant
            raise RuntimeError("Fory serialization produced no result")
        return payload

    def _try_serialize(
        self,
        value: T,
        metadata: PayloadMetadata,
    ) -> tuple[SerializedPayload | None, _ErrorSpec | None]:
        error_spec = _metadata_error(metadata)
        if error_spec is not None:
            return None, error_spec
        if type(value) is not self.registration.python_type:
            return None, (TypeMismatchError, None)
        if not self._semaphore.acquire(timeout=self.limits.acquire_timeout_seconds):
            return None, (ForyConcurrencyError, None)

        body: bytes | None = None
        try:
            try:
                provider_body = self._pool.serialize(value)
            except _FATAL_EXCEPTIONS:
                raise
            except _ForyRegistrationFailureError:
                return None, (ForyRegistrationError, None)
            except Exception:
                return None, (SerdeEncodeError, SerdeErrorCode.FORY_ENCODE)
            if type(provider_body) is not bytes:
                return None, (SerdeEncodeError, SerdeErrorCode.FORY_ENCODE)
            body = provider_body
            if _ENVELOPE.size + len(body) > self.limits.max_output_size:
                return None, (PayloadLimitError, SerdeErrorCode.OUTPUT_LIMIT)
            header = _ENVELOPE.pack(
                b"BTFY",
                FORY_VERSION,
                0,
                self.registration.schema_id,
                self.registration.schema_version,
                self.registration.type_id,
                len(body),
            )
            return SerializedPayload(metadata=metadata, data=header + body), None
        finally:
            body = None
            self._semaphore.release()

    def deserialize(
        self,
        payload: SerializedPayload,
        *,
        expected_metadata: PayloadMetadata,
    ) -> T:
        """Deserialize a trusted envelope against independent caller policy."""
        result, error_spec = self._try_deserialize(payload, expected_metadata)
        del payload, expected_metadata
        if error_spec is not None:
            raise _new_error(error_spec)
        if result is None:  # pragma: no cover - internal completeness invariant
            raise RuntimeError("Fory deserialization produced no result")
        return result

    def _try_deserialize(
        self,
        payload: SerializedPayload,
        expected_metadata: PayloadMetadata,
    ) -> tuple[T | None, _ErrorSpec | None]:
        if type(payload) is not SerializedPayload:
            return None, (TypeError, "payload must be an exact SerializedPayload")
        actual_error = _metadata_error(payload.metadata)
        if actual_error is not None:
            return None, actual_error
        expected_error = _metadata_error(expected_metadata)
        if expected_error is not None:
            if expected_error[0] is TypeError:
                return None, (TypeError, "expected_metadata must be an exact PayloadMetadata")
            return None, expected_error

        data = payload.data
        if len(data) > self.limits.max_input_size:
            return None, (PayloadLimitError, SerdeErrorCode.INPUT_LIMIT)
        if len(data) < _ENVELOPE.size:
            return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)

        (
            magic,
            envelope_version,
            flags,
            schema_id,
            schema_version,
            type_id,
            body_length,
        ) = _ENVELOPE.unpack_from(data)
        if magic != b"BTFY":
            return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)
        if envelope_version != FORY_VERSION:
            return None, (UnsupportedVersionError, None)
        if flags != 0:
            return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)
        if (
            schema_id != self.registration.schema_id
            or schema_version != self.registration.schema_version
        ):
            return None, (SchemaMismatchError, None)
        if type_id != self.registration.type_id:
            return None, (TypeMismatchError, None)
        if body_length == 0 or body_length != len(data) - _ENVELOPE.size:
            return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)
        root_header = data[_ENVELOPE.size]
        if root_header & 0xFC or root_header & 0x02 or not root_header & 0x01:
            return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)
        if not self._semaphore.acquire(timeout=self.limits.acquire_timeout_seconds):
            return None, (ForyConcurrencyError, None)

        try:
            try:
                buffer = _pyfory.Buffer(memoryview(data)[_ENVELOPE.size :])
                result = self._pool.deserialize(buffer)
                fully_consumed = buffer.get_reader_index() == body_length
            except _FATAL_EXCEPTIONS:
                raise
            except _ForyRegistrationFailureError:
                return None, (ForyRegistrationError, None)
            except Exception:
                return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)
            if not fully_consumed:
                return None, (MalformedPayloadError, SerdeErrorCode.INVALID_FORY)
            if type(result) is not self.registration.python_type:
                return None, (TypeMismatchError, None)
            return result, None
        finally:
            self._semaphore.release()
