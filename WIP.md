# WIP

Snapshot: 2026-07-20 KST
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
- `bluetape-audit`: stdlib-only immutable audit values, explicit bounded
  validation, and preservation helpers, implemented for issue #25 while PyPI
  publication remains on HOLD.
- `bluetape-cache`: stdlib-only bounded synchronous and async local TTL loading
  caches, implemented and merged for issue #50 while PyPI publication remains
  on HOLD.
- `bluetape-cache-redis`: byte-only sync and async Redis providers, strict
  bounded result envelopes, and bounded Redis lease load coordination,
  implemented for issues #54 and #55 while PyPI publication remains on HOLD.
- `bluetape-codec`: strict URL-safe Base64 and hexadecimal helpers, added for
  issue #9 in the source workspace while PyPI publication remains on HOLD.
- `bluetape-compression`: bounded gzip, zlib, and raw-DEFLATE helpers from #9,
  plus structural compressor contracts and opt-in LZ4, Snappy, and Zstandard
  providers from #59. PyPI publication remains on HOLD.
- `bluetape-logging`: stdlib `logging` plus `contextvars` helpers.
- `bluetape-id`: stdlib-only UUIDv4/v7 and random/monotonic ULID values,
  implemented for issue #13 with process-local generator state.
- `bluetape-jwt`: issue #18 is implemented and locally verified on
  `feat/issue-18-jwt-key-rotation` with nine JWS algorithms, immutable claims
  and profiles, active/retired/revoked key lifecycle, strict verification,
  issuance-policy composition, and an optional bounded verified-result cache.
  PR review and merge remain pending; PyPI publication stays on HOLD.
- `bluetape-measure`: immutable runtime dimension-checked linear measurements,
  implemented for issue #13 with caller-owned custom unit definitions.
- `bluetape-money`: exact Decimal money and current ISO 4217 currencies,
  implemented for issue #13 with caller-owned exchange rates and historical
  policy. PyPI publication remains on HOLD.
- `bluetape-observability`: API-only OpenTelemetry adapters for resilience and
  Redis observer events, implemented for issue #24 with caller-owned SDK and
  exporter lifecycle. PyPI publication remains on HOLD.
- `bluetape-resilience`: stdlib-only sync/async retry, circuit breaker,
  bulkhead, cooperative async timeout, and immutable fluent pipelines,
  implemented for issue #12 on `feat/issue-12-resilience-policies` while PyPI
  publication remains on HOLD.
- `bluetape-serde`: stdlib-only immutable payload contracts and strict,
  bounded JSON v1 serialization, implemented for issue #45 in the source
  workspace, plus a CPython 3.13-only Apache Fory extra implemented for issue
  #46. PyPI publication remains on HOLD.
- `bluetape-testing`: pytest helpers that start internal-first before promising
  a broad public API.
- `bluetape-testcontainers`: ecosystem-owned Redis 8, PostgreSQL 18, and
  caller-selected LocalStack test server wrappers with dynamic loopback ports,
  immutable details, explicit fixture ownership, and serial Docker verification.

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
  follow-ups #45/#46, local cache #50, and the completed Redis provider and
  coordination umbrella #51; issues #35 through #44 and #47 through #49 are
  not implied by these explicit ranges.
- Research-first issues #10 and #23 have source-backed decisions. Issues #14,
  #16, #21, #31, and #34 must produce package boundary decisions before
  implementation starts.
- Issue #45 strict JSON serde is available in the source workspace. Issue #46
  Apache Fory is implemented and locally verified with Python, Go, Rust, and
  Kotlin fixtures; PR review and merge remain pending. PyPI publication stays
  on HOLD.
- Issue #11 cache/Redis delivery is complete through #50 local caches and the
  #51 Redis coordination umbrella, including merged #57 Testcontainers, #54
  Redis provider, and #55 sync/async load coordination. Issue #56 near-cache
  invalidation remains an independent upstream-blocked track and is not a
  requirement for #11 or #51 completion. Issue #59 provides the compressor
  contracts used to reduce Redis payloads.
- Issue #12 resilience policies are implemented and locally verified on the
  feature branch. PR review and merge remain pending; PyPI publication stays
  on HOLD.
- Issue #13 ID, measure, and money value packages are implemented and locally
  verified on the feature branch. The default meta install remains core-only;
  PyPI publication stays on HOLD.

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
| `0.3.0` | First implementation wave after research gates | Candidate scope depends on pending decisions from #21, #31, and #34; #10, #14, #16, and #23 now constrain their implementation follow-ups. |

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
- #11 - Cache and Redis coordination umbrella. Required delivery is complete
  through #50 local caches and #51 Redis provider/load coordination; the
  explicitly independent #56 near-cache invalidation track remains
  upstream-blocked and does not block #11 closeout.
- #50 - Bounded sync and async local TTL loading caches. Implemented and merged
  as `bluetape-cache`.
- #51 - Redis cache coordination and provider boundary. Required delivery is
  complete through #57, #54, and #55. The explicitly independent #56 near-cache
  invalidation track remains upstream-blocked and does not block #51 closeout.
- #54 - Redis byte provider and bounded result-envelope substrate. Implemented
  and merged into `develop`; it is the provider substrate used by #55.
- #55 - Bounded sync/async Redis load coordination. Implemented and merged on
  the #54 provider substrate with expiring leases and atomic token-checked
  publish.
- #56 - RESP3 client-tracking near-cache invalidation. Independent from #51
  coordination delivery and currently blocked by upstream client behavior.
- #57 - Ecosystem-owned Testcontainers Redis 8 wrapper. Implemented, merged,
  and consumed by the #54 and #55 integration suites.
