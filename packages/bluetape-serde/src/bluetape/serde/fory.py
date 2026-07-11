"""Apache Fory contracts for authenticated internal serialization."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_missing_provider = False
try:
    import pyfory as _pyfory  # noqa: F401 - provider use begins with ForyAdapter
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
    "ForyLimits",
    "ForyRegistration",
]

_LOGICAL_NAME = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", re.ASCII)


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
