# PyPI Preflight

This document records the publish boundary for the first `bluetape-py` release.
It is a preflight checklist, not permission to publish.

## Target Release

- Version: `v0.1.0`
- Source branch before release PR: `develop`
- Release branch: `main`
- Tag: `v0.1.0`

## Target Distributions

| Distribution | Import path | Default `bluetape` dependency | Publish in `v0.1.0` |
|---|---|---:|---:|
| `bluetape` | none | yes | yes |
| `bluetape-core` | `bluetape.core` | yes | yes |
| `bluetape-logging` | `bluetape.logging` | no | yes |
| `bluetape-testing` | `bluetape.testing` | no | yes |

The `bluetape` meta distribution must keep its default dependency list limited
to `bluetape-core`.

## Trusted Publishing Status

Status: hold.

Before publishing, confirm outside this repository:

1. PyPI project ownership for every target distribution.
2. Whether GitHub Actions trusted publishing is configured for each project.
3. Which GitHub environment, if any, is allowed to publish.
4. Whether TestPyPI dry-run publication is required before PyPI.

No tag, GitHub Release, workflow dispatch, or `uv publish` command should run
until the release owner explicitly approves the publish step.

## Local Verification

Run these commands from the release candidate commit:

```bash
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

CI must also run `uv build --all-packages` before a release tag is created.
