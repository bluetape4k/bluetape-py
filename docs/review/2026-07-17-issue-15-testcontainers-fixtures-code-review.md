# Issue #15 Testcontainers Fixture Families 코드 검토

## 범위 및 방법

- Review range: `origin/develop...a88a81da8c3335494782d4a460ca3f5cc19b60c9`
- Review target: PostgreSQL/LocalStack fixture family, shared lifecycle support,
  Redis compatibility, extra와 wheel metadata, service CI, bilingual docs,
  mandatory Type A lesson
- 방법: 여섯 개의 분리된 main-session lens 후 integration pass. Native
  performance lane이 5,356.6초 동안 material progress 없이 멈춰 main session이
  회수했으며 child-agent result는 사용하지 않았다.

## Severity 요약

| Severity | Count | 결과 |
|---|---:|---|
| P0 | 0 | Pass |
| P1 | 0 | Pass |
| P2 | 0 | Pass |
| P3 | 2 | 근거와 함께 보류 |

## 여섯 관점 검토

### 1. Performance 및 resource use

**PASS.** 각 wrapper는 provider container 하나를 소유하고 background worker나
global registry를 노출하지 않으며 synchronous start/stop만 수행한다. LocalStack은
`LocalStackServer.__init__`에서 selected service를 한 번 normalize하고
`with_services(*services)`로 한 번 전달한다. Integration job은 Docker pressure를
늘리지 않고 Redis, PostgreSQL, LocalStack을 `timeout-minutes: 30` 아래 serial로
실행한다.

### 2. Stability 및 lifecycle correctness

**PASS.** Shared state/error contract가 Redis symbol identity를 보존한다. 새
wrapper는 restart-after-close를 거부하고 반복 `start()`/`close()`를 안전하게
하며 cleanup 전에 detail을 clear한다. Cleanup도 실패하면 caller exception을
보존하고 retry를 위해 provider handle을 유지한다. Start failure는 typed error를
publish하기 전에 cleanup을 시도한다. Unit matrix와 real-container test가 success,
invalid input, start failure, cleanup failure, abnormal context exit를 다룬다.

### 3. Security 및 isolation

**PASS.** Image reference는 명시적 non-`latest` tag 또는 complete SHA-256
digest를 요구하고 URI, whitespace, control, credential-shaped digest를 거부한다.
Published port는 loopback-only로 요청하고 검증한다. PostgreSQL password와
LocalStack credential은 repr에서 제외하며 PostgreSQL URL은 caller value를
percent-encode한다. LocalStack은 ambient AWS credential을 무시하고 wrapper-owned
synthetic credential만 반환한다.

### 4. Operations 및 CI

**PASS.** 모든 wrapper에 service-specific Docker label을 적용한다. Service job은
Docker preflight, locked `all` extra와 focused test group 설치, 세 integration
path의 serial 실행, `timeout-minutes: 30`을 사용한다. English/Korean runbook은
label inspection, 확인된 removal, Ryuk ownership, image default, provider-specific
timeout ownership을 설명한다.

### 5. Developer API 및 packaging

**PASS.** Public root export는 명시적이고 provider object는 private으로 유지한다.
Optional provider import는 lazy하여 base import가 boto3, Psycopg, SQLAlchemy,
PostgreSQL/LocalStack provider module을 load하지 않는다. `postgres`, `aws`,
`all` extra는 focused이고 caller client는 test group에 둔다. Wheel metadata와
namespace coexistence를 assertion하며 root `bluetape` default/meta-extra
contract는 변경하지 않는다.

### 6. Caller 경험 및 documentation

**PASS.** Paired English/Korean docs가 install choice, supported service, image
default, explicit ownership, example, CI serialization, cleanup, Redis-only
compatibility에 동의한다. Connection detail object는 immutable이고 secret은 repr에서
redact하지만 caller-owned client에는 제공한다. Failure category는 stable하며 raw
provider diagnostic 없이 service/image context를 actionable하게 제공한다.

## 보류한 P3

1. Testcontainers 4.14.2의 LocalStack provider가 deprecated `wait_for_logs`를
   사용해 readiness warning을 낸다. Bluetape가 직접 호출하지 않고 real-service
   behavior는 모두 통과했다. Compatible Testcontainers upgrade 후 provider,
   wheel, serial Docker gate를 재실행해야 한다.
2. Synchronous package라 pytest-asyncio가 focused `test` group에서 의도적으로
   빠졌지만 workspace config가 `asyncio_mode`를 선언해 isolated environment에서
   unknown option warning이 난다. Focused test 114개는 통과했으며 isolation을
   약화시키는 unrelated runtime dependency는 추가하지 않는다.

## 통합 판정

구현 diff는 승인된 acceptance criteria를 만족하며 알려진 P0/P1/P2 defect가 없다.
두 P3는 bounded follow-up condition이 있는 외부/tooling warning이며 fixture
contract를 약화시키지 않는다. 최종 결과: **P0=0, P1=0, P2=0, P3=2**.
Exact-head GitHub CI와 review-thread verification이 남은 merge-ready 조건이다.
