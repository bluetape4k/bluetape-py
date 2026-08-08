# Issue #45 엄격한 JSON Serde 교훈

## 배경

Issue #45에서는 `bluetape-py`의 첫 공용 직렬화 계약과 엄격하고 제한된 JSON
구현을 도입했다. 이 작업은 성능, 안정성, 보안, 운영, 개발자, 사용자 관점에서
검토했다.

## 결정 사항

- 예외 객체 그래프를 리소스 안전성 경계의 일부로 취급한다. `raise
  ... from None`은 원인을 숨기지만 `__context__`나 traceback locals를 제거하지는 않는다.
  핸들러를 빠져나온 뒤 public typed error를 만들고, 그 전에 source, decoded text,
  metadata, partial output locals를 해제한다.
- 네이티브 decoder와 encoder의 구성 실패도 정제한다. public serde 오류가 이미
  깨끗하더라도 caller에게 노출되는 `TypeError`나 `ValueError` traceback이 같은
  대형 객체를 계속 보유할 수 있다.
- 증분 출력을 하나의 `bytearray`에 누적한다. `list[bytes]`는 마지막에 발생하는
  quadratic 복사를 피하지만 작은 chunk가 많을 때도 과도한 메모리를 사용할 수
  있으므로 `tracemalloc` 회귀 테스트로 이를 보호한다.
- 대칭적인 정수 계약을 명시한다. CPython의 process-global integer digit 설정은
  변경 가능하고 환경에 따라 달라지므로 JSON encode와 decode가 각각 public
  640-digit limit을 독립적으로 강제한다.
- 실행 가능한 verification selector와 파싱 가능한 Lore trailer를 테스트 대상으로
  유지한다. 오래된 selector나 겉보기에는 그럴듯하지만 분리된 trailer는 product
  code가 올바르더라도 증거 체인을 약화한다.
- Apache Fory는 Issue #45 범위 밖에 둔다. Issue #46이 binary serialization을
  담당하며, 여기서 정립한 payload, error, limit, trust, schema-ID,
  cross-language conformance 계약을 재사용해야 한다.
- graph preflight 상태는 O(depth)로 유지한다. completed-container memo는 반복되는
  DAG traversal을 해결하지만 O(unique containers)만큼 커진다. 대신 보수적인
  encoded-byte lower bound로 반복 확장을 제한한다. Unicode validation scan에서
  string을 비용에 포함하고 dict key는 지연 처리한다. one-byte occurrence counter만
  사용하면 여러 DAG 경로에서 동일한 대형 shared value를 다시 scan할 수 있다.
- JSON string은 Unicode scalar value로 취급한다. Python decoder는 escaped surrogate
  code point를 허용하므로, 유효한 pair는 non-BMP scalar로 normalize하고 짝이 없는
  surrogate는 명시적으로 거부해 decode 결과를 다시 encode할 수 있도록 한다.

## 결과

최종 독립 검토 매트릭스는 `P0=0 P1=0 P2=0 P3=0`에 도달했다. publication 전에
serde 대상 테스트, repository-wide tests, Ruff checks, package builds, wheel
metadata, isolated installation smoke tests를 로컬에서 통과했다.

## 향후 작업 지침

- failure path에서 untrusted 또는 대형 데이터를 처리할 때는 exception message만
  확인하지 말고 전체 traceback과 context graph를 검사한다.
- streaming adapter에서는 adversarial chunk size와 allocation peak를 측정한다.
- shared-reference graph는 결정적인 visit counter로 테스트한다. wall-clock threshold는
  traversal complexity를 입증하기에 변동이 너무 크다. 또한 서로 다른 sibling
  container를 폭넓게 구성해 complexity 수정이 bounded CPU를 O(unique containers)
  auxiliary memory와 조용히 맞바꾸지 않는지 확인한다. 큰 shared string value와 key도
  포함해 node counter가 반복 scan 작업을 숨기지 못하게 한다.
- format contract가 이식 가능해야 할 때는 bounded numeric behavior를 변경 가능한
  interpreter-global setting에 위임하지 않는다.
- plan이나 review artifact에서 복사한 command는 적힌 그대로 다시 실행한다.
- repository가 Lore를 durable decision record로 사용할 때는 push 전에 Git tooling으로
  commit trailer를 검증한다.
