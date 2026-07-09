# bluetape-py

Python-native bluetape libraries for backend services, testing, logging, and operational helpers.

`bluetape-py` is a Python 3.13+ workspace. The default `bluetape` distribution stays thin and installs only `bluetape-core`; heavier capabilities are split into explicit packages and extras.

## Package Policy

| Distribution | Import path | Default install | Purpose |
|---|---|---:|---|
| `bluetape` | none | yes | Thin meta distribution that depends on `bluetape-core`. |
| `bluetape-core` | `bluetape.core` | yes | Stdlib-only foundation helpers. |
| `bluetape-logging` | `bluetape.logging` | no | Stdlib logging and `contextvars` helpers. |
| `bluetape-testing` | `bluetape.testing` | no | Internal-first pytest helpers with a documented stable subset. |

## Install

```bash
pip install bluetape
pip install "bluetape[logging]"
pip install "bluetape[testing]"
```

## Development

```bash
uv sync --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
