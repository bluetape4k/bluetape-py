# Issue #7 Collections 패키지 교훈

날짜: 2026-07-10 KST

## 배경

Issue #7에서는 `v0.1.0` 이후 첫 확장 package인 `bluetape-collections`를
도입했다.

## 결정

package는 Python-native이면서 eager 방식으로 유지한다. 첫 public surface는
`bluetape.collections`에서 chunking, grouping, distinct, partition과
exception-transparent map/filter helper를 제공한다. `bluetape-go`나 bluetape4k와의
광범위한 parity까지 시도하지 않는다.

## 결과

계획 검토에서 구현 전에 보완해야 할 중요한 공백을 발견했다.

- caller-owned container mutation과 예상된 iterator consumption을 구분한다.
- thin `bluetape` meta dependency boundary를 증명한다.
- publishing이 HOLD인 동안 현재 PyPI에서 사용할 수 있다고 오해하게 만드는
  README 문구를 피한다.
- single-pass/no-extra-full-copy 불변 조건과 stdlib allocation smoke를 추가한다.

## 향후 지침

새 `bluetape-py` package를 추가할 때는 설치 문구와 package source availability를
별도로 검토한다. publishing이 활성화되기 전에는 README 예제에 향후 사용할
`pip install` 형태를 보여줄 수 있지만, PyPI hold 상태도 함께 명시해야 한다.
