# bluetape

Thin meta distribution for Python-native bluetape packages.

The default install depends only on `bluetape-core`.

## Install Shape

```bash
pip install bluetape
pip install "bluetape[collections]"
pip install "bluetape[logging]"
pip install "bluetape[testing]"
pip install "bluetape[all]"
```

The meta distribution intentionally publishes no root `bluetape` import module.
Focused packages own focused import paths such as `bluetape.core`,
`bluetape.collections`, `bluetape.logging`, and `bluetape.testing`.

PyPI publication is currently on hold for this repository. The commands above
describe the intended public install shape after publishing is enabled.
