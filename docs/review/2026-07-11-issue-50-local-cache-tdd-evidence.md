# Issue #50 Local Cache TDD 근거

날짜: 2026-07-11
기준선: `bluetape-cache` 전 workspace test 737개
현재 결과: cache test 120개를 포함한 workspace test 857개

## Behavior-first 순서

| Slice | RED 근거 | GREEN 근거 |
|---|---|---|
| Package 및 constructor | Distribution, export, validation, exact signature contract가 없어 실패 | Constructor/export/typing/package contract 통과. huge finite TTL conversion과 non-callable clock 포함 |
| TTL/LRU state | Public state method와 `_CacheState`가 없어 state case 25개 실패 | Exact-tick expiry, rollback clamp, MRU movement, live-LRU eviction, heap compaction, counter, invalidation, loop ownership 통과 |
| Sync loading | `get_or_load`와 flight ownership 전이라 loading case 12개 실패 | Same-key coalescing, different-key progress, recursion, failure identity, supersession, hard limit, exact gauge 통과 |
| Async loading | Async flight ownership과 generation gate 전이라 loading case 10개 실패 | Coalescing, inherited recursion rejection, mutation generation, task admission rollback, publication failure cleanup 통과 |
| Async cancellation | Shielded caller ownership 전이라 cancellation/abandonment/saturation case 실패 | Surviving waiter, last-waiter abandonment, cancellation-resistant loader, self-cancellation, saturation recovery, task cleanup 통과 |
| Repeated cancellation | 두 번째 cancel이 waiter cleanup을 중단하고 phantom active flight를 남김 | Lock-contention probe가 여러 cancellation delivery를 보존하면서 waiter release를 정확히 한 번 완료 |
| Cleanup task admission | Rejecting loop task factory가 release coroutine을 누수시키고 caller cancellation을 덮어씀 | 제출되지 않은 coroutine을 close하고 inline fallback cleanup이 수렴하며 caller cancellation/value semantics 유지 |
| Packaging | `cache` extra가 없어 `KeyError` 발생 | Metadata test, all-package build, default-install isolation, explicit-extra import 통과 |

## Deterministic lifecycle 증명

- Sync 및 async test file이 benchmark 전에 10회 연속 통과했다. 반복마다
  `64 passed`이며 finite thread/task/event boundary를 사용하고 pending-task
  warning은 없었다.
- 최종 cache suite는 finite thread/task/event boundary에서 `120 tests`를
  통과했고 pending-task warning이 없었다.
- 최종 workspace run은 명시적인 all-package/all-extra sync 후
  `uv run --no-sync pytest -q`를 사용했으며 결과는 `857 passed in 8.41s`였다.
- Apache Fory extra를 prune하고 collection에서 실패한 뒤 기본
  `uv run pytest -q` 경로는 근거로 채택하지 않았다. 모든 package extra를
  다시 설치하고 `--no-sync`를 사용해 environment mismatch를 숨기지 않고
  현재 workspace를 증명했다.

## Fresh validation ladder

```text
uv run --no-sync ruff format --check .     38 files already formatted
uv run --no-sync ruff check .              All checks passed
uv run pytest packages/bluetape-cache/tests -q   120 passed
uv sync --all-packages --all-extras --locked
uv run --no-sync pytest -q                 857 passed
uv lock --check                            resolved 20 packages
uv build --all-packages                    10 distributions built
isolated no-index base/cache-extra smoke   PASS
actionlint                                 PASS
git diff --check                           PASS
```

새 collected-test delta는 정확히 `857 - 737 = 120`이며 cache package suite와
일치한다.
