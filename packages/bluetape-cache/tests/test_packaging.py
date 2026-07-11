import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_cache_distribution_is_stdlib_only_and_requires_python_313() -> None:
    project = load_pyproject(ROOT / "packages/bluetape-cache/pyproject.toml")["project"]

    assert project["dependencies"] == []
    assert project["requires-python"] == ">=3.13"


def test_cache_distribution_owns_the_bluetape_cache_namespace() -> None:
    specification = importlib.util.find_spec("bluetape.cache")

    assert specification is not None
    assert specification.origin is not None
    assert Path(specification.origin).name == "__init__.py"


def test_meta_distribution_keeps_core_as_its_only_default_dependency() -> None:
    project = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]

    assert project["dependencies"] == ["bluetape-core==0.1.0"]


def test_meta_distribution_forwards_the_cache_extra() -> None:
    project = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    extras = project["optional-dependencies"]

    assert extras["cache"] == ["bluetape-cache==0.1.0"]
    assert "bluetape-cache==0.1.0" in extras["dev"]
    assert "bluetape-cache==0.1.0" in extras["all"]
