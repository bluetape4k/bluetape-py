# Release Guide

This guide defines the Python package release flow for `bluetape-py`.

## Model

`bluetape-py` is a Python 3.13+ `uv` workspace with multiple focused PyPI
distributions. Consumers select package versions from PyPI, while Git tags and
GitHub Releases record the repository release state.

Branch roles:

- `develop` is the integration branch.
- `main` is the release branch.
- Release tags are created on `main`, after `develop` has been promoted through
  a pull request.

Versioning:

- `v0.x.0` is used for milestone feature groups before `v1.0.0`.
- `v0.x.y` is used for patch fixes and release hygiene updates.
- `v0` versions do not promise stable public API compatibility.

## Release Preconditions

Before creating a release PR:

1. The milestone has no open issues.
2. `CHANGELOG.md` contains `## [vX.Y.Z] - YYYY-MM-DD`.
3. `WIP.md` reflects the target release-preparation state.
4. `docs/release/release-guide.md` reflects the current release policy.
5. No `vX.Y.Z` tag exists locally or remotely.
6. No GitHub Release exists for `vX.Y.Z`.
7. Local validation passes.
8. GitHub CI passes on the target `develop` commit.
9. PyPI publish credentials and target repository are confirmed outside the
   repository before any publish action.
10. `docs/release/pypi-preflight.md` lists the intended distributions and
    records the current trusted publishing hold status.

Useful preflight commands:

```bash
git status --short --branch
git fetch --prune origin main develop --tags
git log --oneline origin/main..origin/develop
gh issue list --repo bluetape4k/bluetape-py --milestone "X.Y.Z" --state open
gh pr list --repo bluetape4k/bluetape-py --state open
git tag --list "vX.Y.Z"
git ls-remote --tags origin "refs/tags/vX.Y.Z*"
gh release view vX.Y.Z --repo bluetape4k/bluetape-py
rg -n "## \\[vX\\.Y\\.Z\\]" CHANGELOG.md
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Standard Release Flow

1. Prepare `develop`.
   - Update `CHANGELOG.md`.
   - Update `WIP.md`.
   - Update release docs when the process changes.
   - Run local validation.

2. Close milestone bookkeeping.
   - Verify milestone open issue count is zero.
   - Close the GitHub milestone.

3. Promote `develop` to `main`.
   - Open a release PR with base `main` and head `develop`.
   - Verify the PR body includes release scope, validation evidence, milestone
     status, and tag plan.
   - Wait for PR CI to pass.
   - Merge the release PR.

4. Tag the release commit.
   - Fetch `main`.
   - Fast-forward local `main` to `origin/main`.
   - Confirm `CHANGELOG.md` on `main` contains the version section.
   - Create an annotated tag on `main`:

```bash
git switch main
git pull --ff-only origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

5. Create the GitHub Release.
   - Use the matching `CHANGELOG.md` section as the release note source.
   - Include validation evidence and tag target commit.

6. Publish distributions.
   - Confirm the build artifacts correspond to the tagged commit.
   - Publish only the intended distributions.
   - Verify package metadata and install behavior from PyPI after publication.

## `v0.1.0` Release Plan

`v0.1.0` contains the initial Python-native foundation:

- workspace structure and Python 3.13+ policy;
- thin `bluetape` meta distribution;
- `bluetape-core`, `bluetape-logging`, and `bluetape-testing`;
- English and Korean root documentation;
- package READMEs and release preflight documentation.

The first release intends to publish exactly these distributions:

- `bluetape`
- `bluetape-core`
- `bluetape-logging`
- `bluetape-testing`

Publishing remains on hold until PyPI project ownership and trusted publishing
are confirmed outside the repository. Do not dispatch a publish workflow or
upload artifacts while issue #5 is open.

The complete fail-closed workspace classification is maintained in
`docs/release/pypi-preflight.md`. `bluetape-benchmark` is built and tested but
is private and must never be selected for upload. Its private classifier is
only defense in depth; any unclassified workspace distribution blocks release
preflight before build artifacts are selected.

Release sequence:

1. Verify milestone `0.1.0` has zero open issues.
2. Merge the release-readiness PR so `CHANGELOG.md`, `WIP.md`, README locale
   files, and this release guide reflect `v0.1.0`.
3. Close milestone `0.1.0`.
4. Merge `develop` into `main` through a release PR.
5. Tag `main` as `v0.1.0`.
6. Create GitHub Release `v0.1.0`.
7. Publish PyPI distributions only after release preflight issue #5 is closed.
