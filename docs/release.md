# Release Guide

Detailed release procedure: [`docs/release/release-guide.md`](release/release-guide.md).
PyPI package preflight: [`docs/release/pypi-preflight.md`](release/pypi-preflight.md).

## Branches

- `develop` is the default integration branch.
- `main` is release-only and should be updated from `develop` through a pull
  request.

## Versioning

Use semantic versioning once the first tag is published.

- `v0.1.0`: first foundation release.
- `v0.x.0`: new package families or meaningful feature groups.
- `v0.x.y`: bug fixes, docs, compatibility adjustments, and small non-breaking
  improvements.

Before `v1.0.0`, public APIs may still change. Document breaking changes in
`CHANGELOG.md`.

## Release Tag Criteria

- `README.md` and `README.ko.md` are current for the release scope.
- Package READMEs are current for every published distribution.
- `CHANGELOG.md` has an `Unreleased` section that can become the target
  `vX.Y.Z` section.
- `WIP.md` records the target release-preparation state.
- The matching milestone is closed with zero open issues.
- `uv sync --all-packages` passes locally.
- `uv build --all-packages` passes locally.
- `uv run pytest` passes locally.
- `uv run ruff check .` passes locally.
- `uv run ruff format --check .` passes locally.
- GitHub Actions CI passes on `develop`, including the `uv build --all-packages`
  distribution build step.
- PyPI credentials or trusted publishing are explicitly confirmed before any
  publish action.

## Changelog Rule

Keep `CHANGELOG.md` in Keep a Changelog style:

- `Added`
- `Changed`
- `Deprecated`
- `Removed`
- `Fixed`
- `Security`

Move entries from `Unreleased` into the version section when tagging.

## Tag Procedure

1. Ensure `develop` is green.
2. Update `CHANGELOG.md`.
3. Update `WIP.md`.
4. Open and merge a `develop` to `main` release PR.
5. Tag on `main`.
6. Push the tag.
7. Create GitHub release notes from `CHANGELOG.md`.
8. Publish PyPI artifacts only from the verified release commit.
