import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_focused_distribution_has_exact_runtime_dependencies() -> None:
    project = load_pyproject(ROOT / "packages/bluetape-cache-redis/pyproject.toml")["project"]
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == [
        "bluetape-compression==0.1.0",
        "bluetape-serde==0.1.0",
        "redis==8.0.1",
    ]


def test_workspace_registers_the_focused_distribution() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")
    assert "bluetape-cache-redis==0.1.0" in root["project"]["dependencies"]
    assert root["tool"]["uv"]["sources"]["bluetape-cache-redis"] == {"workspace": True}
    assert "packages/bluetape-cache-redis" in root["tool"]["uv"]["workspace"]["members"]


def test_meta_extra_is_explicit_and_aggregate_extras_remain_redis_free() -> None:
    project = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    extras = project["optional-dependencies"]
    assert extras["cache-redis"] == ["bluetape-cache-redis==0.1.0"]
    assert all("redis" not in dependency for dependency in extras["dev"])
    assert all("redis" not in dependency for dependency in extras["all"])


def test_nested_namespace_is_importable_without_root_convenience_package() -> None:
    assert importlib.util.find_spec("bluetape.cache") is not None
    specification = importlib.util.find_spec("bluetape.cache.redis")
    assert specification is not None
    assert specification.origin is not None
    assert Path(specification.origin).name == "__init__.py"
