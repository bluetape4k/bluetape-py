# Issue #24 Observability Delivery Lessons

## Context and decision

관측성은 domain package에 SDK lifecycle을 넣는 기능이 아니라, 이미 존재하는 typed observer
event를 별도 opt-in 배포가 안전한 OpenTelemetry API signal로 번역하는 경계 문제였다. 운영 SDK,
exporter, global provider, flush, shutdown은 application이 계속 소유하고 Bluetape adapter는 동기식
호출 안에서 고정된 scalar만 기록한다.

## Reusable findings

### Focused dependency isolation must include pytest collection

Marker deselection은 test module import 뒤에 일어난다. 따라서 workspace-only dependency를 top-level로
import하면 해당 test가 제외되더라도 focused 환경이 collection에서 실패한다. 선택적 dependency는
fixture나 marked test 본문 안에서 import하고, focused sync 직후 전체 test directory를 실제로
수집해야 한다.

여러 distribution을 한 pytest process에서 모을 때 비패키지 test directory의 bare `_support`와
`test_packaging.py` 같은 basename은 전역 module name으로 충돌한다. package-specific helper와 test
module 이름을 사용하거나 고유한 test package namespace를 사용해야 한다. Focused 통과만으로는 이
충돌을 발견할 수 없으므로 full-workspace collection이 필수다.

### Normalize the complete event before emitting anything

한 field가 invalid일 때 span event는 남고 metric만 빠지는 부분 성공은 진단을 왜곡한다. 모든 consumed
field를 closed enum, exact bool, signed-64-bit count, finite non-negative duration으로 먼저 정규화한 뒤
완성된 allowlist만 각 channel에 전달해야 한다. Ordinary `Exception`은 telemetry no-op으로 격리하되
`KeyboardInterrupt`, `SystemExit`, `GeneratorExit` 같은 process-control `BaseException`은 helper와
public adapter 경계 양쪽에서 그대로 전파해야 한다.

### Current span is borrowed context, not adapter state

Adapter는 호출 시점의 recording span만 조회하고 저장하지 않는다. 이 규칙은 nested/sequential span의
stale reuse를 막고 coroutine별 `contextvars` 격리를 그대로 활용한다. Raw thread, executor, detached
task, process, remote transport에 대한 암묵적 propagation을 약속하지 않으며, baggage와 logging
context도 자동으로 attribute로 올리지 않는다.

### Runtime failure channels should be isolated independently

Span lookup, recording check, span event, counter, histogram은 순서가 있는 별도 best-effort channel이다.
한 channel의 ordinary 실패가 뒤 channel을 막거나 다음 event에 남아서는 안 된다. 반면 생성 시 meter
lookup과 instrument 생성은 wiring 오류이므로 fail-fast가 맞다. 이 구분을 테스트하면 mutable health
state나 package-owned diagnostic registry 없이도 domain result를 보존할 수 있다.

### SDK tests need an explicit selected lane

Generic workspace는 SDK 부재를 먼저 증명하고 `observability_sdk`를 제외한다. SDK import, real provider,
reader, exporter, SDK benchmark subprocess는 모두 해당 marker 아래 있어야 한다. Focused lane은 SDK와
domain prerequisite import를 먼저 증명하고 marker만 선택한 뒤 JUnit의 test 수와 skip/failure/error
0을 검사해야 silent skip을 막을 수 있다.

### Cardinality and privacy review starts from forbidden inputs

허용할 field 목록뿐 아니라 policy name, Redis key/value/namespace, exception text, arbitrary attribute,
log context, baggage, trace/span ID처럼 절대 읽지 않을 값을 raising property와 hostile sentinel로
검증해야 한다. Metric에는 closed low-cardinality 값만 두고 attempt/poll/duration 같은 detail은 필요한
span event나 histogram에만 제한한다.

## Verification evidence

- Focused API 57개와 SDK-selected 8개가 통과했고 SDK JUnit skip은 0이었다.
- Full workspace 1,586개가 통과했으며 Ruff, format, 15-package build, actionlint가 통과했다.
- Wheel verifier가 focused/default/readme 세 환경의 dependency 및 module origin 격리를 증명했다.
- API/SDK 각 3회 성능 run, 64 KiB retained-allocation 한도, thread/task/lifecycle 비소유를 증명했다.
- 여섯 관점 implementation review는 P0=0, P1=0, P2=0으로 수렴했다.

## Future guard

새 adapter나 signal을 추가할 때 production dependency, consumed allowlist, forbidden field, metric
descriptor, current-context 범위, ordinary failure 격리, BaseException 전파, SDK marker, benchmark budget,
focused/full collection을 함께 갱신한다. Exporter나 background work가 필요해지면 기존 adapter에
숨기지 말고 application-owned 구성 또는 별도 배포 경계로 다시 설계한다.
