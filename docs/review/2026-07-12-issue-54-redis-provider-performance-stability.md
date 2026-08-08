# Issue #54 Redis Provider 성능 및 안정성

날짜: 2026-07-12 KST

## Non-Gating Envelope Snapshot

명령:

```bash
uv run python packages/bluetape-cache-redis/benchmarks/envelope_benchmark.py \
  | tee /tmp/issue-54-envelope-benchmark.json
```

환경: Python 3.13.14, macOS 26.5.1, arm64. Benchmark는 짧은 warmup 후 encode와
decode를 측정한다. Absolute latency, throughput, production-capacity, machine
간 ranking을 주장하지 않는다.

| Case | Format | Encoded bytes | Samples | Median ns | p95 ns |
|---|---|---:|---:|---:|---:|
| empty | binary-v1 | 94 | 5,000 | 4,500 | 4,791 |
| empty | json-v1 | 195 | 5,000 | 5,959 | 6,583 |
| small, 1 KiB | binary-v1 | 1,118 | 1,000 | 4,833 | 5,083 |
| small, 1 KiB | json-v1 | 1,563 | 1,000 | 8,667 | 9,167 |
| near-limit, 8 MiB | binary-v1 | 8,388,702 | 10 | 603,562 | 616,041 |
| near-limit, 8 MiB | json-v1 | 11,185,007 | 10 | 23,473,166 | 25,121,584 |

Byte-heavy case에서 Binary가 JSON보다 작다. 두 near-limit encoded result는
설정된 16 MiB outer bound보다 작다. Raw output은
`/tmp/issue-54-envelope-benchmark.json`에 저장했으며 이 temporary path는
evidence location이지 tracked release artifact가 아니다.

## 안정성 근거

Sync close subset은 10회 연속 실행했고 run마다 6 passed, 총 60개였다. Async
close/cancel/loop subset은 10회 연속 실행했고 run마다 9 passed, 총 90개였다.
Hang, pending-task warning, leaked-task warning, flaky failure는 0개였다.

Redis integration은 ecosystem `RedisServer`를 통해 serial로 실행했고 8개가
통과했다. TTL expiry, `SET NX PX`, fixed Lua compare-delete, borrowed
sync/async lifecycle, binary/JSON round trip, unsafe fallback 없는 script ACL
denial, redacted connection failure를 포함한다.

## Scan 결과

| Priority | File:Line | Lens | 발견 | 처리 |
|---|---|---|---|---|
| none | `_formats.py:125`, `_formats.py:269` | performance | Binary와 JSON이 큰 output을 구성하기 전에 outer bound를 예측하고 적용한다. | PASS |
| none | `_async_provider.py:230-302` | performance | Async command가 redis-py를 직접 await하며 async path에 executor나 blocking sync client가 없다. | PASS |
| none | `_provider.py:326`, `_async_provider.py:304` | stability | Owned close 전에 admission을 drain하며 lifecycle lock이 Redis command I/O를 감싸지 않는다. | PASS |
| none | `_async_provider.py:328-386` | stability | 정확히 하나의 transient cleanup task를 shield하고 join한 뒤 clear한다. | PASS |
