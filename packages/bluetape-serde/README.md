# bluetape-serde

Strict, bounded payload contracts and JSON serialization for Python 3.13+.

`bluetape-serde` is implemented in the source workspace. PyPI publication is
still on hold, so use the source-workspace or local-wheel commands below today.
The registry commands and `bluetape[serde]` extra describe the future public
install shape and are not available from PyPI until publication is enabled.

## Install

Runnable now from the repository root:

```bash
uv sync --all-packages
uv run --package bluetape-serde python -c "import bluetape.serde"
uv build --package bluetape-serde
```

After building, the generated wheel can be installed into an isolated local
environment and exercised end to end:

```bash
tmp_dir="$(mktemp -d)"
uv build --package bluetape-serde --out-dir "$tmp_dir/dist"
uv venv "$tmp_dir/venv"
uv pip install --python "$tmp_dir/venv/bin/python" "$tmp_dir"/dist/bluetape_serde-*.whl
"$tmp_dir/venv/bin/python" -c 'from bluetape.serde import PayloadMetadata, TrustProfile, json_deserialize, json_serialize; m = PayloadMetadata(format="json", version=1, content_type="application/json", trust_profile=TrustProfile.UNTRUSTED); p = json_serialize({"order_id": 42}, metadata=m); assert json_deserialize(p, expected_metadata=m) == {"order_id": 42}'
rm -rf "$tmp_dir"
```

PyPI commands such as these are intentionally unavailable today:

```bash
pip install bluetape-serde
pip install "bluetape[serde]"
```

The default `bluetape` meta distribution remains core-only. Serde is an
explicit extra or focused distribution; Apache Fory is not included. Fory is a
separate follow-up tracked by
[#46](https://github.com/bluetape4k/bluetape-py/issues/46).

## Public API

Import the public surface from `bluetape.serde`:

- contracts: `PayloadMetadata`, `SerializedPayload`, `TrustProfile`, and
  `JsonValue`;
- operations: `json_serialize` and `json_deserialize`;
- limits: `DEFAULT_MAX_INPUT_SIZE`, `DEFAULT_MAX_OUTPUT_SIZE`,
  `DEFAULT_MAX_NESTING_DEPTH`, `MAX_SUPPORTED_NESTING_DEPTH`, and
  `MAX_JSON_INTEGER_DIGITS`;
- failures: `SerdeError`, `InvalidMetadataError`, `FormatMismatchError`,
  `ContentTypeMismatchError`, `UnsupportedVersionError`,
  `TrustProfileMismatchError`, `PayloadLimitError`, `MalformedPayloadError`,
  `SerdeEncodeError`, and `SerdeErrorCode`.

The ordered public surface contains 21 exports and `SerdeErrorCode` contains
17 fixed codes.

`PayloadMetadata` and `SerializedPayload` are frozen, slotted, keyword-only
dataclasses. `SerializedPayload.data` accepts exact immutable `bytes`.

The only implemented wire contract is strict JSON v1:

| Field | Required value |
|---|---|
| `format` | `"json"` |
| `version` | `1` |
| `content_type` | `"application/json"` |
| `trust_profile` | Caller-selected `TrustProfile.UNTRUSTED` or `TrustProfile.TRUSTED_INTERNAL` |

## Caller-Owned Policy

Use `TrustProfile.UNTRUSTED` by default. The producer records the selected
profile in payload metadata, but the consumer must construct
`expected_metadata` separately from authenticated caller configuration. Never
derive the expected policy from `payload.metadata`; doing so lets the payload
select its own policy.

```python
from bluetape.serde import (
    PayloadMetadata,
    SerdeError,
    SerializedPayload,
    TrustProfile,
    json_deserialize,
    json_serialize,
)

# Producer policy comes from producer configuration.
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

# A transport may reconstruct the immutable envelope from authenticated
# routing metadata plus received bytes.
received_payload = SerializedPayload(
    metadata=wire_payload.metadata,
    data=wire_payload.data,
)

# Consumer policy is constructed independently from authenticated caller
# configuration, never copied from received_payload.metadata.
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

`TrustProfile.TRUSTED_INTERNAL` is allowed only across a closed boundary whose
producer is both authenticated and authorized. Network location, a private
subnet, or a payload claim is insufficient. The trusted profile never bypasses
format, version, content-type, UTF-8, duplicate-key, finite-number, type, byte,
or nesting bounds:

```python
from bluetape.serde import (
    PayloadMetadata,
    SerializedPayload,
    TrustProfile,
    json_deserialize,
)

trusted_producer_metadata = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
trusted_payload = SerializedPayload(
    metadata=trusted_producer_metadata,
    data=b'{"service":"inventory"}',
)
trusted_consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)

