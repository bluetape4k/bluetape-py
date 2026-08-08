# bluetape-audit

[English](README.md) | 한국어

Python 네이티브 bluetape 애플리케이션을 위한 저장소 독립적이고 표준 라이브러리만
사용하는 감사 이벤트 값과 검증 패키지입니다. 애플리케이션이 하나의 감사 사실을
호출자 소유 인프라로 전달하도록 돕지만, 그 사실이 저장되었다고 주장하지 않습니다.

<picture>
  <source srcset="../../docs/images/readme-diagrams/audit-contract-boundary.svg" type="image/svg+xml">
  <img src="../../docs/images/readme-diagrams/audit-contract-boundary.png" alt="감사 계약 소유권 경계">
</picture>

[SVG 원본 열기](../../docs/images/readme-diagrams/audit-contract-boundary.svg).

## 설치

패키지 소유권과 trusted publishing을 확인하는 동안 PyPI 공개는 현재 보류
상태입니다. 현재 개발에는 소스 workspace를 사용하고 wheel 수준 검증이 필요하면
전용 산출물을 로컬에서 빌드합니다.

```bash
uv sync --all-packages
uv build --package bluetape-audit
```

공개 이후에는 전용 배포본을 다음과 같이 설치합니다.

```bash
pip install bluetape-audit
```

또는 얇은 메타 배포본에서 명시적으로 선택합니다.

```bash
pip install "bluetape[audit]"
```

기본 `pip install bluetape`는 계속 core-only입니다.

## 빠른 시작

애플리케이션이 payload를 직렬화하고, 호출자 소유 adapter가 첫 부작용 직전에 전체
이벤트를 검증합니다.

<!-- audit-example:start -->
```python
import json
from datetime import datetime, timezone
from bluetape.audit import (
    AuditError, AuditEvent, AuditIdentity, AuditLimits, AuditPayload, validate_audit_event,
)
storage_limits = AuditLimits(max_payload_bytes=64 * 1024)
stored: list[AuditEvent] = []
def append_to_caller_storage(event: AuditEvent) -> None:
    validate_audit_event(event, storage_limits)
    stored.append(event)  # caller-owned adapter side effect
payload = json.dumps({"reason": "customer_request"}).encode("utf-8")
event = AuditEvent(
    event_id="01JZTESTAUDIT0000000000000",
    action="order.cancelled",
    occurred_at=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
    subject=AuditIdentity("order", "order-123"),
    actor=AuditIdentity("user", "user-456"),
    correlation_id="request-789",
    causation_id="command-012",
    payload=AuditPayload(payload, "application/json", "1"),
    metadata={"source": "orders-api"},
)
try:
    append_to_caller_storage(event)
except AuditError:
    # Record only a bounded package-owned rejection category, never the event.
    raise
```
<!-- audit-example:end -->

애플리케이션 수준 사전 검증은 빠른 실패에 유용하지만 adapter 검증이 기준입니다.
검증은 영속 캡처가 아닙니다. 호출자 소유 storage/outbox/transport의 부작용만
영속성 또는 전달을 성립시킬 수 있습니다.

## 필드 의미

- `event_id`는 하나의 감사 사실을 식별합니다. 같은 사실의 재시도에는 event ID를
  재사용하고, 다른 사실에는 다른 ID를 사용합니다.
- `action`은 호출자 소유 동작 이름이며 패키지는 registry를 두거나 정규화하지 않습니다.
- `occurred_at`은 호출자가 제공한 timezone-aware 시각이며 UTC로 바꾸지 않습니다.
- `subject`는 사실의 대상을, 선택적인 `actor`는 행위 주체를 식별합니다.
- `correlation_id`와 `causation_id`는 호출자 소유 요청·인과 연결을 보존합니다.
- `payload.data`는 불변 bytes snapshot입니다. 패키지는 이를 직렬화, 파싱, 재작성하지
  않습니다. `metadata`는 문자열 mapping의 복사된 불변 snapshot입니다.

문자열, mapping, payload bytes를 만들기 전에 upstream allocation limits를
적용하십시오. 생성자 ceiling은 이미 만들어진 값만 제한하며 network, request body,
decompression 또는 process memory 제한이 아닙니다.

## 어댑터 검증

