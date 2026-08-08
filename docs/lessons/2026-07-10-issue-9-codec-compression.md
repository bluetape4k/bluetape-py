# Issue #9 Codec 및 Compression 경계

## 배경

Issue #9에서는 thin default `bluetape` install을 유지하면서 codec과 compression에
집중한 distribution을 추가했다.

## 결정

- URL-safe Base64는 strict ASCII/form validation과 canonical re-encode comparison을
  통과한 뒤에만 decode한다.
- public output limit에 `zlib.Decompress.flush(length)`를 사용하지 않는다. 이
  length는 hard cap이 아니다. 대신 모든 `decompress(..., max_length)` 호출을
  제한하고, 진행이 멈춘 truncated input은 실패시킨다.
- raw gzip/zlib backend message나 context는 노출하지 않는다. input bytes가 포함될
  수 있기 때문이다.
- optional stdlib `zlib`은 lazy-load해 제한된 Python build에서도 compression
  namespace를 import할 수 있도록 한다.

## 결과

Focused pytest coverage로 canonical codec rejection, gzip multi-member limit,
chunk-boundary/trailing handling, bounded expansion, unavailable backend 동작을
증명했다.

## 지침

향후 streaming API는 자체 EOF, truncated-final-input, post-terminal,
double-terminal-call contract를 가져야 한다. 이 계약을 현재 byte helper에
사후적으로 끼워 넣지 않는다.
