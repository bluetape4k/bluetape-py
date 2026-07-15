import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]
PACKAGE = ROOT / "packages/bluetape-id"


def test_distribution_metadata_is_stdlib_only() -> None:
    with (PACKAGE / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)

    assert metadata["project"] == {
        "name": "bluetape-id",
        "version": "0.1.0",
        "description": "Python-native UUID and ULID value helpers for bluetape.",
        "readme": "README.md",
        "requires-python": ">=3.13",
        "dependencies": [],
    }
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.id"
    assert not (PACKAGE / "src/bluetape/__init__.py").exists()
    module = importlib.import_module("bluetape.id")
    assert module.__all__ == [
        "IDError",
        "InvalidIDError",
        "IDOverflowError",
        "UUID7Generator",
        "ULIDGenerator",
        "MonotonicULIDGenerator",
        "uuid4",
        "uuid7",
        "uuid7_timestamp_ms",
        "ulid",
        "parse_ulid",
        "ulid_timestamp_ms",
    ]
