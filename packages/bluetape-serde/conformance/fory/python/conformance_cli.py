#!/usr/bin/env python3
"""Generate and verify the canonical Apache Fory conformance record."""

from __future__ import annotations

import argparse
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pyfory
from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyRegistration,
)


@dataclass(slots=True)
class ConformanceRecord:
    record_id: pyfory.Int64 = pyfory.field(id=1)  # noqa: RUF009 - Fory field metadata
    name: str = pyfory.field(id=2)
    active: bool = pyfory.field(id=3)
    scores: list[pyfory.Int32] = pyfory.field(id=4)  # noqa: RUF009 - Fory field metadata


EXPECTED = ConformanceRecord(
    record_id=pyfory.Int64(7),
    name="blue",
    active=True,
    scores=[pyfory.Int32(1), pyfory.Int32(2), pyfory.Int32(3)],
)


def metadata() -> PayloadMetadata:
    return PayloadMetadata(
        format=FORY_FORMAT,
        version=FORY_VERSION,
        content_type=FORY_CONTENT_TYPE,
        trust_profile=TrustProfile.TRUSTED_INTERNAL,
    )


def adapter() -> ForyAdapter[ConformanceRecord]:
    return ForyAdapter(
        registration=ForyRegistration(
            python_type=ConformanceRecord,
            schema_id=1112819289,
            schema_version=1,
            type_id=1001,
            logical_name="io.bluetape.serde.ConformanceRecord",
        )
    )


def generate(output: Path) -> None:
    payload = adapter().serialize(EXPECTED, metadata=metadata())
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(payload.data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def verify(source: Path) -> None:
    received = SerializedPayload(metadata=metadata(), data=source.read_bytes())
    result = adapter().deserialize(received, expected_metadata=metadata())
    if result != EXPECTED:
        raise ValueError("Fory conformance value does not match the canonical record")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "generate":
        generate(arguments.path)
    else:
        verify(arguments.path)


if __name__ == "__main__":
    main()
