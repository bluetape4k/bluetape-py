import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_adapter_distribution_has_exact_runtime_dependencies_and_uses_uv_build() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-leader-redis/pyproject.toml")
    project = metadata["project"]

    assert project["name"] == "bluetape-leader-redis"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == ["bluetape-leader==0.1.0", "redis==8.0.1"]
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == (
        "bluetape.leader.redis"
    )


def test_workspace_registers_the_adapter_distribution() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")

    assert "bluetape-leader-redis==0.1.0" in root["project"]["dependencies"]
    assert root["tool"]["uv"]["sources"]["bluetape-leader-redis"] == {"workspace": True}
    assert "packages/bluetape-leader-redis" in root["tool"]["uv"]["workspace"]["members"]


def test_adapter_namespace_imports_without_exporting_future_behavior() -> None:
    adapter = importlib.import_module("bluetape.leader.redis")

    assert adapter.__all__ == []


def test_lock_resolves_exact_adapter_runtime_dependencies() -> None:
    lock = load_pyproject(ROOT / "uv.lock")
    packages = {package["name"]: package for package in lock["package"]}
    adapter = packages["bluetape-leader-redis"]

    assert [dependency["name"] for dependency in adapter["dependencies"]] == [
        "bluetape-leader",
        "redis",
    ]
    assert packages["redis"]["version"] == "8.0.1"


def test_initial_readmes_reserve_only_the_adapter_boundary() -> None:
    english = " ".join(
        (ROOT / "packages/bluetape-leader-redis/README.md").read_text().split()
    )
    korean = " ".join(
        (ROOT / "packages/bluetape-leader-redis/README.ko.md").read_text().split()
    )

    assert "The current package only reserves the Redis adapter namespace." in english
    assert "Redis lock and leader behavior are not implemented yet." in english
    assert "현재 패키지는 Redis adapter namespace만 예약합니다." in korean
    assert "Redis lock과 leader 동작은 아직 구현하지 않았습니다." in korean
