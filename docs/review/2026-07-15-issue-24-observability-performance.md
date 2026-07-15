# Issue #24 Observability Performance and Ownership Evidence

Date: 2026-07-15 KST
Implementation evidence head: `40676c3d963a641ac230f40731fe065b9c2401ee`

## Environment

- macOS 26.5.2, Darwin 25.5.0, arm64
- Apple M5
- CPython 3.13.14
- uv 0.11.28
- 100,000 measured calls per adapter per run, 3 runs per mode

All values below are incremental adapter cost after subtracting the same-mode empty callback
baseline. Values are nanoseconds.

## API-only mode

| Adapter | Run 1 median/p95 | Run 2 median/p95 | Run 3 median/p95 | Budget verdict |
|---|---:|---:|---:|---|
| Policy | 708 / 750 | 709 / 750 | 708 / 750 | 3/3 pass |
| Redis | 501 / 542 | 500 / 542 | 500 / 542 | 3/3 pass |
| Redis coordination | 624 / 666 | 583 / 666 | 625 / 749 | 3/3 pass |

Budget: median at most 25,000 ns and p95 at most 75,000 ns. No SDK provider, reader, exporter,
or recording span was constructed; exported event count was zero. Thread identifiers reconciled
before and after the complete run.

## Caller-owned local SDK mode

| Adapter | Run 1 median/p95 | Run 2 median/p95 | Run 3 median/p95 | Budget verdict |
|---|---:|---:|---:|---|
| Policy | 4,541 / 4,708 | 4,583 / 12,333 | 4,583 / 4,833 | 3/3 pass |
| Redis | 5,624 / 5,875 | 5,666 / 5,874 | 5,583 / 5,751 | 3/3 pass |
| Redis coordination | 6,749 / 6,958 | 6,708 / 6,958 | 6,750 / 6,958 | 3/3 pass |

Budget: median at most 150,000 ns and p95 at most 500,000 ns. Each fixture capped exported span
events at 128 and recorded application-owned shutdown order `tracer`, then `meter`. Thread
identifiers reconciled before and after the complete run.

## Deterministic ownership gates

`test_performance_contract.py` passed 9 tests before evidence writing:

- every event object became collectible after its call;
- each independently measured adapter retained at most 64 KiB over 100,000 calls;
- production sources owned no thread, task, queue, executor, lock, weak/global registry, or
  close/flush/shutdown lifecycle;
- complete API and SDK benchmark subprocesses repeated without resource leakage.

Network exporter latency and external collector behavior are application-owned and therefore N/A
for this package-level performance gate.
