# Issue #18 JWT 및 Key Rotation Implementation Plan Review

- 날짜: 2026-07-20 KST
- 대상: `docs/superpowers/plans/2026-07-20-issue-18-jwt-key-rotation-implementation-plan.md`
- 기준: 승인 spec 및 spec review
- 방식: 작성자와 분리된 read-only critic review, correction 후 동일 critic 재검토

## 최종 판정

- Plan gate: **PASS**
- P0: **0**
- P1: **0**
- P2: **0**

## 해결한 초기 P1

1. RSA JWK의 `kid`, `alg`, `use`, `key_ops`를 intended operation과 비교하는
   positive/negative matrix를 추가했다.
2. 아직 구현되지 않은 symbol을 Task 1에서 final `__all__`로 export하던 순서를
   없앴다. 각 task는 실제 symbol만 단계적으로 export하고 final exact surface는
   모든 symbol이 생기는 Task 7에서 고정한다.
3. issuance transformation을 Task 4 profile constructor와 Task 6 decorator가
   중복 소유하던 문제를 제거했다. Task 6의 private pure function 하나가 변환을
   소유하고 decorator가 clock을 한 번 capture한다.
4. `VerifiedToken.headers`를 승인·검증된 custom non-reserved protected header만
   포함하는 immutable mapping으로 고정했다. `alg`, `kid`, `typ` 및 reserved
   header는 포함하지 않는다.
5. 큰 batch RED/GREEN을 25개의 file/test-node 단위 microcycle, intended RED,
   minimum GREEN slice, 대표 test/implementation snippet으로 분해했다.
6. security review 대상 SHA와 이후 evidence-only delta의 provenance를 분리했다.
   PR body의 `## DoD Status`는 local completion이 아니라 별도 PR gate로 이동했다.

## 해결한 P2 및 최종 실행 보정

- public export 순서를 spec 분류와 일치시켰다.
- bool-as-int NumericDate, cyclic/depth/node-bounded JSON, overflow error mapping을
  hostile matrix에 추가했다.
- cache get/set/clear failure를 재현하는 private `cache_factory` injection seam을
  고정했다.
- wheel smoke에 설치, import, assertion, cleanup command를 명시했다.
- clean checkout에 `dist/`가 없을 수 있다는 최종 P1을 해결하기 위해
  task-scoped output directory에 `bluetape-cache`와 `bluetape-jwt` wheel을 각각
  build하고 동일 artifacts만 smoke target에 설치하도록 보정했다.

## 최종 확인

- approved algorithm, key strength, lifecycle, claim/profile, decorator, cache,
  redaction/logging 계약이 모두 owning task와 named microcycle에 연결된다.
- async #88, JWE #89, compression #90, distributed/remote repository는 구현 범위
  밖에 남아 있다.
- exact public surface와 signature, strict header/JSON boundary, cache key/TTL/epoch,
  review SHA provenance가 구현자가 추측하지 않아도 될 정도로 고정됐다.
- clean checkout 기준 명령과 local stop boundary가 실행 가능하고 일관된다.
- push, PR, merge, release, publication 권한은 이 plan에 포함되지 않는다.

## 검증 증거

- 독립 critic 최종 판정: `APPROVE — P0=0, P1=0, P2=0`
- `git diff --check`: PASS
- production code 변경: 없음
