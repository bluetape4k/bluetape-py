"""Deterministic benchmark timing summaries."""

import math
from collections.abc import Sequence

from ._contracts import TimingSummary


def _validated_samples(samples: Sequence[int]) -> tuple[int, ...]:
    values = tuple(samples)
    if not values:
        raise ValueError("samples must not be empty")
    if any(type(value) is not int for value in values):
        raise TypeError("samples must contain exact ints")
    if any(value < 0 for value in values):
        raise ValueError("samples must be non-negative")
    return values


def nearest_rank(samples: Sequence[int], percentile: float) -> int:
    """Return the documented nearest-rank percentile from a copied sequence."""
    values = _validated_samples(samples)
    if type(percentile) not in (int, float) or isinstance(percentile, bool):
        raise TypeError("percentile must be an exact number")
    if not math.isfinite(percentile) or not 0 < percentile <= 100:
        raise ValueError("percentile must be in (0, 100]")
    ordered = sorted(values)
    return ordered[math.ceil(float(percentile) / 100 * len(ordered)) - 1]


def summarize_timings(
    samples_ns: Sequence[int], *, operations_per_sample: int = 1
) -> TimingSummary:
    """Summarize raw nanosecond samples without unsupported tail claims."""
    values = _validated_samples(samples_ns)
    if type(operations_per_sample) is not int:
        raise TypeError("operations_per_sample must be an exact int")
    if operations_per_sample <= 0:
        raise ValueError("operations_per_sample must be positive")
    total = sum(values)
    if total <= 0:
        raise ValueError("total sample duration must be positive")
    return TimingSummary(
        operations_per_sample=operations_per_sample,
        raw_samples_ns=values,
        min_ns=min(values),
        median_ns=nearest_rank(values, 50),
        p95_ns=nearest_rank(values, 95) if len(values) >= 20 else None,
        p99_ns=nearest_rank(values, 99) if len(values) >= 100 else None,
        max_ns=max(values),
        throughput_ops_per_sec=float(
            operations_per_sample * len(values) * 1_000_000_000 / total
        ),
    )


__all__ = ["nearest_rank", "summarize_timings"]
