# bluetape-benchmark

[English](README.md) | 한국어

bluetape-py 저장소 전용 비공개 benchmark 계약입니다. 표준 라이브러리 전용
`bluetape.benchmark` 패키지는 저장소 benchmark가 사용하는 불변 timing,
report, atomic JSON, paired comparison helper를 제공합니다.

작업공간에서는 이 distribution을 build하고 test하지만 publish하거나 `bluetape`
meta distribution으로 설치해서는 안 됩니다. `Private :: Do Not Upload`는 PyPI
방어 계층일 뿐이고, fail-closed release allowlist가 주 경계입니다. 의도적으로 공개
설치 extra를 제공하지 않습니다.

Redis coordination command와 operator 규칙은
[`bluetape-cache-redis` README](../bluetape-cache-redis/README.ko.md)에 있습니다.
검증된 외부 산출물 두 개는 다음과 같이 비교합니다.

```bash
uv run python -m bluetape.benchmark.compare \
  --baseline /external/baseline.json \
  --candidate /external/candidate.json \
  --output /external/comparison.json
```

비교 작업은 delta를 계산하기 전에 runner, pair, policy, registry, lock,
dependency, platform, mode, scenario identity를 확인합니다. 결과는 benchmark
근거이며 production capacity 또는 SLO 보장이 아닙니다.
