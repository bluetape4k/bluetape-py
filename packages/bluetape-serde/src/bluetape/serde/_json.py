"""Strict, bounded JSON serialization support."""

import json
import math
import sys
from collections.abc import Iterator

from ._contracts import (
    ContentTypeMismatchError,
    FormatMismatchError,
    MalformedPayloadError,
    PayloadLimitError,
    PayloadMetadata,
    SerdeEncodeError,
    SerdeError,
    SerdeErrorCode,
    SerializedPayload,
    TrustProfileMismatchError,
    UnsupportedVersionError,
)

DEFAULT_MAX_INPUT_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_OUTPUT_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_NESTING_DEPTH = 100
MAX_SUPPORTED_NESTING_DEPTH = 256

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

type _TraversalFrame = tuple[int, Iterator[object]]


class _DuplicateKeyError(ValueError):
    pass


class _NonFiniteNumberError(ValueError):
    pass


def _unsupported_value_error() -> SerdeEncodeError:
    return SerdeEncodeError(code=SerdeErrorCode.UNSUPPORTED_VALUE)


def _dict_values(value: dict[str, JsonValue]) -> Iterator[JsonValue]:
    for key, item in value.items():
        if type(key) is not str:
            raise _unsupported_value_error()
        yield item


def _preflight_json_value(value: object, *, max_nesting_depth: int) -> None:
    """Validate a JSON value graph while retaining only its active path."""
    active_container_ids: set[int] = set()
    stack: list[_TraversalFrame] = []
    current = value

    while True:
        current_type = type(current)
        if current is None or current_type is bool:
            pass
        elif current_type is int or current_type is str:
            pass
        elif current_type is float:
            if not math.isfinite(current):
                raise SerdeEncodeError(code=SerdeErrorCode.ENCODE_NON_FINITE_NUMBER)
        elif current_type is list or current_type is dict:
            if len(stack) + 1 > max_nesting_depth:
                raise PayloadLimitError(code=SerdeErrorCode.NESTING_LIMIT)

            container_id = id(current)
            if container_id in active_container_ids:
                raise SerdeEncodeError(code=SerdeErrorCode.CIRCULAR_REFERENCE)

            active_container_ids.add(container_id)
            if current_type is list:
                iterator: Iterator[object] = iter(current)
            else:
                iterator = _dict_values(current)
            stack.append((container_id, iterator))
        else:
            raise _unsupported_value_error()

        while stack:
            container_id, iterator = stack[-1]
            try:
                current = next(iterator)
            except StopIteration:
                stack.pop()
                active_container_ids.remove(container_id)
                continue
            break
        else:
            return


def _validate_configuration(
    *,
    metadata: PayloadMetadata,
    max_output_size: int,
    max_nesting_depth: int,
) -> None:
    if type(metadata) is not PayloadMetadata:
        raise TypeError("metadata must be an exact PayloadMetadata")
    if type(max_output_size) is not int:
        raise TypeError("max_output_size must be an exact int")
    if type(max_nesting_depth) is not int:
        raise TypeError("max_nesting_depth must be an exact int")
    if not 0 <= max_output_size < sys.maxsize:
        raise ValueError("max_output_size must be between 0 and sys.maxsize - 1")
    if not 0 <= max_nesting_depth <= MAX_SUPPORTED_NESTING_DEPTH:
        raise ValueError("max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH")


def _validate_json_metadata(metadata: PayloadMetadata) -> None:
    if metadata.format != "json":
        raise FormatMismatchError
    if metadata.content_type != "application/json":
        raise ContentTypeMismatchError
    if metadata.version != 1:
        raise UnsupportedVersionError


def _validate_deserialize_configuration(
    *,
    payload: SerializedPayload,
    expected_metadata: PayloadMetadata,
    max_input_size: int,
    max_nesting_depth: int,
) -> None:
    if type(payload) is not SerializedPayload:
        raise TypeError("payload must be an exact SerializedPayload")
    if type(expected_metadata) is not PayloadMetadata:
        raise TypeError("expected_metadata must be an exact PayloadMetadata")
    if type(max_input_size) is not int:
        raise TypeError("max_input_size must be an exact int")
    if type(max_nesting_depth) is not int:
        raise TypeError("max_nesting_depth must be an exact int")
    if not 0 <= max_input_size < sys.maxsize:
        raise ValueError("max_input_size must be between 0 and sys.maxsize - 1")
    if not 0 <= max_nesting_depth <= MAX_SUPPORTED_NESTING_DEPTH:
        raise ValueError("max_nesting_depth must be between 0 and MAX_SUPPORTED_NESTING_DEPTH")


