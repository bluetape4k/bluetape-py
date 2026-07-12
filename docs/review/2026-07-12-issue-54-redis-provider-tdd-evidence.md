# Issue #54 Redis Provider TDD Evidence

Date: 2026-07-12 KST  
Branch: `feat/issue-54-redis-provider`  
Implementation base: `eb272ac58a2fd0b8445de334b84ee8d557d9d3e7`

## Baseline

Before implementation:

```text
uv sync --all-packages --extra fory --extra compression-native --locked
uv run pytest -q
1099 passed in 8.65s
```

## RED/GREEN Record

| Task | RED evidence | GREEN evidence | Commit |
|---|---|---|---|
| Contracts and package boundary | `ModuleNotFoundError: bluetape.cache.redis` | 23 contract/packaging tests | `1a74c54` |
| Binary envelope | missing `BinaryEnvelopeFormat` | 18 binary tests; 19 contracts | `0d2376e` |
| JSON envelope | missing `JsonEnvelopeFormat` | 38 format tests; 19 contracts | `2bcd50c` |
| Envelope composition | missing `ResultEnvelopeCodec` | 16 base + 1 native; 74 combined | `47dcd31` |
| Sync provider | missing provider module/constant | 36 sync tests; close subset repeated | `3810056` |
| Async provider | missing `AsyncRedisProvider` | 13 async tests; cancellation/close repeated | `4953b8d` |
| Redis 8 integration | new Testcontainers cases before integration commit | 8 serial Redis 8 tests | `34c6fdf` |
| Packaging and CI | dedicated `redis-provider` job assertion failed | 7 packaging tests, build, isolated wheels, `actionlint` | `208cfc4` |
| Documentation | narrow scaffold lacked complete API/rollout guidance | locale/API smoke and diff check | `5c2ccbd` |

## Full-Suite Finding and Repair

The first full-suite run collected two top-level `test_contracts` modules and
failed before tests ran. The Redis file was renamed to
`test_redis_contracts.py`; the exact two-file regression set then passed 211
tests and the full suite passed 1,237 tests. Commit: `6ed10b1`.

This failure was observable only at workspace scope, so the full-suite rung is
retained as a mandatory package-addition guard.

## Fresh Validation

| Command | Result |
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

## Isolated Wheel Proof

- Default wheel environment installed only `bluetape` and `bluetape-core`;
  `find_spec("redis") is None` passed.
- The plan's first focused smoke invocation installed only
  `bluetape-cache-redis` and then tried to import `TTLCache`; it failed because
  the approved spec intentionally excludes `bluetape-cache` from the focused
  provider's exact runtime dependencies.
- The corrected coexistence proof explicitly installed both locally built
  `bluetape-cache==0.1.0` and `bluetape-cache-redis==0.1.0`. Both `TTLCache` and
  `SyncRedisProvider` imported successfully. No dependency was added to repair
  a smoke-command premise that contradicted the approved dependency boundary.

