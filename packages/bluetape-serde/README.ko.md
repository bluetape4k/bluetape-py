# bluetape-serde

[English](README.md) | 한국어

Python 3.13+용 strict, bounded payload 계약과 JSON serialization, 선택적 Apache
Fory cross-language adapter를 제공한다.

`bluetape-serde`는 source workspace에 구현되어 있다. PyPI publication은 아직
보류 중이므로 현재는 source-workspace 또는 local-wheel 명령을 사용한다. 아래
registry command와 `bluetape[serde]` extra는 향후 public install 형태를
설명하며 publication을 활성화하기 전에는 PyPI에서 사용할 수 없다.

## 설치

Repository root에서 지금 실행할 수 있다.

```bash
uv sync --all-packages
uv run --package bluetape-serde python -c "import bluetape.serde"
uv sync --all-packages --extra fory --python 3.13.14 --locked
uv run --package bluetape-serde --extra fory --python 3.13.14 python -c "import bluetape.serde.fory"
uv build --package bluetape-serde
```

Build한 wheel은 격리된 local environment에 설치해 end-to-end로 실행할 수 있다.

```bash
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
uv build --package bluetape-serde --out-dir "$tmp_dir/dist"
uv venv "$tmp_dir/venv"
uv pip install --python "$tmp_dir/venv/bin/python" "$tmp_dir"/dist/bluetape_serde-*.whl
"$tmp_dir/venv/bin/python" -c 'from bluetape.serde import PayloadMetadata, TrustProfile, json_deserialize, json_serialize; m = PayloadMetadata(format="json", version=1, content_type="application/json", trust_profile=TrustProfile.UNTRUSTED); p = json_serialize({"order_id": 42}, metadata=m); assert json_deserialize(p, expected_metadata=m) == {"order_id": 42}'
```

다음 PyPI command는 현재 사용할 수 없다.

```bash
pip install bluetape-serde
pip install "bluetape[serde]"
pip install "bluetape-serde[fory]"
pip install "bluetape[fory]"
```

기본 `bluetape` meta distribution은 core-only다. Serde는 명시적인 extra 또는
focused distribution으로 설치한다. Apache Fory는 `fory` extra에서만 사용할 수
있고 현재 CPython 3.13이 필요하며 base, `serde`, `dev`, `all` extra에서는
제외된다.

| 설치 대상 | Serde 포함 | Apache Fory 포함 |
|---|---:|---:|
| `bluetape` | 아니오 | 아니오 |
| `bluetape[serde]` | 예 | 아니오 |
| `bluetape[dev]` | 예 | 아니오 |
| `bluetape[all]` | 예 | 아니오 |
| `bluetape[fory]` | 예 | 예 |
| `bluetape-serde[fory]` | 예 | 예 |

## Public API

Public surface는 `bluetape.serde`에서 import한다.

- 계약: `PayloadMetadata`, `SerializedPayload`, `TrustProfile`, `JsonValue`
- 작업: `json_serialize`, `json_deserialize`
- 제한: `DEFAULT_MAX_INPUT_SIZE`, `DEFAULT_MAX_OUTPUT_SIZE`,
  `DEFAULT_MAX_NESTING_DEPTH`, `MAX_SUPPORTED_NESTING_DEPTH`,
  `MAX_JSON_INTEGER_DIGITS`
- 오류: `SerdeError`, `InvalidMetadataError`, `FormatMismatchError`,
  `ContentTypeMismatchError`, `UnsupportedVersionError`,
  `TrustProfileMismatchError`, `SchemaMismatchError`, `TypeMismatchError`,
  `ForyRegistrationError`, `ForyConcurrencyError`, `PayloadLimitError`,
  `MalformedPayloadError`, `SerdeEncodeError`, `SerdeErrorCode`

Root public surface는 25개 export이며 `SerdeErrorCode`에는 23개의 고정 code가
있다. Provider-dependent `bluetape.serde.fory`는 `fory` extra 설치 시에만
`ForyAdapter`, `ForyLimits`, `ForyRegistration`과 세 wire constant를 export한다.

`PayloadMetadata`와 `SerializedPayload`는 frozen, slotted, keyword-only
dataclass다. `SerializedPayload.data`에는 정확히 immutable `bytes`만 사용할
수 있다.

기본 wire 계약은 strict JSON v1이다.

| 필드 | 필수 값 |
|---|---|
| `format` | `"json"` |
| `version` | `1` |
| `content_type` | `"application/json"` |
| `trust_profile` | Caller가 선택한 `TrustProfile.UNTRUSTED` 또는 `TrustProfile.TRUSTED_INTERNAL` |

