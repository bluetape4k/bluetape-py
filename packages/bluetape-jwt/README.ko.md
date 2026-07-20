# bluetape-jwt

[English](README.md) | 한국어

`bluetape-jwt`는 Python 3.13 이상에서 엄격한 동기 JWS 발급·검증과 in-memory
key rotation을 제공합니다. `joserfc`와 `bluetape-cache`는 Bluetape가 소유하는
불변 값과 안정적인 redacted 예외 뒤에 둡니다. source workspace 구현은
완료됐지만 PyPI 배포는 repository 전체 release hold를 따릅니다.

<!-- jwt-scenario:install -->
## 설치

focused distribution 또는 명시적인 meta extra를 사용합니다. 기본
`pip install bluetape`는 계속 core-only입니다.

```bash
pip install bluetape-jwt
pip install "bluetape[jwt]"
```

지원 algorithm은 `HS256`, `HS384`, `HS512`, `RS256`, `RS384`, `RS512`,
`PS256`, `PS384`, `PS512`로 고정됩니다. HMAC secret은 hash 폭 이상이어야 하고,
RSA key modulus는 2048 bit 이상이어야 합니다.

<!-- jwt-scenario:profile-provider -->
## 하나의 security profile 고정

각 `JWSProvider`는 하나의 algorithm, repository, validation profile로
구성합니다. 호출별로 `typ`, issuer, audience, required claim, algorithm 규칙을
완화할 수 없습니다.

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

검증 결과는 불변입니다. `headers` mapping에는 profile이 승인한 custom protected
header만 들어갑니다. `alg`, `kid`, `typ`는 전용 field로 제공하거나 검증 경계
안에서만 사용합니다.

<!-- jwt-scenario:issuance-policy -->
## lifetime policy는 decorator로 분리

`JWSProvider.issue()`는 caller claim에 registered claim을 몰래 추가하거나
교체하지 않습니다. `IssuanceProfileProvider`가 누락된 `iat`와 `exp`를 정책에
따라 채운 뒤 발급을 위임합니다.

`IssuanceProfile(default_ttl=None)`은 임의의 만료일을 만들지 않습니다.
application이 명시적으로 선택하면 `exp`가 없는 token은 만료되지 않을 수
있습니다. package는 7일이나 365일 같은 공통 기본값을 제공하지 않습니다.
application이 access, refresh, service token용 named profile을 직접 정의해야
합니다. caller가 지정한 `iat`와 `exp`는 보존하며, `max_ttl`을 넘는 lifetime은
줄여서 저장하지 않고 거부합니다.

<!-- jwt-scenario:rotation-revocation -->
## Rotation과 revocation

key status는 repository가 소유합니다.

- `ACTIVE`는 새 token을 발급하고 기존 token도 검증합니다.
- `RETIRED`는 기존 token만 검증하며 새 token 발급에는 쓰지 않습니다.
- `REVOKED`는 key material이 없는 tombstone입니다. revocation publish 뒤에
  snapshot을 얻은 검증 요청은 거부합니다.

`repository.rotate(new_key)`는 기존 active key를 retire하고 새 active key를
atomic하게 publish합니다. `repository.revoke(kid)`는 사용할 수 있는 material을
제거합니다. 이미 예전 immutable snapshot을 얻은 작업은 완료될 수 있지만,
결과는 예전 epoch에만 속하며 새 cache epoch로 승격되지 않습니다.

<!-- jwt-scenario:cache-boundary -->
## Cache 경계

`VerifiedTokenCacheOptions`를 지정하지 않으면 cache는 비활성화됩니다. bounded
local cache는 SHA-256 token digest, validation-profile fingerprint, repository
epoch로 entry를 구분합니다. raw token을 key로 저장하지 않고, 실패 결과를
cache하지 않으며, hit마다 temporal policy를 다시 검증합니다.

이 cache는 성능 최적화일 뿐 revocation list나 distributed consistency
mechanism이 아닙니다. rotation, retirement, revocation으로 repository epoch가
바뀌면 provider가 새 epoch를 관찰할 때 오래된 local entry를 비웁니다.

<!-- jwt-scenario:security-boundary -->
## Security 경계

compact input은 크기가 제한된 base64url segment 세 개로 정확히 구성해야 합니다.
provider는 local key를 찾기 전에 duplicate JSON name, `none`, algorithm
confusion, 잘못된 `typ`, 누락되거나 잘못된 `kid`, 승인되지 않은 protected
header, `jku`/`jwk`/`x5u`/`x5c` 같은 remote key header, `zip`, 알 수 없는
`crit`를 거부합니다. issuer와 audience는 profile의 exact rule로 검증합니다.

JWS payload는 서명할 뿐 암호화하지 않습니다. token을 가진 사람은 protected
header와 payload를 읽을 수 있으므로 claim에 secret을 넣으면 안 됩니다. 예외와
package 소유 log event에는 token, key, signature, claim, caller header 값을
기록하지 않습니다.

<!-- jwt-scenario:follow-ups -->
## 명시적인 후속 작업

두 method로 구성된 `TokenProvider` 계약은 decorator 합성을 고려했지만, 이번
issue에서는 async repository/provider (#88), JWE encryption (#89), versioned
compression envelope (#90)을 구현하지 않습니다. 이후 encryption과 compression은
같은 `issue(claims)` / `verify(token)` 계약을 감쌀 수 있지만, 현재의 three-segment
JWS provider가 암묵적으로 제공하는 기능은 아닙니다.
