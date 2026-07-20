# bluetape-jwt

구현 상태: 진행 중 (issue #18).

현재 package 경계는 승인된 `JWSAlgorithm` 값과 안정적이고 redacted된 예외
type만 공개합니다. signing, verification, key rotation, typed claims, issuance
profile, 선택적 verified-result cache는 이후 구현 단계에서 추가하며 아직 사용할
수 없습니다.

이 distribution은 Python 3.13 이상을 대상으로 하고 `joserfc`를
`bluetape.jwt` API 뒤에 숨깁니다. 이후 선택적 local cache 경계를 위해
`bluetape-cache`에 의존하지만, 얇은 `bluetape` 기본 설치는 core-only 상태를
유지합니다.
