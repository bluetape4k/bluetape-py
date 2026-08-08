# Issue #46 Apache Fory 통합 교훈

날짜: 2026-07-11

## 배경

Issue #46에서는 기존 serde contract에 CPython 3.13 전용 Apache Fory adapter를
추가했다. default install의 범위를 넓히거나 payload가 type/codec 동작을 선택하도록
허용하지 않았다.

## 결정과 결과

- provider와 무관한 error code는 `bluetape.serde`에 유지하되, `pyfory`는 명시적인
  `bluetape.serde.fory` module에서만 import한다.
- Fory bytes를 고정 20-byte `BTFY` envelope로 감싼다. reconstruction 전에
  metadata, schema, type, length, root-header gate를 실행할 수 있어야 한다.
- `(schema_id, schema_version, type_id)`를 application-owned route configuration으로
  취급한다. schema가 바뀌면 새 route를 만들며, 기존 tuple의 의미를 변경하지 않는다.
- 모든 언어에서 varint mapping과 explicit field ID를 사용한다. Python/Go/Rust/Kotlin
  annotation을 제거하면 겉보기에는 비슷한 type이 만들어지지만 cross-language
  identity contract가 약해진다.
- provider의 encode/decode/registration failure는 새 public error boundary에서
  변환한다. API contract상 진단이 필요한 direct provider initialization failure는
  보존하되, serde domain failure에 payload나 provider exception text를 절대 넣지
  않는다.
- public Fory `Buffer` reader index로 body를 정확히 소비했는지 증명한다. length가
  같다는 사실만으로는 trailing bytes 앞에서 멈추는 decoder를 감지할 수 없다.
- `ThreadSafeFory` 앞에 semaphore를 두어 provider access를 제한한다. sleep 대신
  barrier와 identity assertion으로 ordinary failure 뒤 permit release와 동일
  runtime 재사용을 증명한다.

## 검증 증거

- focused contract, Fory, packaging test 339개가 통과했다.
- performance/allocation/RSS observation 5개가 통과했다.
- workspace test 737개가 CPython 3.13.14에서 통과했다.
- Python, Go, Rust, Kotlin이 새 deterministic fixture를 생성해 Python artifact를
  검증했고, Python은 모든 producer artifact를 검증했다.
- Ruff, all-package build, actionlint, manifest verification, diff check가 통과했다.

## 검토에서 놓친 점과 향후 보호 장치

- focused feature suite만으로는 오래된 shared export assertion을 놓칠 수 있다. 항상
  Step 6-R 전에 full workspace suite를 실행한다.
- 이전에 실행한 `uv sync`만으로는 충분한 CI contract가 아니다. 각 provider command에
  package, extra, exact Python version을 명시한다.
- 승인된 spec의 example도 public contract의 일부다. API review에서 최종 callable
  signature와 대조한다.
- committed fixture, canonical manifest metadata, runtime-generated artifact,
  downloaded executable verifier는 서로 다른 증거로 유지한다. 최종 CI job에서
  artifact verification을 recompilation으로 대체하지 않는다.
