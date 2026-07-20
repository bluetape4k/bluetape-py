# bluetape-jwt

English | [한국어](README.ko.md)

`bluetape-jwt` provides strict synchronous JWS signing, verification, and
in-memory key rotation for Python 3.13+. It keeps `joserfc` and
`bluetape-cache` behind immutable Bluetape-owned values and stable, redacted
exceptions. The package is implemented in the source workspace; PyPI
publication remains on the repository-wide release hold.

<!-- jwt-scenario:install -->
## Install

Use either the focused distribution or the explicit meta extra. The default
`pip install bluetape` remains core-only.

```bash
pip install bluetape-jwt
pip install "bluetape[jwt]"
```

Supported algorithms are exactly `HS256`, `HS384`, `HS512`, `RS256`, `RS384`,
`RS512`, `PS256`, `PS384`, and `PS512`. HMAC secrets must be at least the hash
width, and RSA keys must have a modulus of at least 2048 bits.

<!-- jwt-scenario:profile-provider -->
## Bind One Security Profile

Each `JWSProvider` is constructed with one algorithm, one repository, and one
validation profile. Callers cannot weaken `typ`, issuer, audience, required
claims, or algorithm rules per verification call.

```python
from datetime import UTC, datetime, timedelta

from bluetape.jwt import (
    InMemoryKeyRepository,
    IssuanceProfile,
    IssuanceProfileProvider,
    JWSAlgorithm,
    JWSProvider,
    JWTKey,
    TokenClaims,
    ValidationProfile,
    VerifiedTokenCacheOptions,
)

key = JWTKey.from_hmac_secret(
    "2026-07-primary",
    JWSAlgorithm.HS256,
    b"replace-with-at-least-32-secret-bytes",
)
repository = InMemoryKeyRepository(active=key)
validation = ValidationProfile(
    token_type="access+jwt",
    allowed_issuers=frozenset({"https://issuer.example"}),
    accepted_audiences=frozenset({"orders-api"}),
    required_claims=frozenset({"scope"}),
    protected_headers={"tenant": "primary"},
)
cache = VerifiedTokenCacheOptions(
    default_ttl=timedelta(minutes=5),
    max_size=10_000,
)
signer = JWSProvider(
    JWSAlgorithm.HS256,
    repository,
    validation,
    cache=cache,
)
issuance = IssuanceProfile(
    default_ttl=timedelta(minutes=15),
    max_ttl=timedelta(hours=1),
)
provider = IssuanceProfileProvider(signer, issuance)

claims = TokenClaims(
    issuer="https://issuer.example",
    subject="user-123",
    audience=("orders-api",),
    custom={"scope": "orders:read"},
)
token = provider.issue(claims)
verified = provider.verify(token)
```

The verified result is immutable. Its `headers` mapping contains only the
profile-approved custom protected headers; `alg`, `kid`, and `typ` have
dedicated fields or remain inside the verification boundary.

<!-- jwt-scenario:issuance-policy -->
## Keep Lifetime Policy in a Decorator

`JWSProvider.issue()` signs the caller's claims without silently adding or
replacing registered claims. `IssuanceProfileProvider` optionally supplies
missing `iat` and `exp` values before delegating.

`IssuanceProfile(default_ttl=None)` does not invent an expiration date. A token
without `exp` can therefore remain non-expiring if the application explicitly
chooses that policy. The package publishes no universal 7-day or 365-day
default; applications should define named access, refresh, or service-token
profiles themselves. Explicit caller `iat` and `exp` values are preserved, and
lifetimes above `max_ttl` are rejected rather than clamped.

<!-- jwt-scenario:rotation-revocation -->
## Rotation and Revocation

The repository owns key status:

- `ACTIVE` signs and verifies.
- `RETIRED` verifies existing tokens but never signs new tokens.
- `REVOKED` is a material-free tombstone and rejects verification attempts
  whose snapshot was captured after revocation was published.

`repository.rotate(new_key)` atomically retires the old active key and
publishes the new active key. `repository.revoke(kid)` removes usable material.
An operation that already captured the old immutable snapshot may complete;
it can only produce an old-epoch result and cannot promote that result into a
newer cache epoch.

<!-- jwt-scenario:cache-boundary -->
## Cache Boundary

Caching is disabled unless `VerifiedTokenCacheOptions` is supplied. The local
bounded cache keys entries by the SHA-256 token digest, validation-profile
fingerprint, and repository epoch. It never stores the raw token as a key,
never caches failures, and rechecks temporal policy on every hit.

The cache is an optimization, not a revocation list or distributed consistency
mechanism. Rotation, retirement, and revocation advance the repository epoch
and clear stale local entries when the provider observes the new epoch.

<!-- jwt-scenario:security-boundary -->
## Security Boundary

Compact input must contain exactly three bounded base64url segments. The
provider rejects duplicate JSON names, `none`, algorithm confusion, wrong
`typ`, missing or invalid `kid`, unapproved protected headers, remote key
headers such as `jku`/`jwk`/`x5u`/`x5c`, `zip`, and unknown `crit` before local
key resolution. Issuer and audience checks are exact profile rules.

JWS payloads are signed, not encrypted: anyone holding a token can read its
protected header and payload. Do not place secrets in claims. Exceptions and
owned log events are redacted and never include tokens, keys, signatures,
claims, or caller header values.

<!-- jwt-scenario:follow-ups -->
## Explicit Follow-ups

The two-method `TokenProvider` contract is intentionally composable, but this
issue does not implement asynchronous repositories/providers (#88), JWE
encryption (#89), or a versioned compression envelope (#90). Future encryption
and compression can wrap the same `issue(claims)` / `verify(token)` contract;
they are not implicit features of the current three-segment JWS provider.
