import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[4]


def load_project(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)["project"]


def test_distribution_owns_testcontainers_namespace_and_dependency() -> None:
    project = load_project(ROOT / "packages/bluetape-testcontainers/pyproject.toml")

    assert project["name"] == "bluetape-testcontainers"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == ["testcontainers>=4.14.2,<5"]
    specification = importlib.util.find_spec("bluetape.testcontainers")
    assert specification is not None


def test_meta_distribution_forwards_only_explicit_testcontainers_extra() -> None:
    project = load_project(ROOT / "packages/bluetape/pyproject.toml")
    extras = project["optional-dependencies"]

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert extras["testcontainers"] == ["bluetape-testcontainers==0.1.0"]
    assert "bluetape-testcontainers==0.1.0" in extras["dev"]
    assert "bluetape-testcontainers==0.1.0" in extras["all"]


def test_production_packages_remain_testcontainers_free() -> None:
    for package in ("bluetape-core", "bluetape-cache", "bluetape-testing"):
        project = load_project(ROOT / f"packages/{package}/pyproject.toml")
        dependencies = project["dependencies"]
        assert all("testcontainers" not in dependency for dependency in dependencies)


def test_meta_default_does_not_forward_testcontainers() -> None:
    project = load_project(ROOT / "packages/bluetape/pyproject.toml")

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert "bluetape-testcontainers" not in project["dependencies"]


def test_wrapper_does_not_depend_on_redis_py() -> None:
    project = load_project(ROOT / "packages/bluetape-testcontainers/pyproject.toml")

    assert all(not dependency.startswith("redis") for dependency in project["dependencies"])
