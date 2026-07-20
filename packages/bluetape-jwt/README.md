# bluetape-jwt

Implementation status: in progress for issue #18.

The current package boundary exposes only the approved `JWSAlgorithm` values and
stable, redacted exception types. Signing, verification, key rotation, typed
claims, issuance profiles, and optional verified-result caching will be added in
subsequent implementation steps and are not available yet.

The distribution targets Python 3.13 or newer and keeps `joserfc` behind the
`bluetape.jwt` API. It depends on `bluetape-cache` for the later optional local
cache boundary; the thin `bluetape` default install remains core-only.
