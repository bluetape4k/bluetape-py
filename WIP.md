# WIP

Snapshot: 2026-07-10 KST
Scope: `0.1.0` Python-native foundation and `0.2.0` ecosystem package planning.

## Current Target Release

`v0.1.0` - initial Python-native bluetape workspace.

The first release keeps the default install thin and establishes the focused
distribution model:

- `bluetape`: thin meta distribution, default dependency is `bluetape-core`.
- `bluetape-core`: stdlib-only validation and foundation helpers.
- `bluetape-logging`: stdlib `logging` plus `contextvars` helpers.
- `bluetape-testing`: pytest helpers that start internal-first before promising
  a broad public API.

## Current State

- The repository is a Python 3.13+ `uv` workspace with focused packages under
  `packages/`.
- `develop` is the integration branch and `main` is release-only.
- Issues #1 through #5 are closed for the `0.1.0` foundation, documentation,
  and release preflight scope.
- PR #35 merged the remaining `0.1.0` implementation scope into `develop`.
- PyPI publication remains on HOLD until project ownership and trusted
  publishing are confirmed outside this repository.
- Milestone `0.2.0` tracks ecosystem expansion issues #7 through #34 after the
  foundation is released.
- Research-first issues #10, #14, #16, #21, #23, #31, and #34 must produce
  source-backed package boundary decisions before implementation starts.

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

## Release Checklist

Branch policy:

- Use `develop` as the default integration branch.
- Use `main` as the stable release branch.
- Promote the verified `develop` tree to `main` before creating a stable tag and
  publishing to PyPI.

Before `v0.1.0`:

1. Close issues #1 through #5. Done.
2. Confirm `README.md`, `README.ko.md`, package READMEs, `WIP.md`, and
   `CHANGELOG.md` describe the same release scope.
3. Run `uv sync --all-packages`.
4. Run `uv build --all-packages`.
5. Run `uv run pytest`.
6. Run `uv run ruff check .`.
7. Run `uv run ruff format --check .`.
8. Verify GitHub Actions CI on `develop`.
9. Close milestone `0.1.0`.
10. Promote `develop` to `main` through a release PR.
11. Tag `v0.1.0` on `main`.
12. Create GitHub Release `v0.1.0`.
13. Publish distributions only after PyPI ownership and trusted publishing are
    confirmed.

## Milestone Roadmap

| Milestone | Theme | Notes |
|---|---|---|
| `0.1.0` | Core helpers, logging, testing, docs, and release preflight | Keep the default install thin and the APIs Python-native. |
| `0.2.0` | Ecosystem package planning and first expansion tracks | Track issues #7-#34; research-first work gates broad adapters. |
| `0.3.0` | First implementation wave after research gates | Candidate scope depends on accepted research decisions from #10, #14, #16, #21, #23, #31, and #34. |

## Task Queue

### `0.1.0` - Foundation

- #1 - Expand `bluetape-core` foundation helpers. Implemented in PR #35.
- #2 - Stabilize `bluetape-logging` context helpers. Implemented in PR #35.
- #3 - Grow internal-first `bluetape-testing` helpers. Implemented in PR #35.
- #4 - Publish initial package boundary and install guide. Closed by PR #6.
- #5 - Prepare `v0.1.0` release and PyPI publishing path. Implemented in PR #35.

### `0.2.0` - Ecosystem Backlog

- #7 - Collections helper package.
- #8 - Async and bounded concurrency primitives.
- #9 - Codec and compression packages.
- #10 - Serialization strategy research.
- #11 - Cache and Redis coordination packages.
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
