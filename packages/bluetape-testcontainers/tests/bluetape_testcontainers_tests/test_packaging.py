import importlib.util
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[4]


def load_project(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)["project"]


def load_document(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


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


def test_wrapper_extras_and_test_clients_are_isolated() -> None:
    document = load_document(ROOT / "packages/bluetape-testcontainers/pyproject.toml")
    project = document["project"]
    extras = project["optional-dependencies"]
    test_group = document["dependency-groups"]["test"]

    assert project["dependencies"] == ["testcontainers>=4.14.2,<4.15"]
    assert extras == {
        "postgres": ["testcontainers[postgres]>=4.14.2,<4.15"],
        "aws": ["testcontainers[localstack]>=4.14.2,<4.15"],
        "all": [
            "testcontainers[postgres]>=4.14.2,<4.15",
            "testcontainers[localstack]>=4.14.2,<4.15",
        ],
    }
    assert test_group == [
        "boto3>=1,<2",
        "psycopg[binary]>=3.2,<4",
        "pytest>=8.4.0",
    ]


def test_root_meta_extra_stays_base_only() -> None:
    project = load_project(ROOT / "packages/bluetape/pyproject.toml")

    assert project["optional-dependencies"]["testcontainers"] == ["bluetape-testcontainers==0.1.0"]
    assert "[aws]" not in project["optional-dependencies"]["testcontainers"][0]
    assert "[postgres]" not in project["optional-dependencies"]["testcontainers"][0]


def test_wrapper_does_not_depend_on_redis_py() -> None:
    project = load_project(ROOT / "packages/bluetape-testcontainers/pyproject.toml")

    assert all(not dependency.startswith("redis") for dependency in project["dependencies"])


def test_base_import_does_not_load_optional_providers() -> None:
    script = """
import importlib.abc
import sys

blocked = {"boto3", "psycopg", "sqlalchemy", "testcontainers.localstack", "testcontainers.postgres"}

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked or any(fullname.startswith(name + ".") for name in blocked):
            raise AssertionError(f"optional provider imported: {fullname}")
        return None

sys.meta_path.insert(0, Blocker())
import bluetape.testcontainers as tc
for name in tc.__all__:
    getattr(tc, name)
print("base-import-ok")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "base-import-ok"


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
    assert "Provides-Extra: postgres\n" in metadata
    assert "Provides-Extra: aws\n" in metadata
    assert "Provides-Extra: all\n" in metadata
    assert "boto3" not in metadata.split("Provides-Extra:", 1)[0]
    assert "psycopg" not in metadata.split("Provides-Extra:", 1)[0]
