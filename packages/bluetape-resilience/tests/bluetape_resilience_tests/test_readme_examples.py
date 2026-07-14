"""Executable and parity checks for resilience package documentation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[2]
REPOSITORY_ROOT = Path(__file__).parents[4]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _example(readme: str, name: str) -> str:
    pattern = (
        rf"<!-- resilience-example:{name}:start -->\s*"
        rf"```python\s*(.*?)\s*```\s*"
        rf"<!-- resilience-example:{name}:end -->"
    )
    match = re.search(pattern, readme, flags=re.DOTALL)
    assert match is not None, f"missing executable {name} example"
    return match.group(1)


@pytest.mark.parametrize("locale", ["README.md", "README.ko.md"])
def test_package_readme_sync_example_executes(locale: str) -> None:
    namespace: dict[str, object] = {"__name__": "__readme_example__"}
    exec(_example(_read(PACKAGE_ROOT / locale), "sync"), namespace)


@pytest.mark.parametrize("locale", ["README.md", "README.ko.md"])
def test_package_readme_async_example_executes(locale: str) -> None:
    namespace: dict[str, object] = {"__name__": "__readme_example__"}
    exec(_example(_read(PACKAGE_ROOT / locale), "async"), namespace)


def test_package_readmes_cover_the_same_public_contract() -> None:
    english = _read(PACKAGE_ROOT / "README.md")
    korean = _read(PACKAGE_ROOT / "README.ko.md")
    required = {
        "bluetape-resilience",
        "bluetape[resilience]",
        "ResiliencePipeline",
        "AsyncResiliencePipeline",
        "with_retry",
        "with_circuit_breaker",
        "with_bulkhead",
        "with_timeout",
        "PolicyEvent",
        "RetryExhaustedError",
        "PolicyTimeoutError",
        "CircuitOpenError",
        "BulkheadRejectedError",
    }
    for term in required:
        assert term in english
        assert term in korean


@pytest.mark.parametrize(
    "relative_path",
    [
        "README.md",
        "README.ko.md",
        "packages/bluetape/README.md",
        "packages/bluetape/README.ko.md",
        "docs/package-layout.md",
        "WIP.md",
        "CHANGELOG.md",
    ],
)
def test_workspace_docs_register_resilience_distribution(relative_path: str) -> None:
    assert "bluetape-resilience" in _read(REPOSITORY_ROOT / relative_path)


def test_agents_records_resilience_boundary() -> None:
    agents = _read(REPOSITORY_ROOT / "AGENTS.md")
    assert "`bluetape-resilience` stays stdlib-only" in agents
    assert "sync timeout" in agents
