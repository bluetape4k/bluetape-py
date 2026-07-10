# bluetape

Thin meta distribution for Python-native bluetape packages.

The default install depends only on `bluetape-core`.

## Install Shape

```bash
pip install bluetape
pip install "bluetape[asyncio]"
pip install "bluetape[codec]"
pip install "bluetape[collections]"
pip install "bluetape[compression]"
pip install "bluetape[logging]"
pip install "bluetape[testing]"
pip install "bluetape[all]"
```

The meta distribution intentionally publishes no root `bluetape` import module.
Focused packages own focused import paths such as `bluetape.asyncio`,
`bluetape.codec`, `bluetape.collections`, `bluetape.compression`,
`bluetape.core`, `bluetape.logging`, and `bluetape.testing`.

The `asyncio` extra installs `bluetape-async`, which provides bounded,
call-scoped structured-concurrency helpers. The default install remains limited
to `bluetape-core`.

The `codec` and `compression` extras install strict encoded-text helpers and
bounded gzip/zlib/raw-DEFLATE helpers respectively. They remain optional and
never change the default dependency set.

PyPI publication is currently on hold for this repository. The commands above
describe the intended public install shape after publishing is enabled.
