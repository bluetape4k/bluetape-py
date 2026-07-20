# Issue #18 JWT 및 Key Rotation Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `bluetape-jwt`에 9개 승인 JWS 알고리즘, 엄격한 typed claim 검증, atomic local key rotation, optional bounded verified-result cache, 향후 encryption/compression wrapper가 합성할 수 있는 동기 `TokenProvider` 계약을 구현한다.

**Architecture:** `bluetape.jwt`는 Bluetape 소유의 불변 key/claim/profile 값을 공개하고 `joserfc`는 제한된 JWS registry와 strict JSON decoder 뒤에 숨긴다. `InMemoryKeyRepository`는 immutable snapshot과 epoch를 lock 아래 atomic publish한다. `JWSProvider`는 하나의 algorithm·repository·validation profile에 고정되고, `IssuanceProfileProvider`만 low-level provider를 decorate한다. 선택적인 내부 cache adapter는 기존 `bluetape.cache.TTLCache`를 사용한다.

**Tech Stack:** Python 3.13.14, stdlib dataclasses/enum/typing/datetime/json/hashlib/logging/threading, `joserfc>=1.7.4,<2`, `bluetape-cache==0.1.0`, uv workspace와 `uv_build`, pytest, Ruff, isolated wheel smoke tests, Lore commits.

---

## 승인 입력과 정지 경계

- 승인 spec: `docs/superpowers/specs/2026-07-20-issue-18-jwt-key-rotation-design.md`
- spec review: `docs/superpowers/reviews/2026-07-20-issue-18-jwt-key-rotation-step-2r-spec-review.md`
- issue/milestone: #18 / `0.2.0`
- repo/base/head: `bluetape4k/bluetape-py`, `develop`, `feat/issue-18-jwt-key-rotation`
- distribution/import: `bluetape-jwt==0.1.0`, `bluetape.jwt`
- runtime: `bluetape-cache==0.1.0`, `joserfc>=1.7.4,<2`
- follow-up: async #88, JWE #89, compression #90
- 사용자는 revised spec과 implementation planning 진입을 승인했다.
- 이 plan은 local implementation, test, 문서, review artifact, commit까지만
  승인 대상으로 제안한다. push, PR, merge, issue closure, tag, release,
  publication, workflow dispatch, destructive cleanup은 이후 별도 gate다.

## 실행 규칙

- `.worktrees/feat-issue-18-jwt-key-rotation`의 해당 feature branch에서만 작업한다.
- 각 behavior family는 focused test -> 의도한 RED -> 최소 GREEN -> owning test
  file 순서로 진행한다. import/fixture 오류나 이미 통과한 RED는 증거가 아니다.
- token, digest, `kid`, claims/header 값, secret, PEM/JWK, signature, 내부 exception
  text, epoch를 package message, `repr`, log, review artifact에 노출하지 않는다.
- provider마다 algorithm/profile은 하나뿐이다. verify 호출별 override를 만들지 않는다.
- `joserfc`와 `TTLCache` 타입은 public API에서 숨긴다. remote lookup이나
  `authlib.jose`를 추가하지 않는다.
- cache는 default-disabled다. `KeyError`만 miss이며 다른 failure는 propagate한다.
- JWE, compression, async, distributed repository, remote JWKS, background worker는
  구현하지 않는다.
- production/test에 미완성 작업 표식이나 빈 동작 branch, universal token TTL,
  global registry, package-owned logging handler를 남기지 않는다.
- 각 commit은 Lore protocol과 fresh `Tested:` evidence를 포함한다. head가 바뀌면
  영향을 받은 test/review/verifier evidence를 새 head에서 다시 만든다.

## Artifact Map과 Spec Coverage

| 책임 | 파일 | Task |
|---|---|---|
| package/error/algorithm | root/meta/package `pyproject.toml`, `uv.lock`, `_errors.py`, `_algorithms.py` | 1 |
| key material/strength | `_keys.py`, `test_keys.py` | 2 |
| repository/rotation/log | `_repository.py`, `test_repository.py` | 3 |
| claims/profiles | `_claims.py`, `_profiles.py`, 관련 tests | 4 |
| strict JOSE/provider | `_provider.py`, `test_provider.py`, `test_security.py` | 5 |
| issuance decorator | `_issuance.py`, `test_issuance.py` | 6 |
| bounded cache | `_cache.py`, `test_cache.py` | 7 |
| hostile/concurrency/log matrix | package security/repository/cache/logging tests | 8 |
| package/docs/release inventory | README pairs, wheel tests, WIP, CHANGELOG, package layout, preflight | 9 |
| full validation/review/lesson | `docs/review`, `docs/lessons`, WIP | 10 |

Spec의 package boundary, 9개 algorithm, key strength, repository-owned lifecycle,
typed claims, single clock capture, strict header/claim 검증, decorator, cache
digest/profile/epoch, redaction/logging, hostile/concurrency/packaging 전략은 위 task에
각각 일대일로 연결한다.

## 3-P Risk Prediction

| 위험 | 예방/증거 | rollback |
|---|---|---|
| algorithm confusion | exact header precheck + one-item registry + family tests | Task 5 revert |
| secret leak | fixed messages, `from None`, canary scans | owning error/key commit revert |
| weak key | HS hash-width minimum, RSA >=2048 at import/use | Task 2 revert |
| stale revoke cache | snapshot epoch key, clear, barrier tests | Task 7 revert; uncached provider 유지 |
| profile drift | immutable constructor-only policy, canonical fingerprint | Tasks 4-5 revert |
| duplicate JSON bypass | bounded header preparse와 strict header/payload decoder | Task 5 revert |
| cache failure concealment | `KeyError` only miss, `JWTCacheError` tests | Task 7 revert |
| logging disclosure | exact level/count/allowed-field tests | Tasks 3/7 revert |
| default install widening | wheel metadata/blocked-import smoke | Task 1/9 metadata revert |

