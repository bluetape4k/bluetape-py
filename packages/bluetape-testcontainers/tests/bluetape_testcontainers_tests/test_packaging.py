import importlib.util
import subprocess
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[4]


def load_project(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)["project"]


def test_distribution_owns_testcontainers_namespace_and_dependency() -> None:
    project = load_project(ROOT / "packages/bluetape-testcontainers/pyproject.toml")

    assert project["name"] == "bluetape-testcontainers"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == ["testcontainers>=4.14.2,<4.15"]
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


def test_built_wheels_preserve_version_and_namespace_coexistence(tmp_path: Path) -> None:
    distribution_dir = tmp_path / "dist"
    for package in ("bluetape-core", "bluetape-testcontainers"):
        subprocess.run(
            ["uv", "build", "--package", package, "--wheel", "--out-dir", distribution_dir],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    core_wheel = next(distribution_dir.glob("bluetape_core-*.whl"))
    wrapper_wheel = next(distribution_dir.glob("bluetape_testcontainers-*.whl"))
    with zipfile.ZipFile(core_wheel) as archive:
        core_names = set(archive.namelist())
    with zipfile.ZipFile(wrapper_wheel) as archive:
        wrapper_names = set(archive.namelist())
        metadata_name = next(name for name in wrapper_names if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode()

    assert "bluetape/__init__.py" not in core_names | wrapper_names
    assert "bluetape/core/__init__.py" in core_names
    assert "bluetape/testcontainers/__init__.py" in wrapper_names
    assert "Name: bluetape-testcontainers\n" in metadata
    assert "Version: 0.1.0\n" in metadata
    assert "Requires-Python: >=3.13\n" in metadata
    assert "Requires-Dist: testcontainers>=4.14.2,<4.15\n" in metadata