호출자 소유 adapter는 첫 부작용 직전에 `validate_audit_event(event, limits)`를
호출합니다. 애플리케이션이 사전 검증했더라도 이 위치가 정본입니다. 버전이 있는
adapter 소유 제한을 사용하고 강화하기 전에 replay 호환성과 producer 호환성을
확인하십시오. 운영자가 적용 정책을 식별해야 하면 외부의 bounded policy ID를
내보내되, 이는 event metadata가 아닙니다. 거부된 값을 절대 기록하지 마십시오.

## 안전한 오류 처리

모든 필드는 민감할 수 있습니다. 예외 메시지를 파싱하거나 event, payload, identity,
metadata 또는 거부 값을 로그로 남기지 마십시오. 제한된 rejection metric에는 다음
패키지 소유 범주만 사용할 수 있습니다.

| 속성 | 안전한 사용 |
|---|---|
| `field_category` | `payload.data`, `metadata.key`, `metadata` 같은 제한된 필드 범주 |
| `limit_name` | 제한된 설정 이름 |

```python
from bluetape.audit import AuditLimitExceededError

try:
    append_to_caller_storage(event)
except AuditLimitExceededError as error:
    rejection_counter.add(  # application-owned telemetry
        1,
        {"field_category": error.field_category, "limit_name": error.limit_name},
    )
    raise
```

## 비식별화 경계

Identity, payload, event의 `repr()`은 값과 무관한 고정된 비식별 형태입니다. 패키지
예외는 호출자 값을 반복하지 않습니다. 이는 우발적인 패키지 노출을 막지만 패키지
소유 redaction, classification, encryption, authorization 또는 logging 시스템이
아닙니다. 모든 출력은 호출자가 책임집니다.

## 페이로드 디스패치

`(content_type, schema_version)` 쌍은 신뢰할 수 없는 호출자 주장입니다. Parser 선택
전과 header 방출 전에 adapter allowlist로 확인하십시오. 지원하지 않는 쌍은 파싱
전에 거부합니다. 이 쌍이 Python class, storage adapter, fallback 또는 transport를
암묵적으로 고르게 해서는 안 되며, 패키지는 bytes가 주장된 형식과 일치하는지
검증하지 않습니다.

## 점진적 도입

새 write 또는 명시적인 호출자 migration에만 값 계약을 도입합니다. 도입은 기존
history를 절대 재작성하지 않습니다. Reader와 migration은 알 수 없는 payload bytes를
그대로 보존해야 합니다. 새 payload route를 추가할 때는 reader를 producer보다 먼저
배포하고 adapter 정책에 대한 replay/producer 호환성을 검증하십시오.

## 제거와 롤백

전용 설치를 제거합니다.

```bash
pip uninstall bluetape-audit
```

메타 배포본 자체도 제거하려면 다음을 사용합니다.

```bash
pip uninstall bluetape
```

패키지 소유 data migration은 없습니다. 격리된 rollback smoke는 meta-extra 환경에서
`bluetape-audit`를 제거한 뒤 `bluetape`와 `bluetape.core` import,
`bluetape.audit is absent`, dependency check 통과를 증명합니다. Core-only 기본 설치도
`bluetape.audit is absent`를 증명합니다.

## 소유하는 것과 소유하지 않는 것

패키지는 불변 감사 값, 생성자 ceiling, 명시적 정책 검증, 값 안전 오류, 결정적 테스트
도우미를 소유합니다. 호출자는 직렬화, 할당 한도, 정책 version, repository, transaction,
durable history, outbox, relay, broker, delivery, retry, retention, authorization,
redaction, logging, telemetry를 소유합니다. 즉 repository, history,
outbox는 외부에 남습니다.

## 테스트 도우미

`bluetape.audit.testing`은 adapter 테스트를 위한 결정적 값과 정확한 보존 assertion을
제공합니다.

```python
from bluetape.audit.testing import assert_audit_event_preserved, make_audit_event

expected = make_audit_event(action="order.cancelled")
actual = adapter_round_trip(expected)
assert_audit_event_preserved(actual, expected)
```

이는 값 assertion이지 durable history가 아닙니다. 도우미는 adapter가 event를
commit, retain, order 또는 deliver했음을 증명하지 않습니다.
