# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning once the first tag is published.

## [Unreleased]

### Added

- Add the opt-in `bluetape-testcontainers` Redis 8 wrapper with explicit
  lifecycle, bounded readiness, dynamic connection details, and serial Docker
  CI coverage.
- `bluetape-async` source workspace package with bounded structured-concurrency
  helpers under `bluetape.asyncio`, including ordered `map_bounded` execution.
- `bluetape-collections` source workspace package with eager stdlib-only
  helpers under `bluetape.collections` for chunking, grouping, distinct,
  partitioning, and exception-transparent map/filter transforms.
- `bluetape-codec` source workspace package with strict canonical URL-safe
  Base64 and hexadecimal helpers under `bluetape.codec`.
- `bluetape-compression` source workspace package with bounded gzip,
  zlib-wrapped, and raw-DEFLATE helpers under `bluetape.compression`.
- Structural `Compressor` Protocol and immutable gzip, zlib, raw-DEFLATE, LZ4
  frame, raw Snappy, and Zstandard frame implementations with stable algorithm
  IDs, bounded decompression, strict malformed/trailing-data failures, and
  provider-isolated `lz4`, `snappy`, `zstd`, and `native` extras. The meta
  distribution forwards the native choices without adding them to its default,
  `dev`, or `all` dependency sets.
- `bluetape-cache` source workspace package with stdlib-only bounded
  synchronous and async local TTL loading caches under `bluetape.cache`,
  including LRU capacity, same-key load coalescing, mutation supersession,
  in-flight load limits, and immutable statistics. This is a new API and needs
  no migration alias or compatibility shim; Redis remains tracked by issue #51.
- `bluetape-serde` source workspace package with immutable payload contracts,
  caller-owned trust policy, fixed typed errors, and strict bounded JSON v1
  serialization under `bluetape.serde`, including bounded `bytearray` output
  assembly, source-free public error tracebacks, and a deterministic 640-digit
  JSON integer limit.
- Optional `bluetape-serde[fory]` and `bluetape[fory]` CPython 3.13 extras with
  a trusted-internal Apache Fory adapter, fixed schema/type envelopes, bounded
  runtime concurrency, stable errors, and Python/Go/Rust/Kotlin conformance
  artifacts. Fory remains excluded from the base, `serde`, `dev`, and `all`
  extras.

## [v0.1.0] - 2026-07-10

### Added

- Initial Python-native workspace documentation for the thin `bluetape` meta
  distribution and the focused `bluetape-core`, `bluetape-logging`, and
  `bluetape-testing` packages.
- Korean root README parity for the initial package boundary, install policy,
  usage examples, package documentation links, and roadmap.
- README bitmap hero and workspace overview diagram assets.
- `WIP.md` for release planning, milestone scope, and the ecosystem backlog.
- Release and package-layout documentation under `docs/`.
- Research index documentation for future research-first package decisions.
- Milestone `0.2.0` planning visibility through ecosystem issues #7 through
  #34, including research gates #10, #14, #16, #21, #23, #31, and #34.
- `require_instance` in `bluetape-core`.
- `log_context(override=False)` duplicate-key protection and case-insensitive
  logging redaction defaults.
- `eventually` and `eventually_async` handling for falsy non-`None` values plus
  positive timeout/interval validation.
- PyPI preflight documentation for the intended `v0.1.0` distributions.

### Changed

- Root README now points detailed planning and release state to `WIP.md`,
  `CHANGELOG.md`, and `docs/release.md` instead of carrying the full planning
  model inline.
- GitHub Actions CI now builds all workspace distributions with
  `uv build --all-packages`.
