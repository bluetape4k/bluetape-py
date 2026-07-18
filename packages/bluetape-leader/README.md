# bluetape-leader

English | [한국어](README.ko.md)

`bluetape-leader` reserves the stdlib-only, backend-neutral package boundary
for future leader election and distributed lock contracts.

The current public surface contains only sanitized leader error contracts.
Leader options, leases, electors, and lock behavior are not implemented yet.
Use this package as a contract preview, not as a working coordination library.

PyPI publication is on hold. The eventual focused and meta-extra install shapes
will be:

```bash
pip install bluetape-leader
pip install "bluetape[leader]"
```

Redis support remains isolated in the opt-in `bluetape-leader-redis`
distribution. The default `bluetape` install remains core-only.
