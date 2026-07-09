# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning once the first tag is published.

## [Unreleased]

No unreleased changes yet.

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
