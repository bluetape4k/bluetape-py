"""Non-gating binary/JSON result-envelope size and latency evidence."""

import json
import math
import platform
import statistics
import sys
from time import perf_counter_ns

from bluetape.cache.redis import (
    BinaryEnvelopeFormat,
    EnvelopeFormat,
    JsonEnvelopeFormat,
    ResultEnvelope,
)
from bluetape.serde import PayloadMetadata, TrustProfile

CASES = {
    "empty": b"",
    "small": b"x" * 1024,
    "near_limit": b"x" * (8 * 1024 * 1024),
}
SAMPLES = {"empty": 5_000, "small": 1_000, "near_limit": 10}


def measure(
    formatter: EnvelopeFormat,
    envelope: ResultEnvelope,
    samples: int,
) -> dict[str, object]:
    """Measure one format without asserting environment-specific latency."""
    encoded = formatter.encode(envelope)
    warmup = min(samples, 10)
    for _ in range(warmup):
        assert formatter.decode(formatter.encode(envelope)) == envelope

    timings: list[int] = []
    for _ in range(samples):
        started = perf_counter_ns()
        assert formatter.decode(formatter.encode(envelope)) == envelope
        timings.append(perf_counter_ns() - started)

    return {
        "format": formatter.format_id,
        "encoded_bytes": len(encoded),
        "median_ns": int(statistics.median(timings)),
        "p95_ns": sorted(timings)[max(0, math.ceil(samples * 0.95) - 1)],
        "samples": samples,
    }


def main() -> None:
    """Print machine-readable benchmark evidence for all cases and formats."""
    metadata = PayloadMetadata(
        format="bytes",
        version=1,
        content_type="application/octet-stream",
        trust_profile=TrustProfile.UNTRUSTED,
    )
    results: dict[str, list[dict[str, object]]] = {}
    for case, payload in CASES.items():
        envelope = ResultEnvelope(
            version=1,
            owner_token="benchmark-owner",
            metadata=metadata,
            compression_algorithm="identity",
            payload=payload,
        )
        results[case] = [
            measure(formatter, envelope, SAMPLES[case])
            for formatter in (BinaryEnvelopeFormat(), JsonEnvelopeFormat())
        ]

    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
