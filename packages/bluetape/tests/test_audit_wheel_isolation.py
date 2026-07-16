from __future__ import annotations

import subprocess
import zipfile
from email import message_from_bytes
from email.message import Message
from pathlib import Path
from typing import NamedTuple

import pytest

ROOT = Path(__file__).parents[3]
PYTHON_VERSION = "3.13.14"
AUDIT_ERROR_EXPORT_PREFIX = (
    "AuditError",
    "InvalidAuditIdentityError",
    "InvalidAuditPayloadError",
    "InvalidAuditEventError",
    "InvalidAuditLimitsError",
    "AuditLimitExceededError",
)


class Wheels(NamedTuple):
    audit_build: subprocess.CompletedProcess[str]
    audit: Path | None
    meta: Path
    core: Path


def capture(
    *args: str | Path,
    cwd: Path = ROOT,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def command_failure(completed: subprocess.CompletedProcess[str]) -> str:
    return (
        f"command failed with exit code {completed.returncode}: {completed.args!r}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )


def run(
    *args: str | Path,
    cwd: Path = ROOT,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    completed = capture(*args, cwd=cwd, timeout=timeout)
    assert completed.returncode == 0, command_failure(completed)
    return completed


@pytest.fixture(scope="session")
def audit_wheels(tmp_path_factory: pytest.TempPathFactory) -> Wheels:
    wheelhouse = tmp_path_factory.mktemp("audit-wheelhouse")
    for package in ("bluetape-core", "bluetape"):
        run(
            "uv",
            "build",
            "--package",
            package,
            "--wheel",
            "--out-dir",
            wheelhouse,
        )
    audit_build = capture(
        "uv",
        "build",
        "--package",
        "bluetape-audit",
        "--wheel",
        "--out-dir",
        wheelhouse,
    )

    return Wheels(
        audit_build=audit_build,
        audit=next(wheelhouse.glob("bluetape_audit-*.whl"), None),
        meta=next(wheelhouse.glob("bluetape-*.whl")),
        core=next(wheelhouse.glob("bluetape_core-*.whl")),
    )


def require_audit_wheel(wheels: Wheels) -> Path:
    assert wheels.audit_build.returncode == 0, command_failure(wheels.audit_build)
    assert wheels.audit is not None, "audit build succeeded without producing a wheel"
    return wheels.audit


def new_venv(path: Path) -> Path:
    run("uv", "venv", "--python", PYTHON_VERSION, path)
    return path / "bin/python"


def wheel_metadata(wheel: Path) -> Message:
    with zipfile.ZipFile(wheel) as archive:
        metadata_path = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        return message_from_bytes(archive.read(metadata_path))


def pip_check(python: Path) -> None:
    run("uv", "pip", "check", "--python", python)


_AUDIT_IMPORT_PROBE = f"""
import importlib
import importlib.util
from pathlib import Path
import socket
import sys

def deny_network(*args, **kwargs):
    raise AssertionError("network access is forbidden during isolated imports")

socket.socket = deny_network
socket.create_connection = deny_network
prefix = Path(sys.prefix).resolve()
root = importlib.import_module("bluetape")
root_paths = tuple(Path(item).resolve() for item in root.__path__)
assert root_paths
assert all(item.is_relative_to(prefix) for item in root_paths)
spec_paths = tuple(
    Path(item).resolve() for item in root.__spec__.submodule_search_locations
)
assert spec_paths == root_paths
spec = importlib.util.find_spec("bluetape.audit")
assert spec is not None
assert spec.origin is not None
assert Path(spec.origin).resolve().is_relative_to(prefix)
module = importlib.import_module("bluetape.audit")
assert module.__file__ is not None
assert Path(module.__file__).resolve().is_relative_to(prefix)
exports = tuple(module.__all__)
assert exports[:6] == {AUDIT_ERROR_EXPORT_PREFIX!r}
missing = object()
assert all(getattr(module, name, missing) is not missing for name in exports)
"""


_DEFAULT_IMPORT_PROBE = """
import importlib
import importlib.util
from pathlib import Path
import socket
import sys

def deny_network(*args, **kwargs):
    raise AssertionError("network access is forbidden during isolated imports")

socket.socket = deny_network
socket.create_connection = deny_network
prefix = Path(sys.prefix).resolve()
root = importlib.import_module("bluetape")
assert root.__file__ is None
root_paths = tuple(Path(item).resolve() for item in root.__path__)
assert root_paths
assert all(item.is_relative_to(prefix) for item in root_paths)
spec_paths = tuple(
    Path(item).resolve() for item in root.__spec__.submodule_search_locations
)
assert spec_paths == root_paths
core_spec = importlib.util.find_spec("bluetape.core")
assert core_spec is not None
assert core_spec.origin is not None
assert Path(core_spec.origin).resolve().is_relative_to(prefix)
core = importlib.import_module("bluetape.core")
assert core.__file__ is not None
assert Path(core.__file__).resolve().is_relative_to(prefix)
assert importlib.util.find_spec("bluetape.audit") is None
"""


def test_audit_and_meta_wheel_metadata_preserve_dependency_boundaries(
    audit_wheels: Wheels,
) -> None:
    audit_wheel = require_audit_wheel(audit_wheels)
    audit_metadata = wheel_metadata(audit_wheel)
    meta_metadata = wheel_metadata(audit_wheels.meta)

    assert audit_metadata.get_all("Requires-Dist") is None
    with zipfile.ZipFile(audit_wheel) as archive:
        assert "bluetape/__init__.py" not in archive.namelist()

    requirements = meta_metadata.get_all("Requires-Dist") or []
    default_requirements = [item for item in requirements if ";" not in item]
    audit_requirements = [item for item in requirements if 'extra == "audit"' in item]
    assert default_requirements == ["bluetape-core==0.1.0"]
    assert "audit" in (meta_metadata.get_all("Provides-Extra") or [])
    assert audit_requirements == ['bluetape-audit==0.1.0; extra == "audit"']


def test_focused_audit_wheel_imports_offline_from_its_own_venv(
    audit_wheels: Wheels,
    tmp_path: Path,
) -> None:
    audit_wheel = require_audit_wheel(audit_wheels)
    python = new_venv(tmp_path / "focused-audit")
    run(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--offline",
        "--no-index",
        "--no-deps",
        audit_wheel,
    )

    run(python, "-I", "-c", _AUDIT_IMPORT_PROBE, cwd=tmp_path)
    pip_check(python)


def test_meta_audit_extra_installs_offline_and_audit_removal_rolls_back(
    audit_wheels: Wheels,
    tmp_path: Path,
) -> None:
    audit_wheel = require_audit_wheel(audit_wheels)
    wheelhouse = audit_wheel.parent
    python = new_venv(tmp_path / "meta-audit-extra")
    run(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--offline",
        "--no-index",
        "--find-links",
        wheelhouse,
        "bluetape[audit]==0.1.0",
    )

    run(python, "-I", "-c", _AUDIT_IMPORT_PROBE, cwd=tmp_path)
    pip_check(python)

    run("uv", "pip", "uninstall", "--python", python, "bluetape-audit")
    run(python, "-I", "-c", _DEFAULT_IMPORT_PROBE, cwd=tmp_path)
    pip_check(python)


def test_default_meta_install_stays_core_only(
    audit_wheels: Wheels,
    tmp_path: Path,
) -> None:
    wheelhouse = audit_wheels.meta.parent
    python = new_venv(tmp_path / "meta-default")
    run(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--offline",
        "--no-index",
        "--find-links",
        wheelhouse,
        "bluetape==0.1.0",
    )

    run(python, "-I", "-c", _DEFAULT_IMPORT_PROBE, cwd=tmp_path)
    pip_check(python)