## Exact Production Blueprint

### Public exports

```python
__all__ = [
    "JWTError", "JWTConfigurationError", "JWTKeyError", "JWTKeyStateError",
    "JWTKeyUnavailableError", "JWTTokenError", "JWTMalformedTokenError",
    "JWTUnsupportedTokenError", "JWTSignatureError", "JWTExpiredError",
    "JWTNotYetValidError", "JWTClaimError", "JWTIssuancePolicyError",
    "JWTCacheError", "JWSAlgorithm", "KeyStatus", "JSONValue", "JWTKey",
    "KeyEntry", "KeySnapshot", "KeyRepository", "InMemoryKeyRepository",
    "TokenClaims", "VerifiedToken", "IssuanceProfile", "ValidationProfile",
    "TokenProvider", "IssuanceProfileProvider", "JWSProvider",
    "VerifiedTokenCacheOptions",
]
```

`JSONValue`는 public recursive annotation이다. mapping은 `MappingProxyType`,
sequence는 tuple로 defensive freeze한다. bytes/set/custom object와 NaN/Infinity,
cycle, depth 32 초과, node 10,000개 초과는 거부한다. caller value overflow는
`JWTClaimError`, signed payload의 같은 위반은 `JWTMalformedTokenError`로 변환한다.

### Fixed limits와 strict header

```python
_MAX_KID_BYTES = 128
_MAX_TOKEN_BYTES = 16_384
_MAX_PROTECTED_HEADER_BYTES = 512
_MAX_JSON_DEPTH = 32
_MAX_JSON_NODES = 10_000
_REGISTERED_CLAIMS = frozenset({"iss", "sub", "aud", "exp", "nbf", "iat", "jti"})
_RESERVED_HEADERS = frozenset({
    "alg", "kid", "typ", "crit", "jku", "jwk", "x5u", "x5c",
    "x5t", "x5t#S256", "cty", "b64", "zip",
})
```

식별자/name/value는 blank, surrounding whitespace, NUL, bound 초과를 거부한다.
`kid`는 UTF-8 byte 수로 제한한다. custom protected header는
`ValidationProfile.protected_headers: Mapping[str, str]`의 exact non-blank 값만
허용하고 reserved name을 거부한다. issue 때 emit하고 verify 때 exact-match한다.
호출별 header 입력은 없다.

private `_StrictJSONDecoder`는 duplicate object name을 거부한다. protected header는
bounded base64url decode 후 먼저 strict decode한다. `JWSRegistry`는 default 전체가
아니라 `alg`, `kid`, `typ`, profile custom header만 등록하고
`algorithms=[algorithm.value]`, `strict_check_header=True`를 사용한다. payload에도
같은 decoder class를 전달한다.

### Public signatures

```python
class JWTKey:
    @classmethod
    def from_hmac_secret(cls, kid: str, algorithm: JWSAlgorithm, secret: bytes) -> "JWTKey": ...

    @classmethod
    def from_rsa_private(
        cls, kid: str, algorithm: JWSAlgorithm,
        material: str | bytes | Mapping[str, object], *, password: bytes | None = None,
    ) -> "JWTKey": ...

    @classmethod
    def from_rsa_public(
        cls, kid: str, algorithm: JWSAlgorithm,
        material: str | bytes | Mapping[str, object],
    ) -> "JWTKey": ...

    @property
    def kid(self) -> str: ...
    @property
    def algorithm(self) -> JWSAlgorithm: ...
    @property
    def can_sign(self) -> bool: ...
    def public_jwk(self) -> Mapping[str, str]: ...
```

`JWTKey`는 frozen/slotted/repr-disabled/identity-equality/unhashable이다. HMAC minimum
bits는 HS256=256, HS384=384, HS512=512다. RSA modulus는 provider key의 public
numbers 기준 2048 bits 이상이다. HMAC export와 RSA private material export는
금지한다. RSA private/public wrapper의 `public_jwk()`는 모두 `kty`, `kid`, `alg`,
`n`, `e` public projection만 새 immutable mapping으로 반환한다.
RSA JWK metadata는 fail-closed matrix를 적용한다. `alg`가 있으면 selected RS/PS
algorithm과 같아야 하고, `use`가 있으면 `sig`만 허용한다. private factory의
`key_ops`가 있으면 `sign`과 `verify`를 정확히 모두 포함해야 하고 public
factory는 `verify`만 허용한다. 검증된 caller-owned `key_ops` list는 dependency
validation과 dependency import 전에 snapshot한다. absent metadata는 wrapper
arguments로 policy를 부여한다.
unknown/encryption operation 또는 conflicting `kid`는 거부한다. 이 exact private
policy는 `joserfc`가 sign-only key의 verification을 거부하는 실제 동작에 맞춰
active signing key의 verification capability를 보존한다.

