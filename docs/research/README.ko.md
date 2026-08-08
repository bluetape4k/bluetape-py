# 리서치 색인

[English](README.md) | [한국어](README.ko.md)

리서치 노트는 bluetape4k, bluetape-go, bluetape-rs의 source capability를
Python package scope, dependency candidate, GitHub issue와 연결합니다.

| 마일스톤 | 리서치 |
|---|---|
| `0.2.0` | [Issue #10 직렬화 전략](2026-07-10-issue-10-serialization-strategy.md) |
| `0.2.0` | [Issue #13 ID, measure, money 경계](2026-07-15-issue-13-value-packages.md) — 구현 경계 authority |
| `0.2.0` | [Issue #14 SQL, repository, audit, outbox 전략](2026-07-16-issue-14-sql-repository-audit-outbox-strategy.md) |
| `0.2.0` | [Issue #16 AWS, graph, text, image adapter 경계](2026-07-18-issue-16-adapter-boundaries.md) |
| `0.2.0` | [Issue #23 observability 및 OpenTelemetry 경계](2026-07-15-issue-23-observability-opentelemetry-boundaries.md) |

## 갱신 규칙

대규모 implementation issue를 추가하거나 milestone scope를 바꾸기 전에 matching
research note를 먼저 갱신합니다. 각 note는 다음 내용을 명시해야 합니다.

- 확인한 소스 repository와 module;
- Python package 방향;
- 후보 dependency와 배제한 대안;
- 연결된 issue;
- 현재 결정과 non-goal.

Research issue는 implementation approval이 아닙니다. Package boundary,
dependency policy, test, release impact가 분명해진 뒤 구현을 시작합니다.
