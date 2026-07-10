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
MAX_JSON_INTEGER_DIGITS = 640
_MAX_JSON_INTEGER_MAGNITUDE = 10**MAX_JSON_INTEGER_DIGITS

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

type _TraversalFrame = tuple[int, int, Iterator[object]]
type _SerdeErrorSpec = tuple[type[SerdeError], SerdeErrorCode]
type _NativeConfigurationErrorSpec = tuple[type[TypeError] | type[ValueError], str]


class _DuplicateKeyError(ValueError):
    pass


class _NonFiniteNumberError(ValueError):
    pass


class _NestingLimitError(ValueError):
    pass


class _IntegerDigitLimitError(ValueError):
    pass


class _UnpairedSurrogateError(ValueError):
    pass


def _unsupported_value_error() -> SerdeEncodeError:
    return SerdeEncodeError(code=SerdeErrorCode.UNSUPPORTED_VALUE)


def _error_spec(error: SerdeError) -> _SerdeErrorSpec:
    return type(error), error.code


def _fresh_serde_error(spec: _SerdeErrorSpec) -> SerdeError:
    error_type, code = spec
    if error_type is FormatMismatchError:
        return FormatMismatchError()
    if error_type is ContentTypeMismatchError:
        return ContentTypeMismatchError()
    if error_type is UnsupportedVersionError:
        return UnsupportedVersionError()
    if error_type is TrustProfileMismatchError:
        return TrustProfileMismatchError()
    return error_type(code=code)  # type: ignore[call-arg]


def _dict_values(value: dict[str, JsonValue]) -> Iterator[JsonValue]:
    for key, item in value.items():
        if type(key) is not str:
            raise _unsupported_value_error()
        _validate_unicode_scalar_string(key)
        yield item


def _validate_unicode_scalar_string(value: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise _unsupported_value_error()


def _preflight_json_value(value: object, *, max_nesting_depth: int) -> None:
    """Validate a JSON graph with active-path cycle and completed-depth state."""
    active_container_ids: set[int] = set()
    completed_container_depths: dict[int, int] = {}
    stack: list[_TraversalFrame] = []
    current = value

    while True:
        current_type = type(current)
        if current is None or current_type is bool:
            pass
        elif current_type is int:
            if current >= _MAX_JSON_INTEGER_MAGNITUDE or current <= -_MAX_JSON_INTEGER_MAGNITUDE:
                raise PayloadLimitError(code=SerdeErrorCode.INTEGER_DIGIT_LIMIT)
        elif current_type is str:
            _validate_unicode_scalar_string(current)
        elif current_type is float:
            if not math.isfinite(current):
                raise SerdeEncodeError(code=SerdeErrorCode.ENCODE_NON_FINITE_NUMBER)
        elif current_type is list or current_type is dict:
            entry_depth = len(stack) + 1
            if entry_depth > max_nesting_depth:
                raise PayloadLimitError(code=SerdeErrorCode.NESTING_LIMIT)

            container_id = id(current)
            if container_id in active_container_ids:
                raise SerdeEncodeError(code=SerdeErrorCode.CIRCULAR_REFERENCE)

            if completed_container_depths.get(container_id, -1) < entry_depth:
                active_container_ids.add(container_id)
                if current_type is list:
                    iterator: Iterator[object] = iter(current)
                else:
                    iterator = _dict_values(current)
                stack.append((container_id, entry_depth, iterator))
        else:
            raise _unsupported_value_error()

        while stack:
            container_id, entry_depth, iterator = stack[-1]
            try:
                current = next(iterator)
            except StopIteration:
                stack.pop()
                active_container_ids.remove(container_id)
                completed_container_depths[container_id] = max(
                    completed_container_depths.get(container_id, -1),
                    entry_depth,
                )
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
                raise _NestingLimitError
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


def _parse_limited_int(value: str) -> int:
    digit_count = len(value) - (value.startswith("-"))
    if digit_count > MAX_JSON_INTEGER_DIGITS:
        raise _IntegerDigitLimitError
    return int(value)


def _normalize_unicode_scalar_string(value: str) -> str:
    normalized: list[str] | None = None
    index = 0
    while index < len(value):
        code_point = ord(value[index])
        if 0xD800 <= code_point <= 0xDBFF:
            if index + 1 >= len(value):
                raise _UnpairedSurrogateError
            low_surrogate = ord(value[index + 1])
            if not 0xDC00 <= low_surrogate <= 0xDFFF:
                raise _UnpairedSurrogateError
            if normalized is None:
                normalized = [value[:index]]
            normalized.append(chr(0x10000 + ((code_point - 0xD800) << 10) + low_surrogate - 0xDC00))
            index += 2
            continue
        if 0xDC00 <= code_point <= 0xDFFF:
            raise _UnpairedSurrogateError
        if normalized is not None:
            normalized.append(value[index])
        index += 1
    return value if normalized is None else "".join(normalized)


def _normalize_decoded_strings(value: JsonValue) -> JsonValue:
    value_type = type(value)
    if value_type is str:
        return _normalize_unicode_scalar_string(value)
    if value_type is list:
        for index, item in enumerate(value):
            value[index] = _normalize_decoded_strings(item)
        return value
    if value_type is dict:
        key_updates: list[tuple[str, str]] = []
        for key, item in value.items():
            value[key] = _normalize_decoded_strings(item)
            normalized_key = _normalize_unicode_scalar_string(key)
            if normalized_key != key:
                if normalized_key in value:
                    raise _DuplicateKeyError
                key_updates.append((key, normalized_key))
        for key, normalized_key in key_updates:
            value[normalized_key] = value.pop(key)
        return value
    return value


def json_deserialize(
    payload: SerializedPayload,
    *,
    expected_metadata: PayloadMetadata,
    max_input_size: int = DEFAULT_MAX_INPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> JsonValue:
    """Deserialize strict UTF-8 JSON with at most MAX_JSON_INTEGER_DIGITS per integer."""
    configuration_error: _NativeConfigurationErrorSpec | None = None
    try:
        _validate_deserialize_configuration(
            payload=payload,
            expected_metadata=expected_metadata,
            max_input_size=max_input_size,
            max_nesting_depth=max_nesting_depth,
        )
    except (TypeError, ValueError) as error:
        configuration_error = (type(error), str(error))

    if configuration_error is not None:
        error_type, error_message = configuration_error
        del payload, expected_metadata, max_input_size, max_nesting_depth, configuration_error
        raise error_type(error_message)

    metadata_error: _SerdeErrorSpec | None = None
    try:
        _validate_json_metadata(expected_metadata)
        _validate_actual_metadata(payload.metadata, expected=expected_metadata)
    except SerdeError as error:
        metadata_error = _error_spec(error)

    if metadata_error is not None:
        del payload, expected_metadata
        raise _fresh_serde_error(metadata_error)

    data = _payload_data(payload)
    if len(data) > max_input_size:
        error_spec: _SerdeErrorSpec = (PayloadLimitError, SerdeErrorCode.INPUT_LIMIT)
        del payload, expected_metadata, data
        raise _fresh_serde_error(error_spec)

    replacement: SerdeError | None = None
    text: str | None = None
    try:
        text = _decode_utf8(data)
    except UnicodeDecodeError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_UTF8)

    if replacement is not None:
        error_spec = _error_spec(replacement)
        del payload, expected_metadata, data, text, replacement
        raise _fresh_serde_error(error_spec)
    if text is None:
        raise AssertionError("UTF-8 decoder returned no text")

    nesting_limit: PayloadLimitError | None = None
    try:
        _preflight_json_text(text, max_nesting_depth=max_nesting_depth)
    except _NestingLimitError:
        nesting_limit = PayloadLimitError(code=SerdeErrorCode.NESTING_LIMIT)

    if nesting_limit is not None:
        error_spec = _error_spec(nesting_limit)
        del payload, expected_metadata, data, text, nesting_limit
        raise _fresh_serde_error(error_spec)

    result: JsonValue | None = None
    try:
        result = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
            parse_int=_parse_limited_int,
        )
        result = _normalize_decoded_strings(result)
    except _DuplicateKeyError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.DUPLICATE_KEY)
    except _NonFiniteNumberError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.DECODE_NON_FINITE_NUMBER)
    except _IntegerDigitLimitError:
        replacement = PayloadLimitError(code=SerdeErrorCode.INTEGER_DIGIT_LIMIT)
    except _UnpairedSurrogateError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_JSON)
    except json.JSONDecodeError:
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_JSON)
    except (ValueError, RecursionError):
        replacement = MalformedPayloadError(code=SerdeErrorCode.INVALID_JSON)

    if replacement is not None:
        error_spec = _error_spec(replacement)
        del payload, expected_metadata, data, text, result, replacement
        raise _fresh_serde_error(error_spec)
    return result


