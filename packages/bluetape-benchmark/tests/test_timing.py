import pytest
from bluetape.benchmark import nearest_rank, summarize_timings


def test_nearest_rank_sorts_a_copy() -> None:
    samples = [50, 10, 40, 20, 30]
    assert nearest_rank(samples, 50) == 30
    assert nearest_rank(samples, 95) == 50
    assert samples == [50, 10, 40, 20, 30]


def test_summary_uses_honest_tail_gates() -> None:
    smoke = summarize_timings([1, 2, 3, 4, 5], operations_per_sample=8)
    assert smoke.p95_ns is None and smoke.p99_ns is None
    full = summarize_timings(range(1, 21), operations_per_sample=1)
    assert full.p95_ns == 19 and full.p99_ns is None
    assert summarize_timings(range(1, 101)).p99_ns == 99


def test_throughput_uses_completed_public_operations() -> None:
    result = summarize_timings([1_000_000_000, 1_000_000_000], operations_per_sample=8)
    assert result.throughput_ops_per_sec == 8.0


@pytest.mark.parametrize("samples", [[], [True], [-1], [1.5]])
def test_samples_require_non_empty_non_negative_exact_ints(samples: list[object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        summarize_timings(samples)  # type: ignore[arg-type]


@pytest.mark.parametrize("percentile", [0, 101, float("nan"), True])
def test_nearest_rank_rejects_invalid_percentile(percentile: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        nearest_rank([1], percentile)  # type: ignore[arg-type]


def test_input_sequence_is_copied_to_immutable_tuple() -> None:
    samples = [1, 2, 3]
    result = summarize_timings(samples)
    samples[0] = 100
    assert result.raw_samples_ns == (1, 2, 3)
