"""Fast source-tree packaging checks for bluetape-resilience."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_resilience_distribution_is_stdlib_only_python_313() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-resilience/pyproject.toml")
    project = metadata["project"]
    assert project["name"] == "bluetape-resilience"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == []
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.resilience"


def test_root_workspace_registers_resilience_once() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")
    dependency = "bluetape-resilience==0.1.0"
    member = "packages/bluetape-resilience"
    assert root["project"]["dependencies"].count(dependency) == 1
    assert root["tool"]["uv"]["sources"]["bluetape-resilience"] == {"workspace": True}
    assert root["tool"]["uv"]["workspace"]["members"].count(member) == 1


def test_no_root_bluetape_convenience_package_is_created() -> None:
    assert not (ROOT / "packages/bluetape-resilience/src/bluetape/__init__.py").exists()
