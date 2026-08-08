# Issue #10 Python Serialization 전략

## 결정

`bluetape-serde`는 Python standard library로 만든 strict JSON adapter를 포함하는 dependency-free contract package로 시작합니다. 첫 implementation slice에는 generic object serializer, registry, unsafe Python-object adapter를 넣지 않습니다.

Package는 명시적인 `bluetape[serde]` extra로 유지하며 default `bluetape` install은 `bluetape-core`만 포함합니다.

## 기준선과 trust boundary

| 사용 사례 | 초기 결정 | 이유 |
| --- | --- | --- |
| Portable text payload | Strict stdlib JSON | 제3자 runtime dependency가 없고 명확한 text boundary를 제공합니다. |
| Untrusted input | 명시적 `UNTRUSTED` profile | finite byte 및 nesting-depth limit을 강제하고 non-finite constant와 duplicate key를 거부하며 type/class reconstruction을 금지하고 typed failure를 반환합니다. |
| Trusted internal payload | 명시적 `TRUSTED_INTERNAL` profile | 예외를 발생시킬 수 있지만 명시적인 finite byte 및 nesting-depth limit을 끄지 않으며 hidden fallback이나 implicit unsafe codec을 활성화하지 않습니다. |
| Python object graph | 범위 밖 | `pickle`은 unpickle 중 임의 코드를 실행할 수 있고 cross-language format이 아닙니다. |

