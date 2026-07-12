# Issue #59 Compressor Contracts 7-Tier Pre-PR Review

- Date: 2026-07-12
- Diff base: `origin/develop@e30ef9644c6a405b77063ca1026825474bd90d44`
- Reviewed head before evidence commit: `e8b4100d9d6ae484aace928d236dec8759526fac`
- Module slices: base contract, native providers, packaging/CI, public docs
- Execution: main-session fallback for each isolated lens because the available collaboration
  interface cannot supply the OMX-required typed `agent_type`; no untyped reviewer was dispatched.
- Final verdict: `PASS` (`P0=0`, `P1=0`)

## Iteration 1 findings

| Priority | File:Line | Lens | Finding | Disposition |
|---|---|---|---|---|
| P1 | `packages/bluetape-compression/README.md:77` and `README.ko.md:78` | User/Caller | Docs claimed a missing native provider raises `CompressionError`, while source and approved spec require `ModuleNotFoundError`. | Fixed both locales; focused provider-loader tests `2 passed`; caller lens rerun clean. |
| P2 | `packages/bluetape-compression/pyproject.toml:4` | Integration/User | Distribution description still characterized the whole package as stdlib helpers after opt-in native contracts were added. | Changed to `Bounded byte compression contracts for bluetape-py.`; packaging build rerun in the final verification. |

## Post-PR CI finding

| Priority | File:Line | Lens | Finding | Disposition |
|---|---|---|---|---|
| P1 | `.github/workflows/ci.yml:96` | Stability/Ops/Integration | The focused package sync installed runtime and native dependencies but not `pytest`; a previously populated local workspace environment masked the clean-runner failure. | Added a non-published package-local `test` dependency group, synced it explicitly, added a regression assertion, and reproduced the exact native job in a temporary clean environment with `98 passed` and strict config. |

## Final perspective results

| Tier | Scope and evidence | P0 | P1 | P2 | P3 | Verdict |
|---|---|---:|---:|---:|---:|---|
| 1. Performance | Bounded stdlib/LZ4 loops, Snappy/Zstd preflight, large and window-budget tests | 0 | 0 | 0 | 0 | PASS |
| 2. Stability | Terminal-state checks, provider failure handling, resource/state ownership, dedicated CI | 0 | 0 | 0 | 0 | PASS |
| 3. Security | Decompression-bomb bounds, algorithm confusion rejection, payload-free errors/logging, exact pins | 0 | 0 | 0 | 0 | PASS |
| 4. Operator/Ops | Install diagnostics, CI isolation, rollback boundary, no secret/payload logs or lifecycle | 0 | 0 | 0 | 0 | PASS |
| 5. Developer/API | Structural Protocol, frozen classes, stable IDs, exact exports, validation, legacy function compatibility | 0 | 0 | 0 | 0 | PASS |
| 6. User/Caller | Extras, examples, bounds/errors, locale parity, Kotlin semantic parity without wire claim | 0 | 0 | 0 | 0 | PASS after P1 repair |
| 7. Integration | Spec/plan traceability, lock/metadata, CI hazard, README/WIP/CHANGELOG, evidence integrity | 0 | 0 | 0 | 0 | PASS after P2 repair |

## Lens notes

### Performance

No unbounded output buffer, input refeeding, retry, polling, provider-context reuse, or hidden
auto-detection was found. Input conversion creates a caller-owned immutable `bytes` snapshot,
which is intentional for stable provider boundaries. No benchmark ranking is claimed.

### Stability

All implementations are stateless between calls. Native providers have explicit availability at
construction and deterministic failure classification. Tests cover invalid terminal states,
fatal-failure propagation, repeatability, and input reference release.

### Security

The public API never chooses an algorithm from payload bytes. LZ4 uses an output budget; Snappy and
Zstd reject oversized declarations before decode. Error text is fixed and no logging dependency or
payload logging exists. Encryption, trust policy, and Redis envelope negotiation remain out of
scope and are not implied by docs.

### Operator/Ops

Focused missing-extra guidance identifies the exact install action. Base CI proves providers are
absent before opt-in sync, while a separate native job proves the explicit matrix. There are no
health, shutdown, metric, or runbook requirements because the package owns no process resource or
service lifecycle.

### Developer/API

Existing function signatures and exports remain; object adapters delegate to them. The Protocol is
not runtime-checkable, third-party implementations need no inheritance, configurations reject bool
and out-of-range integers, and native exports remain small and ordered. Public docstrings and
README names match source.

### User/Caller

The package and meta README locale pairs show exact extras, constructors, IDs, bounds, errors, and
`serialize -> compress -> store` composition. The repaired missing-provider type now matches source.
PyPI availability and cross-language wire compatibility are explicitly not claimed.

### Main-session integration

The diff is limited to #59 code, tests, dependency metadata/lock, CI, approved design/plan, review
evidence, README locale pairs, package policy, WIP, and CHANGELOG. No module registration, database,
container, migration, coverage threshold, or release action is introduced. #54 remains blocked on
merge and rebase.

## Convergence

- Baseline pre-PR: `P0=0`, `P1=1`, `P2=1`, `P3=0`.
- Post-PR CI: one additional P1 exposed a missing package-local test-tool declaration.
- Repairs: fixed the missing-provider exception docs, package metadata description, and clean CI
  test dependency boundary.
- Affected reruns: provider-loader tests, caller claim scan, locale parity, package build, full
  compressor/full non-Docker suites, Ruff, actionlint, lock check, and diff check.
- Final local rerun: `P0=0`, `P1=0`, `P2=0`, `P3=0`; live CI rerun is tracked by PR #60.

Step 6-R verdict: `PASS`.
