# Issue #50 Local Cache 사양 검토

- Spec: `docs/superpowers/specs/2026-07-11-issue-50-local-cache-design.md`
- Review gate: Type A Step 2-R
- 날짜: 2026-07-11
- 최종 gate: P0=0, P1=0

## 검토 관점

| Lens | 초기 주요 발견 | 해결 | 최종 |
| --- | --- | --- | --- |
| Performance | Different-key concurrency wording가 너무 넓고 expiry sweep가 O(max_size) work를 유발할 수 있으며 benchmark input이 고정되지 않음 | Concurrency 주장을 loader body로 좁히고 bounded stale-node expiry heap 도입, reproducible benchmark matrix 요구 | P0=0, P1=0 |
| Stability | Owner-only flight와 abandoned async loader가 누수되거나 stale value를 publish할 수 있으며 cancellation과 loop binding의 ownership rule이 정확하지 않음 | Active/owned flight 분리, abandonment를 versioned non-publishable로 만들고 immediate caller cancellation과 terminal cache ownership, atomic loop binding 지정 | P0=0, P1=0 |
| Security | Distinct-key load가 unbounded이고 observability가 sensitive data를 노출할 수 있으며 entry count는 byte limit가 아님 | `max_inflight`, low-cardinality snapshot, opaque task name, redaction과 untrusted object sizing에 대한 caller 책임 추가 | P0=0, P1=0 |
| Operator | Snapshot counter가 current flight occupancy를 노출하지 않음 | Current active/abandoned/superseded gauge와 lock-consistent lifecycle semantics 추가 | P0=0, P1=0 |
| User | Same-key owner precedence, `invalidate()` result, `ttl=None`, value identity, adoption example이 모호함 | Owner loader/TTL precedence, return value, default-TTL behavior, strong identity semantics, README example 요구 정의 | P0=0, P1=0 |
| Developer | Mutation generation, key typing, validation taxonomy, export, stats lifetime가 불충분 | Generation isolation, `Hashable` typing, exact exception/export, counter-versus-gauge lifetime rule 추가 | P0=0, P1=0 |

## 통합 판정

Spec은 planning을 위한 implementation-ready 상태다. Redis coordination은 issue
#51에 남기고 thin default installation을 유지하며, synchronous 및 asynchronous
caller 모두에 대해 bounded entry와 loader ownership을 정의한다.

P0=0 P1=0
