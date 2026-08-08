# Issue #24 Observability 성능 및 ownership 근거

날짜: 2026-07-15 KST
Implementation evidence head: `40676c3d963a641ac230f40731fe065b9c2401ee`

## 환경

- macOS 26.5.2, Darwin 25.5.0, arm64
- Apple M5
- CPython 3.13.14
- uv 0.11.28
- Adapter마다 run당 100,000 measured call, mode마다 3 run

아래 값은 같은 mode의 empty callback baseline을 뺀 incremental adapter cost다.
단위는 nanosecond다.

## API-only mode

| Adapter | Run 1 median/p95 | Run 2 median/p95 | Run 3 median/p95 | Budget 판정 |
|---|---:|---:|---:|---|
| Policy | 708 / 750 | 709 / 750 | 708 / 750 | 3/3 pass |
| Redis | 501 / 542 | 500 / 542 | 500 / 542 | 3/3 pass |
| Redis coordination | 624 / 666 | 583 / 666 | 625 / 749 | 3/3 pass |

Budget는 median 최대 25,000 ns, p95 최대 75,000 ns다. SDK provider, reader,
exporter, recording span을 생성하지 않았고 exported event count는 0이다. 전체
run 전후 thread identifier를 대조했다.

## Caller-owned local SDK mode

| Adapter | Run 1 median/p95 | Run 2 median/p95 | Run 3 median/p95 | Budget 판정 |
|---|---:|---:|---:|---|
| Policy | 4,541 / 4,708 | 4,583 / 12,333 | 4,583 / 4,833 | 3/3 pass |
| Redis | 5,624 / 5,875 | 5,666 / 5,874 | 5,583 / 5,751 | 3/3 pass |
| Redis coordination | 6,749 / 6,958 | 6,708 / 6,958 | 6,750 / 6,958 | 3/3 pass |

Budget는 median 최대 150,000 ns, p95 최대 500,000 ns다. 각 fixture는 exported
span event를 128개로 제한하고 application-owned shutdown order `tracer`, 다음
`meter`를 기록했다. 전체 run 전후 thread identifier를 대조했다.

## Deterministic ownership gate

`test_performance_contract.py`가 evidence 작성 전에 9개 test를 통과했다.

- 각 event object는 call 후 collectible 상태
- 각 adapter는 100,000 call 동안 최대 64 KiB를 보존
- Production source가 thread, task, queue, executor, lock, weak/global registry,
  close/flush/shutdown lifecycle를 소유하지 않음
- Complete API와 SDK benchmark subprocess가 resource leak 없이 반복됨

Network exporter latency와 external collector behavior는 application-owned이므로
package-level performance gate에서는 N/A다.
