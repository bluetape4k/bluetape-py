# Issue #12 Resilience Policies Verifier

Date: 2026-07-14 KST
Implementation evidence HEAD: `b21a7c6f922e8c29654b7979d512ac28066c0773`
Issue: <https://github.com/bluetape4k/bluetape-py/issues/12>

## Acceptance criteria

| # | Verification | Result |
| --- | --- | --- |
| 1 | Focused wheel has no `Requires-Dist`; `bluetape.resilience` imports; base meta environment contains only `bluetape` and `bluetape-core`. | PASS |
| 2 | Retry tests cover return preservation, attempt bounds, deterministic backoff, non-retryable propagation, exhaustion cause, partial callables, and cancellation. | PASS |
| 3 | Timeout tests distinguish owned expiry, direct `TimeoutError`, and external cancellation and compare task sets; no sync `Timeout` export exists. | PASS |
| 4 | Circuit tests cover all states, lazy recovery, bounded probes, sync/async stale generations, predicates, snapshots, clocks, cancellation, and cross-loop rejection. | PASS |
| 5 | Bulkhead tests cover sync/async capacity, immediate/bounded wait, waiters, rejection, observer/BaseException paths, and exact permit release. | PASS |
| 6 | Async retry/circuit/bulkhead/timeout tests propagate `CancelledError`; one/repeated reconciliation cancellation leaves zero owned state and emits no cancellation terminal. | PASS |
| 7 | Pipeline tests prove immutability, last-added-outermost, decorator/direct calls, metadata/bound methods, partial callables, and sync/async/generator misuse rejection. | PASS |
| 8 | Frozen/slotted event and snapshot contracts, exact enums/order, reentrant observers, safe errors, and recursive secret-sentinel checks pass. | PASS |
| 9 | Executed English/Korean README examples show both pipeline families and contrasting retry/breaker order. | PASS |
| 10 | Root/meta/package locale docs, AGENTS, package layout, WIP, changelog, workspace/meta metadata, lock, classifier, builds, and isolated installs agree. | PASS |

## Exact validation

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

- Base `bluetape`: installed distributions exactly `bluetape`, `bluetape-core`;
  `find_spec("bluetape.resilience") is None`.
- Direct `bluetape-resilience`: one installed distribution, exact ordered 24-name
  `__all__`, no `Timeout`, and no runtime dependencies.
- `bluetape[resilience]`: installed distributions exactly `bluetape`,
  `bluetape-core`, and `bluetape-resilience`; both pipeline families import.
- All installs used fresh temporary environments, `--no-index`, and freshly built
  local artifacts, preventing source-tree or registry leakage.

## Workflow boundary

Implementation and pre-PR verification are complete at this boundary. PR creation,
merge, tag, publication, release, workflow dispatch, milestone mutation, and issue
closure remain unauthorized.

Verifier result: **PASS — P0=0 P1=0**.