def json_serialize(
    value: JsonValue,
    *,
    metadata: PayloadMetadata,
    max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
) -> SerializedPayload:
    """Serialize exact JSON with at most MAX_JSON_INTEGER_DIGITS per integer."""
    configuration_error: _NativeConfigurationErrorSpec | None = None
    try:
        _validate_configuration(
            metadata=metadata,
            max_output_size=max_output_size,
            max_nesting_depth=max_nesting_depth,
        )
    except (TypeError, ValueError) as error:
        configuration_error = (type(error), str(error))

    if configuration_error is not None:
        error_type, error_message = configuration_error
        del value, metadata, max_output_size, max_nesting_depth, configuration_error
        raise error_type(error_message)

    preflight_error: _SerdeErrorSpec | None = None
    try:
        _validate_json_metadata(metadata)
        _preflight_json_value(value, max_nesting_depth=max_nesting_depth)
    except SerdeError as error:
        preflight_error = _error_spec(error)

    if preflight_error is not None:
        del value, metadata
        raise _fresh_serde_error(preflight_error)

    output = bytearray()
    encoder: json.JSONEncoder | None = None
    chunk: str | None = None
    encoded_chunk: bytes | None = None
    replacement: _SerdeErrorSpec | None = None
    try:
        encoder = json.JSONEncoder(
            ensure_ascii=False,
            allow_nan=False,
            check_circular=True,
            separators=(",", ":"),
        )
        for chunk in encoder.iterencode(value):
            encoded_chunk = chunk.encode("utf-8")
            if len(encoded_chunk) > max_output_size - len(output):
                replacement = (PayloadLimitError, SerdeErrorCode.OUTPUT_LIMIT)
                break
            output.extend(encoded_chunk)
    except RecursionError:
        replacement = (SerdeEncodeError, SerdeErrorCode.ENCODE_RECURSION)
    except (TypeError, ValueError):
        replacement = (SerdeEncodeError, SerdeErrorCode.UNSUPPORTED_VALUE)

    if replacement is not None:
        del value, metadata, output, encoder, chunk, encoded_chunk
        raise _fresh_serde_error(replacement)

    return SerializedPayload(metadata=metadata, data=bytes(output))
