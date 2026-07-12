# Issue #59 Compressor Contracts Lessons

## Context

Redis payload를 줄이기 전에 serializer와 독립적으로 조합할 수 있는 compressor
계약이 필요했다. Kotlin/JVM 사용자가 익숙한 interface형 기능과 실패 규칙은
유지하되, Python API를 nominal hierarchy나 언어 간 wire 호환에 묶지 않아야 했다.

## Decisions

- `typing.Protocol`로 structural contract를 만들고 bundled 구현은 frozen, slotted
  dataclass로 제공한다. Custom compressor는 상속 없이 같은 계약을 구현할 수 있다.
- 기본 distribution은 stdlib-only로 유지한다. LZ4, Snappy, Zstd는 focused extra와
  aggregate `native` extra로만 설치하고 `bluetape`의 default/dev/all에는 넣지 않는다.
- 모든 decoder가 같은 public bound를 제공하더라도 provider 특성에 맞춰 구현한다.
  LZ4는 incremental `remaining + 1` budget, Snappy는 raw declared length preflight,
  Zstd는 frame content size preflight를 사용한다.
- Redis 조합 순서는 `serialize -> compress -> store`, 읽기는 역순이다. Algorithm과
  schema는 envelope/configuration이 명시해야 하며 payload auto-detection은 하지 않는다.

## Surprises and failures

- `python-zstandard`의 one-shot `max_output_size`는 content size가 기록된 frame에서
  기대한 hard cap으로 사용할 수 없었다. 따라서 content size를 먼저 읽어 한도를
  검사하고, unknown size frame을 계약 밖 입력으로 거절해야 했다.
- Optional provider test를 한 process에 모으면 앞선 import가 뒤 환경을 오염시킬 수
  있었다. Provider-free import와 focused missing-extra 검증은 subprocess 또는 별도
  wheel venv로 분리해야 실제 설치 경계를 증명한다.
- Provider exception을 handler 안에서 곧바로 바꾸면 `__context__`와 traceback이 raw
  diagnostic 또는 caller payload를 잡고 있을 수 있다. Ordinary failure는 handler를
  빠져나온 뒤 새 stable error로 발생시키고 `MemoryError`와 `BaseException`은 보존한다.
- 7-Tier user/caller review에서 README가 missing provider 오류를
  `CompressionError`라고 잘못 설명한 P1을 발견했다. Source, spec, test가 맞아도 문서의
  exact exception type은 별도 claim-to-source 검사가 필요하다.

## Outcome and evidence

- Six immutable implementations and the legacy function API pass 221 focused tests.
- The full non-Docker workspace run passes 1097 tests with one Testcontainers test deselected.
- Base/focused/aggregate wheel environments prove provider isolation and namespace-package shape.
- Ruff, lock validation, all-package sdist/wheel builds, actionlint, and diff check pass.
- Pre-PR convergence finished at `P0=0`, `P1=0`, `P2=0`, `P3=0` after the README and package
  description repairs.

## Future guard

Provider upgrades must rerun strict trailing/corruption fixtures, declared-size preflight spies,
large bounded round-trips, exact metadata tests, and isolated focused-extra wheel environments.
Do not approve a version bump from aggregate tests alone. #54 must consume stable algorithm IDs
only after #59 merges and the Redis branch rebases onto current `origin/develop`.