Python `json` 문서는 malicious input이 상당한 CPU와 memory를 소비할 수 있으며 module 자체에는 input-size 또는 nesting limit이 없다고 경고합니다. 따라서 향후 adapter는 caller-visible size 및 nesting-depth gate를 통과한 뒤에만 bytes를 받아야 합니다. Bytes contract는 UTF-8 전용으로 고정하여 `json.loads()` 전에 byte-size gate와 string/escape-aware structural depth preflight를 결정적으로 수행합니다. 이후 standard library의 permissive non-finite constant와 duplicate key를 허용하지 않는 strict JSON semantics를 구성합니다. Test에는 invalid UTF-8, depth boundary, over-depth input, string 안의 bracket, escaped character가 포함되어야 합니다.
[Python json documentation](https://docs.python.org/3/library/json.html)

`pickle`은 fallback codec이 아닙니다. Python은 untrusted 또는 tampered data를 unpickle하면 arbitrary code가 실행될 수 있다고 문서화합니다. 향후 명시된 unsafe adapter를 수용하더라도 별도의 opt-in package로 만들고 `TRUSTED_INTERNAL`을 요구하며 모든 untrusted decode path에서 제외해야 합니다.
[Python pickle documentation](https://docs.python.org/3/library/pickle.html)

## 제안하는 계약 용어

첫 implementation issue는 optional backend adapter보다 먼저 다음 public concept를 정의해야 합니다.

- `PayloadMetadata`: format identifier, schema/version identifier, optional content type입니다. Metadata는 payload를 설명하며 `repr`이나 error에 payload bytes를 노출하지 않습니다.
- `SerializedPayload`: immutable metadata와 `bytes`입니다. empty bytes도 data로 취급하며 implicit null convention으로 사용하지 않습니다.
- `TrustProfile`: `UNTRUSTED`와 `TRUSTED_INTERNAL`이며 모든 decode operation에서 caller가 선택합니다.
- Typed decode subtype를 가진 `SerdeError`: format mismatch, unsupported version, trust-profile violation, payload-limit violation, malformed payload를 표현합니다.

Version 또는 format mismatch는 typed error를 발생시켜야 합니다. `None`으로 decode하거나 다른 codec을 조용히 선택하거나 cache eviction/rebuild policy를 실행해서는 안 됩니다. 그런 운영 동작은 caller의 책임입니다.

## Optional adapter 결정

| Candidate | 결정 | 경계 |
| --- | --- | --- |
| `orjson` | `orjson` extra로 보류 | 성능 중심 JSON backend이며 error와 strictness semantics를 포함한 표준 contract를 유지해야 합니다. |
| `msgpack` | 후속 `msgpack` extra | Portable binary format입니다. 명시적인 `max_buffer_size`를 전달하고 untrusted decode에서는 `strict_map_key=True`를 유지합니다. |
| `pydantic` | 후속 `pydantic` extra | Model-to-JSON integration만 담당하며 Pydantic이 model owner로 남고 serde core를 대체하지 않습니다. |
| `cbor2` | 후속 `cbor` extra | Compact tagged binary format으로 유용하지만 project가 malicious input에 대해 테스트하지 않았다고 밝힙니다. |
| Apache Fory / `pyfory` | `fory` extra로 확정 | Base contract를 따르는 별도 optional adapter이며 release 전에 Python/Go/Rust/Kotlin schema conformance를 입증해야 합니다. |

`orjson`은 일반적인 Python application type을 지원하고 bytes를 생성하므로 contract owner가 아니라 성능 구현 후보입니다.
[orjson project documentation](https://github.com/ijl/orjson)

`msgpack-python`은 효율적인 binary interchange format이며 unreliable input에 대한 방어로 `max_buffer_size`와 `strict_map_key=True`를 문서화합니다.
[msgpack-python documentation](https://github.com/msgpack/msgpack-python)

Pydantic은 `model_dump_json()`으로 model을 JSON으로 직렬화하고 지원하지 않는 value에는 serialization error를 발생시킵니다. Model lifecycle은 `bluetape-serde` 밖에 둡니다. [Pydantic serialization documentation](https://pydantic.dev/docs/validation/latest/concepts/serialization/)

`cbor2`는 CBOR tag와 shared reference를 지원하지만 malicious input에 대해 테스트하지 않았다고 명시합니다. 따라서 untrusted baseline을 정의할 수 없습니다. [cbor2 project page](https://pypi.org/project/cbor2/)

Apache Fory는 Python support와 cross-language schema registration을 문서화합니다. 이는 확정된 별도 optional adapter이며 JSON 또는 MessagePack의 transparent fallback이 아닙니다. Release 전에 명시적인 schema/type-id fixture suite를 입증해야 하며 첫 release는 `TRUSTED_INTERNAL` 전용입니다. Untrusted Fory decode path에는 fixed allowlisted schema/type-id, dynamic type/class loading 금지, finite payload/depth/reference limit, malformed/adversarial fixture를 포함하는 별도의 승인된 threat model과 security gate가 필요합니다.
[Apache Fory overview](https://fory.apache.org/docs/introduction/overview/)

## Cross-language compatibility

- Interoperability는 byte-for-byte가 아니라 semantic 기준입니다. 일치하는 format identifier, schema/version, field semantics, conformance fixture가 필요합니다.
- JSON과 MessagePack은 application이 canonical field name, number range, datetime, bytes, map-key, duplicate-key policy를 정의한 경우에만 portable payload가 될 수 있습니다.
- Fory compatibility는 명시적인 cross-language schema mode로 제한하며 Python-native object graph에서 추론하지 않습니다.
- Python `pickle`, Pydantic 내부 표현, library-specific default는 cross-language contract가 아닙니다.

이 원칙은 sibling Go/Rust/Kotlin의 교훈을 보존합니다. Payload metadata와 trust profile은 caller-visible이지만 unsafe type reconstruction과 cache policy는 generic decode API로 유출하지 않습니다.

## Non-goal

- Serializer registry, auto-detection, stream/file API, encryption, compression composition, schema migration engine을 제공하지 않습니다.
- 첫 implementation issue에는 `pickle`, `marshal`, YAML, protobuf, Avro adapter를 넣지 않습니다. Fory는 base contract 뒤의 명시적인 별도 extra이며 다른 format의 fallback이 아닙니다.
- JSON parsing만으로 process-memory ceiling을 제공한다고 주장하지 않습니다. Transport와 input-size admission은 caller가 소유합니다.

## 후속 작업

1. [#45](https://github.com/bluetape4k/bluetape-py/issues/45): `bluetape-serde` payload contract와 strict stdlib JSON adapter를 추가합니다.
2. Base contract를 검증한 뒤에만 optional MessagePack, CBOR, Pydantic adapter package를 추가합니다.
3. [#46](https://github.com/bluetape4k/bluetape-py/issues/46): Python, Go, Rust, Kotlin schema/type-id conformance fixture를 release gate로 포함하는 확정 Apache Fory adapter를 `fory` extra로 추가합니다. 초기 decode support는 `TRUSTED_INTERNAL` 전용입니다.

## Retrieval note

- 2026-07-10에 연결된 공식 Python/project documentation과 local `bluetape-go`, `bluetape-rs`, `bluetape4k` source에서 가져왔습니다.
- 외부 image는 필요하지 않았습니다.