```python
@dataclass(frozen=True, slots=True)
class KeyEntry:
    status: KeyStatus
    key: JWTKey | None

@dataclass(frozen=True, slots=True)
class KeySnapshot:
    entries: Mapping[str, KeyEntry]
    epoch: int
    @property
    def active(self) -> KeyEntry | None: ...

class KeyRepository(Protocol):
    def snapshot(self) -> KeySnapshot: ...
    def add_verification_key(self, key: JWTKey) -> KeySnapshot: ...
    def rotate(self, key: JWTKey) -> KeySnapshot: ...
    def retire(self, kid: str) -> KeySnapshot: ...
    def revoke(self, kid: str) -> KeySnapshot: ...

class InMemoryKeyRepository:
    def __init__(
        self, *, active: JWTKey | None = None,
        verification_keys: Iterable[JWTKey] = (),
    ) -> None: ...
```

`REVOKED` entry는 `key=None`, active/retired entry는 material 필수다. constructor는
epoch 0 snapshot을 atomic publish하고 성공 mutation만 epoch를 정확히 1 올린다.
repository는 첫 material이 정한 정확한 algorithm에 lifetime 동안 결합한다.
bootstrap/add/rotate의 다른 algorithm 또는 family는 publication 전에 거부한다.

```python
@dataclass(frozen=True, slots=True)
class TokenClaims:
    issuer: str | None = None
    subject: str | None = None
    audience: tuple[str, ...] = ()
    expires_at: datetime | None = None
    not_before: datetime | None = None
    issued_at: datetime | None = None
    jwt_id: str | None = None
    custom: Mapping[str, JSONValue] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class VerifiedToken:
    kid: str
    algorithm: JWSAlgorithm
    token_type: str
    issuer: str
    subject: str | None
    audience: tuple[str, ...]
    expires_at: datetime | None
    not_before: datetime | None
    issued_at: datetime | None
    jwt_id: str | None
    custom: Mapping[str, JSONValue]
    headers: Mapping[str, str]
```

`VerifiedToken.headers`는 profile이 승인하고 exact-match된 custom non-reserved
protected header만 immutable하게 포함한다. `alg`, `kid`, `typ`와 다른 reserved
header는 전용 field 또는 rejection 경계에만 존재하며 이 mapping에 중복되지 않는다.

datetime input은 aware여야 하며 UTC로 normalize한다. 발급 payload는 integer
NumericDate를 쓰고 수신 NumericDate는 bool을 제외한 finite int/float만 허용하며,
verified result는 UTC datetime이다. profile이 `iss`/`aud`를 항상 요구하므로
`VerifiedToken.issuer`와 `audience`는 non-optional이다.

```python
@dataclass(frozen=True, slots=True)
class IssuanceProfile:
    default_ttl: timedelta | None = None
    max_ttl: timedelta | None = None
    add_issued_at: bool = True
    clock: Callable[[], datetime] = _utc_now

@dataclass(frozen=True, slots=True)
class ValidationProfile:
    token_type: str
    allowed_issuers: frozenset[str]
    accepted_audiences: frozenset[str]
    required_claims: frozenset[str] = frozenset()
    protected_headers: Mapping[str, str] = field(default_factory=dict)
    clock_skew: timedelta = timedelta(0)
    max_token_age: timedelta | None = None
    clock: Callable[[], datetime] = _utc_now

class TokenProvider(Protocol):
    def issue(self, claims: TokenClaims) -> str: ...
    def verify(self, token: str) -> VerifiedToken: ...

class IssuanceProfileProvider:
    def __init__(self, provider: TokenProvider, profile: IssuanceProfile) -> None: ...

@dataclass(frozen=True, slots=True)
class VerifiedTokenCacheOptions:
    default_ttl: timedelta
    max_size: int

class JWSProvider:
    def __init__(
        self, algorithm: JWSAlgorithm, repository: KeyRepository,
        validation_profile: ValidationProfile, *,
        cache: VerifiedTokenCacheOptions | None = None,
    ) -> None: ...
```

profile constructor는 policy 값만 검증/freeze하고 required claims에 `iss`/`aud`를,
max age 사용 시 `iat`를 포함한다. fingerprint는 clock identity를 제외한 canonical
policy JSON의 SHA-256이다. claims 변환은 Task 6의 private pure function
`_apply_issuance_profile(claims, profile, *, now) -> TokenClaims` 하나가 소유하며
decorator가 clock을 한 번 capture해 호출한다.

`_repository`와 `_cache`만 stdlib module logger를 만든다. fixed message는
`jwt_repository_transition`, `jwt_cache_operation`; context는 `event`, `operation`,
`outcome`, `error_category`만 허용한다. success transition=INFO 한 번,
failed transition=WARNING 한 번, terminal cache failure=ERROR 한 번이다.

cache failure test seam은 private
`_VerifiedTokenCache(options, *, cache_factory: Callable[..., TTLCache] = TTLCache)`로
고정한다. production은 default factory만 쓰고 test는 get/set/clear가 지정된
exception을 내는 fake cache factory를 주입한다.

> 위 protocol body의 `...`는 Python protocol/stub 표기이며 production placeholder를
> 허용한다는 의미가 아니다.

## Mandatory TDD Microcycle Ledger

아래 ledger가 task의 batch RED/GREEN보다 우선한다. 각 행을 독립적으로 test
function 작성 -> 해당 node의 예상 failure 확인 -> 최소 production slice 작성 ->
같은 node GREEN 순서로 완료한 뒤에만 task-level suite를 실행한다.

