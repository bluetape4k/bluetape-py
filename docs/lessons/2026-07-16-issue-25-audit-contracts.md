# Issue #25 저장소 독립 감사 계약 교훈

## 맥락과 결정

감사 이벤트는 결국 저장되어야 하지만 첫 패키지가 repository나 history protocol을
소유하면 query, transaction, pagination, retention, outbox delivery까지 너무 일찍
고정된다. `bluetape-audit`는 하나의 감사 사실을 표현하는 불변 값, 명시적 제한 검증,
안전한 오류, adapter 보존 테스트만 제공하고 영속성은 구체 adapter와 호출자에게
남기는 values-first 경계를 선택했다.

Payload도 JSON tree가 아니라 호출자가 선언한 content type/schema version과 불변
bytes로 유지했다. Repository, history, JSON codec, global user/request context는 모두
거절했다. 이 결정은 기능 부족이 아니라 아직 source-backed 공통 계약이 없는 영역을
공개 API로 고정하지 않기 위한 범위 통제다.

## 재사용 가능한 발견

### Values-first는 adapter 선택을 미루면서도 중요한 계약을 고정한다

Event ID, action, occurrence time, subject/actor, correlation/causation,
payload, metadata는 storage와 무관하게 의미가 안정적이다. 반면 append/list/query,
transaction, idempotency, outbox relay는 storage와 운영 방식에 따라 달라진다. 먼저
값을 고정하면 후속 PostgreSQL adapter가 같은 event를 사용할 수 있지만 core package가
SQL이나 delivery lifecycle을 소유하지 않는다.

### Python 경계에서는 exact built-in이 숨은 실행을 막는다

`str`, `bytes`, `dict`, `datetime`, `timezone`/`ZoneInfo`의 exact type만 받으면 custom
subclass나 mapping hook이 검증 중 코드를 실행하는 경로를 줄일 수 있다. Coercion,
normalization, UTC 변환을 하지 않으므로 caller 값과 timezone의 wall/offset/fold 의미도
그대로 보존된다. Framework 객체 편의보다 결정적이고 검토 가능한 경계를 우선한다.

### Metadata는 private copy를 검증하고 마지막에 공개한다

입력 dict를 먼저 검증한 뒤 copy하면 검증한 내용과 보존한 내용이 달라질 수 있다.
Entry 수를 사전 확인하고, built-in shallow copy를 정확히 한 번 만들고, private copy의
수를 다시 확인한 뒤 그 copy만 한 번 검증하고 마지막에 read-only proxy로 공개해야
한다. `_copy_metadata` seam은 thread race를 만들지 않고 이 순서와 실패 원자성을
결정적으로 시험하게 했다.

### 구성 가능한 제한은 hard ceiling보다 엄격해질 수만 있다

Constructor ceiling은 package가 보존하거나 복사하는 작업을 제한한다. Adapter 정책은
환경에 따라 더 엄격할 수 있지만 ceiling보다 넓어지면 이미 constructor가 거절한 값을
허용한다고 오해하게 된다. `AuditLimits`를 equal-or-stricter로 제한하고 adapter가
versioned policy를 첫 부작용 직전에 적용하도록 하면 의미가 단순해진다. 정책 강화 전
producer와 replay 호환성을 확인하고 정책 ID는 event metadata 밖의 bounded telemetry로
관리해야 한다.

### 시간 동등성은 instant가 아니라 보존 계약에 맞춘 구조 비교다

감사 값은 caller가 제공한 timezone-aware datetime을 정규화하지 않는다. Python의 기본
datetime equality만 사용하면 같은 instant와 같은 표현을 구분하기 어렵다. Wall fields,
UTC offset, fold로 고정 크기 key를 만들어 비교하면 offset/fold 의미가 보존되고 timezone
변환이나 database lookup이 필요 없다.

### 안전한 오류는 값 대신 닫힌 범주를 제공한다

고정 메시지만 제공하면 운영자가 어떤 정책이 초과됐는지 알 수 없다. 반대로 rejected
value를 메시지에 넣으면 payload, identity, metadata가 노출된다.
`AuditLimitExceededError.field_category`와 `limit_name`만 닫힌 저카디널리티 값으로
제공하면 caller가 메시지를 파싱하거나 민감한 값을 로그로 남기지 않고도 metric을
만들 수 있다. 모든 event field는 민감할 수 있다는 가정이 안전한 기본값이다.

