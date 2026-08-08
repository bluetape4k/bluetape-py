# Issue #24 Observability TDD 근거

날짜: 2026-07-15 KST
Issue: #24, milestone `0.2.0`
Implementation evidence head: `40676c3d963a641ac230f40731fe065b9c2401ee`

## 승인된 입력

- Spec SHA256: `f555888ace6273bb7049073bdf953c816870599d725167321ed7e1f06c26f6a1`
- Spec review SHA256: `d28395e897d8944e13b68bda6c0997ebb88b8191ac6173bf75c20549e489b49a`
- Plan SHA256: `1943735f953f0d854a699d4ee7701851684223b9e803d3ed745401568e312339`
- Plan review SHA256: `be76f14965bb544697eeb1c438aae0cb12182bc744b839ae962191c17e22a118`

## RED에서 GREEN으로의 전환

| Task | RED 근거 | GREEN 근거 | Owning commit |
|---|---|---|---|
| Distribution boundary | Distribution, workspace registration, lock entry, classifier가 없어 packaging registry run 4 failures/6 passes | 10 boundary/classifier node 통과; wheel metadata는 `opentelemetry-api>=1.43,<2`만 포함 | `4d88d91` |
| Bounded recording primitive | `bluetape.observability._recording`이 없어 `test_recording.py` collection 실패 | Normalization, span, failure-isolation, source-boundary test 6개 통과 | `be3b72b` |
| Resilience 및 Redis adapter | 두 public module과 세 class가 없어 public API/adapter test 실패 | Public API, resilience, Redis mapping test 31개 통과 | `ae18d35` |
| Real SDK 및 context | SDK-selected test에 implementation-backed aggregation/current-context proof 없음 | SDK integration test 6개가 skip 없이 caller-owned teardown으로 통과 | `c64891e` |
| Resource 및 performance | Deterministic ownership, retention, allocation, benchmark contract test 없음 | Deterministic test 9개와 3-run benchmark mode 두 개가 budget 충족 | `78be6ac` |
| Docs, CI, wheel isolation | README execution, logging separation, CI ownership, isolated wheel probe 없음 | Documentation test, `actionlint`, focused/default/readme wheel verifier 통과 | `3bc2e5f` |

실제로 실패한 run만 RED로 표시했다. 이미 올바른 runtime behavior에 대해 나중에
추가한 review coverage는 retroactive RED가 아닌 coverage repair로 기록한다.

## Review-driven coverage repair

- `a1245e4`는 실제 sync/async Redis provider와 unobserved control을 짝짓고
  모든 SDK metric의 type/unit/description을 assertion하며 adapter normalization
  boundary에서 process-control exception 전파를 증명했다.
- `e672889`는 focused gate가 marker deselection 전에 collection됨을 확인한
  뒤 workspace-only logging import를 marker 뒤로 이동했다.
- `40676c3`는 un-packaged observability test에 unique helper/module name을
  부여하고 SDK benchmark subprocess parameter만 `observability_sdk`로 mark하며
  남은 fail-closed release classifier를 조정했다.

## Evidence 전 수렴 gate

Focused dependency state:

```text
57 passed, 9 deselected
8 SDK-selected passed, 58 deselected
JUnit failures=0 errors=0 skipped=0
Ruff check passed; 15 files formatted; focused sdist and wheel built
```

Fresh all-package/all-extra sync 후 `opentelemetry.sdk` 부재를 증명한 full workspace:

```text
1586 passed, 139 deselected
Ruff check passed; 126 files formatted
15 distributions built as sdist and wheel
wheel verifier, actionlint, and git diff --check passed
```

Evidence commit은 self-referential하지 않는다. Exact SHA와 fresh post-commit
rerun은 이 파일에 넣는 content가 아니라 delivery evidence다.
