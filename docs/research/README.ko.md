# Research Index

[English](README.md) | [한국어](README.ko.md)

Research note는 bluetape4k, bluetape-go, bluetape-rs의 source capability를
Python package scope, dependency candidate, GitHub issue와 연결합니다.

| Milestone | Research |
|---|---|
| `0.2.0` | [Issue #10 직렬화 전략](2026-07-10-issue-10-serialization-strategy.md) |
| `0.2.0` | Issue #14 SQL, repository, and audit outbox strategy research - pending |
| `0.2.0` | Issue #16 AWS, graph, text, and image adapter boundary research - pending |

## 갱신 규칙

Broad implementation issue를 추가하거나 milestone scope를 바꾸기 전에 matching
research note를 먼저 갱신합니다. 각 note는 다음 내용을 명시해야 합니다.

- 확인한 source repository와 module;
- Python package direction;
- candidate dependency와 rejected alternative;
- linked issue;
- current decision과 non-goal.

Research issue는 implementation approval이 아닙니다. Package boundary,
dependency policy, test, release impact가 분명해진 뒤 구현을 시작합니다.
