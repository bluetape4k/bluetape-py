# Issue #12 Resilience 성능 및 안정성 근거

날짜: 2026-07-14 KST
Implementation evidence HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`

## Performance gate

Performance threshold: **N/A**. 승인된 issue는 stdlib policy semantics를 추가할 뿐
throughput이나 latency target을 승인하지 않았다. Hot-loop benchmark를 임의로
만들면 contract와 무관한 release gate가 되므로 만들지 않았다. 대신 state
mutation에만 lock을 사용하고 caller code는 lock 밖에서 호출하며 worker,
scheduler, detached task, exporter, polling loop를 사용하지 않는다.

## 5회 안정성 matrix

Full resilience package가 bounded matrix다. 두 execution family를 포함하고
circuit generation/probe, bulkhead saturation/waiter cancellation, timeout
cancellation, observer reentrancy/privacy, pipeline order를 다룬다.

```text
for run in 1 2 3 4 5; do
  uv run pytest packages/bluetape-resilience -q
done

run 1: 144 passed in 0.10s
run 2: 144 passed in 0.11s
run 3: 144 passed in 0.11s
run 4: 144 passed in 0.11s
run 5: 144 passed in 0.11s
```

결과: 720 test execution, failure 0, timeout 0, hang 0. Package 이동 후
`b21a7c6`에서 144 test를 0.16s에 통과했다.

## Cleanup 및 boundedness 증명

- Sync thread는 bounded event와 `join(1)`을 사용하며 모든 test가 thread가
  더 이상 살아 있지 않음을 assertion한다.
- Async cancellation test는 waiter cancellation, admitted cancellation,
  reconciliation을 기다리는 completion 중 cancellation, cleanup 중 repeated
  cancellation을 다룬다.
- Cleanup은 caller task에서 수행한다. Production code에 `asyncio.shield()`,
  `create_task()`, thread, timer, executor가 없다.
- Circuit 및 bulkhead test는 최종 probe/permit/waiter ownership이 0임을
  assertion한다. Timeout test는 task set을 비교하고 package-owned task가 없음을 확인한다.
- Lazy circuit recovery는 다음 caller admission까지 work를 수행하지 않는다.

Stability gate: **PASS**.
