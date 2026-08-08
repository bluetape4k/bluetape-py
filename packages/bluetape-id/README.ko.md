# bluetape-id

[English](README.md) | 한국어

Python 3.13+에서 표준 라이브러리만 사용해 UUIDv4, 단조 UUIDv7, 난수 ULID,
명시적 단조 ULID 값을 제공합니다.

## 설치

PyPI 배포는 보류 중입니다. 목표 설치 형태는 집중 배포 패키지 또는 opt-in
meta extra입니다.

```bash
pip install bluetape-id
pip install "bluetape[id]"
```

기본 `bluetape` 설치에는 이 패키지가 포함되지 않습니다.

## 빠른 시작

<!-- value-example:start -->
```python
from bluetape.id import MonotonicULIDGenerator, parse_ulid, ulid, uuid4, uuid7

random_uuid = uuid4()
sortable_uuid = uuid7()
random_ulid = ulid()
monotonic = MonotonicULIDGenerator()
first, second = monotonic.new(), monotonic.new()

assert random_uuid.version == 4
assert sortable_uuid.version == 7
assert parse_ulid(random_ulid) == random_ulid
assert first < second
```
<!-- value-example:end -->

`UUID7Generator`, `ULIDGenerator`, `MonotonicULIDGenerator`는 결정적 테스트를
위한 clock과 entropy callback을 받습니다. Callback 실패 시 entropy byte를 오류
메시지에 복사하지 않습니다.

## ID는 비밀값이 아님

UUID와 ULID는 식별자이지 자격 증명이 아닙니다. UUIDv7과 ULID는 밀리초
타임스탬프를 노출하며 process-local 단조 순서는 분산 전체 순서가 아닙니다. ID에
비밀을 넣거나 순서를 authorization, uniqueness, cross-process coordination 보장으로
사용하지 마십시오.

## 생성기 상태

모듈의 `uuid7()`은 process-local thread-safe 생성기 하나를 공유합니다. `ulid()`는
random entropy를 사용하며 단조성을 약속하지 않습니다. 한 프로세스에서 lock 획득
순서가 필요할 때 `MonotonicULIDGenerator`를 직접 생성합니다.

단조 상태는 의도적으로 일시적입니다. 재시작, fork, upgrade, rollback 후에는 새
상태에서 시작합니다. 더 강한 epoch, machine identity, persistence, distributed-order
정책은 애플리케이션이 소유합니다.

## 영속성과 롤백

Canonical lowercase UUID 문자열 또는 canonical 26-character ULID 문자열만
저장합니다. `uuid7_timestamp_ms()`, `parse_ulid()`, `ulid_timestamp_ms()`가 이 경계를
검증합니다. Version wrapper와 직렬화된 generator state는 없습니다. `bluetape-id`
또는 `bluetape[id]`를 제거하기 전에 import를 중단하고 application storage의
canonical 문자열은 유지합니다.

## 보류 범위

KSUID는 실제 compatibility consumer가 생길 때까지 보류합니다. Snowflake ID는
machine identity, epoch, clock rollback, restart persistence를 별도로 설계해야 합니다.
Secret, database key, distributed coordination, 패키지 소유 background worker는
제공하지 않습니다.
