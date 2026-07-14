# Issue #12 Resilience Performance and Stability Evidence

Date: 2026-07-14 KST
Implementation evidence HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`

## Performance gate

Performance threshold: **N/A**. The approved issue adds stdlib policy semantics and
did not approve a throughput or latency target. Inventing a hot-loop benchmark would
create a release gate unrelated to the contract. The implementation instead keeps
locks around state mutation only, invokes caller code outside locks, and uses no
worker, scheduler, detached task, exporter, or polling loop.

## Five-run stability matrix

The full resilience package is the bounded matrix. It includes both execution
families and covers circuit generations/probes, bulkhead saturation/waiter
cancellation, timeout cancellation, observer reentrancy/privacy, and pipeline order.

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

Result: 720 test executions, zero failure, zero timeout, and zero hang. A post-move
package rerun at `b21a7c6` passed all 144 tests in 0.16s.

## Cleanup and boundedness proof

- Sync threads use bounded events and `join(1)`; every test asserts the thread is no
  longer alive.
- Async cancellation tests cover waiter cancellation, admitted cancellation,
  cancellation while completion waits for reconciliation, and repeated cancellation
  during cleanup.
- Cleanup remains in the caller task. No `asyncio.shield()`, `create_task()`, thread,
  timer, or executor exists in production code.
- Circuit and bulkhead tests assert final zero probe/permit/waiter ownership. Timeout
  tests compare task sets and find no package-owned task.
- Lazy circuit recovery performs no work until the next caller admission.

Stability gate: **PASS**.
