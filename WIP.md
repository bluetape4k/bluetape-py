# WIP

Snapshot: 2026-07-12 KST
Scope: `v0.1.0` released foundation and `0.2.0` ecosystem package planning.

## Current Target

`0.2.0` - ecosystem package planning and first expansion tracks.

`v0.1.0` has been released as the initial Python-native bluetape workspace:
<https://github.com/bluetape4k/bluetape-py/releases/tag/v0.1.0>.

The released foundation keeps the default install thin and establishes the
focused distribution model:

- `bluetape`: thin meta distribution, default dependency is `bluetape-core`.
- `bluetape-core`: stdlib-only validation and foundation helpers.
- `bluetape-collections`: stdlib-only eager iterable/list/dict helpers, added
  for issue #7 in the source workspace while PyPI publication remains on HOLD.
- `bluetape-async`: stdlib-only bounded `asyncio` helpers, added for issue #8
  in the source workspace while PyPI publication remains on HOLD.
- `bluetape-cache`: stdlib-only bounded synchronous and async local TTL loading
  caches, implemented for issue #50 on `feat/issue-50-local-cache` while PyPI
  publication remains on HOLD. Redis coordination is tracked separately in #51.
- `bluetape-cache-redis`: byte-only sync and async Redis providers plus strict,
  bounded binary/JSON result envelopes, implemented for issue #54 on
  `feat/issue-54-redis-provider` while PyPI publication remains on HOLD. Redis
  load coordination remains issue #55 work.
- `bluetape-codec`: strict URL-safe Base64 and hexadecimal helpers, added for
  issue #9 in the source workspace while PyPI publication remains on HOLD.
- `bluetape-compression`: bounded gzip, zlib, and raw-DEFLATE helpers from #9,
  plus structural compressor contracts and opt-in LZ4, Snappy, and Zstandard
  providers from #59. PyPI publication remains on HOLD.
- `bluetape-logging`: stdlib `logging` plus `contextvars` helpers.
- `bluetape-serde`: stdlib-only immutable payload contracts and strict,
  bounded JSON v1 serialization, implemented for issue #45 in the source
  workspace, plus a CPython 3.13-only Apache Fory extra implemented for issue
  #46. PyPI publication remains on HOLD.
- `bluetape-testing`: pytest helpers that start internal-first before promising
  a broad public API.
- `bluetape-testcontainers`: ecosystem-owned Redis 8 test server wrapper,
  implemented for issue #57 with explicit lifecycle, bounded readiness,
  dynamic connection details, and serial Docker verification. PyPI publication
  remains on HOLD.

## Current State

- The repository is a Python 3.13+ `uv` workspace with focused packages under
  `packages/`.
- `develop` is the integration branch and `main` is release-only.
- `v0.1.0` is tagged on `main` and has a GitHub Release.
- Issues #1 through #5 are closed for the `0.1.0` foundation, documentation,
  and release preflight scope.
- PyPI publication remains on HOLD until project ownership and trusted
  publishing are confirmed outside this repository.
- Milestone `0.2.0` tracks ecosystem issues #7 through #34, serialization
  follow-ups #45/#46, local cache #50, and Redis follow-up #51; issues #35
  through #44 and #47 through #49 are not implied by these explicit ranges.
- Research-first issues #10, #14, #16, #21, #23, #31, and #34 must produce
  source-backed package boundary decisions before implementation starts.
- Issue #45 strict JSON serde is available in the source workspace. Issue #46
  Apache Fory is implemented and locally verified with Python, Go, Rust, and
  Kotlin fixtures; PR review and merge remain pending. PyPI publication stays
  on HOLD.
- Issue #11 remains the cache/Redis umbrella. Issue #50 local caches are
  complete. Issue #57 is the implemented Testcontainers prerequisite, and #59
  provides the compressor contracts needed to reduce Redis payloads. #54 Redis
  provider integration is implemented on its source branch; #55 Redis load
  coordination remains pending.

## `0.1.0` Scope

1. Establish workspace layout, package naming, Python version policy, and uv
   build/test/release commands.
2. Add `bluetape-core` for small shared validation and foundation helpers.
3. Add `bluetape-logging` for low-friction context-aware logging helpers
   without package-owned global logger state.
4. Add `bluetape-testing` for internal-first pytest helpers, eventual waits,
   and future async/test-fixture boundaries.
5. Publish root and package README documentation in English and Korean where a
   localized README exists.
6. Prepare the first PyPI release path after local and GitHub CI validation are
   stable.

## `v0.1.0` Release Record

Branch policy:

- Use `develop` as the default integration branch.
- Use `main` as the stable release branch.
- Promote the verified `develop` tree to `main` before creating a stable tag and
  publishing to PyPI.

- GitHub Release: <https://github.com/bluetape4k/bluetape-py/releases/tag/v0.1.0>
- Tag target: `596e4898c915b55339521814ae7303953b50f4d2`
- Foundation issues #1 through #5: closed.
- Milestone `0.1.0`: closed.
- PyPI publication: HOLD until ownership and trusted publishing are confirmed.

## `0.2.0` Working Rules

1. Use research-first issues for broad dependency or package-boundary choices.
2. Keep the default `bluetape` install thin.
3. Add new package families only after their import path, distribution name,
   dependency boundary, tests, and README shape are explicit.
4. Keep active package README files aligned with root README locale files when
   user-facing behavior changes.
5. Record completed user-facing changes in `CHANGELOG.md`.

## Milestone Roadmap