# This call is valid only after authentication and authorization establish the
# closed internal boundary. All strict JSON and finite resource checks remain.
trusted_value = json_deserialize(
    trusted_payload,
    expected_metadata=trusted_consumer_policy,
    max_input_size=4 * 1024 * 1024,
    max_nesting_depth=64,
)
```

## Strictness and Limits

Both trust profiles use identical strict JSON behavior and finite resource
limits. There is no permissive trusted decoder.

- Input and output defaults are 16 MiB:
  `DEFAULT_MAX_INPUT_SIZE == DEFAULT_MAX_OUTPUT_SIZE == 16 * 1024 * 1024`.
- Default nesting depth is `DEFAULT_MAX_NESTING_DEPTH == 100`; callers may
  lower it, but the hard ceiling is `MAX_SUPPORTED_NESTING_DEPTH == 256`.
- Every exact JSON integer is limited to
  `MAX_JSON_INTEGER_DIGITS == 640` decimal digits. The boundary is identical
  for encode and decode and does not depend on `sys.set_int_max_str_digits`.
- Decode requires strict UTF-8, exact JSON syntax, unique object keys, and
  finite numbers. `NaN`, `Infinity`, duplicate keys, malformed text, and
  invalid UTF-8 are rejected.
- Encode accepts only exact JSON values and exact key types: `None`, `bool`,
  `int`, finite `float`, `str`, `list`, and `dict[str, JsonValue]`. Subclasses,
  unsupported values, non-string keys, circular references, non-finite
  numbers, and excess recursion fail.
- Metadata comparison is exact. Wrong format, content type, version, or trust
  profile is a hard typed failure. Unsupported versions never fall back.

Encode extends one `bytearray` with accepted UTF-8 chunks and converts it to
`bytes` once; it does not retain a list of per-chunk byte objects.

The 16 MiB limits bound accepted input bytes and emitted output bytes. They do
not guarantee a fixed process-memory ceiling: Python decoding, strings, object
graphs, and encoder chunks can require additional memory. Set smaller limits
for the deployment and isolate hostile parsing when a hard memory boundary is
required.

## Stable Errors

All serde domain failures inherit from `SerdeError`, expose an immutable
`.code`, and use fixed payload-free messages. Caller type and configuration
mistakes remain native `TypeError` or `ValueError`; they are not wrapped as
`SerdeError`. Catch the narrow domain class when recovery differs, or catch
`SerdeError` and switch on `SerdeErrorCode`:

| Error class | Codes |
|---|---|
| `InvalidMetadataError` | `INVALID_METADATA` |
| `FormatMismatchError` | `FORMAT_MISMATCH` |
| `ContentTypeMismatchError` | `CONTENT_TYPE_MISMATCH` |
| `UnsupportedVersionError` | `UNSUPPORTED_VERSION` |
| `TrustProfileMismatchError` | `TRUST_PROFILE_MISMATCH` |
| `PayloadLimitError` | `INPUT_LIMIT`, `OUTPUT_LIMIT`, `NESTING_LIMIT`, `INTEGER_DIGIT_LIMIT` |
| `MalformedPayloadError` | `INVALID_UTF8`, `DUPLICATE_KEY`, `DECODE_NON_FINITE_NUMBER`, `INVALID_JSON` |
| `SerdeEncodeError` | `UNSUPPORTED_VALUE`, `CIRCULAR_REFERENCE`, `ENCODE_NON_FINITE_NUMBER`, `ENCODE_RECURSION` |

Metadata mismatches are typed and never fall through to parsing:

```python
from bluetape.serde import (
    FormatMismatchError,
    PayloadMetadata,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfile,
    json_deserialize,
)

received_payload = SerializedPayload(
    metadata=PayloadMetadata(
        format="legacy_json",
        version=1,
        content_type="application/json",
        trust_profile=TrustProfile.UNTRUSTED,
    ),
    data=b'{"order_id":42}',
)
consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.UNTRUSTED,
)

try:
    json_deserialize(received_payload, expected_metadata=consumer_policy)
except FormatMismatchError as error:
    assert error.code is SerdeErrorCode.FORMAT_MISMATCH
else:
    raise AssertionError("format mismatch was accepted")
```

`TRUSTED_INTERNAL` does not relax byte limits:

```python
from bluetape.serde import (
    PayloadLimitError,
    PayloadMetadata,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfile,
    json_deserialize,
)

trusted_payload = SerializedPayload(
    metadata=PayloadMetadata(
        format="json",
        version=1,
        content_type="application/json",
        trust_profile=TrustProfile.TRUSTED_INTERNAL,
    ),
    data=b'{"order_id":42}',
)
trusted_consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)

try:
    json_deserialize(
        trusted_payload,
        expected_metadata=trusted_consumer_policy,
        max_input_size=4,
    )
except PayloadLimitError as error:
    assert error.code is SerdeErrorCode.INPUT_LIMIT
else:
    raise AssertionError("trusted payload bypassed max_input_size")
```

`TRUSTED_INTERNAL` also retains strict JSON parsing:

```python
from bluetape.serde import (
    MalformedPayloadError,
    PayloadMetadata,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfile,
    json_deserialize,
)

trusted_payload = SerializedPayload(
    metadata=PayloadMetadata(
        format="json",
        version=1,
        content_type="application/json",
        trust_profile=TrustProfile.TRUSTED_INTERNAL,
    ),
    data=b'{"order_id":}',
)
trusted_consumer_policy = PayloadMetadata(
    format="json",
    version=1,
    content_type="application/json",
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)

try:
    json_deserialize(trusted_payload, expected_metadata=trusted_consumer_policy)
except MalformedPayloadError as error:
    assert error.code is SerdeErrorCode.INVALID_JSON
else:
    raise AssertionError("trusted payload bypassed strict JSON parsing")
```

Do not log the raw payload as part of error handling. The package intentionally
keeps payload bytes and values out of error messages and representations.

## Version Rollout and Rollback

Readers for v1 must be deployed before v1 writers. Isolate old and new formats
with a versioned namespace, topic, queue, key prefix, or path; do not mix them
and rely on auto-detection.

For rollback, stop v1 writes first. Retain the prior reader and writer until all
v1 data drains, expires, is evicted, or is explicitly migrated. An unsupported
version is a hard rejection. If an older format must remain readable, configure
that older reader explicitly outside this package and route to it by the
versioned boundary; `bluetape-serde` never performs implicit fallback.

## Non-Goals

- payload-selected policy, schema, code, class, or dynamic loading;
- implicit format detection, version fallback, or legacy-reader dispatch;
- object graph, pickle, stream/file, encryption, compression, or transport APIs;
- a hard process-memory guarantee from byte limits alone;
- Apache Fory in the JSON v1 scope. Fory remains the separate #46 follow-up.
