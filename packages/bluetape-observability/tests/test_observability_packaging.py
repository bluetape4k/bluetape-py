from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]
PACKAGE_ROOT = ROOT / "packages/bluetape-observability"


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_distribution_metadata_is_focused_and_exact() -> None:
    metadata = load_pyproject(PACKAGE_ROOT / "pyproject.toml")

    assert metadata["project"] == {
        "name": "bluetape-observability",
        "version": "0.1.0",
        "description": "OpenTelemetry adapters for Bluetape resilience and Redis observer events.",
        "readme": "README.md",
        "requires-python": ">=3.13",
        "dependencies": ["opentelemetry-api>=1.43,<2"],
    }
    assert metadata["dependency-groups"]["test"] == [
        "bluetape-cache-redis==0.1.0",
        "bluetape-resilience==0.1.0",
        "opentelemetry-sdk>=1.43,<2",
        "pytest>=8.4.0",
        "pytest-asyncio>=1.1.0",
    ]
    assert "optional-dependencies" not in metadata["project"]
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == ("bluetape.observability")


def test_workspace_registers_observability_exactly_once() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")

    assert root["project"]["dependencies"].count("bluetape-observability==0.1.0") == 1
    assert root["tool"]["uv"]["sources"]["bluetape-observability"] == {"workspace": True}
    assert root["tool"]["uv"]["workspace"]["members"].count("packages/bluetape-observability") == 1


def test_meta_distribution_does_not_reference_observability() -> None:
    meta = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")["project"]

    assert all("observability" not in item for item in meta["dependencies"])
    assert all(
        "observability" not in item
        for values in meta["optional-dependencies"].values()
        for item in values
    )


def test_nested_namespace_is_importable_without_root_convenience_package() -> None:
    assert not (PACKAGE_ROOT / "src/bluetape/__init__.py").exists()

    specification = importlib.util.find_spec("bluetape.observability")
    assert specification is not None
    assert specification.origin is not None
    assert Path(specification.origin).name == "__init__.py"


def test_historical_release_target_does_not_gain_observability() -> None:
    preflight = (ROOT / "docs/release/pypi-preflight.md").read_text()
    target_table = preflight.split("## Target Distributions", 1)[1].split(
        "## Fail-Closed Workspace Classification", 1
    )[0]

    assert "`bluetape-observability`" not in target_table


def test_ci_and_wheel_verifier_own_focused_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    verifier = (ROOT / "scripts/verify-observability-wheels.sh").read_text()

    assert "observability:" in workflow
    assert "Sync observability test dependencies" in workflow
    assert "Test observability SDK contracts without skips" in workflow
    assert "not observability_sdk and not observability_workspace" in workflow
    assert "issue24-observability-sdk.xml" not in workflow
    assert "scripts/verify-observability-wheels.sh" in workflow
    assert 'find_spec("opentelemetry.sdk") is None' in workflow
    assert 'find_spec("bluetape.observability")' in workflow

    for value in (
        "set -euo pipefail",
        "mktemp -d",
        "--require-hashes",
        "--no-emit-local",
        "trap 'rm -rf \"$tmp_dir\"' EXIT",
        '"$tmp_dir/focused/bin/python" -I',
        '"$tmp_dir/default/bin/python" -I',
        '"$tmp_dir/readme/bin/python" -I',
        "uv pip check",
        "observability-requirements.txt",
        "redis-requirements.txt",
    ):
        assert value in verifier
