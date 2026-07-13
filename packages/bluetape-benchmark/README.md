# bluetape-benchmark

English | [한국어](README.ko.md)

Private, source-workspace-only benchmark contracts for bluetape-py. The
stdlib-only `bluetape.benchmark` package provides immutable timing, report,
atomic JSON, and paired-comparison helpers used by repository benchmarks.

The workspace builds and tests this distribution, but it must never be
published or installed through the `bluetape` meta distribution. `Private ::
Do Not Upload` is PyPI defense in depth; the release allowlist is the primary
fail-closed boundary. There is intentionally no public installation extra.

Redis coordination commands and operator rules live in the
[`bluetape-cache-redis` README](../bluetape-cache-redis/README.md). Compare two
validated external artifacts with:

```bash
uv run python -m bluetape.benchmark.compare \
  --baseline /external/baseline.json \
  --candidate /external/candidate.json \
  --output /external/comparison.json
```

Comparison checks runner, pair, policy, registry, lock, dependency, platform,
mode, and scenario identity before calculating deltas. Results are benchmark
evidence, never production-capacity or SLO claims.
