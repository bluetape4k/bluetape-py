# Issue #18 JWT 키 회전 교훈

## 맥락과 결정

JWT 지원은 서명 함수 하나를 추가하는 작업이 아니었다. 공개 경계는 알고리즘 선택,
키 수명주기, claim 정책, 발급 시간 정책, 회전 중 동시성, 검증 결과 캐시, 오류와 로그의
노출 범위를 함께 고정해야 한다. `bluetape-jwt`는 동기 compact JWS만 소유하고,
비동기 API, JWE 암호화, 압축, 원격 키 저장소는 각각 후속 이슈 #88, #89, #90과 별도
adapter 범위로 남겼다.

## 재사용 가능한 발견

### 알고리즘 허용 목록만으로 algorithm confusion을 막을 수 없다

Provider가 하나의 `JWSAlgorithm`에 고정되고, 검증 시 protected header의 `alg`와
repository key의 알고리즘이 모두 그 값과 일치해야 한다. Decoder에도 같은 단일
알고리즘 목록을 전달하고, 중복 JSON key와 허용되지 않은 header를 서명 검증 전에
거절해야 parser와 crypto backend의 관대한 기본값이 정책을 넓히지 않는다.

지원 목록은 HS256/384/512, RS256/384/512, PS256/384/512의 아홉 개로 닫았다.
`none`, HMAC/RSA 교차 사용, 임의 custom header, 중복 header/payload key는 모두
명시적인 실패 경로다. 새 알고리즘은 enum 추가만으로 끝나지 않고 key-strength,
provider binding, hostile mismatch matrix를 함께 추가해야 한다.

### 회전은 mutable key map이 아니라 불변 snapshot의 epoch 전환이다

`InMemoryKeyRepository`는 active key와 active/retired/revoked entry 집합을 하나의
`KeySnapshot`으로 게시한다. 회전과 폐기는 새 snapshot을 만든 뒤 epoch를 증가시켜
원자적으로 교체한다. 검증 한 건은 처음 획득한 snapshot 안에서 완료될 수 있지만,
새 검증과 캐시는 증가한 epoch를 관찰해야 한다.

이 구조는 이미 시작된 검증을 강제로 중단시키지 않으면서도 revoked key가 다음
operation에서 사용되지 않게 한다. 분산 저장소는 동일한 의미를 제공하더라도 이 로컬
구현을 network I/O나 background refresh로 확장하지 말고 별도 adapter에서 consistency와
failure semantics를 정의해야 한다.

### 검증 결과 캐시는 서명 검증을 대체하지만 시간 정책과 폐기를 대체하지 않는다

Optional cache key는 raw token이 아니라 SHA-256 digest, validation profile fingerprint,
key snapshot epoch의 조합이다. Cache hit에서도 `exp`와 `nbf`를 현재 기준 시각으로 다시
검증하고, entry TTL은 configured TTL과 token의 남은 수명 중 더 짧은 값으로 제한한다.
Epoch가 바뀌면 기존 entry를 비우며, 검증 중 회전으로 live epoch가 달라진 결과는
cache에 넣지 않는다.

따라서 cache hit는 현재 profile과 key epoch에서 이미 암호학적으로 검증됐다는 뜻일
뿐이다. Cache는 revocation list가 아니고, 음수 결과를 저장하지 않으며, cache backend
오류는 token이나 claim을 로그에 남기지 않는 닫힌 `JWTCacheError`로 실패한다.

### 수명 정책은 signer의 숨은 기본값이 아니라 바깥 decorator가 소유한다

Low-level `JWSProvider`는 caller가 준 immutable claims를 그대로 서명한다.
`IssuanceProfileProvider`가 바깥에서 `iat`와 `exp` 정책을 합성하며,
`default_ttl=None`은 만료 시간을 만들지 않는다. 7일이나 365일 같은 보편 기본값은
안전하거나 보편적이지 않으므로 제공하지 않았다. Caller가 `iat` 또는 `exp`를 이미
제공하면 그 값이 authoritative하다.

`TokenProvider.issue/verify`의 작은 동기 계약을 유지했기 때문에 향후 JWE나 압축도
outer decorator로 합성할 수 있다. 다만 compact JWS payload는 서명됐을 뿐 읽을 수
있으므로 현재 provider를 암호화 기능으로 설명하거나 compression header를 암묵적으로
처리해서는 안 된다.

