# Issue #46 Apache Fory 조사

## 결론

`bluetape-serde`에 Apache Fory를 명시적 `fory` extra로 추가한다. 첫 버전은
Python native mode가 아니라 cross-language mode만 제공하며, 호출자가 선택한
`TRUSTED_INTERNAL` 경계, 사전 등록된 타입, 유한한 자원 제한을 항상 요구한다.

현재 upstream Python 패키지는 `pyfory 1.3.0`이다. CPython 3.8-3.13용 wheel은
제공하지만 CPython 3.14 wheel과 source distribution은 제공하지 않는다. 따라서
프로젝트의 공식 CI 기준인 CPython 3.13.14에서 Fory 검증을 수행하고, Python 3.14에서
`fory` extra를 지원한다고 주장하지 않는다.

## Upstream API 근거

- Python xlang runtime은 `pyfory.Fory(xlang=True, strict=True, ref=False, ...)`로
  명시적으로 구성할 수 있다.
- strict mode는 등록된 application type만 역직렬화한다.
- `pyfory 1.3.0` tagged source는 xlang custom type을 numeric `type_id` 또는
  stable name 중 하나로 등록한다. 둘은 동시에 지정할 수 없다. 공식 guide 일부는
  name-only로 설명하지만 release source가 numeric xlang registration을 명시하므로
  이 작업은 tagged source를 우선 근거로 사용한다.
- Issue #46은 동일한 numeric `type_id`를 모든 언어의 Fory runtime과 bluetape
  envelope에 등록한다. stable logical name은 schema/manifest 문서 식별자로만
  유지한다.
- Fory 1.3 schema metadata는 numeric field ID를 지원한다. Kotlin KSP는
  `@ForyField(id=N)`을 사용하므로 Kotlin metadata를 제거하지 않고 Python
  `pyfory.field(id=N)`, Go `fory:"id=N"`, Rust `#[fory(id=N)]`까지 같은 ID를
  부여해 네 언어 field identity를 일치시킨다.
- upstream은 `max_depth`, `max_type_fields`, `max_type_meta_bytes`,
  `max_schema_versions_per_type`, `max_average_schema_versions_per_type` 제한을
  제공한다. Tagged `1.3.0` Python wheel에는 graph-memory constructor limit가
  없으므로 hard decoded-heap limit을 주장하지 않는다.
- xlang mode는 Python, Go, Rust, Java/Kotlin 간 payload exchange를 지원한다.

## Local Ecosystem 근거

- `bluetape-py` Issue #45가 `PayloadMetadata`, `SerializedPayload`, caller-owned
  trust policy, typed payload-free errors를 제공한다.
- `bluetape-go/cache/rediscoord/fory`는 Fory를 opt-in child package로 격리하고
  byte/depth/type-metadata limits와 deterministic registration을 요구한다. 다만
  현재 구현은 native mode라 Issue #46 xlang fixture를 그대로 재사용할 수 없다.
- `bluetape-rs` Issue #115는 Rust/Go/Kotlin/Java/Python compatibility matrix를
  별도 release gate로 요구하며 아직 구현되지 않았다.
- `bluetape4k-projects`의 기존 Fory serializer는 JVM-native object serialization
  용도이므로 새 conformance fixture에는 별도의 xlang configuration이 필요하다.

## 채택 경계

| 항목 | 결정 |
| --- | --- |
| dependency | `pyfory==1.3.0`, `bluetape-serde[fory]`에서만 설치 |
| Python | Fory extra와 fixture CI는 CPython 3.13.14 |
| mode | `xlang=True`, `strict=True`, `compatible=False` fixed schema mode |
| reference tracking | `ref=False`; count limit가 아니라 tracking-disabled 불변식 |
| trust | `TRUSTED_INTERNAL` only |
| type identity | 모든 언어에서 동일한 numeric Fory xlang `type_id` |
| application identity | bluetape envelope의 `schema_id`, `schema_version`, `type_id` |
| selection | caller가 expected registration을 전달; payload-driven lookup 금지 |
| limits | input/output/depth/type metadata/schema versions/concurrency 모두 finite |
| fallback | JSON/native/pickle/unknown type fallback 없음 |

## Cross-Language Fixture 전략

하나의 단순하고 안정적인 `ConformanceRecord` fixed schema를 정의한다. Python,
Go, Rust, Kotlin producer가 동일한 field order, non-nullability, numeric type ID,
numeric field IDs, field widths를 사용해 fixture를 생성한다. fixture manifest는
다음을 고정한다.

- envelope version
- schema ID와 schema version
- application type ID
- Fory xlang numeric type ID와 logical manifest name
- compatible mode와 reference tracking setting
- semantic expected value
- producer language/runtime/Fory version
- payload SHA-256

Python test는 네 언어 fixture를 모두 decode하고 같은 semantic value를 확인한다.
각 producer source와 regeneration command를 저장하고 CI에서 fixture drift를
검증한다. 단순히 Python round-trip만 통과한 경우 cross-language conformance를
완료로 처리하지 않는다.

## Source

- <https://fory.apache.org/docs/guide/python/>
- <https://fory.apache.org/docs/guide/python/configuration/>
- <https://fory.apache.org/docs/guide/python/type_registration/>
- <https://fory.apache.org/docs/guide/python/xlang_serialization/>
- <https://fory.apache.org/docs/guide/python/schema_metadata/>
- <https://fory.apache.org/docs/guide/rust/field_configuration/>
- <https://fory.apache.org/docs/0.16/guide/go/struct_tags/>
- <https://fory.apache.org/docs/next/guide/kotlin/schema_metadata/>
- <https://fory.apache.org/docs/guide/xlang/serialization/>
- <https://github.com/apache/fory/blob/v1.3.0/python/pyfory/_fory.py>
- <https://github.com/apache/fory/blob/v1.3.0/python/pyfory/registry.py>
- <https://pypi.org/project/pyfory/>
- <https://github.com/bluetape4k/bluetape-py/issues/46>
- <https://github.com/bluetape4k/bluetape-rs/issues/115>

## Retrieval Notes

- Retrieved 2026-07-11 from current Apache Fory documentation, PyPI release
  metadata, live GitHub issues, and local sibling repositories.
- No external images or copied long-form source content were required.
