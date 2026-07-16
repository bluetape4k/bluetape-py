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

## Fail-Closed Workspace Classification

Every current workspace distribution is classified below. Release tooling and
review must fail when a workspace member is absent from both sets.

Publishable distributions (subject to the target-release table and explicit
release approval):

- `bluetape`
- `bluetape-async`
- `bluetape-audit`
- `bluetape-cache`
- `bluetape-cache-redis`
- `bluetape-codec`
- `bluetape-collections`
- `bluetape-compression`
- `bluetape-core`
- `bluetape-id`
- `bluetape-logging`
- `bluetape-measure`
- `bluetape-money`
- `bluetape-observability`
- `bluetape-resilience`
- `bluetape-serde`
- `bluetape-testcontainers`
- `bluetape-testing`

Private distributions, never publishable:

- `bluetape-benchmark`

The classifier on `bluetape-benchmark` is PyPI defense in depth.
Exact release selection is the primary control: an unknown member blocks
preflight, and a publish command must use an explicitly approved subset of the
publishable set.

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
