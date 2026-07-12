"""Shared support for optional native compression providers."""

import importlib
from collections.abc import Callable

from bluetape.compression import CompressionError


def load_provider(module_name: str, *, install: str):
    """Load one provider or raise focused guidance when it is directly absent."""
    top_level_name = module_name.split(".", 1)[0]
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != top_level_name:
            raise

    raise ModuleNotFoundError(install, name=top_level_name) from None


def provider_call[T](operation: Callable[[], T], *, message: str) -> T:
    """Run a provider call and translate ordinary failures without retaining their context."""
    failed = False
    try:
        return operation()
    except MemoryError:
        raise
    except Exception:
        failed = True

    if failed:
        raise CompressionError(message) from None
    raise AssertionError("unreachable")
