from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]
PACKAGE_ROOT = ROOT / "packages/bluetape-audit"


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_distribution_metadata_is_focused_and_exact() -> None:
    metadata = load_pyproject(PACKAGE_ROOT / "pyproject.toml")

    assert metadata["project"] == {
        "name": "bluetape-audit",
        "version": "0.1.0",
        "description": "Python-native storage-neutral audit event contracts for bluetape.",
        "readme": "README.md",
        "requires-python": ">=3.13",
        "dependencies": [],
    }
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.audit"


def test_workspace_registers_audit_exactly_once() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")
    dependency = "bluetape-audit==0.1.0"

    assert root["project"]["dependencies"].count(dependency) == 1
    assert root["tool"]["uv"]["sources"]["bluetape-audit"] == {"workspace": True}
    assert root["tool"]["uv"]["workspace"]["members"].count("packages/bluetape-audit") == 1


def test_meta_extra_includes_audit_without_widening_default() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")
    project = metadata["project"]
    dependency = "bluetape-audit==0.1.0"

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert project["optional-dependencies"]["audit"] == [dependency]
    assert dependency in project["optional-dependencies"]["dev"]
    assert dependency in project["optional-dependencies"]["all"]
    assert metadata["tool"]["uv"]["sources"]["bluetape-audit"] == {"workspace": True}


def test_nested_namespace_import_has_no_root_initializer() -> None:
    assert not (PACKAGE_ROOT / "src/bluetape/__init__.py").exists()

    module = importlib.import_module("bluetape.audit")
    assert module.__file__ is not None
    assert Path(module.__file__).name == "__init__.py"


def test_audit_is_publishable_but_not_a_historical_release_target() -> None:
    preflight = (ROOT / "docs/release/pypi-preflight.md").read_text()
    target_table, classification = preflight.split("## Fail-Closed Workspace Classification", 1)

    assert "`bluetape-audit`" not in target_table
    assert "`bluetape-audit`" in classification