### 검증 위치와 durability 소유권을 문서와 그림에서 분리한다

Application prevalidation은 빠른 실패일 뿐 storage gate가 아니다. Caller-owned adapter가
첫 부작용 직전에 `validate_audit_event`를 호출하는 위치가 정본이며, 성공 반환도 recorded,
committed, delivered를 뜻하지 않는다. SVG+PNG는 package code와 first-side-effect boundary를
다른 ownership region으로 배치해 이 차이를 글보다 빠르게 드러낸다. PNG 원본 검토가
script 결과와 다르면 PNG를 우선하고 다시 렌더해야 한다.

### Namespace package 경계는 source import가 아니라 격리 wheel로 증명한다

Focused wheel과 `bluetape[audit]`는 audit를 제공하고 기본 `bluetape`는 core-only여야 한다.
Built wheel을 offline/no-index 환경에 설치하고 `python -I`, module origin, socket denial,
METADATA, root initializer 부재를 확인해야 sibling checkout 누출을 막을 수 있다. Meta-extra
환경에서 audit만 제거한 뒤 namespace와 core가 남고 audit가 사라지는 smoke는 설치
rollback을 증명하지만 data migration을 약속하지 않는다.

### 새 distribution은 모든 fail-closed 분류 정본에 등록한다

Focused package 테스트와 build가 통과해도 workspace 전체를 열거하는 publishable/private
분류가 여러 package test에 존재할 수 있다. 첫 canonical workspace replay가 resilience 쪽
중복 집합의 `bluetape-audit` 누락을 잡았다. 새 distribution을 추가할 때는 `rg`로 exhaustive
classification 집합을 모두 찾아 동일하게 갱신하고, equality assertion을 느슨하게 만들지
않는다. 중복 자체를 정리하는 작업은 별도 범위로 두되 현재 fail-closed 보호는 유지한다.

### Package README도 현재 publish authority를 직접 말해야 한다

루트 README가 PyPI hold를 설명해도 package README로 바로 진입한 사용자는 registry 명령을
현재 사용 가능한 절차로 받아들일 수 있다. 각 package Install 절은 현재 source workspace
sync와 local wheel build를 먼저 제시하고, `pip install` 형태는 publication 이후 목표라고
명시해야 한다. Localized README 계약에 이 상태와 명령을 함께 고정하면 release authority와
사용자 안내가 갈라지는 것을 막을 수 있다.

## 향후 가드

후속 audit adapter는 이 package에 repository/history/JSON/global context를 추가하지 않는다.
구체 storage package가 caller-owned transaction과 첫 side effect를 명시하고, stable event
ID 재시도, atomic capture, idempotency, ordering, backpressure, retention, relay와 delivery
semantics를 자체 spec과 conformance test로 증명해야 한다. Payload route는 adapter allowlist로
parser/header 사용 전에 확인하고 unsupported pair는 parsing 전에 거절한다.

Public field나 export를 바꾸면 constructor/validator/helper total order, hostile-marker matrix,
focused/meta/default wheel proof, 동일 EN/KO installed-wheel 예제, SVG+PNG ownership model을 함께
갱신한다. 작은 stdlib-only bounded operation에는 noisy wall-clock benchmark를 추가하지 말고
no-scan, one-copy, fixed-entry, fixed-key 계약을 source와 test로 직접 증명한다.

## 사전 검증 증거

- Task 7 focused set `441 passed`.
- 19개 workspace distribution build와 lock check 통과.
- SVG/PNG connector, crossing, intrusion, geometry, endpoint, corner failure 모두 0.
- 각 Task spec/quality review는 P0=0, P1=0으로 수렴.
- 첫 candidate workspace replay가 publication 분류 누락을 재현했고, 두 exhaustive
  classification suite의 bounded repair 검증은 `11 passed`.
- 첫 exact-head review의 stability/Ops P2 두 건을 닫은 README 및 전체 ordered-validation
  보강 검증은 `102 passed`.

최종 exact-head canonical replay와 독립 six-lens/verifier 결과는 이 파일을 포함한 evidence
commit 이후 변경 없는 SHA에서 workflow receipt와 PR body에 기록한다.
