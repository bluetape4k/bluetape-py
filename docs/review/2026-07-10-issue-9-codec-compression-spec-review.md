# Issue #9 Codec 및 Compression 사양 검토

## 범위

구현 계획을 세우기 전에 `bluetape-codec`와 `bluetape-compression` v1 계약을
대상으로 `docs/superpowers/specs/2026-07-10-issue-9-codec-compression-design.md`를
검토했다.

## 결과

P0: 0

P1: 0

판정: PASS

## 근거

| Review lane | 결과 | 범위 |
|---|---:|---|
| Performance | PASS | bounded `decompress()` output, `flush()` 없음, no-progress termination, `Py_ssize_t` range |
| Stability | PASS | chunk-boundary trailing data, member transition, truncation, no partial result |
| Security | PASS | canonical Base64url, decompression-bomb bound, payload-free error contract |
| Operator | PASS | thin default install, lazy optional-zlib availability, rollback 및 wheel smoke check |
| Developer | PASS | public API feasibility, lazy backend contract, package layout, testability |
| User | PASS | default, error expectation, wire format, README 및 install 명확성 |

초기 adversarial review에서 unsafe assumption을 발견했다.
`zlib.Decompress.flush()`는 hard output bound를 적용하지 않는다. 따라서
계약에서 이를 금지하고 `max_length=remaining + 1`인 `decompress()` call만
허용한다. 또한 malformed truncated input이 무한 반복하지 않도록 no-progress
terminal state를 지정하고, zlib/raw-deflate terminal member 뒤의 unread byte를
거부하며, 모든 gzip member가 하나의 remaining-output counter를 공유하도록
했다.

Specification은 `remaining + 1`이 C API에서 유효하도록
`max_output_size`를 `sys.maxsize - 1` 범위로 제한한다. Compression error는
고정되고 payload가 없는 message와 suppressed context를 사용해 chained
gzip/zlib error를 통한 우발적인 payload 노출을 막는다. `zlib`는 optional
Python stdlib module이므로 package는 backend를 lazy-load한다. zlib가 없는
build에서도 import는 가능하고 helper call은 문서화된 고정 `CompressionError`로
실패한다.

## Non-blocking notes

- v1은 `max_input_size`를 의도적으로 생략한다. byte input은 이미 caller가
  소유하며 input cap은 bytes-returning API의 process memory ceiling을 만들지
  않는다. Streaming 및 file API는 별도 작업으로 남긴다.
- Native optional backend와 compressor registry는 명시적으로 범위 밖이다.