| Task | named microstep / test node | intended RED | minimum GREEN slice |
|---|---|---|---|
| 1 | `test_algorithms.py::test_algorithm_values_are_exact` | enum import/value failure | `JWSAlgorithm` 9 values |
| 1 | `test_errors.py::test_public_errors_are_redacted` | exception import/message failure | error hierarchy/constants |
| 1 | `test_packaging.py::test_workspace_registers_jwt` | metadata assertion failure | package/workspace/meta entries |
| 2 | `test_keys.py::test_hmac_strength_matches_hash_width` | factory missing/reject absent | HMAC factory + bit gate |
| 2 | `test_keys.py::test_rsa_jwk_metadata_matches_intended_operation` | conflicting metadata accepted | exact JWK metadata validator |
| 2 | `test_keys.py::test_rsa_modulus_is_at_least_2048_bits` | weak key accepted | modulus gate |
| 2 | `test_keys.py::test_public_jwk_contains_no_private_material` | export missing/private field | public projection |
| 3 | `test_repository.py::test_snapshot_enforces_entry_invariants` | value type/invariant missing | frozen entry/snapshot |
| 3 | `test_repository.py::test_rotate_retires_old_active_once` | transition missing/wrong epoch | locked publish helper |
| 3 | `test_repository.py::test_failed_transition_preserves_snapshot` | partial mutation/log mismatch | validate-before-publish + log |
| 3 | `test_repository.py::test_concurrent_readers_see_complete_snapshot` | partial state/race failure | immutable snapshot under RLock |
| 4 | `test_claims.py::test_custom_claims_are_deeply_frozen` | caller mutation visible | budgeted `_freeze_json` |
| 4 | `test_claims.py::test_numeric_date_rejects_bool_and_overflow` | bool/overflow accepted | strict NumericDate conversion |
| 4 | `test_profiles.py::test_validation_profile_fingerprint_is_stable` | unstable/missing fingerprint | canonical policy digest |
| 5 | `test_provider.py::test_provider_round_trips_each_algorithm` | provider missing | issue/signature/typed result happy path |
| 5 | `test_security.py::test_algorithm_mismatch_fails_before_key_resolution` | wrong error precedence | bounded header preflight |
| 5 | `test_security.py::test_duplicate_payload_name_is_rejected` | duplicate accepted | strict payload decoder |
| 5 | `test_provider.py::test_verified_headers_are_custom_only` | reserved fields leak | custom-only result projection |
| 6 | `test_issuance.py::test_issuance_profile_fills_only_missing_times` | decorator missing | pure transform + delegation |
| 6 | `test_issuance.py::test_issuance_profile_rejects_excess_lifetime` | over-limit delegated | max-TTL guard |
| 7 | `test_cache.py::test_cache_key_uses_digest_profile_and_epoch` | cache missing/raw token key | `_CacheKey` + adapter |
| 7 | `test_cache.py::test_cache_hit_rechecks_current_time` | stale result returned | profile temporal recheck |
| 7 | `test_cache.py::test_revoke_race_never_publishes_current_epoch` | wrong epoch publish | post-verify epoch guard |
| 7 | `test_cache.py::test_cache_get_failure_is_not_a_miss` | failure swallowed | strict adapter exception mapper |
| 8 | `test_logging.py::test_logging_contract_has_no_sensitive_fields` | unexpected record/context | exact event helpers |

각 node command는 같은 형식으로 실행한다.

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_keys.py::test_hmac_strength_matches_hash_width -q
```

예를 들어 첫 HMAC microcycle의 test와 최소 implementation shape는 다음과 같다.

```python
@pytest.mark.parametrize(
    ("algorithm", "minimum_bytes"),
    [(JWSAlgorithm.HS256, 32), (JWSAlgorithm.HS384, 48), (JWSAlgorithm.HS512, 64)],
)
def test_hmac_strength_matches_hash_width(algorithm, minimum_bytes):
    key = JWTKey.from_hmac_secret("current", algorithm, b"x" * minimum_bytes)
    assert key.can_sign is True
    with pytest.raises(JWTKeyError):
        JWTKey.from_hmac_secret("weak", algorithm, b"x" * (minimum_bytes - 1))
```

```python
def _require_hmac_strength(algorithm: JWSAlgorithm, secret: bytes) -> None:
    minimum_bits = {"HS256": 256, "HS384": 384, "HS512": 512}[algorithm.value]
    if len(secret) * 8 < minimum_bits:
        raise JWTKeyError("invalid key material")
```

대표 strict-header microcycle은 key resolver spy가 호출되지 않은 상태까지 assert한다.

```python
def test_algorithm_mismatch_fails_before_key_resolution(provider, repository_spy, wrong_alg_unknown_kid_token):
    with pytest.raises(JWTUnsupportedTokenError):
        provider.verify(wrong_alg_unknown_kid_token)
    assert repository_spy.snapshot_calls == 1
```

대표 cache-failure microcycle은 private injection seam을 통해 `KeyError`와 terminal
failure를 분리한다.

```python
def test_cache_get_failure_is_not_a_miss(cache_options, failing_factory):
    cache = _VerifiedTokenCache(cache_options, cache_factory=failing_factory)
    with pytest.raises(JWTCacheError, match="cache operation failed"):
        cache.get(_cache_key())
