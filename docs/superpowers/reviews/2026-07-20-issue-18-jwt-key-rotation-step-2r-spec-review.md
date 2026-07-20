# Step 2-R Spec Review - Issue #18 JWT 및 Key Rotation

- 날짜: 2026-07-20 KST
- 대상: `docs/superpowers/specs/2026-07-20-issue-18-jwt-key-rotation-design.md`
- 검토 방식: 작성자와 분리된 read-only critic review

## 최종 판정

- Spec gate: **PASS**
- P0: **0**
- P1: **0**

## 해결된 P1

### 1차 검토

1. verification-only RSA public key를 repository에 직접 등록할 경로가 없었다.
   `add_verification_key()`와 초기 retired key bootstrap 계약을 추가했다.
2. issuer와 audience의 빈 집합 및 match 의미가 정의되지 않았다. 비어 있지 않은
   allowed issuer/accepted audience 집합, issuer exact match, audience 교집합
   match를 고정했다.
3. issuance `max_ttl`과 validation `max_token_age`가 사용할 reference time 및
   missing `iat` 의미가 불명확했다. attempt마다 clock을 한 번만 읽고 모든
   temporal check가 같은 capture를 사용하도록 고정했다.
4. concurrent revoke가 이미 snapshot을 capture한 verification까지 소급 취소하는
   것처럼 읽혔다. operation의 linearization point를 snapshot capture로 정의하고,
   old-epoch result가 current-epoch cache에 publish되지 못하도록 명시했다.

### 2차 검토

1. user-collaboration spec이 영어로 작성되어 repository 언어 정책을 위반했다.
   code, command, identifier, URL을 제외한 설명과 결정 기록을 한국어로 전환했다.
2. 공개 `KeyStatus`의 소유 위치가 불명확했다. `JWTKey`는 material/capability만
   소유하고 repository-owned 불변 `KeyEntry`가 상태를 소유하도록 분리했다.
3. RS/PS key의 최소 RSA 강도가 빠져 있었다. import, bootstrap, rotation,
   issue/verify 경로에서 2048-bit 미만 modulus를 거부하도록 고정했다.
4. cache failure 우회 범위가 넓고 운영 가시성이 없었다. `KeyError`만 정상 miss로
   인정하고 다른 `get`/`set`/`clear` failure는 redacted `JWTCacheError`로
   propagate하도록 변경했다.

### 최종 검토 전 보정

`bluetape-py-patterns`의 production logging 계약에 따라 stdlib module logger를
사용하는 low-cardinality 운영 logging을 추가했다. repository lifecycle
transition과 terminal cache failure만 지정 level에서 한 번 기록하고, token,
digest, `kid`, claim/header value, key material, exception text, epoch는 모두
제외한다. package는 handler나 root logger 상태를 변경하지 않는다.

## 최종 확인 사항

- provider는 하나의 JWS algorithm과 하나의 validation profile에 고정된다.
- `TokenProvider` protocol은 issuance profile과 후속 JWE/compression decorator가
  합성할 수 있는 최소 계약이다.
- `ACTIVE -> RETIRED -> REVOKED` transition, public-key bootstrap, tombstone,
  epoch invalidation이 하나의 repository contract로 닫혀 있다.
- low-level issue는 caller claims를 변경하지 않고 optional issuance profile만
  누락된 time claim을 정책적으로 보충한다.
- cache는 bounded/finite/default-disabled이며 cryptographic validation이나 current
  temporal validation을 우회하지 않는다.
- RSA 최소 강도, header 제한, algorithm-family separation, redaction, logging,
  hostile-input test가 acceptance 범위에 포함된다.
- #88 async, #89 JWE, #90 compression 구현은 #18 범위 밖으로 유지된다.

## 검증 증거

- 독립 critic 최종 판정: `APPROVE — P0=0, P1=0`
- `git diff --check`: PASS
- spec 외 production code 변경: 없음

## 남은 공백

없음. exact public signature와 export 순서는 다음 implementation plan에서 이
명세의 보안 및 ownership 계약을 약화하지 않는 범위로 고정한다.
