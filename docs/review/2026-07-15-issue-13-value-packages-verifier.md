# Issue #13 value packages verifier

날짜: 2026-07-15 KST
Evidence commit 전 verified implementation head:
`76e89614a96e4ab7ea3af37adfc5fb626f0e4981`

## Acceptance criteria

| Criterion | 근거 | 결과 |
|---|---|---|
| 독립적인 Python 3.13 distribution 3개 | ID, measure, money package suite 통과 및 세 stdlib-only wheel 독립 build | Pass |
| Exact public contract | Ordered export, signature, immutability, parsing, primitive schema, invalid input test | Pass |
| ID ordering/state boundary | UUIDv7/ULID vector, same-tick order, rollback, overflow, entropy failure, concurrency, 5,000-value run | Pass |
| Dimension-safe measurement | Registry, conversion, arithmetic, serialization, invalid dimension, 10,000 round trip | Pass |
| Exact money/explicit rounding | Ordinary arithmetic silent rounding trap, explicit quantization만 허용, money test 85개 통과 | Pass |
| Reproducible current ISO data | Exact schema, canonical 250/150 minimum, full provenance, count 280/178, byte-identical regeneration | Pass |
| Thin default install | Default meta environment는 core만 포함하고 세 value module 없음 | Pass |
| Bilingual docs/visual | EN/KO installed-wheel example, SVG/PNG XML/render/connector/geometry/endpoint/visual audit 통과 | Pass |

## 검증 matrix

| Gate | 근거 | 결과 |
|---|---|---|
| Package target | ID 15, measure 18, money 85, meta/docs 6 | Pass |
| CI-shaped workspace | Linux provenance portability repair 후 `1711 passed, 139 deselected` | Pass |
| Focused optional SDK control | Dedicated sync 후 `8 passed, 58 deselected` | Pass |
| Static quality | Ruff lint, 165-file format, actionlint, `git diff --check` | Pass |
| Packaging | 18 workspace distribution을 sdist와 wheel로 build | Pass |
| Value wheel isolation | 18 wheel 정확히 한 번, isolated environment 10개, default absence, socket denial | Pass |
| ISO replay | 280 row, 178 unique currency, byte-identical committed output | Pass |
| Diagram | XML 및 deterministic 2600x1600 render, 모든 audit 통과 | Pass |
| Review | 세 independent six-lens pass가 P0=0, P1=0, P2=0으로 수렴 | Pass |
| Lesson | Mandatory Type A lesson이 exactness/data/wheel/collection finding을 기록 | Pass |

## 근거 기반 N/A 및 pending gate

- Docker/Testcontainers: stdlib-only value package이므로 N/A. Focused CI가
  unrelated service-backed suite ownership을 유지한다.
- External FX, locale, registry, runtime ISO refresh: 승인 범위에서 N/A. Caller-owned
  또는 deferred 상태다.
- Tag, release, publication, workflow dispatch: 요청하지 않아 N/A.
- PR CI와 merge: evidence commit을 rebase하고 approved PR을 만든 뒤 pending.
  Merge에는 새 명시적 승인이 필요하다.

첫 PR run에서 raw CRLF ISO source의 platform checkout 차이를 발견하고 수정했다.
Git은 이제 provenance XML을 binary로 취급하고 index/worktree byte가 일치하며
digest와 byte-identical regeneration이 Linux CI에서도 portable하다.

Local implementation 판정: **PASS**. Evidence commit은 self-referential하지
않으며 exact-head replay와 PR check는 delivery evidence로 남는다.
