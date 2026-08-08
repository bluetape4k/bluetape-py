# Issue #12 Resilience Policies Verifier

날짜: 2026-07-14 KST
Implementation evidence HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`
Issue: <https://github.com/bluetape4k/bluetape-py/issues/12>

## Acceptance criteria

| # | Verification | 결과 |
|---|---|---|
| 1 | Focused wheel에 `Requires-Dist`가 없고 `bluetape.resilience`를 import하며 base meta environment가 `bluetape`와 `bluetape-core`만 포함 | PASS |
| 2 | Retry test가 return preservation, attempt bound, deterministic backoff, non-retryable propagation, exhaustion cause, partial callable, cancellation을 다룸 | PASS |
| 3 | Timeout test가 owned expiry, direct `TimeoutError`, external cancellation을 구분하고 task set을 비교하며 sync `Timeout` export 없음 | PASS |
| 4 | Circuit test가 모든 state, lazy recovery, bounded probe, sync/async stale generation, predicate, snapshot, clock, cancellation, cross-loop rejection을 다룸 | PASS |
| 5 | Bulkhead test가 sync/async capacity, immediate/bounded wait, waiter, rejection, observer/BaseException path, exact permit release를 다룸 | PASS |
| 6 | Async retry/circuit/bulkhead/timeout test가 `CancelledError`를 전파하며 one/repeated reconciliation cancellation 후 owned state 0, cancellation terminal 없음 | PASS |
| 7 | Pipeline test가 immutability, last-added-outermost, decorator/direct call, metadata/bound method, partial callable, sync/async/generator misuse rejection을 증명 | PASS |
| 8 | Frozen/slotted event/snapshot contract, exact enum/order, reentrant observer, safe error, recursive secret-sentinel check 통과 | PASS |
| 9 | 실행한 English/Korean README example이 두 pipeline family와 대비되는 retry/breaker order를 보여 줌 | PASS |
| 10 | Root/meta/package locale docs, AGENTS, package layout, WIP, changelog, workspace/meta metadata, lock, classifier, build, isolated install이 일치 | PASS |

## 정확한 검증

```text
uv sync --all-packages --extra fory --extra native --python 3.13.14 --locked
  resolved 39; checked 36
uv run pytest
  1659 passed in 13.07s
uv run ruff check .
  all checks passed
uv run ruff format --check .
  111 files already formatted
uv build --all-packages
  14 sdists and 14 wheels built, including bluetape_resilience-0.1.0
actionlint
  exit 0
git diff --check
  exit 0
```

## Isolated wheel smoke

- Base `bluetape`: `bluetape`, `bluetape-core`만 설치했고
  `find_spec("bluetape.resilience") is None`.
- Direct `bluetape-resilience`: 하나의 installed distribution, exact ordered
  24-name `__all__`, `Timeout` 없음, runtime dependency 없음.
- `bluetape[resilience]`: `bluetape`, `bluetape-core`,
  `bluetape-resilience`만 설치했고 두 pipeline family를 import.
- 모든 install은 fresh temporary environment, `--no-index`, freshly built
  local artifact를 사용해 source-tree나 registry leakage를 막았다.

## Workflow 경계

Implementation 및 pre-PR verification은 이 경계에서 완료했다. PR creation,
merge, tag, publication, release, workflow dispatch, milestone mutation, issue
closure는 권한이 없다.

Verifier 결과: **PASS — P0=0 P1=0**.
