"""Strict, bounded JSON serialization support."""

import json
import math
import sys
from collections.abc import Iterator

from ._contracts import (
    ContentTypeMismatchError,
    FormatMismatchError,
    PayloadLimitError,
    PayloadMetadata,
    SerdeEncodeError,
    SerdeError,
    SerdeErrorCode,
    SerializedPayload,
    UnsupportedVersionError,
)

DEFAULT_MAX_INPUT_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_OUTPUT_SIZE = 16 * 1024 * 1024
DEFAULT_MAX_NESTING_DEPTH = 100
MAX_SUPPORTED_NESTING_DEPTH = 256

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

type _TraversalFrame = tuple[int, Iterator[object]]


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