```

Task-level suite는 위 node들이 각각 valid RED/GREEN을 가진 뒤의 consolidation
evidence다. 한 batch failure를 여러 production families의 RED로 재사용하지 않는다.

## Task 1: package/error/algorithm boundary를 등록한다

**Depends on:** 승인된 spec과 implementation plan

**Files:** Create `packages/bluetape-jwt/{pyproject.toml,README.md,README.ko.md}`,
`src/bluetape/jwt/{__init__.py,_errors.py,_algorithms.py,py.typed}`,
`tests/bluetape_jwt_tests/{__init__.py,test_errors.py,test_algorithms.py,test_packaging.py}`;
modify root/meta `pyproject.toml`, `uv.lock`, `WIP.md`.

- [ ] exact dependencies/member/source, `bluetape[jwt]`, dev/all inclusion, core-only
  default, no root initializer, `py.typed` packaging tests를 작성한다. Task 1의
  `__all__`은 실제 구현된 errors와 algorithms만 export한다.
- [ ] exception hierarchy, fixed safe messages, suppressed cause, canary absence와
  exact 9-value enum/family tests를 작성한다.
- [ ] RED:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_packaging.py \
  packages/bluetape-jwt/tests/bluetape_jwt_tests/test_errors.py \
  packages/bluetape-jwt/tests/bluetape_jwt_tests/test_algorithms.py -q
```

  예상: package/exports가 없어서 collection 또는 exact assertion failure.

- [ ] package metadata는 `requires-python = ">=3.13"`, dependencies는 exact
  `bluetape-cache==0.1.0`, `joserfc>=1.7.4,<2`, build backend는 repository 표준
  `uv_build`와 module-name `bluetape.jwt`로 구현한다.
- [ ] meta에 `jwt` extra와 dev/all aggregate를 추가하되 default dependency는
  정확히 `bluetape-core==0.1.0`으로 유지한다.
- [ ] `uv lock --python 3.13.14` 후 승인 dependency 외 unexpected addition을
  diff에서 확인한다.
- [ ] GREEN:

```bash
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_errors.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_algorithms.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_packaging.py -q
```

- [ ] Lore commit intent: `Establish the isolated JWT security boundary`.
  `Constraint:` core-only default와 joserfc <2, `Rejected:` joserfc re-export,
  `Tested:` packaging/error/algorithm RED-GREEN을 기록한다.

## Task 2: immutable key material과 strength gate를 구현한다

**Depends on:** Task 1

**Files:** Create `_keys.py`, `test_keys.py`; modify public `__init__.py`.

- [ ] HS256/384/512 exact minimum success와 one-byte-short failure를 parameterize한다.
- [ ] RSA private/public PEM/JWK import, public JWK round-trip, signing capability,
  public-only verification, 1024-bit rejection을 RS/PS family에 걸쳐 test한다.
- [ ] HMAC/RSA confusion, public signing, invalid material/password, invalid `kid`,
  HMAC export와 RSA private-material export를 거부한다.
- [ ] JWK의 `kid`, `alg`, `use`, `key_ops`가 wrapper의 identifier, algorithm,
  capability와 충돌하면 dependency import 전에/직후 fail closed함을 test한다.
  absent metadata, exact `alg`, `use="sig"`, private exact `sign`+`verify`, public
  exact `verify`만 positive이고 private sign-only, `enc`, encryption operation,
  wrong algorithm/kid, unknown operation은 모두 negative인 matrix를 고정한다.
  caller가 validation 전후에 원래 `key_ops` list를 변경해도 owned snapshot과
  imported key capability가 변하지 않는 deterministic regression을 포함한다.
- [ ] `str`/`repr`/exception/traceback에 secret/PEM/JWK canary가 없고 object가
  unhashable임을 test한다.
- [ ] RED: `uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_keys.py -q`
  (expected: `JWTKey` import/factory failure).
- [ ] secret은 `bytes(secret)`로 복사하고 `OctKey.import_key`/`RSAKey.import_key`
  뒤 algorithm, capability, modulus를 검증한다. dependency object는 private field다.
- [ ] RSA private/public wrapper의 `public_jwk()`는 새 immutable public projection을
  반환하고 private fields `d/p/q/dp/dq/qi/oth`가 없음을 확인한다.
- [ ] GREEN:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_keys.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_algorithms.py -q
```

- [ ] Lore commit intent: `Reject JWT keys that cannot uphold the selected algorithm`.
  HMAC/RSA strength constraint, dependency key exposure rejection, verification
  evidence를 trailers에 기록한다.

## Task 3: atomic repository와 rotation lifecycle을 구현한다

**Depends on:** Task 2

**Files:** Create `_repository.py`, `test_repository.py`; modify public `__init__.py`.

- [ ] `KeyEntry` active/retired-material 및 revoked-tombstone invariant,
  `KeySnapshot.entries` immutability를 test한다.
- [ ] empty/initial active/retired public bootstrap, duplicate/tombstoned ID,
  incompatible capability의 constructor atomicity를 test한다.
- [ ] add/rotate/retire/revoke 성공마다 epoch +1, old active retirement, revoke
  material deletion, ID non-reuse를 test한다.
- [ ] failed transition의 snapshot/epoch 보존과 success INFO/failed WARNING 각 한 번,
  low-cardinality/no-canary logging을 test한다.
- [ ] barrier와 concurrent readers로 partial state가 아닌 complete old/new snapshot만
  관찰되는지 test한다.
- [ ] RED: `uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_repository.py -q`.
- [ ] `RLock` 아래 copy -> full validation -> freeze -> single publish helper를
  구현한다. constructor epoch=0, successful mutation만 monotonic +1이다.
- [ ] transition log에는 caller input을 format/extra에 넣지 않고 redacted public
  exception을 `from None`으로 propagate한다.
- [ ] GREEN:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_repository.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_keys.py -q
```

