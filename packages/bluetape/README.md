# bluetape

Thin meta distribution for Python-native bluetape packages.

The default install depends only on `bluetape-core`.

## Install Shape

```bash
pip install bluetape
pip install "bluetape[asyncio]"
pip install "bluetape[cache]"
pip install "bluetape[codec]"
pip install "bluetape[collections]"
pip install "bluetape[compression]"
pip install "bluetape[logging]"
pip install "bluetape[serde]"
pip install "bluetape[fory]"
pip install "bluetape[testing]"
pip install "bluetape[all]"
```

The meta distribution intentionally publishes no root `bluetape` import module.
Focused packages own focused import paths such as `bluetape.asyncio`,
`bluetape.cache`, `bluetape.codec`, `bluetape.collections`,
`bluetape.compression`, `bluetape.core`, `bluetape.logging`, `bluetape.serde`,
and `bluetape.testing`.

| Extra | Focused distribution | Import path | Default install |
|---|---|---|---:|
| `asyncio` | `bluetape-async` | `bluetape.asyncio` | no |
| `cache` | `bluetape-cache` | `bluetape.cache` | no |
| `codec` | `bluetape-codec` | `bluetape.codec` | no |
| `collections` | `bluetape-collections` | `bluetape.collections` | no |
| `compression` | `bluetape-compression` | `bluetape.compression` | no |
| `logging` | `bluetape-logging` | `bluetape.logging` | no |
| `serde` | `bluetape-serde` | `bluetape.serde` | no |
| `fory` | `bluetape-serde[fory]` | `bluetape.serde.fory` | no |
| `testing` | `bluetape-testing` | `bluetape.testing` | no |

The `cache` extra installs the stdlib-only bounded sync and async local TTL
loading caches. Redis remains a separate future distribution under issue #51.

The `asyncio` extra installs `bluetape-async`, which provides bounded,
call-scoped structured-concurrency helpers. The default install remains limited
to `bluetape-core`.

The `codec` and `compression` extras install strict encoded-text helpers and
bounded gzip/zlib/raw-DEFLATE helpers respectively. They remain optional and
never change the default dependency set.

The `serde` extra installs strict payload contracts and bounded JSON v1
serialization. The separate `fory` extra installs `bluetape-serde[fory]` and
currently requires CPython 3.13. Fory is intentionally excluded from the base,
`serde`, `dev`, and `all` extras. The full extra list is `asyncio`, `cache`,
`codec`, `collections`, `compression`, `logging`, `serde`, `fory`, `testing`,
`dev`, and `all`.

PyPI publication is currently on hold for this repository. The commands above
describe the intended public install shape after publishing is enabled and are
not runnable from PyPI today. From the source workspace, run
`uv sync --all-packages --locked`; a locally built focused wheel can also be
installed directly.

```bash
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
uv build --package bluetape-serde --out-dir "$tmp_dir/dist"
uv venv "$tmp_dir/venv"
uv pip install --python "$tmp_dir/venv/bin/python" "$tmp_dir"/dist/bluetape_serde-*.whl
"$tmp_dir/venv/bin/python" -c 'from bluetape.serde import PayloadMetadata, TrustProfile, json_deserialize, json_serialize; m = PayloadMetadata(format="json", version=1, content_type="application/json", trust_profile=TrustProfile.UNTRUSTED); p = json_serialize({"ok": True}, metadata=m); assert json_deserialize(p, expected_metadata=m) == {"ok": True}'
```

The serde surface has 25 ordered exports and 23 stable domain error codes,
including the fixed 640-decimal-digit JSON integer limit. Caller type and
configuration mistakes remain native `TypeError`/`ValueError` rather than
`SerdeError` domain failures. Apache Fory remains trusted-internal only and
requires caller-owned fixed schema/type registration; it never selects a codec
or fallback from payload content.
