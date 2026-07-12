import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from bluetape.compression import CompressionError

_ROOT = Path(__file__).resolve().parents[3]


def test_root_compression_import_does_not_load_the_native_namespace() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import bluetape.compression; "
            "assert 'bluetape.compression.native' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_native_namespace_does_not_eagerly_load_providers() -> None:
    code = """
import sys
import bluetape.compression.native as native

assert native.__all__ == ["Lz4Compressor", "SnappyCompressor", "ZstdCompressor"]
assert not {"lz4", "cramjam", "zstandard"} & sys.modules.keys()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


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


def test_native_provider_extras_are_exact_and_base_metadata_stays_empty() -> None:
    compression = tomllib.loads(
        (_ROOT / "packages/bluetape-compression/pyproject.toml").read_text()
    )["project"]

    assert compression["dependencies"] == []
    assert compression["optional-dependencies"] == {
        "lz4": ["lz4==4.4.5"],
        "snappy": ["cramjam==2.11.0"],
        "zstd": ["zstandard==0.25.0"],
        "native": ["lz4==4.4.5", "cramjam==2.11.0", "zstandard==0.25.0"],
    }


def test_meta_forwarding_extras_do_not_change_default_dev_or_all_dependencies() -> None:
    meta = tomllib.loads((_ROOT / "packages/bluetape/pyproject.toml").read_text())["project"]
    extras = meta["optional-dependencies"]

    assert meta["dependencies"] == ["bluetape-core==0.1.0"]
    assert extras["compression-lz4"] == ["bluetape-compression[lz4]==0.1.0"]
    assert extras["compression-snappy"] == ["bluetape-compression[snappy]==0.1.0"]
    assert extras["compression-zstd"] == ["bluetape-compression[zstd]==0.1.0"]
    assert extras["compression-native"] == ["bluetape-compression[native]==0.1.0"]
    for extra in ("dev", "all"):
        assert not any("[lz4]" in value for value in extras[extra])
        assert not any("[snappy]" in value for value in extras[extra])
        assert not any("[zstd]" in value for value in extras[extra])
        assert not any("[native]" in value for value in extras[extra])


def test_native_compression_marker_is_registered() -> None:
    root = tomllib.loads((_ROOT / "pyproject.toml").read_text())

    assert any(
        marker.startswith("native_compression:")
        for marker in root["tool"]["pytest"]["ini_options"]["markers"]
    )