- #12 - Stdlib-only resilience policies. Implemented on
  `feat/issue-12-resilience-policies` with separate sync/async retry, circuit
  breaker, bulkhead, cooperative async timeout, typed events, immutable state
  snapshots, and fluent decorator pipelines. PR review and merge are pending;
  PyPI publication remains on HOLD.
- #13 - ID, measure, and money value packages. Implemented as three independent
  stdlib-only focused distributions with `id`, `measure`, `money`, and `values`
  extras. KSUID requires a compatibility consumer; Snowflake needs machine/epoch
  ownership; compound/affine measure, locale money, and provider FX remain
  separate trigger-gated issues.
- #14 - SQL, repository, and audit outbox strategy research. Decision recorded
  in `docs/research/2026-07-16-issue-14-sql-repository-audit-outbox-strategy.md`:
  use caller-owned SQLAlchemy Core sync/async connections, keep audit
  storage-neutral, and isolate PostgreSQL transactional outbox behavior in a
  separate adapter with caller-driven relay execution.
- #15 - Testcontainers fixture packages.
- #16 - AWS, graph, text, and image adapter boundary research. Decision
  recorded in `docs/research/2026-07-18-issue-16-adapter-boundaries.md`: keep
  only narrow optional wrappers for bounded synchronous AWS batch behavior,
  literal text matching/masking, and Pillow single-image transforms; prove
  graph values and Neo4j interoperability through examples before publishing a
  common graph API.
- Issue #17 - Leader election and distributed lock contracts. Implemented as the
  stdlib-only `bluetape-leader` contract package and explicit
  `bluetape-leader-redis` single-primary adapter with sync/async bounded
  lifecycle, fencing, isolated wheels, Redis 8 contention evidence, and
  bilingual operating guidance; completed by rebase-merging PR #83 into
  `develop`.
- #18 - JWT and key-rotation helpers. Implemented and locally verified on
  `feat/issue-18-jwt-key-rotation`; PR review and merge remain pending. Async
  providers, JWE encryption, and versioned compression remain separate issues
  #88, #89, and #90.
- #19 - Rules, workflow, batch, and work-report primitives.
- #20 - Probabilistic data structure helpers.
- #21 - Python web API adapter boundary research.
- #22 - Web API helpers and ASGI/FastAPI adapters.
- #23 - Observability and OpenTelemetry boundary research. Decision recorded in
  `docs/research/2026-07-15-issue-23-observability-opentelemetry-boundaries.md`:
  keep domain packages OTel-free and use a separate API-only opt-in bridge if
  #24 proceeds; applications retain SDK/exporter/global lifecycle ownership.
- #24 - Observability hooks and telemetry helpers. Implemented as the focused
  `bluetape-observability` API-only bridge; PR review and merge are pending.
- #25 - Storage-neutral audit event and conformance package. Implemented as the
  stdlib-only `bluetape-audit` opt-in with immutable values, explicit bounded
  validation, safe errors, and deterministic preservation helpers; SQL outbox
  and broker publishers remain separate adapter issues.
- #77 - PostgreSQL transactional audit outbox adapter with caller-transaction
  enqueue, bounded lease-backed claim/mark operations, at-least-once delivery,
  and caller-driven relay execution.
- #26 - Narrow synchronous Boto3 proof for SQS partial results, DynamoDB
  unprocessed-item handling, and at most one proven S3 envelope/checksum helper.
- #27 - Bounded graph value and interoperability proof using direct NetworkX
  and official Neo4j driver integration; multi-backend conformance is deferred.
- #28 - Optional bounded literal multi-pattern matching and union-based masking;
  tokenizer and language-detection abstractions are excluded.
- #29 - Optional bounded Pillow single-image transform proof; pyvips, barcode,
  OCR, CAPTCHA, storage, and framework integration are excluded.
- #30 - SQLAlchemy Core toolkit and explicit application repository helpers;
  outbox storage and encrypted-column work are excluded from the first slice.
- #31 - Geo, spatial, and statistics utility scope research.
- #32 - Provider conformance and benchmark suites.
- #33 - `bluetape-go` to `bluetape-py` ecosystem parity matrix.
- #34 - Config, secrets, and credential provider boundary research.

## Research Gates

Research notes belong under `docs/research/` and should be linked from
`docs/research/README.md` before broad implementation work starts.

- #10 must decide serialization baseline, optional adapters, trust profiles,
  typed errors, and cross-language compatibility expectations.
- #14 decided SQL/transaction ownership, repository helper scope, audit model
  boundaries, PostgreSQL outbox isolation, and the required Testcontainers
  fixture boundary. Implementation remains split across #15, narrowed #25,
  narrowed #30, and focused PostgreSQL outbox issue #77.
- #16 decided that AWS, literal text matching, and Pillow transforms may proceed
  only as narrow optional light wrappers; graph begins with direct dependency
  examples and earns shared values only after two independent consumers.
  Existing issues #26-#29 own the narrowed proofs; broad service/backend/model/
  codec surfaces remain 0.2.x non-goals.
- #21 must decide ASGI/FastAPI/framework adapter boundaries, request-context
  ownership, RFC 7807 scope, and middleware conformance expectations.
- #23 decided stdlib logging hook boundaries, a separate API-only optional
  bridge direction, application-owned SDK/exporter lifecycle, and explicit
  Python 3.13 context propagation expectations.
- #31 must decide whether geo, spatial, statistics, histogram, and geocoding
  helpers are owned APIs, light wrappers, examples only, or rejected.
- #34 must decide configuration, secrets, credentials, KMS/envelope encryption,
  and cloud provider boundary policy before security-sensitive helpers are
  implemented.
