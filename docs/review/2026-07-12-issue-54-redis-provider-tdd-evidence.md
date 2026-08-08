# Issue #54 Redis Provider TDD 근거

날짜: 2026-07-12 KST
브랜치: `feat/issue-54-redis-provider`
Implementation base: `eb272ac58a2fd0b8445de334b84ee8d557d9d3e7`

## 기준선

구현 전:

```text
uv sync --all-packages --extra fory --extra compression-native --locked
uv run pytest -q
1099 passed in 8.65s
```

## RED/GREEN 기록

| Task | RED 근거 | GREEN 근거 | Commit |
|---|---|---|---|
| Contracts 및 package boundary | `ModuleNotFoundError: bluetape.cache.redis` | 23 contract/packaging test | `1a74c54` |
| Binary envelope | `BinaryEnvelopeFormat` 없음 | 18 binary test; 19 contract | `0d2376e` |
| JSON envelope | `JsonEnvelopeFormat` 없음 | 38 format test; 19 contract | `2bcd50c` |
| Envelope composition | `ResultEnvelopeCodec` 없음 | 16 base + 1 native; 74 combined | `47dcd31` |
| Sync provider | Provider module/constant 없음 | 36 sync test; close subset 반복 | `3810056` |
| Async provider | `AsyncRedisProvider` 없음 | 13 async test; cancellation/close 반복 | `4953b8d` |
| Redis 8 integration | Integration commit 전에 새 Testcontainers case | 8 serial Redis 8 test | `34c6fdf` |
| Packaging 및 CI | Dedicated `redis-provider` job assertion 실패 | 7 packaging test, build, isolated wheel, `actionlint` | `208cfc4` |
| Documentation | Narrow scaffold에 complete API/rollout guidance 부족 | Locale/API smoke와 diff check | `5c2ccbd` |

## Full-suite 발견 및 수정

첫 full-suite run에서 top-level `test_contracts` module 두 개가 수집되어
test를 실행하기 전에 실패했다. Redis file을 `test_redis_contracts.py`로
이름을 바꾸고 정확한 두-file regression set에서 211 tests, full suite에서
1,237 tests를 통과시켰다. Commit: `6ed10b1`.

이 failure는 workspace scope에서만 관찰되므로 full-suite rung를 package
addition의 mandatory guard로 유지한다.

## 새 검증

| Command | 결과 |
|---|---|
| `uv sync --all-packages --extra fory --extra compression-native --locked` | PASS |
| `uv run pytest packages/bluetape-cache-redis/tests -m "not testcontainers" -q` | PASS, 130 passed, 8 deselected |
| `uv run pytest -m native_compression packages/bluetape-cache-redis -q` | PASS, 1 passed, 137 deselected |
| `uv run pytest -m testcontainers packages/bluetape-cache-redis -q` | PASS, 8 passed, 130 deselected |
| `uv run pytest` | PASS, 1,237 passed in 6.72s |
| `uv run ruff format --check .` | PASS, 67 files formatted |
| `uv run ruff check .` | PASS |
| `uv lock --check` | PASS |
| `uv build --all-packages` | PASS, all 12 distributions built |
| `actionlint` | PASS |
| `git diff --check` | PASS |

## Isolated wheel 증명

- Default wheel environment에는 `bluetape`와 `bluetape-core`만 설치했으며
  `find_spec("redis") is None`이 통과했다.
- Plan의 첫 focused smoke invocation은 `bluetape-cache-redis`만 설치한
  뒤 `TTLCache`를 import하려 했다. 승인된 spec이 focused provider의
  exact runtime dependency에서 `bluetape-cache`를 의도적으로 제외하므로
  실패했다.
- 수정한 coexistence proof는 local build한 `bluetape-cache==0.1.0`과
  `bluetape-cache-redis==0.1.0`을 모두 명시적으로 설치했다. `TTLCache`와
  `SyncRedisProvider`가 모두 성공적으로 import되었다. 승인된 dependency
  boundary와 모순되는 smoke-command premise를 고치기 위해 dependency를
  추가하지 않았다.
