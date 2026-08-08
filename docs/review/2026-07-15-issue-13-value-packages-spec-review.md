# Issue #13 Value Packages 사양 검토

날짜: 2026-07-15 KST
Issue: #13
판정: PASS
최종 발견: P0=0, P1=0

## 검토 artifact

- Research SHA-256: `5ee5650cf18d83e4c604accc736610581b00741e0582039cab0c894f8a57c066`
- Spec SHA-256: `0988eef8463eca44f485b91a472fe2958d3dbdf419a783a0c24a53de9f48923e`
- Plan SHA-256: `81ededc7b59a0d21c2ad9da5727288012fb8a18df60c99e86a1c4bad7c2da812`

## 독립 관점

| 관점 | 초기 주요 발견 | 수정 | 최종 |
|---|---|---|---|
| Developer/API | 불완전한 declaration, entropy mapping, unsupported generic typing, package/task ownership, executable TDD contract | Signature와 entropy bit 고정, generic을 runtime dimension으로 교체, package metadata/ownership/node를 literal로 작성 | P0=0, P1=0 |
| Operations | Snapshot durability, provenance, atomic replace, hermetic build, classification order, exact-head replay, rollback, diagram proof gap | Committed-source authority, bounded atomic updater, locked dependency preparation, offline wheel probe, pre-review rebase, forward rollback, specialized replay | P0=0, P1=0 |
| User/caller | Measure equivalence/parser rule, generator concurrency, minor-unit behavior, compatibility, rollback, locale docs gap | Exact caller contract, persistence limit, schema, custom-unit ownership, current-ISO limit, uninstall rollback, EN/KO parity | P0=0, P1=0 |

세 최종 independent review가 위의 동일한 spec/plan hash를 사용했다. Reviewer는
artifact를 수정하지 않았다.

Task 1에서 동일한 top-level `test_packaging.py` basename 세 개가 pytest default
import collision을 재현했다. Package test와 모든 plan node/command path를 unique
name으로 바꿨다. 세 관점이 수정된 plan hash를 P0=0, P1=0으로 다시 검토했으며
registry entry 36개와 exact command 36개는 일대일이다.

## Main-session 관점

### Performance

P0=0, P1=0. Parser, unit registry, Decimal coefficient/exponent, XML
byte/row/currency, diagnostic output을 bounded하게 한다. Clock/entropy callback은
generator lock 밖에서 실행하며 background worker, scheduler, provider refresh,
import-time network work를 소유하지 않는다. Focused stability loop를 요구하고
numerical performance threshold는 hot-path regression 근거가 생길 때까지 N/A다.

### Stability

P0=0, P1=0. Generator failure는 state를 변경하지 않는다. Ordering claim은
한 process의 lock acquisition으로 제한한다. Decimal arithmetic은 caller
context를 변경하거나 상속하지 않는 package-local context를 사용한다. ISO output은
same-directory temporary file과 atomic replacement를 사용하며 실패할 때마다
previous output을 보존한다. Serialization은 primitive, versionless이며 v1 schema로
명시적으로 제한한다.

### Security

P0=0, P1=0. ID는 secret이 아니다. Error에서 entropy, caller payload, XML row를
제외한다. Money는 binary float와 non-finite/unbounded input을 거부한다. XML은
DTD/entity marker와 oversized/schema-drifted content를 거부한다. Package
import/build/runtime은 network-free이며 maintainer download 하나만 bounded
timeout과 committed SHA-256 provenance가 있는 explicit HTTPS다.

## 검증

- 여섯 Python code fence가 Python 3.13 syntax contract에서 compile
- Literal Measure declaration이 Python 3.13에서 import되고 signature evaluation
  전에 built-in default가 정의되며 열 개 unit symbol이 정렬됨
- 세 literal package TOML record와 exact root/meta mapping 고정
- `git diff --check` 통과

Spec gate는 닫혔다. Production implementation은 plan의 named RED/GREEN node를
통해서만 시작할 수 있다.
