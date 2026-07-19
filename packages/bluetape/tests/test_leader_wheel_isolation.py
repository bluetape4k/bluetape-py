from __future__ import annotations

import subprocess
import zipfile
from email import message_from_bytes
from email.message import Message
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
PYTHON_VERSION = "3.13.14"
LEADER_EXPORTS = (
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
)
ADAPTER_EXPORTS = (
    "RedisDistributedLock",
    "AsyncRedisDistributedLock",
    "RedisLeaderElector",
    "AsyncRedisLeaderElector",
)


def run(*args: str | Path, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    return completed


@pytest.fixture(scope="session")
def leader_wheels(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    wheelhouse = tmp_path_factory.mktemp("leader-wheelhouse")
    for package in ("bluetape-core", "bluetape-leader", "bluetape-leader-redis", "bluetape"):
        run("uv", "build", "--package", package, "--wheel", "--out-dir", wheelhouse)
    return {
        "core": next(wheelhouse.glob("bluetape_core-*.whl")),
        "leader": next(wheelhouse.glob("bluetape_leader-*.whl")),
        "adapter": next(wheelhouse.glob("bluetape_leader_redis-*.whl")),
        "meta": next(wheelhouse.glob("bluetape-*.whl")),
    }


def metadata(wheel: Path) -> Message:
    with zipfile.ZipFile(wheel) as archive:
        path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        return message_from_bytes(archive.read(path))


def test_leader_wheel_is_stdlib_only_and_has_no_root_namespace_file(
    leader_wheels: dict[str, Path],
) -> None:
    leader = leader_wheels["leader"]
    assert metadata(leader).get_all("Requires-Dist") is None
    with zipfile.ZipFile(leader) as archive:
        assert "bluetape/__init__.py" not in archive.namelist()


def test_leader_core_wheel_imports_without_redis(
    leader_wheels: dict[str, Path], tmp_path: Path
) -> None:
    environment = tmp_path / "leader-only"
    run("uv", "venv", "--python", PYTHON_VERSION, environment)
    python = environment / "bin/python"
    run(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--offline",
        "--no-index",
        "--no-deps",
        leader_wheels["leader"],
    )
    probe = f"""
import importlib.util
import bluetape.leader as leader
assert tuple(leader.__all__) == {LEADER_EXPORTS!r}
assert importlib.util.find_spec('redis') is None
assert importlib.util.find_spec('bluetape.leader.redis') is None
"""
    run(python, "-I", "-c", probe, cwd=tmp_path)


def test_adapter_and_meta_wheel_metadata_preserve_exact_dependency_boundaries(
    leader_wheels: dict[str, Path],
) -> None:
    adapter_requirements = metadata(leader_wheels["adapter"]).get_all("Requires-Dist") or []
    assert adapter_requirements == ["bluetape-leader==0.1.0", "redis==8.0.1"]

    meta = metadata(leader_wheels["meta"])
    requirements = meta.get_all("Requires-Dist") or []
    assert [item for item in requirements if ";" not in item] == ["bluetape-core==0.1.0"]
    assert 'bluetape-leader==0.1.0; extra == "leader"' in requirements
    assert 'bluetape-leader-redis==0.1.0; extra == "leader-redis"' in requirements
    assert "leader" in (meta.get_all("Provides-Extra") or [])
    assert "leader-redis" in (meta.get_all("Provides-Extra") or [])


def test_adapter_exports_are_exact_in_workspace() -> None:
    import bluetape.leader.redis as adapter

    assert tuple(adapter.__all__) == ADAPTER_EXPORTS
