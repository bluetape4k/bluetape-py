import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]
PUBLISHABLE = {
    "bluetape",
    "bluetape-async",
    "bluetape-cache",
    "bluetape-cache-redis",
    "bluetape-codec",
    "bluetape-collections",
    "bluetape-compression",
    "bluetape-core",
    "bluetape-id",
    "bluetape-logging",
    "bluetape-measure",
    "bluetape-money",
    "bluetape-observability",
    "bluetape-resilience",
    "bluetape-serde",
    "bluetape-testcontainers",
    "bluetape-testing",
}
PRIVATE = {"bluetape-benchmark"}


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_benchmark_distribution_is_private_and_stdlib_only() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-benchmark/pyproject.toml")
    project = metadata["project"]
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == []
    assert project["classifiers"] == ["Private :: Do Not Upload"]
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.benchmark"


def test_workspace_builds_but_meta_never_installs_benchmark() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")
    assert root["tool"]["uv"]["sources"]["bluetape-benchmark"] == {"workspace": True}
    assert "packages/bluetape-benchmark" in root["tool"]["uv"]["workspace"]["members"]
    assert all("benchmark" not in item for item in root["project"]["dependencies"])

    meta = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    assert all("benchmark" not in item for item in meta["dependencies"])
    assert all(
        "benchmark" not in item
        for values in meta["optional-dependencies"].values()
        for item in values
    )


def test_cache_redis_uses_benchmark_only_for_tests() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-cache-redis/pyproject.toml")
    assert "bluetape-benchmark==0.1.0" in metadata["dependency-groups"]["test"]
    assert all("benchmark" not in item for item in metadata["project"]["dependencies"])


def test_nested_namespace_is_importable_without_root_convenience_package() -> None:
    specification = importlib.util.find_spec("bluetape.benchmark")
    assert specification is not None
    assert specification.origin is not None
    assert Path(specification.origin).name == "__init__.py"


def test_every_workspace_distribution_is_publishable_or_private() -> None:
    workspace = {
        load_pyproject(path)["project"]["name"]
        for path in (ROOT / "packages").glob("*/pyproject.toml")
    }
    assert workspace == PUBLISHABLE | PRIVATE
    assert PUBLISHABLE.isdisjoint(PRIVATE)
    preflight = (ROOT / "docs/release/pypi-preflight.md").read_text()
    assert all(f"`{name}`" in preflight for name in workspace)
    assert "`bluetape-benchmark` is PyPI defense in depth" in preflight
