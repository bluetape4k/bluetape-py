"""Small stdlib-only foundation helpers for bluetape-py."""

from collections.abc import Sized


def require_instance[T](value: object, expected_type: type[T], name: str) -> T:
    """Return `value` when it is an instance of `expected_type`.

    Raises:
        TypeError: If `value` is not an instance of `expected_type`.
    """
    if not isinstance(value, expected_type):
        raise TypeError(f"{name} must be {expected_type.__name__}")
    return value


def require_not_none[T](value: T | None, name: str) -> T:
    """Return `value` when present, otherwise raise `ValueError`.

    Parameters:
        value: The value to validate.
        name: The caller-facing field or argument name used in the error message.
    """
    if value is None:
        raise ValueError(f"{name} must not be None")
    return value


def require_not_blank(value: str, name: str) -> str:
    """Return `value` when it contains non-whitespace text.

    The original string is returned unchanged so callers do not lose meaningful
    leading or trailing whitespace.
    """
    if not value.strip():
        raise ValueError(f"{name} must not be blank")
    return value


def require_not_empty[T](value: T, name: str) -> T:
    """Return `value` when its length is non-zero."""
    if isinstance(value, Sized) and len(value) == 0:
        raise ValueError(f"{name} must not be empty")
    return value


__all__ = [
    "require_instance",
    "require_not_blank",
    "require_not_empty",
    "require_not_none",
]
