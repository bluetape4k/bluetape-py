# Issue #23 Observability Research 교훈

## 배경과 결정

Issue #23에서는 변화하는 Python 및 OpenTelemetry guidance를 domain package에
telemetry lifecycle을 import하지 않는 안정적인 package boundary로 바꿔야 했다. 기존
logging, resilience, cache, provider contract는 OpenTelemetry-free로 유지한다. 향후
bridge는 별도의 opt-in distribution에 두고, production에서는 OpenTelemetry API만
사용하며 SDK, exporter, global provider, propagation, shutdown은 application이
소유한다.

## 재사용 가능한 발견

### 마무리 단계에서 변동 가능한 사실을 다시 확인한다

외부 research summary가 오래된 OpenTelemetry Python release를 latest로 식별했다.
upstream GitHub release를 live로 확인한 결과 `1.43.0` / `0.64b0`가 최신이었으므로
repository note와 보존된 wiki note를 모두 수정했다. version, signal maturity,
release date, support status를 기록하는 research는 validation 직전에 authoritative
source를 다시 읽어야 한다. source의 품질만으로 temporal drift를 제거할 수 없다.

### telemetry boundary에서 domain event 의미를 보존한다

Typed event는 유용한 telemetry input이지만 모양이 비슷한 event가 하나의 shared
observer contract를 의미하지는 않는다. Resilience observer는 failure를 전파하지만
Redis observer는 이를 격리한다. bridge는 고정된 allowlist field를 event class,
ordering, synchrony, cleanup, failure semantics를 바꾸지 않고 변환해야 한다.
Arbitrary caller observer는 기존 규칙을 유지하고, bridge adapter는 package-local
observer call로 돌아오기 전에 자체 telemetry/API failure를 catch해야 한다.
Instrumentation failure가 새로운 domain result가 되어서는 안 된다.

### execution context와 telemetry payload를 분리한다

Python `contextvars`, OpenTelemetry Context, Baggage, logging field는 ownership과
trust boundary가 서로 다르다. task와 `asyncio.to_thread()` propagation이 임의의
logging context나 baggage를 telemetry attribute로 자동 승격할 근거가 되지는 않는다.
Raw thread와 executor submission에서 propagation이 필요하면 명시적으로 별도 capture한
context를 사용해야 한다.

## 검증 증거

- task, thread, executor, `contextvars.Context` 동작에 대한 Python 3.13.14
  documentation을 확인했다.
- library/application ownership, signal maturity, cardinality, sensitive data guidance에
  대한 OpenTelemetry specification과 Python status page를 확인했다.
- upstream OpenTelemetry Python release list를 live로 다시 읽고 stale version statement를
  review 전에 수정했다.
- documentation diff, local link, independent P0/P1 review, wiki indexing가 research
  artifact의 필수 closeout gate다.

## 향후 보호 장치

Issue #24에서 bridge를 구현하기 전에 OpenTelemetry Python release와 signal status를
다시 갱신한다. API-only no-SDK 동작, injected-provider test, global mutation 없음,
고정된 low-cardinality attribute, hostile sensitive data marker, Python 3.13 context
cleanup을 요구한다. 단지 sibling language repository에 나타난다는 이유만으로 구현
형태를 채택하지 않는다.