- [ ] Lore commit intent: `Make JWT rotation publish one immutable key state at a time`.
  repository-owned state와 retained-key stale authority rejection을 기록한다.

## Task 4: immutable claims와 profiles를 구현한다

**Depends on:** Task 1

**Files:** Create `_claims.py`, `_profiles.py`, `test_claims.py`, `test_profiles.py`;
modify public `__init__.py`.

- [ ] nested caller dict/list mutation이 claims/result에 영향을 주지 않는 deep-freeze
  test를 먼저 작성한다.
- [ ] registered collision, blank/non-string key, bytes/set/object, NaN/Infinity,
  cycle/depth/node overflow, naive datetime를 거부한다.
- [ ] audience normalization, aware UTC normalization, integer NumericDate encode/decode
  boundary를 test한다. inbound bool-as-int와 datetime overflow는 각각
  `JWTClaimError`/`JWTMalformedTokenError`의 owning path에서 검증한다.
- [ ] issuance profile constructor의 positive finite duration, callable clock,
  `default_ttl=None`, max/default 관계 configuration만 test한다. claim 변환과
  clock 호출은 Task 6이 소유한다.
- [ ] validation의 non-empty issuer/audience, issuer exact match, audience intersection,
  required claims, exact typ/header, skew, max age/future iat, stable fingerprint를
  test한다. clock identity는 fingerprint에서 제외한다.
- [ ] RED:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_claims.py \
  packages/bluetape-jwt/tests/bluetape_jwt_tests/test_profiles.py -q
```

- [ ] cycle/depth/node budget을 받는 `_freeze_json`, registered serialization,
  typed result helper와 finite duration, set/header normalization, canonical
  fingerprint, single-reference-time validation을 구현한다.
- [ ] claim validation은 `iss`, `aud`, required names와 exp/nbf/iat/max-age를 같은
  captured `now`로 검사한다.
- [ ] GREEN:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_claims.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_profiles.py -q
```

- [ ] Lore commit intent: `Bind JWT claims to immutable application-owned policy`.
  one-clock constraint와 universal lifetime rejection을 기록한다.

## Task 5: strict uncached JWS issue/verify를 구현한다

**Depends on:** Tasks 2-4

**Files:** Create `_provider.py`, `test_provider.py`, `test_security.py`; modify public
`__init__.py`.

- [ ] 9 algorithm issue/verify, exact alg/kid/typ, caller claims preservation,
  active/retired success, revoked/missing failure를 test한다.
- [ ] `inspect.signature`로 constructor와 two-method protocol, per-call override 부재를
  고정한다.
- [ ] token type/size/segment/empty segment, base64url/UTF-8/JSON, duplicate header와
  payload name, non-object shape를 거부한다.
- [ ] `none`, algorithm/family mismatch, invalid kid/typ, `jku/jwk/x5u/x5c/zip`, unknown
  crit, unapproved header를 local key resolution 전에 거부한다.
- [ ] successful result의 `headers`에는 approved custom header만 있고 alg/kid/typ와
  모든 reserved header가 없음을 exact mapping으로 test한다.
- [ ] bad signature, issuer/audience/required/temporal failures와 secret-bearing injected
  dependency failure가 typed redacted exception으로 변환되는지 test한다.
- [ ] RED:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_provider.py \
  packages/bluetape-jwt/tests/bluetape_jwt_tests/test_security.py -q
```

- [ ] `_StrictJSONDecoder`, bounded header parser, restricted registry, safe exception
  mapper를 구현한다.
- [ ] issue는 one snapshot의 active key를 재확인하고 profile-owned header와 caller
  claims만 서명한다.
- [ ] verify 순서는 preflight -> one snapshot -> one clock -> strict header -> local
  key -> signature -> full profile -> frozen result로 고정한다.
- [ ] `jwt.decode`는 exact one algorithm, restricted registry, strict decoder를 받고
  dependency `Token`은 public operation 밖으로 나가지 않는다.
- [ ] GREEN:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_provider.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_security.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_repository.py -q
```

- [ ] Lore commit intent: `Accept only JWTs that match one predeclared security profile`.
  restricted registry와 decoded-claims privacy를 trailers에 기록한다.

## Task 6: issuance policy를 composable decorator로 구현한다

**Depends on:** Tasks 4-5

**Files:** Create `_issuance.py`, `test_issuance.py`; modify public `__init__.py`.

- [ ] recording fake provider로 original provider/claims를 mutate하지 않고 transformed
  copy만 issue에 전달하며 verify는 그대로 delegate하는지 test한다.
- [ ] explicit iat/exp, `add_issued_at=False`, finite default TTL,
  `default_ttl=None`, max TTL, invalid ordering, one clock call을 test한다.
- [ ] generic reversible fake outer wrapper를 issuance provider/JWS provider와 합성해
  future JWE/compression style가 two-method protocol을 유지함을 증명한다. concrete
  JWE/compression은 만들지 않는다.
- [ ] RED: `uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_issuance.py -q`.
- [ ] immutable provider/profile reference와 `issue`/`verify`만 가진 wrapper를
  구현한다. `_apply_issuance_profile`이 caller-preserving time transformation을
  전부 소유하고 low-level provider는 claim을 추가하지 않는다.
