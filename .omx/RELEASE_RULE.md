# bluetape-py Release Rule

## Version Source

- Workspace package versions live in `packages/*/pyproject.toml` and the root
  `pyproject.toml`.
- `v0.1.0` currently matches all distributions at package version `0.1.0`.
- Release notes are sourced from `CHANGELOG.md`.

## Branch And Tag Model

- `develop` is the integration branch.
- `main` is the release branch.
- Promote `develop` to `main` through a pull request.
- Create annotated release tags on `main` after the release PR is merged.
- Tag format: `vX.Y.Z`.

## Release Preconditions

- Matching milestone has zero open issues and is closed before the release PR is
  merged.
- `CHANGELOG.md` contains the target section, for example
  `## [v0.1.0] - 2026-07-10`.
- `WIP.md` reflects the release-preparation state.
- No local or remote tag exists for the target version.
- No GitHub Release exists for the target version.
- Local validation passes:
  - `uv sync --all-packages`
  - `uv run pytest`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv build --all-packages`
  - `actionlint`
  - `git diff --check`
- GitHub Actions CI passes on `develop` and on the release PR.

## Publishing Rule

- `v0.1.0` intends to publish `bluetape`, `bluetape-core`,
  `bluetape-logging`, and `bluetape-testing`.
- Do not publish to PyPI until project ownership and GitHub Actions trusted
  publishing are confirmed outside this repository.
- A GitHub Release is allowed before PyPI publication, but release notes must
  state that PyPI publication is pending trusted-publishing confirmation.

## Rollback Notes

- If the release PR fails, update `develop` with a corrective PR and recreate
  the release PR.
- If the tag is pushed to the wrong commit before publishing, delete the local
  and remote tag before any package upload.
- If PyPI publication starts, do not delete published files as a rollback
  strategy; publish a corrective patch version instead.
