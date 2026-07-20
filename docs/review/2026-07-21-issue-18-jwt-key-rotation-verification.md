# Issue #18 JWT 키 회전 exact-head 검증

Date: 2026-07-21 KST

Branch: `feat/issue-18-jwt-key-rotation`

Reviewed implementation SHA: `c50810d53bf43a23ffdc25093ca535168108c30b`

## 판정

승인된 issue #18 local implementation 범위는 **PASS**다. 모든 최종 명령은 위
implementation SHA의 clean worktree에서 실행했고, 실행 전후 HEAD가 같음을 확인했다.
최종 보안 리뷰는 `P0=0, P1=0, P2=0`이다.

## Exact-head command evidence

| Gate | 명령/범위 | 결과 |
|---|---|---|
| Locked environment | `uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked` | Pass; 63 resolved, 59 checked |
| Focused JWT | `uv run pytest packages/bluetape-jwt -q` | `301 passed` |
| Wheel/docs/release inventory | JWT wheel isolation, bilingual README, benchmark packaging nodes | `11 passed` |
| Full workspace | `uv run pytest` | `3579 passed`, 1 third-party LocalStack deprecation warning |
| Lint | `uv run ruff check .` | All checks passed |
| Format | `uv run ruff format --check .` | 247 files already formatted |
| Build | `uv build --all-packages` | 22 workspace distributions built as sdist and wheel |
| Workflow syntax | `actionlint` | Pass |
| Patch hygiene | `git diff --check` | Pass |
| Immutable head | `git rev-parse HEAD` plus empty porcelain status | `c50810d...`; clean before and after gates |

## Wheel and metadata isolation

The focused/meta wheel suite clean-built `bluetape-core`, `bluetape-cache`,
`bluetape-jwt`, and `bluetape`, then verified:

- `bluetape-jwt==0.1.0` depends exactly on `bluetape-cache==0.1.0` and
  `joserfc>=1.7.4,<2`.
- The default `bluetape` wheel remains core-only; the `jwt` extra adds exactly
  `bluetape-jwt==0.1.0`.
- The JWT wheel contains no root `bluetape/__init__.py`.
- A clean Python 3.13.14 target imports `bluetape.jwt` from the installed temp
  directory and exposes the reviewed public export order.

The manual smoke rebuilt cache/JWT wheels into task-scoped temporary directories,
installed those exact artifacts plus `joserfc==1.7.4`, ran Python with existing
site-packages disabled, checked metadata/origin/exports/root-initializer absence,
and moved both temporary directories to Trash after success.

## Security and stability evidence

- 아홉 JWS algorithm mismatch matrix와 duplicate header/payload, malformed shape,
  reserved/custom header policy가 통과했다.
- Repository와 verified-result cache concurrency suites를 각각 20회 반복해 총
  40 suite runs가 통과했다.
- Revocation race는 old epoch 결과가 current cache에 게시되지 않음을 검증한다.
- Cache hit은 temporal claims를 다시 검증하고 TTL을 token 잔여 수명 이하로 제한한다.
- 8 MiB oversized input은 전체 UTF-8 copy 전에 거절되며 temporary allocation이
  bounded임을 회귀 테스트가 고정한다.
- Public security values와 error/log records의 canary가 repr, message, structured
  fields에 나타나지 않는다.

## Acceptance and exclusion map

| Approved decision | Evidence | Status |
|---|---|---|
| HS/RS/PS 256/384/512 only | enum, key factories, provider registry, mismatch tests | Pass |
| Strict immutable claims/profile | constructor/fingerprint/temporal and hostile JSON tests | Pass |
| Atomic local key rotation | snapshot/epoch/lifecycle/concurrency tests | Pass |
| Optional bounded verified cache | digest/profile/epoch key, finite TTL/capacity, race/error tests | Pass |
| Explicit issuance policy | `IssuanceProfileProvider`, caller-owned `iat`/`exp`, `default_ttl=None` tests | Pass |
| Decorator-ready sync contract | `TokenProvider.issue/verify` composition tests and bilingual examples | Pass |
| Focused/meta packaging | isolated wheel and metadata tests | Pass |
| Async/JWE/compression excluded | follow-up references #88/#89/#90; no implementation surface | Pass |

## TDD and correction trace

Tasks 1-9 preserved their named RED/GREEN microcycles. Final full replay found two stale
workspace-contract gaps: an initial README assertion and a second fail-closed publishable
inventory. Both were repaired without weakening their assertions. The first exact security
review then found two P1 and two P2 issues; all four were reproduced by failing regressions,
fixed in `c50810d`, and independently re-reviewed to zero findings.

The reusable Type A lesson is recorded in
`docs/lessons/2026-07-21-issue-18-jwt-key-rotation.md`.

## Evidence-only delta contract

This artifact and the sibling security review are the only files allowed after
`reviewed_implementation_sha`. The evidence commit must not change production code, tests,
README/WIP, package metadata, design, plan, or lesson. A separate final verifier must confirm
that delta and the unchanged implementation SHA mapping.

PR creation, GitHub CI, merge, release, publication, and cleanup are outside this local stop
boundary and require their applicable fresh authorization gates.
