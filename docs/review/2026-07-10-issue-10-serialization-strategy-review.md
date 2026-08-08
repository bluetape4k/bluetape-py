# Issue #10 Serialization Strategy 검토

## 범위

영속적인 Python serialization 결정, source attribution, 후속 이슈 #45와
#46을 검토한다.

## 근거

- 공식 Python `json` 및 `pickle` 문서
- orjson, msgpack-python, Pydantic, cbor2, Apache Fory의 primary project 문서
- 로컬 `bluetape-go`, `bluetape-rs`, `bluetape4k` serialization 계약
- `git diff --check`, source-link 검사, live GitHub issue metadata

## 검토 결과

| Tier | 초점 | P0 | P1 | 결과 |
| --- | --- | ---: | ---: | --- |
| Architecture | package 분할 및 semantic interoperability | 0 | 0 | #45가 core 계약을 소유하고, #46은 schema/type-id conformance가 필요한 명시적 Fory extra로 차단되어 있다. |
| Security | 신뢰할 수 없는 decoding 및 unsafe format | 0 | 0 | 승인 전에 finite byte/depth limits, UTF-8 boundary, structural depth preflight, pickle fallback 금지, Fory trusted-only initial decode를 보완했다. |
| Performance | bounded parse 및 adapter 선택 | 0 | 0 | JSON과 MessagePack limits가 명시적이며 auto-detection이나 retry registry를 제안하지 않는다. |
| Stability | typed failure 및 version 동작 | 0 | 0 | metadata/version/trust/limit/malformed case가 명시적 typed error이며 조용한 `None`이나 fallback 경로가 없다. |
| Operator | packaging 및 외부 source 주장 | 0 | 0 | meta default는 core-only로 유지하고 extras와 source link를 명시했다. |
| Developer | 구현 가능한 acceptance criteria | 0 | 0 | #45는 UTF-8/depth tests를, #46은 cross-language fixture와 safety gate를 지정한다. |
| User | 문서화된 범위 및 다음 작업 | 0 | 0 | research index, WIP, linked follow-up issue가 선택한 경로를 공개한다. |

## 결과

`P0=0`, `P1=0`. Research는 documentation PR validation을 진행할 준비가
되었다. 향후 Fory 작업은 #45와 자체 conformance/security gate가 완료될 때까지
차단된다.
