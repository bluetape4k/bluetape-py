# bluetape-py

[English](README.md) | [한국어](README.ko.md)

![bluetape-py hero](docs/assets/bluetape-py-hero.png)

Python-native bluetape libraries for backend services, testing, logging, and
operational helpers.

`bluetape-py` follows the same ecosystem discipline as `bluetape4k`,
`bluetape-go`, and `bluetape-rs`, but it is not a mechanical port. The Python
line starts from Python 3.13+, keeps the default install thin, and splits
heavier capabilities into explicit PyPI distributions and extras.

## Current Status

This repository is in the initial `0.1.0` development track. The first release
is scoped by these open issues. Detailed release planning lives in
[`WIP.md`](WIP.md), and completed user-facing changes are tracked in
[`CHANGELOG.md`](CHANGELOG.md).

| Issue | Scope |
|---:|---|
| [#1](https://github.com/bluetape4k/bluetape-py/issues/1) | Expand the `bluetape-core` foundation helpers. |
| [#2](https://github.com/bluetape4k/bluetape-py/issues/2) | Stabilize `bluetape-logging` context helpers. |
| [#3](https://github.com/bluetape4k/bluetape-py/issues/3) | Grow internal-first `bluetape-testing` helpers. |
| [#4](https://github.com/bluetape4k/bluetape-py/issues/4) | Publish the initial package boundary and install guide. |
| [#5](https://github.com/bluetape4k/bluetape-py/issues/5) | Prepare the `0.1.0` release and PyPI publishing path. |

## Workspace Shape

![bluetape-py workspace overview](docs/images/readme-diagrams/bluetape-py-workspace-overview.png)

The repository is a single `uv` workspace with multiple focused distributions.
The meta package remains intentionally small: `pip install bluetape` installs
only `bluetape-core` by default.

| Distribution | Import path | Default install | Status | Purpose |
|---|---|---:|---|---|
| `bluetape` | none | yes | active | Thin meta distribution that depends on `bluetape-core`. |
| `bluetape-core` | `bluetape.core` | yes | active | Stdlib-only validation and foundation helpers. |
| `bluetape-logging` | `bluetape.logging` | no | active | Stdlib `logging`, `contextvars`, and redaction helpers. |
| `bluetape-testing` | `bluetape.testing` | no | active, internal-first | Pytest helpers used first by this workspace, with a small stable public subset. |
| `bluetape-serde` | `bluetape.serde` | no | planned | Serialization boundary helpers after core APIs settle. |
| `bluetape-cache` | `bluetape.cache` | no | planned | Cache abstractions and in-memory helpers. |
| `bluetape-redis` | `bluetape.redis` | no | planned | Redis-backed adapters once cache contracts are proven. |
| `bluetape-testcontainers` | `bluetape.testcontainers` | no | planned | Testcontainers fixtures for integration-heavy packages. |
| `bluetape-fastapi` | `bluetape.fastapi` | no | planned | FastAPI integration helpers after the core/logging/testing layer stabilizes. |

## Design Position

- Python-native APIs come first; Kotlin, Go, and Rust siblings are references,
  not source languages to copy.
- `bluetape-core` stays stdlib-only.
- `bluetape-logging` stays stdlib-first and builds on `logging` plus
  `contextvars`.
- `bluetape-testing` may depend on `pytest`, but starts as an internal support
  module before promising a broad public API.
- The root `bluetape` distribution exposes extras, but it does not create a
  root `bluetape/__init__.py` import surface.

## Install

The public install shape after the first PyPI release is:

```bash
pip install bluetape
pip install "bluetape[logging]"
pip install "bluetape[testing]"
pip install "bluetape[dev]"
pip install "bluetape[all]"
```

Focused distributions can also be installed directly:

```bash
pip install bluetape-core
pip install bluetape-logging
pip install bluetape-testing
```

For local development from this repository:

```bash
uv sync --all-packages
```

## Usage

### Core validation

```python
from bluetape.core import require_not_blank

service_name = require_not_blank("orders", "service_name")
```

### Logging context

```python
import logging

from bluetape.logging import ContextLogFilter, log_context

logger = logging.getLogger("orders")
logger.addFilter(ContextLogFilter())

with log_context(trace_id="trace-123", tenant="blue"):
    logger.info("order accepted")
```

### Testing waits

```python
from bluetape.testing import eventually

eventually(lambda: cache.get("ready"), timeout=2.0)
```

## Package Documentation

| Package | Documentation |
|---|---|
| `bluetape` | [packages/bluetape/README.md](packages/bluetape/README.md) |
| `bluetape-core` | [packages/bluetape-core/README.md](packages/bluetape-core/README.md) |
| `bluetape-logging` | [packages/bluetape-logging/README.md](packages/bluetape-logging/README.md) |
| `bluetape-testing` | [packages/bluetape-testing/README.md](packages/bluetape-testing/README.md) |

## Roadmap

| Track | Plan |
|---|---|
| `0.1.0` | Stabilize the initial core, logging, testing, documentation, and release preflight issues. |
| `0.2.0` | Track ecosystem package planning in issues #7-#20, with research gates before broad adapters. |
| Later | Add FastAPI helpers and workshop examples only after the base packages are stable. |

Project planning and release policy:

- [WIP.md](WIP.md)
- [CHANGELOG.md](CHANGELOG.md)
- [Package layout policy](docs/package-layout.md)
- [Release guide](docs/release.md)
- [Research index](docs/research/README.md)

## Ecosystem Backlog

The `0.2.0` milestone tracks Python-native equivalents for proven bluetape-go
and bluetape4k ecosystem capabilities. Research issues intentionally come before
implementation where the Python package boundary or dependency choice is not
obvious. See [`WIP.md`](WIP.md) for the issue-by-issue task queue and
[`docs/research/README.md`](docs/research/README.md) for research gates.

## Development

```bash
uv sync --all-packages
uv build --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