def _validate_actual_metadata(
    actual: PayloadMetadata,
    *,
    expected: PayloadMetadata,
) -> None:
    if actual.format != expected.format:
        raise FormatMismatchError
    if actual.content_type != expected.content_type:
        raise ContentTypeMismatchError
    if actual.version != expected.version:
        raise UnsupportedVersionError
    if actual.trust_profile is not expected.trust_profile:
        raise TrustProfileMismatchError


def _payload_data(payload: SerializedPayload) -> bytes:
    return payload.data


def _decode_utf8(data: bytes) -> str:
    return data.decode("utf-8", errors="strict")


def _preflight_json_text(text: str, *, max_nesting_depth: int) -> None:
    """Reject excess structural depth using constant auxiliary state."""
    in_string = False
    escaped = False
    depth = 0

    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == "[" or character == "{":
            depth += 1
            if depth > max_nesting_depth:
                raise PayloadLimitError(code=SerdeErrorCode.NESTING_LIMIT)
        elif (character == "]" or character == "}") and depth > 0:
            depth -= 1


def _reject_duplicate_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError
        value[key] = item
    return value


def _reject_non_finite_constant(_: str) -> JsonValue:
    raise _NonFiniteNumberError


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteNumberError
    return parsed


def json_deserialize(
    payload: SerializedPayload,
    *,
    expected_metadata: PayloadMetadata,
    max_input_size: int = DEFAULT_MAX_INPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> JsonValue:
    """Deserialize strict UTF-8 JSON under caller metadata and resource limits."""
    _validate_deserialize_configuration(
        payload=payload,
        expected_metadata=expected_metadata,
        max_input_size=max_input_size,
        max_nesting_depth=max_nesting_depth,
    )
    _validate_json_metadata(expected_metadata)
    _validate_actual_metadata(payload.metadata, expected=expected_metadata)

    data = _payload_data(payload)
    if len(data) > max_input_size:
        raise PayloadLimitError(code=SerdeErrorCode.INPUT_LIMIT)

    replacement: MalformedPayloadError | None = None
    text: str | None = None
    try:
        text = _decode_utf8(data)
    except UnicodeDecodeError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_UTF8)

    if replacement is not None:
        del payload, data, text
        raise replacement
    if text is None:
        raise AssertionError("UTF-8 decoder returned no text")

    _preflight_json_text(text, max_nesting_depth=max_nesting_depth)

    result: JsonValue | None = None
    try:
        result = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except _DuplicateKeyError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.DUPLICATE_KEY)
    except _NonFiniteNumberError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.DECODE_NON_FINITE_NUMBER)
    except json.JSONDecodeError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_JSON)
    except (ValueError, RecursionError):
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_JSON)

    if replacement is not None:
        del payload, data, text
        raise replacement
    return result


def json_serialize(
    value: JsonValue,
    *,
    metadata: PayloadMetadata,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> SerializedPayload:
    """Serialize an exact JSON value to compact UTF-8 within configured limits."""
    _validate_configuration(
        metadata=metadata,
        max_output_size=max_output_size,
        max_nesting_depth=max_nesting_depth,
    )
    _validate_json_metadata(metadata)
    _preflight_json_value(value, max_nesting_depth=max_nesting_depth)

    chunks: list[bytes] = []
    output_size = 0
    replacement: SerdeError | None = None
    try:
        encoder = json.JSONEncoder(
            ensure_ascii=False,
            allow_nan=False,
            check_circular=True,
            separators=(",", ":"),
        )
        for chunk in encoder.iterencode(value):
            encoded_chunk = chunk.encode("utf-8")
            output_size += len(encoded_chunk)
            if output_size > max_output_size:
                replacement = PayloadLimitError(code=SerdeErrorCode.OUTPUT_LIMIT)
                break
            chunks.append(encoded_chunk)
    except RecursionError:
        replacement = SerdeEncodeError(code=SerdeErrorCode.ENCODE_RECURSION)
    except (TypeError, ValueError):
        replacement = _unsupported_value_error()

    if replacement is not None:
        raise replacement

    return SerializedPayload(metadata=metadata, data=b"".join(chunks))
