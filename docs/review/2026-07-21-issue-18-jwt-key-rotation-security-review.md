# Issue #18 JWT 키 회전 보안 리뷰

Date: 2026-07-21 KST

Reviewed implementation SHA: `c50810d53bf43a23ffdc25093ca535168108c30b`

## 최종 판정

독립 보안 재검토 결과는 **승인**이다.

- P0: 0
- P1: 0
- P2: 0

검토 범위는 `origin/develop..c50810d`이며, 승인된 issue #18 design과 implementation
plan의 algorithm confusion, parser, claim, rotation/cache race, redaction/logging,
dependency/namespace/decorator 경계를 기준으로 삼았다.

## 최초 리뷰와 수정 이력

첫 구현 후보 `d22847fed584e55bfe5470ab7b66174b130b6d85`의 독립 리뷰는
`P0=0, P1=2, P2=2`였다. Zero-P1 gate를 통과하지 않았으므로 다음 네 건을 모두
회귀 테스트로 재현한 뒤 `c50810d`에서 수정했다.

| Severity | 발견 | 수정과 회귀 증거 |
|---|---|---|
| P1 | `TokenClaims`, `VerifiedToken`, `ValidationProfile`, `KeySnapshot`의 자동 repr가 claim/header/policy/`kid`/epoch를 노출 | 보안 값을 보유한 public dataclass의 repr를 비활성화하고 canary 기반 negative tests 추가 |
| P1 | 16,384-byte 제한을 검사하기 전에 전체 token을 UTF-8 bytes로 복사 | code-point 길이를 먼저 검사하고 8 MiB 입력의 peak temporary allocation이 1 MiB 미만임을 `tracemalloc`로 고정 |
| P2 | ill-formed Unicode policy가 raw `UnicodeEncodeError`를 노출 | constructor name validation에서 UTF-8 가능 여부를 확인하고 cause 없는 `JWTConfigurationError`로 변환 |
| P2 | cache terminal event가 승인된 `jwt_cache_operation` 대신 `jwt_cache_failure` 사용 | fixed message와 `event` field를 승인된 이름으로 복구하고 get/set/clear 세 경로를 고정 |

이 네 계약의 전용 회귀 검증은 8 cases가 통과했다. Correction diff의 독립
재검토는 네 finding이 모두 닫혔고 새 P0/P1/P2가 없음을 확인했다.

## 최종 six-lens 결과

| Lens | 확인한 경계 | 결과 |
|---|---|---|
| Algorithm/header | 아홉 알고리즘 allowlist, provider/key family binding, exact `alg`/`kid`/`typ`, custom protected-header allowlist, duplicate key 거부 | Pass |
| Parsing/limits | compact 3-segment shape, base64url, token/header byte 제한, duplicate header/payload, non-finite JSON constant, oversized preflight allocation | Pass |
| Claims/time | immutable typed claims, required issuer/audience, exact audience membership, aware UTC normalization, `exp`/`nbf`/`iat`, skew/max-age | Pass |
| Rotation/cache race | immutable snapshot, monotonic epoch, active/retired/revoked 의미, in-flight old snapshot, epoch cache clear, revoke-before-cache-publish race | Pass |
| Redaction/logging | fixed public errors, suppressed causes, repr canaries, token/key/claim 비노출, low-cardinality repository/cache fields와 fixed events | Pass |
| Packaging/composition | `bluetape-cache`/`joserfc` dependency, namespace root initializer 부재, core-only default meta install, sync `TokenProvider` decorator, #88/#89/#90 제외 | Pass |

## 독립 리뷰 증거

리뷰어는 exact HEAD와 `origin/develop`을 확인하고 관련 source/test/spec/plan을
`git diff`, `nl`, `rg`로 추적했다. 최초 리뷰에서는 public repr canary와 20 MiB
`tracemalloc` probe를 실행했다. 재검토에서는 correction diff와 8개 전용 회귀 case,
`git diff --check d22847f..c50810d`를 확인했다.

전체 `3579 passed` gate는 리더가 같은 implementation SHA에서 별도로 실행했으며,
독립 리뷰어는 broad suite를 중복 실행하지 않았다.

## 잔여 범위와 비주장

- 별도 dependency fuzzing이나 CVE 조사 결과를 주장하지 않는다.
- 임의의 외부 `KeyRepository`, cache backend, decorator 구현의 안전성을 보증하지 않는다.
- Async API, JWE encryption, compression은 각각 #88, #89, #90의 후속 경계다.
- 이 문서는 local implementation review 증거이며 GitHub CI, PR review, merge, release,
  PyPI publication을 주장하지 않는다.