### 안전한 JWT 경계는 입력 크기와 관찰 가능성도 닫아야 한다

Token 전체와 protected header 크기를 먼저 제한하고, base64url segment와 exact JSON
object를 검증한 뒤 JOSE parser에 전달해야 비정상 입력 비용을 제한할 수 있다. 오류는
고정된 public category로 변환하고 token, signature, key material, claim value를 예외
메시지와 structured log field에 포함하지 않는다.

Byte 제한을 `len(token.encode("utf-8"))` 하나로 검사하면 제한을 확인하기 전에 공격자
입력 크기만큼 bytes를 추가 할당한다. Python `str`의 code point 수가 byte 제한보다 큰
경우를 먼저 O(1) 길이 검사로 거절하고, 그 이하의 bounded 입력만 UTF-8 byte 수를
확인해야 한다. 8 MiB 입력의 `tracemalloc` 회귀 테스트가 이 순서를 직접 고정한다.

Frozen dataclass도 기본 `repr`는 안전하지 않다. `TokenClaims`, `VerifiedToken`,
`ValidationProfile`, `KeySnapshot`은 immutable이어도 issuer, audience, custom claim,
header, kid, epoch를 자동 repr에 그대로 포함한다. 민감 값을 보유하는 public 값은
dataclass repr를 비활성화하고 canary가 `repr()`에 없음을 테스트해야 한다. Policy
문자열은 fingerprint 직전 raw `UnicodeEncodeError`가 나지 않도록 constructor에서 UTF-8
가능 여부까지 검증해 redacted `JWTConfigurationError`로 닫는다.

운영 로그는 low-cardinality event, operation, outcome, error category만 제공한다.
Redaction은 애플리케이션 소유이지만 package가 민감한 원문을 애초에 log record에 넣지
않아야 caller-owned redaction을 우회하지 않는다. Fixed event 이름도 운영 필터 계약이므로
`jwt_cache_operation` 같은 승인된 이름을 구현과 테스트에서 동일하게 고정한다.

### 새 distribution은 모든 fail-closed 정본과 격리 wheel에서 증명한다

Focused package가 단독으로 통과해도 workspace의 publishable/private 분류가 여러 테스트에
중복되어 있을 수 있다. 첫 전체 replay가 resilience packaging의 `PUBLISHABLE` 집합에
`bluetape-jwt`가 빠진 것을 잡았다. 새 distribution을 추가할 때는 `rg`로 exhaustive
equality 집합을 모두 찾고 release preflight와 함께 갱신해야 한다.

Source checkout import만으로는 namespace package 격리를 증명할 수 없다. Python 3.13.14로
`bluetape-cache`, `bluetape-jwt`, meta wheel을 만들고 clean target에 설치한 뒤 module origin,
distribution metadata, exact public exports, root `bluetape/__init__.py` 부재를 확인해야
sibling source나 기존 virtualenv가 결과를 오염하지 않는다.

## 향후 가드

- 새 algorithm이나 header는 단일-profile binding과 hostile mismatch matrix 없이 추가하지
  않는다.
- Key repository adapter는 immutable snapshot과 monotonic epoch 의미를 보존하고 background
  task나 global registry를 core package에 넣지 않는다.
- Cache key에 raw token을 넣지 않고, hit의 시간 재검증과 epoch invalidation을 제거하지
  않는다.
- 발급 TTL은 명시적 profile 정책으로만 추가하며 보편적인 장기 기본값을 만들지 않는다.
- JWE와 compression은 동기 `TokenProvider` decorator로 설계하되 각각 #89와 #90의 독립
  threat model과 packaging 결정을 거친다. Async API는 #88에서 별도 수명주기와 cancellation
  계약을 정의한다.
- Public API나 설치 형태가 바뀌면 EN/KO README scenario marker, focused/meta/default wheel,
  release inventory, 두 fail-closed distribution 분류를 함께 검증한다.

## 구현 단계 증거

- 아홉 알고리즘, key/profile/claim/provider/issuance/cache/security/logging 패키지 검증은
  `296 passed`로 수렴했다.
- Wheel/README/release inventory 표적 검증은 `11 passed`, meta package 전체 검증은
  `30 passed`였다.
- Repository와 cache 동시성 suite를 각각 20회 반복해 총 40회 통과시켰다.
- Ruff lint/format, actionlint, build, diff 검증과 최종 exact-head 전체 workspace 결과는
  별도 verification artifact에 고정한다.