## Apache Fory

Fory는 인증·인가된 internal route에서만 사용한다. Application이 immutable
`(schema_id, schema_version, type_id)` identity를 소유하고 하나의 정확한
registered root type에 매핑한다. Payload content로 adapter, registration,
fallback, class, schema를 선택하지 않는다. Nested application class는 지원하지
않으며 scalar field와 container를 사용해 하나의 registered root를 구성한다.

```python
from dataclasses import dataclass

import pyfory

from bluetape.serde import PayloadMetadata, SerializedPayload, TrustProfile
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyRegistration,
)


@dataclass(slots=True)
class OrderAccepted:
    order_id: pyfory.Int64
    status: str


registration = ForyRegistration(
    python_type=OrderAccepted,
    schema_id=0x42544659,
    schema_version=1,
    type_id=1001,
    logical_name="io.bluetape.orders.OrderAccepted",
)
adapter = ForyAdapter(registration=registration)

producer_metadata = PayloadMetadata(
    format=FORY_FORMAT,
    version=FORY_VERSION,
    content_type=FORY_CONTENT_TYPE,
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
wire = adapter.serialize(
    OrderAccepted(order_id=pyfory.Int64(42), status="accepted"),
    metadata=producer_metadata,
)
received = SerializedPayload(metadata=wire.metadata, data=wire.data)
consumer_policy = PayloadMetadata(
    format=FORY_FORMAT,
    version=FORY_VERSION,
    content_type=FORY_CONTENT_TYPE,
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
decoded = adapter.deserialize(received, expected_metadata=consumer_policy)
assert decoded == OrderAccepted(order_id=pyfory.Int64(42), status="accepted")
```

Adapter는 metadata, fixed envelope, schema/type identity, body length, exact body
consumption을 검증한 뒤 root를 반환한다. Bounded runtime pool을 사용하고
payload-selected type을 동적으로 import하지 않는다. `ForyLimits`는 acceptance와
concurrency bound이지 CPU, RSS, wall-clock ceiling이 아니다. Hard resource
containment가 필요하면 adapter를 별도로 제한한 process에서 실행한다.

`pyfory`가 없을 때 `bluetape.serde.fory` import는 고정된
`Install bluetape-serde[fory] with CPython 3.13 to use Apache Fory.` message를
발생시킨다. 설치 후에도 import가 실패하면 transitive dependency, ABI,
provider-initialization exception을 보존하며 missing extra로 잘못 보고하지 않는다.

## Caller-owned policy

기본값으로 `TrustProfile.UNTRUSTED`를 사용한다. Producer는 선택한 profile을
payload metadata에 기록하지만 consumer는 authenticated caller configuration에서
`expected_metadata`를 별도로 구성해야 한다. `payload.metadata`에서 expected
policy를 유도하면 안 된다.

```python
from bluetape.serde import (
    PayloadMetadata,
    SerdeError,
    SerializedPayload,
    TrustProfile,
    json_deserialize,
    json_serialize,
)

producer_metadata = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)
wire_payload = json_serialize(
    {"order_id": 42, "status": "accepted"},
    metadata=producer_metadata,
)
received_payload = SerializedPayload(
    metadata=wire_payload.metadata,
    data=wire_payload.data,
)
consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)

try:
    decoded = json_deserialize(
        received_payload,
        expected_metadata=consumer_policy,
    )
except SerdeError as error:
    print(error.code.value)
else:
    assert decoded == {"order_id": 42, "status": "accepted"}
```

`TrustProfile.TRUSTED_INTERNAL`은 producer가 인증되고 인가된 closed boundary에서만
허용한다. Network location, private subnet, payload claim만으로는 충분하지 않다.
Trusted profile도 format, version, content-type, UTF-8, duplicate-key, finite-number,
type, byte, nesting bound를 우회하지 않는다.

## 오류와 한계

Serde는 payload를 근거로 codec이나 type을 재구성하지 않는다. Metadata mismatch,
unsupported version, trust mismatch, schema/type mismatch, malformed payload,
limit violation, encode failure는 고정된 typed error와 `SerdeErrorCode`로
보고한다. Caller는 입력·출력·nesting·integer-digit limit를 명시적으로 선택할
수 있지만 package가 정한 hard ceiling보다 넓힐 수 없다.

JSON v1은 string object key, finite number, duplicate-key 거부, Unicode scalar,
deterministic structural validation을 사용한다. Fory와 native provider는 명시적
extra와 trusted route가 필요하며, untrusted payload의 자동 dispatch와 fallback은
지원하지 않는다.
