# Issue #18 JWT 및 Key Rotation Helper 설계

- 이슈: [#18](https://github.com/bluetape4k/bluetape-py/issues/18)
- 마일스톤: `0.2.0`
- 날짜: 2026-07-20 KST
- 작업 유형: Type A - Full Feature
- 저장소: `bluetape4k/bluetape-py`
- 기준/작업 브랜치: `develop` <- `feat/issue-18-jwt-key-rotation`

## 승인된 제공 범위

`bluetape.jwt` import 경로를 사용하는 `bluetape-jwt` 배포 패키지 하나를
추가한다. 이 패키지는 동기 JWS 토큰 발급과 검증, 불변 typed claims,
명시적인 validation profile, 로컬 key rotation, 선택적인 bounded verified-result
cache를 제공한다.

사용자는 2026-07-20에 다음 경계를 승인했다.

1. `HS256`, `HS384`, `HS512`, `RS256`, `RS384`, `RS512`, `PS256`,
   `PS384`, `PS512`를 지원한다.
2. 각 `JWSProvider` 인스턴스는 알고리즘 하나와 불변 validation profile
   하나에 정확히 결합한다.
3. thread-safe in-memory 구현을 갖춘 동기 `KeyRepository` protocol을 사용한다.
   async 계약은 #88로 미룬다.
4. key rotation을 `ACTIVE -> RETIRED -> REVOKED`로 모델링한다. active key는
   서명과 검증에 사용하고, retired key는 검증에만 사용하며, revoked key는
   사용할 수 없다.
5. low-level provider에서는 호출자가 제공한 claims를 권위 있는 값으로
   유지한다. 선택적인 issuance-profile decorator가 호출자가 설정한 정책에
   따라 누락된 time claims를 채울 수 있다.
6. typed registered claims와 read-only custom-claims mapping을 포함하는 불변
   `VerifiedToken`을 반환한다.
7. Bluetape 소유의 불변 key wrapper를 공개하고 `joserfc` 타입은 비공개로
   유지한다.
8. #18에서는 최소 provider 합성 계약을 정의한다. 구체적인 JWE 및 compression
   decorator는 #89와 #90으로 미룬다.
9. verified-result caching은 digest key, 유한 TTL, capacity 제한,
   validation-profile 분리, key-epoch 무효화를 갖춘 명시적이고 bounded인
   선택 사항으로만 제공한다.

이 명세는 설계 기록만 승인한다. 구현 계획, production code 수정, PR 생성,
merge, release, tag, publication은 이후 workflow gate로 남겨 둔다.

## 문제

애플리케이션은 algorithm allow-listing, `kid` 선택, typed claim 처리, cache
무효화, secret redaction 규칙을 중복 구현하지 않고 서명된 JWT를 발급·검증하고
key를 rotation할 수 있어야 한다. JOSE 라이브러리를 직접 호출하면 이러한
애플리케이션 수준 경계를 호출자마다 정의해야 하므로, 의도와 다른 알고리즘,
token type, issuer 또는 audience로 토큰을 잘못 수용하기 쉽다.

monolithic authentication service는 다른 문제를 해결한다. JWT는 보편적인
access-token, refresh-token 또는 session lifetime을 정의하지 않으므로, 이
패키지는 7일이나 365일 같은 전역 기본값을 만들어서는 안 된다. 또한 신뢰할
수 없는 token header를 근거로 remote key material을 가져오거나 background
refresh 및 rotation worker를 소유해서도 안 된다.

따라서 첫 Python 구현에는 작고 합성 가능한 provider 계약, 엄격한 JWS 검증,
명시적인 issuance 및 validation profile, rotation 동작을 관찰하고 테스트할 수
있는 로컬 repository가 필요하다.

## 현재 근거

- Issue #18은 명시적인 algorithm allow-listing, `kid` 처리, key-chain
  repository 계약, in-memory provider cache, typed claim access, confusion
  attack·temporal claim·signature·rotation·invalidation·secret redaction 테스트를
  요구한다.
- workspace는 Python 3.13+, 얇은 기본 `bluetape` 설치, 목적별 opt-in package,
  영문·국문 package documentation, dependency 또는 namespace 변경 시 전체
  package build 검증을 요구한다.
- `bluetape-cache`는 이미 thread-safe bounded synchronous `TTLCache`를 소유한다.
  JWT package는 두 번째 범용 cache를 만들지 말고 이 구현을 재사용해야 한다.
- `bluetape-compression`은 structural compressor 계약과 명시적인 호출자 합성을
  제공한다. Compression은 signed JWT/JWS 의미론에 포함되지 않는다.
- `bluetape-go/jwt`는 명시적 algorithm 선택, reserved header 및 claim 보호,
  typed verified reader, key rotation, cache invalidation의 의미론적 참고 대상이다.
  Python packaging과 API 관례는 이 구현에서 계속 권위 있는 기준이다.
- `joserfc` 1.7.4는 Python 3.13, JWS algorithm registry, 명시적인 JWK key type,
  key set, typed package metadata, registered-claim validation을 지원한다.
  deprecated `authlib.jose` namespace를 거치지 않고 직접 채택한다.

주요 표준 및 dependency 참고 자료:

- [RFC 7515 - JSON Web Signature](https://www.rfc-editor.org/rfc/rfc7515.html)
- [RFC 7517 - JSON Web Key](https://www.rfc-editor.org/rfc/rfc7517.html)
- [RFC 7518 - JSON Web Algorithms](https://www.rfc-editor.org/rfc/rfc7518.html)
- [RFC 7519 - JSON Web Token](https://www.rfc-editor.org/rfc/rfc7519.html)
- [RFC 8725 - JWT Best Current Practices](https://www.rfc-editor.org/rfc/rfc8725.html)
- [`joserfc` JWT guide](https://jose.authlib.org/en/guide/jwt/)
- [`joserfc` JWK guide](https://jose.authlib.org/en/guide/jwk/)
- [`joserfc` registry guide](https://jose.authlib.org/en/guide/registry/)

## 검토한 접근 방식

### 1. 합성 가능한 provider, profile, repository 계약 - 선택

`JWSProvider`는 최소 `TokenProvider` protocol을 구현하고 key 상태를
`KeyRepository`에 위임한다. issuance profile은 low-level claim 소유권을
바꾸지 않고 provider를 decorate한다. validation profile은 provider 생성 시
고정한다. 이후 JWE 및 compression package는 JWS 동작을 바꾸지 않고 같은
provider 계약을 감쌀 수 있다.

이 구조는 보안 정책을 명시적으로 유지하고 호출별 validation 약화를 방지하며,
사용자가 요청한 decorator 경계를 제공한다.

### 2. Monolithic JWT service - 거부

token type, default lifetime, signing, verification, rotation, cache policy,
향후 encryption을 결합한 service는 한 애플리케이션에는 편리하지만,
애플리케이션 authentication policy를 전역 library 기본값으로 만든다. 또한
decorator 적용을 어렵게 하고 구체적인 소비자가 필요한 profile을 확립하기
전에 public surface를 확대한다.

### 3. 함수만 제공하는 encode/decode helper - 거부

free function은 `joserfc`와 유사해 배우기 쉽지만, 매 호출마다 algorithm,
key, issuer, audience, type, cache, rotation 선택을 요구한다. 이는 안전하지 않은
설정 drift와 algorithm confusion을 쉽게 만들고 안정적인 decorator target도
제공하지 않는다.

## 목표

1. 지원하는 HMAC 및 RSA JWS 알고리즘으로 엄격한 동기 JWT 발급과 검증을
   제공한다.
2. 각 provider를 하나의 algorithm과 하나의 validation profile에 고정하여
   수신 header가 보안 정책을 선택하지 못하게 한다.
3. key, repository entry, claim, profile, snapshot, verified result를 불변
   Bluetape 소유 값으로 표현한다.
4. 숨겨진 scheduling 없이 로컬 key rotation을 atomic하게 만들고 active,
   retired, revoked 상태를 구분한다.
5. 호출자 소유 claims를 보존하고 선택적 time-claim 기본값을 명시적인
   issuance-profile 책임으로 둔다.
6. 이후 encryption 및 compression decorator가 합성할 수 있는 최소 provider
   protocol을 제공한다.
7. raw token string을 cache key로 보존하지 않고, key-state 변경 후 stale
   result를 수용하지 않는 bounded verified-result cache를 제공한다.
8. provider failure를 안정적이고 redacted된 Bluetape exception으로 변환한다.
9. algorithm, key, claim, cache, lifecycle 소유권을 영문과 국문으로 문서화한다.

## 범위 밖

- JWE encryption, nested JWT 구현 또는 content confidentiality: #89;
- compression, `zip` 또는 opaque compressed envelope: #90;
- async provider 또는 repository 계약: #88;
- Redis, MongoDB, SQL, filesystem, cloud KMS, HSM, Vault 또는 remote JWKS
  repository;
- header가 지시하는 `jku`, `jwk`, `x5u`, `x5c` 또는 기타 network retrieval;
- 자동 algorithm negotiation, mixed-family verification 또는 `none`;
- ECDSA, EdDSA, ECDH, AES JWE, PBES2 또는 승인된 9개 이외의 알고리즘;
- OAuth, OpenID Connect, login session, cookie, refresh flow, revocation list,
  blocklist 또는 application authorization;
- 보편적인 access-token, refresh-token 또는 service-token TTL 상수;
- background rotation, refresh, cleanup, scheduler, worker, detached thread,
  global registry, package-owned logging handler 또는 root logger 설정;
- package가 소유하는 environment variable, file, URL 또는 credential
  discovery에서 secret 수용;
- release, tag, publication, merge 또는 distributed key repository.

## 패키지 경계

```text
packages/bluetape-jwt/
├── pyproject.toml
├── README.md
├── README.ko.md
├── src/bluetape/jwt/
│   ├── __init__.py
│   ├── _algorithms.py
│   ├── _cache.py
│   ├── _claims.py
│   ├── _errors.py
│   ├── _keys.py
│   ├── _profiles.py
│   ├── _provider.py
│   └── _repository.py
└── tests/bluetape_jwt_tests/
    ├── test_algorithms.py
    ├── test_cache.py
    ├── test_claims.py
    ├── test_errors.py
    ├── test_keys.py
    ├── test_packaging.py
    ├── test_profiles.py
    ├── test_provider.py
    ├── test_repository.py
    └── test_security.py
```

- 배포 패키지: `bluetape-jwt`
- import: `bluetape.jwt`
- Python: `>=3.13`
- runtime dependency:
  - `bluetape-cache==0.1.0`
  - `joserfc>=1.7.4,<2`
- build backend: repository 표준 `uv_build`
- root namespace initializer: 없음
- 기본 `bluetape` dependency: 정확히 `bluetape-core==0.1.0`으로 유지
- meta extra: `bluetape[jwt]`는 `bluetape-jwt==0.1.0`을 설치
- 통합 `bluetape[all]`과 `bluetape[dev]`: 현재 aggregate-extra 관례에 따라
  목적별 package를 포함

workspace root는 표준 lint, test, build command가 배포 패키지를 발견하도록
member, local source, workspace dependency로 등록한다. 전용 CI workflow는
추가하지 않는다.

## Public API 분류

`bluetape.jwt.__all__`은 다음 분류 순서로 작고 검토된 surface를 export한다.

1. error;
2. algorithm과 key state;
3. 불변 key value, repository entry, snapshot;
4. repository protocol과 in-memory 구현;
5. claim 및 verified-token value;
6. issuance 및 validation profile;
7. provider protocol과 JWS 구현;
8. cache option.

내부 `joserfc` class, registry, token, claims registry, error는 절대 re-export하지
않는다. 정확한 symbol 순서와 signature 표기는 implementation plan과 package
export test에서 고정하지만, 이 명세의 behavioral contract가 권위 있는 기준이다.

## 알고리즘과 Key Material

```python
class JWSAlgorithm(StrEnum):
    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"
    PS256 = "PS256"
    PS384 = "PS384"
    PS512 = "PS512"


class KeyStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"
    REVOKED = "revoked"
```

모든 provider는 하나의 `JWSAlgorithm`을 받으며 algorithm collection은 받지
않는다. 검증은 key material을 선택하기 전에 protected header의 `alg`를 그
정확한 값과 비교한다.

public 불변 `JWTKey` wrapper는 다음 개념만 소유한다.

- 비어 있지 않고 길이가 제한된 `kid`;
- 정확한 `JWSAlgorithm`;
- HMAC 또는 RSA key family;
- signing capability와 verification-only capability의 구분;
- `repr`, `str`, exception, log에서 숨겨지는 복사된 key material.

`JWTKey`는 repository lifecycle 상태를 소유하지 않는다. `KeyStatus`는 전적으로
repository가 소유하고 snapshot의 public 불변 `KeyEntry`로 표현한다. 이렇게
material/capability와 상태를 분리하면 repository가 transition한 뒤에도 외부에서
보관한 `JWTKey`가 오래된 `ACTIVE` 또는 `RETIRED` 상태를 주장하는 문제를
방지한다.

factory method는 호출자가 제공한 HMAC bytes와 RSA PEM 또는 JWK 값을 받는다.
wrapper를 만들기 전에 algorithm family, key type, intended operation, provider
요구사항을 검증한다. HMAC secret은 선택한 알고리즘이 요구하는 strength를
충족해야 한다. RSA material은 RS/PS import 및 사용 시 modulus가 최소 2048
bits여야 한다. 이는 RFC 7518의 RSA key size 요구사항을 구현 경계에서 강제하여
약한 RSA key가 signing 또는 verification 경로에 진입하지 못하게 하기
위함이다. active signing 용도로 사용할 RSA key에는 private material이 있어야
하고, verification-only RSA key는 public material만 가질 수 있다. public JWK
export는 RSA public material에만 허용한다. 초기 public API는 private 또는
symmetric JWK export를 제공하지 않는다.

key wrapper는 효율을 위해 private internal provider object를 보관할 수 있지만,
그 object는 구현 세부사항으로 남는다. equality와 representation은 출력 가능한
secret material을 드러내거나 비교해서는 안 된다. key value는 일반적으로
hashable하지 않다.

## Repository 및 Rotation 계약

```python
class KeyRepository(Protocol):
    def snapshot(self) -> KeySnapshot: ...
    def add_verification_key(self, key: JWTKey) -> KeySnapshot: ...
    def rotate(self, key: JWTKey) -> KeySnapshot: ...
    def retire(self, kid: str) -> KeySnapshot: ...
    def revoke(self, kid: str) -> KeySnapshot: ...
```

public 불변 `KeyEntry`는 repository가 부여한 `status: KeyStatus`와
`key: JWTKey | None`을 포함한다. `ACTIVE` 및 `RETIRED` entry는 호환되는
`JWTKey` material을 보유하고, `REVOKED` entry는 tombstone만 나타내므로
`key is None`이어야 한다. caller는 `JWTKey` 자체에서 상태를 읽거나 변경할 수
없다.

`KeySnapshot`은 다음을 포함하는 불변 point-in-time view다.

- `kid`로 색인된 public read-only `Mapping[str, KeyEntry]`;
- zero or one `ACTIVE` entry;
- 검증에 사용할 수 있는 `ACTIVE` 및 `RETIRED` entry;
- 재사용 가능한 key material이 없는 `REVOKED` entry tombstone;
- 단조 증가하는 음이 아닌 epoch.

repository invariant:

1. `ACTIVE` entry는 최대 하나다.
2. `add_verification_key(key)`는 호환되는 verification-capable key를
   `RETIRED` `KeyEntry`로 직접 설치한다. RSA public-only key를 허용하고,
   signing key를 만들지 않으며, 중복 또는 tombstoned identifier를 거부하고,
   epoch를 정확히 한 번 증가시킨다.
3. `rotate(new_key)`는 signing-capable private 또는 symmetric material을
   요구하고 소유권을 취하기 전에 전체 candidate를 검증한다. RS/PS candidate는
   RSA modulus가 최소 2048 bits여야 한다.
4. 성공한 rotation은 이전 active entry를 `RETIRED`로 변경하고 새 entry를
   `ACTIVE`로 설치하며 epoch를 정확히 한 번 증가시킨다. `JWTKey` value 자체는
   상태 변경으로 다시 만들거나 변형하지 않는다.
5. `retire(kid)`는 active entry를 `RETIRED`로 변경하고 repository에 signing
   key가 없게 만들 수 있다. 이후 발급은 fail closed하고 검증은 계속된다.
6. `revoke(kid)`는 usable key material을 제거하고 `key=None`인 `REVOKED`
   `KeyEntry` tombstone을 보존하며, 해당 identifier의 향후 signing과
   verification을 거부한다.
7. 하나의 repository lifetime 안에서는 retirement 또는 revocation 이후
   `kid`를 재사용할 수 없다. rotation에는 새 identifier가 필요하다.
8. 누락, 중복, 비호환 또는 잘못된 state transition은 publication 전에
   exception을 발생시키며 snapshot이나 epoch를 변경하지 않는다.
9. 성공한 addition, rotation, retirement, revocation은 매번 epoch를 증가시켜
   provider cache가 이전 key state의 result를 재사용하지 못하게 한다.

`InMemoryKeyRepository`는 lock을 사용해 복사된 불변 snapshot을 atomic하게
publish한다. 빈 상태, 하나의 active signing key, 서로 다른 retired
verification key 0개 이상으로 시작할 수 있다. constructor validation은
atomic하며 이후 mutation과 동일한 identifier, family, capability, RSA modulus
규칙을 적용한다. clock이나 retention scheduler는 소유하지 않는다. retired
key를 revoke할 시점은 호출자가 결정한다.

## Claims 및 검증 결과

`TokenClaims`는 다음 typed registered claims를 포함하는 불변 issuance value다.

- `issuer: str | None` (`iss`)
- `subject: str | None` (`sub`)
- `audience: tuple[str, ...]` (`aud`)
- `expires_at: datetime | None` (`exp`)
- `not_before: datetime | None` (`nbf`)
- `issued_at: datetime | None` (`iat`)
- `jwt_id: str | None` (`jti`)
- `custom: Mapping[str, JSONValue]`

registered claim name은 `custom`에도 나타날 수 없다. claim name은 비어 있지
않은 string이어야 하고 custom value는 JSON-compatible해야 한다. 생성 시
mapping과 sequence를 방어적으로 복사하고 재귀적으로 freeze한다. 호출자
object는 절대 변경하지 않는다.

temporal input은 timezone-aware여야 한다. encoding은 입력 object를 바꾸지
않고 RFC 7519 `NumericDate` integer seconds로 변환한다. verification은
timezone-aware UTC datetime을 반환한다. 유효한 수신 JWT가 single-string form을
사용했더라도 caller에게는 audience를 불변 tuple로 normalize한다.

`VerifiedToken`은 불변이며 다음을 포함한다.

- 검증된 `kid`, algorithm, token type;
- typed registered claims;
- 재귀적으로 read-only인 custom claims;
- validation profile이 허용하는 안전한 read-only non-reserved header.

signature 및 claim validation이 완료된 뒤에만 생성한다. public unverified-token
result type은 제공하지 않는다.

## Issuance Profile

low-level `JWSProvider.issue()`는 caller의 `TokenClaims`에 registered claim을
조용히 추가·삭제·교체하지 않고 서명한다. 이는 application profile이
필수로 만들지 않는 한 registered claim을 선택 사항으로 두는 RFC 7519와
일치한다.

`IssuanceProfile`은 다음을 포함하는 선택적 불변 decorator policy다.

- `default_ttl: timedelta | None`;
- `max_ttl: timedelta | None`;
- 없을 때 `iat`를 추가할지 여부;
- 발급마다 하나의 reference time을 capture하는 injected wall clock.

규칙:

1. profile은 clock을 정확히 한 번 읽는다. effective issuance time은 caller가
   명시한 `iat`가 있으면 그 값이고, 없으면 capture한 reference time이다.
2. caller가 명시한 `iat`와 `exp`를 보존한다.
3. `iat`가 없고 생성하도록 설정했으면 capture한 reference time을 `iat`로
   emit한다.
4. `exp`가 없고 `default_ttl`이 finite하면 `iat`를 emit하지 않더라도
   `exp = effective_issuance_time + default_ttl`로 설정한다.
5. `default_ttl=None`은 default expiration claim이 없다는 뜻이며 far-future
   sentinel date를 encode하지 않는다.
6. 0 이하인 default 또는 maximum TTL은 invalid configuration이다.
7. `max_ttl`을 설정하면 lifetime은 `exp - effective_issuance_time`으로
   측정한다. 명시하거나 생성한 값이 이를 초과하면 clamp하거나 덮어쓰지 않고
   거부한다.
8. `exp <= effective_issuance_time` 또는 `exp <= nbf` 같은 잘못된 temporal
   ordering은 거부한다.

package는 7일, 365일, access-token, refresh-token 또는 service-token 상수를
publish하지 않는다. application은 자체적으로 문서화한 정책에 따라 named
profile을 구성한다.

## Validation Profile

`ValidationProfile`은 immutable하고 fingerprintable하다. 다음을 포함한다.

- 필수인 하나의 정확한 protected-header `typ` 값;
- 비어 있지 않은 allowed issuer frozen set;
- 비어 있지 않은 accepted audience frozen set;
- 필수 registered 및 custom claim name;
- 유한한 음이 아닌 clock skew;
- 선택적인 유한한 양의 maximum token age;
- 명시적으로 이름을 지정한 안전한 custom protected header 정책;
- 결정론적 temporal validation을 위한 injected wall clock.

`iss`와 `aud`는 이 security-focused profile에서 항상 필수이며 required-claim
set에서 제거할 수 없다. 수신 `iss`는 allowed issuer 하나와 정확히 같아야 한다.
수신 `aud`는 비어 있지 않은 string 또는 string array여야 하며 accepted
audience 중 하나 이상을 포함해야 한다. 비어 있는 configured set, blank value,
non-string member는 유효하지 않다. 다른 issuer 또는 audience 관계가 필요한
application은 호출 시 규칙을 약화하지 말고 별도 provider를 구성한다.
`max_token_age`를 설정하면 `iat`가 자동으로 필수가 되고, clock skew를 반영한
뒤 `now - iat`가 limit을 초과하면 token을 거부한다. clock skew를 넘는 future
`iat`도 거부한다. profile은 verification attempt마다 injected clock을 정확히
한 번 읽으며, 같은 capture 값을 `exp`, `nbf`, `iat`, maximum-age 검사와 cache
hit temporal recheck의 공통 reference time으로 사용한다.

각 `JWSProvider`는 생성 시 정확히 하나의 profile을 받는다. `verify()`에는
profile, issuer, audience, required-claim, leeway 또는 algorithm override가 없다.
access-token과 refresh-token 규칙이 필요한 application은 repository를 공유해도
별도 provider를 구성한다. 이는 서로 다른 JWT 종류에 상호 배타적인 validation
rule을 요구하는 RFC 8725와 일치한다.

profile fingerprint는 non-secret policy field를 canonicalize해 생성하며 profile
lifetime 동안 안정적이다. persistent identity로 Python의 randomized process
hash를 사용하지 않는다.

## Provider 및 Decorator 계약

```python
class TokenProvider(Protocol):
    def issue(self, claims: TokenClaims) -> str: ...
    def verify(self, token: str) -> VerifiedToken: ...
```

`JWSProvider`는 protocol을 구현하고 다음을 받는다.

- 하나의 `JWSAlgorithm`;
- 하나의 `KeyRepository`;
- 하나의 `ValidationProfile`;
- 선택적인 verified-result cache option.

issuance-profile wrapper도 `TokenProvider`를 구현한다. 불변 issuance policy에
따라 claims를 변환하고 issuance를 delegate하며 verification은 변경 없이
delegate한다. wrapped provider나 caller claims를 변경하지 않는다.

protocol은 compact JWS segment 수가 아니라 의미론적 input과 output을
의도적으로 기술한다. follow-up #89는 five-segment nested JWE를 반환할 수 있고
#90은 같은 issue/verify 계약을 유지하면서 versioned opaque envelope을 반환할
수 있다. core JWS provider 자체는 항상 표준 three-segment compact JWS JWT를
반환하고 수용한다.

## 발급 흐름

1. 불변 claims value와 issuance-profile result를 검증한다.
2. repository snapshot을 한 번 읽는다.
3. active signing key가 없으면 fail closed한다.
4. active `KeyEntry`에 material이 존재하고 그 key의 algorithm, family,
   capability가 provider와 정확히 일치하는지 확인한다.
5. provider 소유 값인 `alg`, `kid`, 정확한 validation-profile `typ`로 protected
   header를 구성한다.
6. caller가 reserved security header를 설정하거나 override하려는 시도를
   거부한다.
7. 복사된 claim payload를 encode하고 내부 restricted `joserfc` registry로
   서명한다.
8. compact token을 logging하거나 caching하지 않고 반환한다.

## 검증 흐름

1. `str`을 요구하고, 명시적인 maximum encoded-token size를 강제하며, JOSE
   parsing 전에 정확히 세 개의 비어 있지 않은 compact segment를 요구한다.
2. cache addressing을 위해 encoded token의 SHA-256을 계산한다. raw token은
   cache key로 절대 사용하지 않는다.
3. repository snapshot 하나를 읽고 token digest, validation-profile
   fingerprint, snapshot epoch로 cache key를 구성한다.
4. cache hit이면 반환하기 전에 profile clock의 이번 attempt용 단일 reference
   time으로 cached result의 temporal validity를 다시 검사한다.
5. miss이면 header structure, `alg`, `typ`, `kid`를 검증하는 데 충분한 bounded
   protected-header decoding을 수행한다. claims를 trusted data로 소비하지 않는다.
6. `none`, algorithm mismatch, 누락되거나 잘못된 `kid`, type mismatch, `jku`,
   `jwk`, `x5u`, `x5c`, `zip`, 알 수 없는 `crit`, duplicate JSON name, 승인되지
   않은 custom protected header를 거부한다.
7. capture한 local snapshot에서만 `kid`를 resolve한다. `ACTIVE` 또는 `RETIRED`
   상태이고 material이 존재하는 호환 `KeyEntry`만 허용한다. missing entry,
   `REVOKED` entry, material이 없는 entry를 거부한다.
8. provider의 하나뿐인 restricted algorithm 및 key family로 signature를
   검증한다.
9. claim type, required claim, issuer, audience, `exp`, `nbf`, `iat`, clock skew,
   optional maximum age를 하나의 public operation으로 검증한다. 모든 temporal
   검사는 step 4와 같은 단일 captured reference time을 사용한다.
10. 검증된 data를 복사하고 freeze하여 `VerifiedToken`을 만든다.
11. verified result를 cache에 저장하도록 설정한 경우 저장에 성공해야만 값을
    반환한다. `set` failure는 정상 verification success로 숨기지 않는다.

public operation은 cryptographic validation과 profile validation 전의 decoded
claims를 반환하지 않는다.

## Verified-Result Cache

호출자가 유한한 양의 cache TTL과 capacity option을 제공하지 않으면 caching은
비활성화된다. 구현은 `bluetape.cache.TTLCache`를 감싸며 새로운 범용 cache
abstraction을 만들지 않는다.

cache invariant:

- key: `(sha256(token_utf8), validation_profile_fingerprint, repository_epoch)`;
- value: 불변 `VerifiedToken`;
- effective TTL: `exp`가 있으면 configured cache TTL과 양의 remaining token
  lifetime 중 작은 값;
- `exp`가 없는 token: 항상 유한한 configured cache TTL 사용;
- capacity: 기존 LRU 동작을 사용하는 유한한 양의 maximum size;
- negative result: 절대 cache하지 않음;
- rotation: 변경된 repository epoch 때문에 이전 entry에 접근할 수 없으며,
  provider가 새 epoch를 관찰하면 stale data를 해제하도록 소유 cache를 clear함;
- cache hit: current temporal check를 절대 우회하지 않음;
- `TTLCache.get()`이 `KeyError`를 발생시키는 경우만 정상 cache miss로 취급함;
- 예상하지 못한 `get`, `set`, `clear` error는 redacted `JWTCacheError`로
  변환하여 propagate하며 verification을 계속하거나 성공으로 가장하지 않음;
- cache operation failure와 token verification failure 모두 cache miss로
  변환하지 않음.

cache는 provider가 소유하며 process-local이다. revocation list, distributed
consistency mechanism 또는 짧은 token lifetime의 대체물이 아니다. 예상하지
못한 cache terminal failure는 아래 module logging 계약에 따라 한 번 기록한 뒤
`JWTCacheError`로 propagate한다.

## 오류 계약과 Redaction

package는 `JWTError`를 root로 하는 안정적인 Bluetape exception을 공개한다.
public category는 다음을 구분한다.

- invalid configuration;
- invalid key material 또는 key state transition;
- unavailable signing key 또는 verification key;
- malformed 또는 unsupported token/header;
- signature verification failure;
- expired token;
- token not yet valid;
- invalid 또는 missing claim;
- issuance-policy violation;
- cache operation failure인 `JWTCacheError`.

내부 `joserfc`, JSON, decoding, cache, cryptography exception은 변환한다. public
message는 error category, 영향받은 public parameter name 또는 configured
algorithm name을 식별할 수 있다. caller 또는 token이 제공한 `kid` 값, raw
token, secret bytes, private/public PEM, JWK content, signature, claim value,
custom header, 전체 caller payload는 절대 되풀이해서는 안 된다. secret을
포함할 수 있는 underlying exception은 public cause chain에서 억제한다.

예상하지 못한 cache `get`, `set`, `clear` exception도 redacted
`JWTCacheError`로 변환하고 원래 exception text나 cache key를 노출하지 않은 채
호출자에게 propagate한다.

## 운영 Logging 계약

production lifecycle을 소유하는 `_repository`와 `_cache` module은 각각
`logging.getLogger(__name__)`으로 stdlib module logger를 만든다. package는
handler를 추가하거나 logger level, root logger, formatter 또는 전역 logging
상태를 설정하지 않는다.

다음 event만 기록한다.

- 성공한 `add_verification_key`, `rotate`, `retire`, `revoke` transition은
  `INFO`에서 한 번 기록한다.
- publication 전 실패한 repository transition은 `WARNING`에서 한 번 기록한 뒤
  원래의 redacted public exception을 propagate한다.
- 예상하지 못한 cache `get`, `set`, `clear` terminal failure는 `ERROR`에서 한 번
  기록한 뒤 redacted `JWTCacheError`를 propagate한다.

log message와 structured context는 stable low-cardinality `event`, `operation`,
`outcome`, `error_category`만 사용할 수 있다. raw token, token digest, `kid`,
claim/header value, secret, PEM/JWK, signature, key material, exception text,
stack-derived provider payload, repository epoch를 기록하지 않는다. 정상 cache
miss, cache hit, token issue/verify success, 유효하지 않은 외부 token은 module
logger에서 기록하지 않는다. caller는 public exception을 자체 정책에 따라
추가로 관찰할 수 있다.

## 동시성과 소유권

- `InMemoryKeyRepository`는 concurrent synchronous reader와 mutation에
  안전하다.
- provider는 issue 또는 verify attempt마다 하나의 immutable snapshot만
  사용하며, 한 epoch의 key와 다른 epoch의 cache metadata를 결합하지 않는다.
- issue 및 verify operation은 repository snapshot을 capture할 때 linearize된다.
  rotation 또는 revocation은 새 epoch가 publish된 뒤 snapshot을 capture한
  operation에 영향을 준다.
- 이전 immutable snapshot으로 이미 검증 중인 operation은 완료될 수 있다.
  concurrent revoke가 진행되더라도 그 operation의 authorization point는 이전
  snapshot capture이며, result는 이전 epoch로만 keying된다. 완료 전에 현재
  repository epoch가 달라졌다고 확인되면 current-epoch cache entry를 publish할
  수 없고, 어떤 경우에도 revoked material을 current snapshot으로 재해석하거나
  current-epoch result로 승격할 수 없다.
- revocation publication 후 snapshot을 capture한 operation은 `REVOKED`
  `KeyEntry`의 `key=None` tombstone만 관찰하므로 revoked material을 사용할 수
  없다.
- rotation은 완전한 state를 publish하거나 아무 state도 publish하지 않는다.
  failed validation은 key를 부분적으로 retire하거나 install할 수 없다.
- cache operation은 `TTLCache`가 소유한 synchronization을 재사용한다.
- wall-clock claim validation과 monotonic cache expiration은 분리한다.
- injected key, repository, clock, wrapped provider는 명시적으로 달리 문서화하지
  않는 한 caller-owned다. package는 caller resource를 몰래 close, refresh,
  replace하지 않는다.

## 문서화

구현 시 다음 문서를 업데이트한다.

- package `README.md`와 `README.ko.md`: API, lifecycle, threat boundary,
  rotation, cache, decorator example을 서로 일치시킴;
- root `README.md`와 `README.ko.md`: package 및 installation table;
- delivery 진행 중 root `WIP.md`;
- user-facing package 완료 후 root `CHANGELOG.md`;
- rotation/cache flow의 이해를 실질적으로 돕고 repository diagram workflow를
  따를 때만 architecture 또는 sequence visual.

문서에는 signed JWT payload를 읽을 수 있다는 점, retired key가 계속 검증된다는
점, publish된 revocation이 새 verification attempt를 거부한다는 점, 이미 실행
중인 attempt는 capture한 snapshot으로 완료될 수 있다는 점, `exp` 누락 시
non-expiring token이 될 수 있다는 점, cache는 revocation이 아니라는 점,
JWE/compression은 별도 follow-up capability라는 점을 명시해야 한다.

## 후속 이슈

- [#88](https://github.com/bluetape4k/bluetape-py/issues/88): async JWT
  repository 및 provider 계약;
- [#89](https://github.com/bluetape4k/bluetape-py/issues/89): nested
  sign-then-encrypt validation을 사용하는 JWE token-provider decorator;
- [#90](https://github.com/bluetape4k/bluetape-py/issues/90): opt-in bounded
  token compression decorator.

distributed Redis, MongoDB, SQL, KMS, HSM, Vault, remote-JWKS adapter는 동기
repository 계약이 입증된 뒤 별도의 source-backed issue가 필요하다. #88, #89,
#90에 암묵적으로 포함하지 않는다.

## 테스트 전략

### 알고리즘과 Key

- 9개 알고리즘 각각으로 issue 및 verify;
- verification 전에 provider/header algorithm mismatch 거부;
- HMAC/RSA family confusion과 incompatible key operation 거부;
- weak HMAC secret, public-only signing key, 2048-bit 미만 RSA modulus,
  invalid PEM/JWK, invalid `kid`, key identifier reuse 거부;
- RSA private import, direct retired public-key registration,
  public-only verification interoperability 검증;
- RS/PS import와 issue/verify 경로 모두에서 RSA modulus 최소 2048 bits 강제;
- key 및 error representation에 secret material이 없음을 입증.

### Claims 및 Profile

- caller input을 변경하지 않고 명시적인 registered claim과 nested custom
  claim 보존;
- reserved-name collision 및 non-JSON custom value 거부;
- aware-datetime 및 NumericDate boundary 검증;
- valid, expired, not-before, future-issued, issuer, audience, required claim,
  token type, skew, maximum-age case 포함;
- issuer exact match와 audience 교집합 match를 각각 검증하고 빈 값,
  wrong type, 불일치 case 거부;
- issuance default가 누락된 값만 채움을 입증;
- `max_ttl` 이내와 초과 explicit lifetime 포함;
- `default_ttl=None`이 sentinel date를 만들지 않고 `exp`를 생략함을 입증;
- explicit `iat`가 있는 경우와 없는 경우 모두 effective issuance time 규칙 검증;
- verification attempt마다 clock을 한 번만 읽고 모든 temporal check가 같은
  captured reference time을 사용함을 입증;
- 서로 다른 profile이 상대의 token type 또는 audience를 수용할 수 없음을 검증.

### Rotation 및 동시성

- empty repository issuance failure;
- initial active key, atomic rotation, old-key retired verification, new-key
  issuance, explicit retirement, revocation, tombstone 동작;
- `JWTKey`에는 status가 없고 `KeyEntry`가 repository-owned status를 나타냄을
  검증;
- `REVOKED` `KeyEntry`가 material을 포함하지 않고 이전 `JWTKey` reference가
  repository state를 변경하거나 stale status를 주장할 수 없음을 검증;
- failed rotation은 key state와 epoch를 변경하지 않음;
- successful mutation마다 epoch가 정확히 한 번 증가;
- concurrent reader는 완전한 old snapshot 또는 new snapshot만 관찰;
- revocation 후 capture한 operation은 revoked material을 사용하지 않음;
- in-flight old-snapshot verification은 old epoch에서만 완료될 수 있고
  current-epoch cache result를 publish할 수 없음;
- concurrent revoke와 verification을 barrier로 제어하여 snapshot capture 전후
  linearization 규칙과 current-epoch 승격 금지를 결정론적으로 입증.

### Cache

- default-disabled 동작;
- digest/profile/epoch key 분리;
- hit, `KeyError` miss, bounded capacity, LRU eviction, finite TTL, expiration;
- effective TTL이 token `exp`보다 오래 지속되지 않음;
- cache hit가 temporal validity를 다시 검사;
- rotate, retire, revoke가 이전 cached verification result를 무효화;
- invalid signature, malformed token, claim failure를 cache하지 않음;
- cache key 및 diagnostic에 raw token이 없음;
- 예상하지 못한 `get`, `set`, `clear` failure를 redacted `JWTCacheError`로
  변환하고 propagate하며 verification success 또는 miss로 숨기지 않음;
- repository lifecycle transition이 정확히 한 번 low-cardinality event를
  기록하고 `kid`, key material, epoch를 포함하지 않음;
- repository transition failure 및 cache terminal failure가 지정된 level과
  redacted category로 정확히 한 번 기록되며 정상 cache miss와 invalid token은
  기록되지 않음;
- module import와 instance construction이 handler, root level 또는 전역 logging
  state를 변경하지 않음.

### 적대적 입력과 오류

- 과도한 token 및 `kid` 크기;
- invalid base64url, JSON, duplicate name, segment count, header type;
- `none`, `jku`, `jwk`, `x5u`, `x5c`, `zip`, unknown `crit`, 승인되지 않은
  custom header;
- wrong signature, missing key, retired-versus-revoked 동작, internal provider
  failure;
- redacted message와 safe cause chain을 갖춘 안정적인 Bluetape exception
  category.

### 합성과 Packaging

- fake decorator가 `TokenProvider`를 감싸고 issue output을 변환하며 verify 전에
  변환을 되돌리고 verified result를 보존;
- package export와 `py.typed` metadata;
- 기본 `bluetape`는 core-only를 유지하고 `bluetape[jwt]`는 package 설치;
- `bluetape/__init__.py` 없이 root namespace package 동작 유지;
- wheel/sdist metadata 및 clean-environment import smoke test.

## 검증 Gate

이 변경은 package, workspace dependency, lockfile entry, meta extra를 추가하므로
targeted implementation verification 이후 전체 workspace 검증으로 확대한다.

```bash
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv run pytest packages/bluetape-jwt
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build --all-packages
actionlint
git diff --check
```

built artifact를 대상으로 import 및 metadata smoke test를 수행한다. PR을
merge-ready로 보고하기 전에 정확한 implementation head에서 security review가
P0=0 및 P1=0을 보고해야 한다. 같은 정확한 head에서 CI, current review,
unresolved thread, 필요한 human-review artifact를 다시 확인해야 한다.

## 완료 조건

- 승인된 spec 및 implementation plan을 commit;
- 위의 모든 public behavior와 threat boundary를 구현하고 테스트;
- 영문 및 국문 documentation 정합성 유지;
- follow-up boundary #88, #89, #90을 implementation scope 밖에 유지;
- targeted 및 full verification gate를 fresh evidence로 통과;
- exact-head security review가 P0=0 및 P1=0을 기록;
- Type A lesson file에 재사용 가능한 design 또는 implementation learning을
  기록하거나 workflow가 허용하는 경우에만 evidence-backed `N/A` 제공;
- PR body가 workflow에서 요구하는 `## DoD Status` section으로 끝남;
- merge, release, tag, publication은 별도의 명시적 approval gate로 유지.

## 해결된 질문

implementation planning에 필요한 모든 설계 질문이 해결되었다. implementation
plan은 private file placement와 정확한 export order를 다듬을 수 있지만, 여기에
정의된 algorithm, profile, repository-owned key state, cache failure,
redaction, decorator, follow-up boundary를 약화해서는 안 된다.