- [ ] GREEN:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_issuance.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_provider.py -q
```

- [ ] Lore commit intent: `Keep token lifetime policy outside the low-level signer`.
  caller-authority와 universal 7/365-day default rejection을 기록한다.

## Task 7: optional bounded verified-result cache를 구현한다

**Depends on:** Task 5

**Files:** Create `_cache.py`, `test_cache.py`; modify `_provider.py`, public `__init__.py`.

- [ ] no options이면 cache lookup이 없고 signature validation이 매번 실행되는지
  spy로 test한다.
- [ ] positive finite TTL/capacity와 key `(sha256(token_utf8), profile fingerprint,
  snapshot epoch)`를 고정하고 raw token 미보존을 test한다.
- [ ] hit, `KeyError` miss, LRU, configured TTL, `min(cache TTL, positive exp
  remaining)`, exp 없는 finite TTL을 deterministic clocks로 test한다.
- [ ] hit가 one profile clock으로 exp/nbf/iat/max-age를 다시 검사함을 test한다.
- [ ] rotate/retire/revoke epoch change clear, negative-result non-cache를 test한다.
- [ ] injected get/set/clear failure가 ERROR 한 번과 redacted `JWTCacheError`로
  propagate되고 miss/success로 바뀌지 않음을 test한다.
- [ ] failure test는 `_VerifiedTokenCache(..., cache_factory=fake_factory)` private
  seam만 사용하며 public provider constructor에 injection parameter를 추가하지 않는다.
- [ ] barrier로 old-snapshot verify와 concurrent revoke를 제어해 old operation은
  완료 가능하나 current-epoch cache entry를 publish하지 않음을 test한다.
- [ ] RED: `uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_cache.py -q`.
- [ ] private adapter는 `TTLCache[_CacheKey, VerifiedToken]`, `RLock`, observed epoch만
  소유한다. get의 `KeyError`만 miss로 취급한다.
- [ ] verify는 한 snapshot을 crypto/cache key에 함께 쓰고, 성공 후 live epoch가
  동일할 때만 old-epoch key로 set한다. epoch가 달라졌으면 result 반환은 가능하지만
  cache publish는 생략한다.
- [ ] 모든 public symbol이 구현된 이 task에서 `test_public_surface_has_exact_reviewed_order`
  를 추가하고 blueprint의 final `__all__`을 처음으로 exact assert한다.
- [ ] GREEN:

```bash
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_cache.py -q
uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_provider.py -q
uv run pytest packages/bluetape-cache/tests/test_ttl_cache.py -q
```

- [ ] Lore commit intent: `Bound JWT verification reuse to policy and key epochs`.
  temporal recheck와 strict cache failure를 기록한다.

## Task 8: hostile/concurrency/composition/logging matrix를 닫는다

**Depends on:** Tasks 1-7

**Files:** Modify package security/repository/cache/issuance tests; create
`test_logging.py`.

- [ ] spec 테스트 전략의 모든 bullet을 test node에 매핑하고 누락 case를 먼저
  failing regression으로 추가한다.
- [ ] 9개 algorithm 각각 issue/verify와 mismatch가 parameterized matrix에
  포함되는지 collection output으로 확인한다.
- [ ] import/construction 전후 logger handlers/root level/disabled가 같고 event 외
  record가 없으며 record에 canary가 없음을 검사한다.
- [ ] public graph/`__all__`에서 joserfc, TTLCache, private helper가 노출되지 않는다.
- [ ] repository/cache barrier tests를 sleep 없이 20회 반복한다.

```bash
uv run pytest packages/bluetape-jwt -q
for run_index in {1..20}; do
  uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_repository.py -q || exit 1
  uv run pytest packages/bluetape-jwt/tests/bluetape_jwt_tests/test_cache.py -q || exit 1
done
```

- [ ] Lore commit intent: `Prove the JWT boundary under hostile input and rotation races`.
  deterministic barrier와 exact logging evidence를 기록한다.

## Task 9: wheel, bilingual docs, roadmap와 publish inventory를 정합화한다

**Depends on:** Tasks 1-8

**Files:** Modify package README pair; create `packages/bluetape/tests/test_jwt_wheel_isolation.py`,
`test_jwt_readmes.py`; modify benchmark packaging test, `docs/release/pypi-preflight.md`,
root README pair, `docs/package-layout.md`, `WIP.md`, `CHANGELOG.md`.

- [ ] wheel test를 먼저 추가한다: default meta=core-only, `bluetape[jwt]` exact,
  standalone JWT wheel=cache+joserfc, clean import, no root initializer.
- [ ] README parity test에 install, 9 algorithms, lifecycle, strict typ/issuer/audience,
  cache, issuance decorator, no-default-expiry, #88/#89/#90 markers를 고정한다.
- [ ] publish classifier/preflight inventory가 JWT를 누락하는 RED를 확인한다.
- [ ] RED:

```bash
uv run pytest packages/bluetape/tests/test_jwt_wheel_isolation.py \
  packages/bluetape/tests/test_jwt_readmes.py \
  packages/bluetape-benchmark/tests/test_benchmark_packaging.py -q
```

- [ ] package README pair에 같은 example shape로 key/repository/profile/provider,
  issuance decorator, rotation/revocation, cache opt-in을 문서화한다.
- [ ] signed payload readability, retired verify-only, published revoke의 새-attempt
  rejection, in-flight old snapshot completion, missing exp의 non-expiring 가능성,
  cache != revocation list를 양 언어에 명시한다.
- [ ] root README pair/package layout/WIP/CHANGELOG/preflight를 implemented status와
  follow-up boundary에 맞춘다. diagram은 별도 workflow를 정당화할 만큼 관계 이해를
  개선할 때만 추가하며 이번 완료 조건은 아니다.
- [ ] GREEN/build:

```bash
uv run pytest packages/bluetape/tests/test_jwt_wheel_isolation.py \
  packages/bluetape/tests/test_jwt_readmes.py \
  packages/bluetape-benchmark/tests/test_benchmark_packaging.py -q
