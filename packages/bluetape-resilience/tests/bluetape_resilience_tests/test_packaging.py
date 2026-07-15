"""Fast source-tree packaging checks for bluetape-resilience."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[4]
PUBLISHABLE = {
    "bluetape",
    "bluetape-async",
    "bluetape-cache",
    "bluetape-cache-redis",
    "bluetape-codec",
    "bluetape-collections",
    "bluetape-compression",
    "bluetape-core",
    "bluetape-logging",
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


def test_meta_extra_includes_resilience_without_widening_default() -> None:
    project = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    dependency = "bluetape-resilience==0.1.0"
    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert project["optional-dependencies"]["resilience"] == [dependency]
    assert dependency in project["optional-dependencies"]["dev"]
    assert dependency in project["optional-dependencies"]["all"]


def test_every_workspace_distribution_is_fail_closed_classified() -> None:
    workspace = {
        load_pyproject(path)["project"]["name"]
        for path in (ROOT / "packages").glob("*/pyproject.toml")
    }
    assert workspace == PUBLISHABLE | PRIVATE
    preflight = (ROOT / "docs/release/pypi-preflight.md").read_text()
    assert all(f"`{name}`" in preflight for name in workspace)
    target_table = preflight.split("## Fail-Closed Workspace Classification", 1)[0]
    assert "`bluetape-resilience`" not in target_table


def test_generic_ci_collects_and_builds_resilience_package() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "--python 3.13.14 pytest" in workflow
    assert "uv build --all-packages" in workflow
