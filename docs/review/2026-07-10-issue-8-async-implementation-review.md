# Issue #8 Async 구현 검토

## 결과

P0: 0

P1: 0

판정: PASS

## 검증 근거

| 검사 | 결과 |
|---|---|
| Targeted async contract tests | `31 passed` |
| Full workspace tests | `84 passed` |
| Ruff check 및 format check | PASS |
| `uv lock --check` 및 `uv sync --all-packages` | PASS |
| `uv build --all-packages` | 여섯 distribution을 모두 sdist와 wheel로 빌드 |
| Meta wheel metadata | 기본 dependency는 `bluetape-core`뿐이며 `bluetape-async`는 `asyncio` extra로 제한 |
| Fresh async wheel smoke | 격리된 Python 3.14 환경에 설치하고 `map_bounded` import |
| Documented examples | ordered bounded-map 및 self-contained sync example 실행 |
| Diff hygiene | `git diff develop...HEAD --check` PASS |

## 독립 검토

| Lane | 결과 | 근거 |
|---|---|---|
| Code review | APPROVE | self-contained sync comparison example 추가 후 남은 P0/P1 없음 |
| Architecture review | CLEAR | call-scoped ownership, cancellation baseline, terminal admission state, thin default install, Issue #8 sync/async/bounded comparison이 모두 일치 |

구현은 하나의 public `map_bounded` API를 유지하고 worker를 `1..1024`로 제한하며
input order를 보존한다. Call-scoped `asyncio.TaskGroup`을 사용한다. Direct
mapper 또는 iterator cancellation은 cleanup 후 fail closed하고, external
cancellation 및 concurrent race는 native asyncio outcome을 유지한다.
