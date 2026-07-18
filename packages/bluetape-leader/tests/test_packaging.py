import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]
PUBLIC_EXPORTS = [
    "LeaderError",
    "InvalidLeaderOptionsError",
    "InvalidLockNameError",
    "LeaderBackendError",
    "LeaderLeaseLostError",
    "LeaderReleaseError",
    "LeaderExecutionError",
    "LeaderElectionOptions",
    "LeaderLease",
    "FencedLeaderLease",
    "Elected",
    "Skipped",
    "ActionFailed",
    "LeaderRunResult",
    "Renewed",
    "NotHeld",
    "RenewBackendFailure",
    "RenewOutcome",
    "LockLease",
    "AsyncLockLease",
    "DistributedLock",
    "AsyncDistributedLock",
    "LeaderElector",
    "AsyncLeaderElector",
]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_core_distribution_is_stdlib_only_and_uses_uv_build() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-leader/pyproject.toml")
    project = metadata["project"]

    assert project["name"] == "bluetape-leader"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == []
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.leader"


def test_core_public_surface_has_exact_reviewed_order() -> None:
    leader = importlib.import_module("bluetape.leader")

    assert leader.__all__ == PUBLIC_EXPORTS


def test_core_public_import_succeeds_when_redis_imports_are_blocked() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys

class BlockRedis(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "redis" or fullname.startswith("redis."):
            raise AssertionError("bluetape.leader imported Redis")
        return None

sys.meta_path.insert(0, BlockRedis())
import bluetape.leader
""",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_workspace_registers_the_core_distribution() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")

    assert "bluetape-leader==0.1.0" in root["project"]["dependencies"]
    assert root["tool"]["uv"]["sources"]["bluetape-leader"] == {"workspace": True}
    assert "packages/bluetape-leader" in root["tool"]["uv"]["workspace"]["members"]


def test_meta_defaults_and_aggregate_extras_preserve_dependency_boundaries() -> None:
    project = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]
    extras = project["optional-dependencies"]

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert extras["leader"] == ["bluetape-leader==0.1.0"]
    assert extras["leader-redis"] == ["bluetape-leader-redis==0.1.0"]
    assert "bluetape-leader==0.1.0" in extras["dev"]
    assert "bluetape-leader-redis==0.1.0" not in extras["dev"]
    assert "bluetape-leader==0.1.0" in extras["all"]
    assert "bluetape-leader-redis==0.1.0" not in extras["all"]


def test_namespace_is_extended_before_the_adapter_child_imports() -> None:
    assert not (ROOT / "packages/bluetape-leader/src/bluetape/__init__.py").exists()
    assert not (ROOT / "packages/bluetape-leader-redis/src/bluetape/__init__.py").exists()

    leader = importlib.import_module("bluetape.leader")
    adapter = importlib.import_module("bluetape.leader.redis")

    assert len(list(leader.__path__)) >= 2
    assert adapter.__all__ == []


def test_lock_registers_the_stdlib_only_core_distribution() -> None:
    lock = load_pyproject(ROOT / "uv.lock")
    packages = {package["name"]: package for package in lock["package"]}

    assert packages["bluetape-leader"].get("dependencies", []) == []


def test_initial_readmes_state_only_the_current_package_boundary() -> None:
    english = " ".join((ROOT / "packages/bluetape-leader/README.md").read_text().split())
    korean = " ".join((ROOT / "packages/bluetape-leader/README.ko.md").read_text().split())

    assert "The current public surface contains only sanitized leader error contracts." in english
    assert "Leader options, leases, electors, and lock behavior are not implemented yet." in english
    assert "현재 공개 표면은 값이 노출되지 않는 leader 오류 계약만 포함합니다." in korean
    assert "옵션, lease, elector, lock 동작은 아직 구현하지 않았습니다." in korean
