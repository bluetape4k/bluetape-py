import importlib
import sys

import pytest
from bluetape.compression import CompressionError


def test_root_compression_import_does_not_load_the_native_namespace() -> None:
    assert "bluetape.compression.native" not in sys.modules


def test_native_namespace_does_not_eagerly_load_providers() -> None:
    module = importlib.import_module("bluetape.compression.native")

    assert module.__all__ == []
    assert not {"lz4", "cramjam", "zstandard"} & sys.modules.keys()


def test_provider_loader_translates_only_a_direct_missing_provider(monkeypatch) -> None:
    support = importlib.import_module("bluetape.compression.native._support")

    def missing(_: str):
        raise ModuleNotFoundError("raw provider diagnostic", name="lz4")

    monkeypatch.setattr(support.importlib, "import_module", missing)

    with pytest.raises(ModuleNotFoundError) as raised:
        support.load_provider(
            "lz4.frame",
            install="Install bluetape-compression[lz4] to use Lz4Compressor.",
        )

    assert raised.value.name == "lz4"
    assert str(raised.value) == "Install bluetape-compression[lz4] to use Lz4Compressor."
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert "diagnostic" not in str(raised.value)


@pytest.mark.parametrize(
    "failure",
    [
        ModuleNotFoundError("transitive dependency missing", name="xxhash"),
        ImportError("provider ABI mismatch"),
        OSError("native library unavailable"),
        MemoryError("allocation failed"),
    ],
)
def test_provider_loader_preserves_non_missing_provider_failures(monkeypatch, failure) -> None:
    support = importlib.import_module("bluetape.compression.native._support")

    def fail(_: str):
        raise failure

    monkeypatch.setattr(support.importlib, "import_module", fail)

    with pytest.raises(type(failure), match=str(failure)) as raised:
        support.load_provider("lz4.frame", install="focused guidance")

    assert raised.value is failure


def test_provider_call_returns_success_without_translation() -> None:
    support = importlib.import_module("bluetape.compression.native._support")

    assert support.provider_call(lambda: b"ok", message="provider failed") == b"ok"


def test_provider_call_translates_ordinary_failures_without_context() -> None:
    support = importlib.import_module("bluetape.compression.native._support")

    def fail() -> bytes:
        raise RuntimeError("raw provider diagnostic")

    with pytest.raises(CompressionError) as raised:
        support.provider_call(fail, message="compression failed")

    assert str(raised.value) == "compression failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert not hasattr(raised.value, "operation")


@pytest.mark.parametrize(
    "failure",
    [
        MemoryError("allocation failed"),
        KeyboardInterrupt(),
        SystemExit(),
        GeneratorExit(),
    ],
)
def test_provider_call_preserves_fatal_failures(failure) -> None:
    support = importlib.import_module("bluetape.compression.native._support")

    def fail() -> bytes:
        raise failure

    with pytest.raises(type(failure)) as raised:
        support.provider_call(fail, message="provider failed")

    assert raised.value is failure
