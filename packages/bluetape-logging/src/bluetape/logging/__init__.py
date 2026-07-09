"""Stdlib logging and context helpers for bluetape-py."""

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from logging import Filter, LogRecord

_log_context: ContextVar[dict[str, object] | None] = ContextVar(
    "bluetape_log_context",
    default=None,
)


def get_log_context() -> dict[str, object]:
    """Return a shallow copy of the current logging context."""
    return dict(_log_context.get() or {})


@contextmanager
def log_context(**values: object):
    """Temporarily merge values into the current context-local logging context."""
    merged = get_log_context()
    merged.update(values)
    token = _log_context.set(merged)
    try:
        yield
    finally:
        _log_context.reset(token)


class ContextLogFilter(Filter):
    """Attach current context values to each `LogRecord`."""

    def filter(self, record: LogRecord) -> bool:
        for key, value in get_log_context().items():
            setattr(record, key, value)
        return True


def redact(
    values: Mapping[str, object],
    *,
    keys: Iterable[str],
    replacement: str = "***",
) -> dict[str, object]:
    """Return a copy with selected keys replaced by `replacement`."""
    sensitive = set(keys)
    return {key: replacement if key in sensitive else value for key, value in values.items()}


__all__ = [
    "ContextLogFilter",
    "get_log_context",
    "log_context",
    "redact",
]
