from __future__ import annotations

import subprocess
import zipfile
from email import message_from_bytes
from email.message import Message
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
PYTHON_VERSION = "3.13.14"
JWT_EXPORTS = (
    "JWTError",
    "JWTConfigurationError",
    "JWTKeyError",
    "JWTKeyStateError",
    "JWTKeyUnavailableError",
    "JWTTokenError",
    "JWTMalformedTokenError",
    "JWTUnsupportedTokenError",
    "JWTSignatureError",
    "JWTExpiredError",
    "JWTNotYetValidError",
    "JWTClaimError",
    "JWTIssuancePolicyError",
    "JWTCacheError",
    "JWSAlgorithm",
    "KeyStatus",
    "JSONValue",
    "JWTKey",
    "KeyEntry",
    "KeySnapshot",
    "KeyRepository",
    "InMemoryKeyRepository",
    "TokenClaims",
    "VerifiedToken",
    "IssuanceProfile",
    "ValidationProfile",
    "TokenProvider",
    "IssuanceProfileProvider",
    "JWSProvider",
    "VerifiedTokenCacheOptions",
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
def jwt_wheels(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    wheelhouse = tmp_path_factory.mktemp("jwt-wheelhouse")
    for package in ("bluetape-core", "bluetape-cache", "bluetape-jwt", "bluetape"):
        run("uv", "build", "--package", package, "--wheel", "--out-dir", wheelhouse)
    return {
        "core": next(wheelhouse.glob("bluetape_core-*.whl")),
        "cache": next(wheelhouse.glob("bluetape_cache-*.whl")),
        "jwt": next(wheelhouse.glob("bluetape_jwt-*.whl")),
        "meta": next(wheelhouse.glob("bluetape-*.whl")),
    }


def metadata(wheel: Path) -> Message:
    with zipfile.ZipFile(wheel) as archive:
        path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        return message_from_bytes(archive.read(path))


def test_jwt_and_meta_metadata_preserve_exact_dependency_boundaries(
    jwt_wheels: dict[str, Path],
) -> None:
    jwt_requirements = metadata(jwt_wheels["jwt"]).get_all("Requires-Dist") or []
    assert jwt_requirements == ["bluetape-cache==0.1.0", "joserfc>=1.7.4,<2"]
    with zipfile.ZipFile(jwt_wheels["jwt"]) as archive:
        assert "bluetape/__init__.py" not in archive.namelist()

    meta = metadata(jwt_wheels["meta"])
    requirements = meta.get_all("Requires-Dist") or []
    assert [item for item in requirements if ";" not in item] == ["bluetape-core==0.1.0"]
    assert 'bluetape-jwt==0.1.0; extra == "jwt"' in requirements
    assert "jwt" in (meta.get_all("Provides-Extra") or [])


def test_default_meta_wheel_remains_core_only(
    jwt_wheels: dict[str, Path],
    tmp_path: Path,
) -> None:
    environment = tmp_path / "default-meta"
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
        jwt_wheels["core"],
        jwt_wheels["meta"],
    )
    run(
        python,
        "-I",
        "-c",
        "import importlib.util; assert importlib.util.find_spec('bluetape.jwt') is None",
        cwd=tmp_path,
    )


def test_focused_jwt_wheel_imports_from_clean_environment(
    jwt_wheels: dict[str, Path],
    tmp_path: Path,
) -> None:
    environment = tmp_path / "focused-jwt"
    run("uv", "venv", "--python", PYTHON_VERSION, environment)
    python = environment / "bin/python"
    run(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "joserfc>=1.7.4,<2",
        jwt_wheels["cache"],
        jwt_wheels["jwt"],
    )
    probe = f"""
import bluetape.jwt as jwt
assert tuple(jwt.__all__) == {JWT_EXPORTS!r}
assert jwt.__path__
"""
    run(python, "-I", "-c", probe, cwd=tmp_path)
