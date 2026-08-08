# Issue #65 Redis Coordination benchmark 근거

이 note는 `docs/review/artifacts/issue-65-redis-coordination-benchmark.json`의 bounded smoke evidence를 해석합니다. Production capacity나 SLO 주장이 아니라 repeatability와 correctness artifact입니다.

## 재현

검증된 artifact는 clean source tree에서 다음 명령으로 생성했습니다.

```bash
uv run python packages/bluetape-cache-redis/benchmarks/coordination_benchmark.py \
  --profile smoke --mode both --seed 20260712 --role snapshot \
  --output docs/review/artifacts/issue-65-redis-coordination-benchmark.json
```

고정된 smoke registry는 12개 result, 60개 measured sample, 10,400개 measured operation, 12개 warmup을 생성했습니다. Safety ceiling은 full registry에서 상속하며 최대 24개 result, 64 caller, 8 coordinator, 8 key, 15,728,640-byte value, aggregate payload 32 MiB입니다.

## 환경

- Source Git SHA: `b989f8619a10af22f2c4725dcc2e697663709c6b`
- Python: Darwin arm64의 CPython 3.13.14
- Redis client: 8.0.1; ephemeral Redis server: 8.8.0
- Redis image digest: `sha256:2838d5524559494f6f1cd66e97e76b200d64a633a8614200620755ed395daf32`
- Policy: `redis-coordination-benchmark-v1`
- Policy digest: `7e7c46760f9c9d04c82f63972e8f7e0ab304710e725b759cb0606d1955bae8ad`
- Registry digest: `9e114b562ced345d7c7aab9295ab074173475dc192d25784811f38c37dfd3285`
- Lock digest: `a825207f86a8935492348035f65b942db501fe4fb6d3609797c3e678cdcbbd36`

## 관찰된 smoke median

| Mode | Scenario | Median ns | Correctness loaders | Correctness Redis commands |
| --- | --- | ---: | ---: | ---: |
| sync | local-only | 7,704,417 | 4 | 0 |
| sync | local-hit | 453,792 | 0 | 0 |
| sync | single-coordinator | 9,126,125 | 1 | 2 |
| sync | multi-coordinator | 17,385,333 | 1 | 17 |
| sync | completed-reuse | 1,466,250 | 0 | 10 |
| sync | unrelated-keys | 9,828,083 | 4 | 8 |
| async | local-only | 6,537,333 | 4 | 0 |
| async | local-hit | 1,006,209 | 0 | 0 |
| async | single-coordinator | 8,527,542 | 1 | 2 |
| async | multi-coordinator | 10,110,834 | 1 | 17 |
| async | completed-reuse | 1,256,000 | 0 | 10 |
| async | unrelated-keys | 6,882,959 | 4 | 8 |

각 smoke case는 측정 sample이 5개뿐입니다. 따라서 schema에는 p95와 p99가 모두 `null`로 기록됩니다. p95에는 최소 20개 sample, p99에는 최소 100개 sample이 필요합니다. 위 median은 이 capture run만 설명하며 machine 간 regression threshold로 사용해서는 안 됩니다.

## Correctness 해석

모든 correctness invariant가 통과했습니다. `correctness_*` field는 warmup과 measurement 전에 실행한 별도의 instrumented phase에서 생성합니다. Command recorder, loader counter, envelope-size probe는 timed path에 설치하지 않습니다. Single 및 multi coordinator case는 각각 하나의 loader로 수렴했고, unrelated key는 독립적인 loader 4개를 사용했으며, completed-result reuse는 waiter loader를 호출하지 않았고 local-only/local-hit는 Redis command를 실행하지 않았습니다. Active/completed result byte는 correctness snapshot만 설명합니다. `process_high_water_bytes`는 measurement 후 sampling하며 platform-local이므로 서로 다른 OS나 process model 사이에서 비교할 수 없습니다.

이 artifact는 하나의 ephemeral local Redis 환경에서 bounded execution, report integrity, 의도한 coordination semantics를 입증합니다. Deployment sizing, tail-latency guarantee, throughput capacity, production topology behavior, SLO를 입증하지는 않습니다.
