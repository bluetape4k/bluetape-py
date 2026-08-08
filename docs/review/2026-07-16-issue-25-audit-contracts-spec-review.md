# Issue #25 Audit Contracts Specification 검토

날짜: 2026-07-16 KST
Issue: #25 - `feat: add storage-neutral audit event contracts`
Artifact: `docs/superpowers/specs/2026-07-16-issue-25-audit-contracts-design.md`

## 검토 범위

여섯 independent read-only perspective가 implementation planning 전에 written
design을 검토했다. Reviewer에게 write, commit, GitHub mutation, build, test
권한은 없었다. Main session이 severity를 정규화하고 spec을 수정한 뒤 affected
lens만 convergence review를 요청했다.

| Perspective | Role surface | 초기 | 최종 |
|---|---|---:|---:|
| Performance | `code-reviewer` | P0=0, P1=1 | P0=0, P1=0 |
| Stability/reliability | `verifier` | P0=0, P1=3 | P0=0, P1=0 |
| Security/privacy | `code-reviewer` | P0=0, P1=2 | P0=0, P1=0 |
| Operator/Ops | `verifier` | P0=0, P1=2 | P0=0, P1=0 |
| Developer/public API | `code-reviewer` | P0=0, P1=5 | P0=0, P1=0 |
| User/caller | `writer` | P0=0, P1=3 | P0=0, P1=0 |

최종 independent 판정: 여섯 관점 모두 **P0=0, P1=0**.

## 주요 수정

### Bounded construction 및 immutable snapshot

임의의 `Mapping`을 explicit validation 전에 복사하면 caller code를 실행하거나
package bound 없이 allocate할 수 있다는 발견을 수정했다.

- Exact built-in metadata `dict`만 받는다.
- Copy 전에 package hard entry ceiling을 확인한다.
- Private shallow copy 한 번만 수행하고 length를 재확인한다.
- Insertion order로 private copy만 validate한다.
- Complete validation 후에만 read-only proxy를 publish한다.
- Concurrent source mutation에 대한 caller precondition을 문서화한다.

Opaque payload byte는 copy/scan 없이 length-check하고 exact caller bytes object를
보존한다. Default `AuditLimits`는 package hard ceiling이며 explicit policy는
같거나 더 엄격할 수 있지만 넓힐 수 없다.

### Stable timestamp semantics

Mutable/stateful caller `tzinfo`를 허용하던 임의의 aware datetime을 수정했다.
Exact built-in `datetime`과 stdlib `datetime.timezone` 또는 `zoneinfo.ZoneInfo`
만 받고 custom/subclass behavior를 거부한다. Wall-clock field, UTC offset, `fold`
를 보존하며 structural timestamp equality를 명시한다.

### 안전하고 실행 가능한 error

`InvalidAuditLimitsError`를 추가하고 constructor/validator exception ownership을
정의했다. 모든 value type의 `repr`은 constant redacted literal이다.
`AuditLimitExceededError`는 closed mapping의 bounded `field_category`와
`limit_name`만 노출하고 rejected value를 저장하지 않는다. 잘못된 validator
argument와 testing-helper unknown override는 value-free deterministic
`TypeError` message를 사용한다.

### 정확한 Python API

Constructor positional/keyword behavior, exact metadata typing, final/subclass
policy, equality, hashing, repr, validation precedence, helper comparison order,
mismatch category, deterministic factory value를 고정했다. `AuditEvent`는
명시적으로 unhashable이고 metadata equality는 order-insensitive다.
`dataclasses.replace()`는 public contract 밖이다.

### Caller/operator ownership

Event identity, action, occurrence time, subject, actor, correlation, causation의
normative semantics를 추가했다. Adapter validation은 first side effect 직전의
authoritative gate이며 앞선 application validation으로 대체할 수 없다.

Successful validation은 durable capture가 아니다. Atomic capture, stable event ID
idempotency, retry classification, ordering, backpressure, retention,
quarantine/dead-letter, partial-failure recovery는 adapter/operator가 소유한다.

### 실행 가능한 documentation 경계

Direct/meta install, install-to-adapter example, safe error handling,
`(content_type, schema_version)` dispatch, incremental adoption, removal rollback,
English/Korean parity checklist를 고정했다. Framework value는 지원되는 built-in으로
caller가 명시적으로 변환해야 한다.

## Main-session 통합 check

| Check | 근거 | 결과 |
|---|---|---|
| Issue boundary | Live issue #25와 #14 research가 audit value를 SQL/outbox와 분리 | PASS |
| Public surface | Exact export/signature, exception taxonomy, equality/hash/repr, helper behavior 선언 | PASS |
| Storage neutrality | Repository/history/SQL/outbox/broker/worker/serializer/logging/global context 없음 | PASS |
| Package boundary | Python 3.13+, stdlib-only, optional `audit` extra, core-only default 불변 | PASS |
| Testability | Boundary, limit+1, hostile-marker, snapshot, timezone, helper, packaging, wheel, bilingual example 지정 | PASS |
| Operational honesty | Validation을 durability/transaction/delivery/upstream allocation 보장과 분리 | PASS |
| Placeholder | TBD/TODO/FIXME/deferred API choice/unresolved branch 없음 | PASS |
| Diff hygiene | `git diff --check` | PASS |

## 잔여 non-blocking 위험

- Durable adapter가 없으므로 atomic capture, idempotency, replay, delivery는
  future adapter obligation이며 검증된 code가 아니다.
- Character ceiling은 encoded database/transport byte를 제한하지 않으므로
  adapter가 destination-specific constraint를 적용해야 한다.
- Exact built-in input은 deterministic side-effect-free construction을 위해
  framework convenience를 의도적으로 포기한다.
- Caller가 classification/redaction 경계를 무시하면 persistence, logging,
  tracing, serialization, transport가 값을 공개할 수 있다.

## Gate 결과

Written specification은 내부적으로 수렴했고 user review 준비가 되었다.
Implementation planning과 production-code edit는 committed specification을
user가 승인할 때까지 차단된다.