```

- [ ] 아래 exact command로 task-scoped directory에 JWT/cache wheels를 각각 clean
  build하고, 같은 artifacts와 joserfc를 temporary target에 설치해 import/final
  exports smoke 후 두 directory를 삭제한다.

```bash
jwt_wheel_dir="$(mktemp -d)"
jwt_smoke_dir="$(mktemp -d)"
trap 'rm -rf "$jwt_wheel_dir" "$jwt_smoke_dir"' EXIT
uv build --package bluetape-cache --wheel --out-dir "$jwt_wheel_dir"
uv build --package bluetape-jwt --wheel --out-dir "$jwt_wheel_dir"
uv pip install --target "$jwt_smoke_dir" "joserfc>=1.7.4,<2" \
  "$jwt_wheel_dir/bluetape_cache-0.1.0-py3-none-any.whl" \
  "$jwt_wheel_dir/bluetape_jwt-0.1.0-py3-none-any.whl"
PYTHONPATH="$jwt_smoke_dir" python -c \
  'import bluetape.jwt; assert bluetape.jwt.__all__[-2:] == ["JWSProvider", "VerifiedTokenCacheOptions"]'
rm -rf "$jwt_wheel_dir" "$jwt_smoke_dir"
trap - EXIT
```
- [ ] Lore commit intent: `Document the operational limits of signed JWT rotation`.
  JWE/compression non-claim과 bilingual parity를 기록한다.

## Task 10: full gate, exact-head review, verifier, lesson과 local closeout을 완료한다

**Depends on:** Tasks 1-9

**Files:** Create security review, verification, Type A lesson under `docs/review`와
`docs/lessons`; modify `WIP.md`.

- [ ] targeted fresh gate:

```bash
uv sync --all-packages --all-extras --all-groups --python 3.13.14 --locked
uv run pytest packages/bluetape-jwt -q
uv run pytest packages/bluetape/tests/test_jwt_wheel_isolation.py \
  packages/bluetape/tests/test_jwt_readmes.py \
  packages/bluetape-benchmark/tests/test_benchmark_packaging.py -q
```

- [ ] full gate와 exact outputs를 verification artifact에 기록한다.

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build --all-packages
actionlint
git diff --check
```

- [ ] built meta/JWT/cache metadata와 clean target imports를 다시 smoke하고 root
  initializer가 생성되지 않았음을 확인한다.
- [ ] Type A lesson에는 실제 reusable learning을 한국어로 기록한다. 이 security
  package에는 evidence-backed N/A를 사용하지 않는다.
- [ ] WIP에는 local evidence만 기록하고 PR/CI/review/merge를 선반영하지 않는다.
- [ ] production/test/docs/lesson/WIP를 먼저 commit하고 그 SHA를
  `reviewed_implementation_sha`로 고정한다.
- [ ] 그 exact SHA에서 독립 security review가 algorithm confusion, parsing, claims,
  rotation/cache race, redaction/logging, dependency boundary를 검토한다. P0/P1이
  0이 아니면 correction commit 후 새 SHA와 affected gate를 다시 만든다.
- [ ] security review와 verification artifact만 추가하는 evidence commit을 만든다.
  별도 verifier는 final HEAD에서 `reviewed_implementation_sha..HEAD`가 허용된
  evidence files만 포함함과 spec/commands/artifacts/docs/follow-up exclusion을
  확인한다. verifier 결과는 local workflow evidence에도 보존한다.
- [ ] Lore evidence intent: `Preserve the verified JWT security decisions for future changes`.
  reviewed implementation SHA, evidence-only delta, verifier와 external gate를 기록한다.
- [ ] final report는 branch/HEAD, commits, changed files, test counts, P0/P1, lesson,
  risks를 포함한다.
- [ ] stop: local commits와 verification에서 멈춘다. push/PR은 repo/base/head가 있는
  새 explicit approval 후, merge는 exact-head CI/reviews/threads/human artifact 확인
  후 fresh approval을 받아야 한다.
- [ ] workflow-required PR body `## DoD Status`는 local completion 조건이 아니다.
  PR creation이 별도로 승인된 뒤 PR gate에서 작성·검증한다.

## Plan Self-Review Checklist

- [ ] 승인 범위/범위 밖/public behavior/test strategy/full gate가 task에 매핑됐다.
- [ ] exports, signatures, key strength, size limits, header policy, cache key/TTL/epoch,
  logging fields가 exact하게 고정됐다.
- [ ] claims/result/profile types와 `iss`/`aud` 필수 의미가 전체 plan에서 일관된다.
- [ ] 모든 family에 intended RED, minimum GREEN, owning test command가 있다.
- [ ] planned production files의 미완성 작업 표식 scan 결과가 0이다.
- [ ] #88/#89/#90과 distributed/remote repository가 구현 task에 없다.
- [ ] push/PR/merge/release/publication authorization이 없고 stop boundary가 분명하다.
- [ ] independent plan review가 P0=0/P1=0일 때만 user plan approval gate로 이동한다.
