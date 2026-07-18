# bluetape-leader-redis

English | [한국어](README.ko.md)

`bluetape-leader-redis` reserves the opt-in Redis adapter package boundary for
`bluetape-leader`.

The current package only reserves the Redis adapter namespace.
Redis lock and leader behavior are not implemented yet. Do not use this
placeholder for coordination or ownership decisions.

PyPI publication is on hold. The eventual focused and meta-extra install shapes
will be:

```bash
pip install bluetape-leader-redis
pip install "bluetape[leader-redis]"
```

The distribution depends only on `bluetape-leader==0.1.0` and `redis==8.0.1`
at runtime. It remains absent from the default, `dev`, and `all` meta installs.