| Milestone | Theme | Notes |
|---|---|---|
| `v0.1.0` | Released core helpers, logging, testing, docs, and release preflight | Kept the default install thin and the APIs Python-native. |
| `0.2.0` | Ecosystem package planning and first expansion tracks | Track issues #7-#34 plus serialization follow-ups #45/#46; research-first work gates broad adapters. |
| `0.3.0` | First implementation wave after research gates | Candidate scope depends on accepted research decisions from #10, #14, #16, #21, #23, #31, and #34. |

## Task Queue

### `v0.1.0` - Released Foundation

Historical release scope; all items are closed.

- #1 - Expand `bluetape-core` foundation helpers. Implemented in PR #35.
- #2 - Stabilize `bluetape-logging` context helpers. Implemented in PR #35.
- #3 - Grow internal-first `bluetape-testing` helpers. Implemented in PR #35.
- #4 - Publish initial package boundary and install guide. Closed by PR #6.
- #5 - Prepare `v0.1.0` release and PyPI publishing path. Implemented in PR #35.

### `0.2.0` - Ecosystem Backlog

- #7 - Collections helper package. Implemented by `bluetape-collections` in
  the source workspace; PyPI publication remains part of the release hold.
- #8 - Async and bounded concurrency primitives. Implemented by
  `bluetape-async` in the source workspace; PyPI publication remains on HOLD.
- #9 - Codec and compression packages. Implemented by `bluetape-codec` and
  `bluetape-compression` in the source workspace; PyPI publication remains on
  HOLD.
- #59 - Composable compressor contracts and optional native providers.
  Implemented with a structural Python Protocol, immutable gzip/zlib/DEFLATE/
  LZ4/Snappy/Zstandard implementations, bounded decompression, and isolated
  extras. This is the compression prerequisite consumed by #54.
- #10 - Serialization strategy research. Decision recorded in
  `docs/research/2026-07-10-issue-10-serialization-strategy.md`; follow-ups
  are #45 (contracts/strict JSON) and #46 (Apache Fory adapter).
- #45 - Immutable payload contracts and strict bounded JSON v1 serde.
  Implemented and locally verified in the source workspace; PR review and
  merge are pending.
- #46 - Apache Fory adapter and Python/Go/Rust/Kotlin conformance. Separate
  trusted-internal CPython 3.13 extra implemented and locally verified in the
  source workspace; PyPI publication remains on HOLD.
- #11 - Cache and Redis coordination umbrella.
- #50 - Bounded sync and async local TTL loading caches. Implemented by
  `bluetape-cache` on `feat/issue-50-local-cache`; PR review and merge are
  pending.
- #51 - Redis cache coordination and provider boundary. Pending after the
  local cache contract; split into #54, #55, #56, and prerequisite #57.
- #54 - Redis byte provider and bounded result-envelope substrate. Implemented
  and locally verified on `feat/issue-54-redis-provider`; PR review and merge
  remain pending.
- #55 - Redis load coordination. Pending on the #54 provider substrate.
- #57 - Ecosystem-owned Testcontainers Redis 8 wrapper. Implemented and
  verified on `feat/issue-57-testcontainers-redis`; consumed by #54 integration
  tests and retained for #55.
- #12 - Resilience policies.
- #13 - ID, measure, and money value packages.
- #14 - SQL, repository, and audit outbox strategy research.
- #15 - Testcontainers fixture packages.
- #16 - AWS, graph, text, and image adapter boundary research.
- #17 - Leader election and distributed lock contracts.
- #18 - JWT and key-rotation helpers.
- #19 - Rules, workflow, batch, and work-report primitives.
- #20 - Probabilistic data structure helpers.
- #21 - Python web API adapter boundary research.
- #22 - Web API helpers and ASGI/FastAPI adapters.
- #23 - Observability and OpenTelemetry boundary research.
- #24 - Observability hooks and telemetry helpers.
- #25 - Audit event and outbox publisher packages.
- #26 - AWS integration provider packages.
- #27 - Graph package and backend conformance suites.
- #28 - Text search, tokenizer, and masking packages.
- #29 - Image and media helper packages.
- #30 - SQL toolkit, repository, and outbox helpers.
- #31 - Geo, spatial, and statistics utility scope research.
- #32 - Provider conformance and benchmark suites.
- #33 - `bluetape-go` to `bluetape-py` ecosystem parity matrix.
- #34 - Config, secrets, and credential provider boundary research.

## Research Gates

Research notes belong under `docs/research/` and should be linked from
`docs/research/README.md` before broad implementation work starts.

- #10 must decide serialization baseline, optional adapters, trust profiles,
  typed errors, and cross-language compatibility expectations.
- #14 must decide SQL/transaction ownership, repository helper scope, audit
  model boundaries, outbox storage strategy, and required Testcontainers
  fixtures.
- #16 must decide whether AWS, graph, text, and image work should be first-class
  packages, optional adapters, or examples only.
- #21 must decide ASGI/FastAPI/framework adapter boundaries, request-context
  ownership, RFC 7807 scope, and middleware conformance expectations.
- #23 must decide stdlib logging hook boundaries, OpenTelemetry extras, and
  async context propagation expectations.
- #31 must decide whether geo, spatial, statistics, histogram, and geocoding
  helpers are owned APIs, light wrappers, examples only, or rejected.
- #34 must decide configuration, secrets, credentials, KMS/envelope encryption,
  and cloud provider boundary policy before security-sensitive helpers are
  implemented.
