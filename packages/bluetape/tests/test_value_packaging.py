import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_meta_value_extras_are_exact_and_default_stays_core_only() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")
    meta = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")
    project = meta["project"]
    extras = project["optional-dependencies"]
    expected = [
        "bluetape-id==0.1.0",
        "bluetape-measure==0.1.0",
        "bluetape-money==0.1.0",
    ]

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert extras["id"] == [expected[0]]
    assert extras["measure"] == [expected[1]]
    assert extras["money"] == [expected[2]]
    assert extras["values"] == expected
    assert [item for item in extras["dev"] if item in expected] == expected
    assert [item for item in extras["all"] if item in expected] == expected

    for distribution in ("bluetape-id", "bluetape-measure", "bluetape-money"):
        dependency = f"{distribution}==0.1.0"
        member = f"packages/{distribution}"
        assert root["project"]["dependencies"].count(dependency) == 1
        assert root["tool"]["uv"]["sources"][distribution] == {"workspace": True}
        assert root["tool"]["uv"]["workspace"]["members"].count(member) == 1
        assert meta["tool"]["uv"]["sources"][distribution] == {"workspace": True}


def test_value_packages_are_publishable_but_not_historical_release_targets() -> None:
    distributions = ("bluetape-id", "bluetape-measure", "bluetape-money")
    preflight = (ROOT / "docs/release/pypi-preflight.md").read_text()
    target_table, classification = preflight.split("## Fail-Closed Workspace Classification", 1)
    assert all(f"`{distribution}`" not in target_table for distribution in distributions)
    assert all(f"`{distribution}`" in classification for distribution in distributions)


def test_generic_ci_discovers_value_packages_without_a_dedicated_workflow() -> None:
    workflows = sorted(path.name for path in (ROOT / ".github/workflows").glob("*.yml"))
    assert workflows == ["ci.yml", "fory-conformance.yml"]
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "paths:" not in ci
    assert "uv run ruff check ." in ci
    assert "uv run ruff format --check ." in ci
    assert "pytest\n          --strict-markers" in ci
    assert "uv build --all-packages" in ci


def test_value_wheel_verifier_reports_exact_origins_and_isolation() -> None:
    completed = subprocess.run(
        [ROOT / "scripts/verify-value-wheels.sh"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["schema_version"] == 1
    assert summary["lock_sha256"] == hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
    assert set(summary["wheel_counts"]) == set(summary["workspace_distributions"])
    assert set(summary["wheel_counts"].values()) == {1}
    assert len(summary["local_wheels"]) == len(summary["workspace_distributions"])
    assert all(len(wheel["sha256"]) == 64 for wheel in summary["local_wheels"])
    assert summary["focused_metadata"] == {
        "bluetape-id": {"requires_dist": [], "root_namespace_initializer": False},
        "bluetape-measure": {"requires_dist": [], "root_namespace_initializer": False},
        "bluetape-money": {"requires_dist": [], "root_namespace_initializer": False},
    }

    expected_environments = {
        "focused-id",
        "focused-measure",
        "focused-money",
        "meta-id",
        "meta-measure",
        "meta-money",
        "meta-values",
        "meta-dev",
        "meta-all",
        "meta-default",
    }
    environments = summary["environments"]
    assert set(environments) == expected_environments
    for result in environments.values():
        assert result["network_free"] is True
        assert result["pip_check"] is True
        assert result["python_isolated"] is True
        assert all("site-packages/bluetape/" in origin for origin in result["origins"].values())
        for artifact in result["external_artifacts"]:
            assert artifact["name"]
            assert artifact["version"]
            assert artifact["hashes"]
            assert all(len(digest) == 64 for digest in artifact["hashes"])

    assert environments["focused-id"]["modules"] == ["bluetape.id"]
    assert environments["focused-measure"]["modules"] == ["bluetape.measure"]
    assert environments["focused-money"]["modules"] == ["bluetape.money"]
    assert environments["meta-values"]["modules"] == [
        "bluetape.id",
        "bluetape.measure",
        "bluetape.money",
    ]
    assert environments["meta-default"]["modules"] == ["bluetape.core"]
    assert environments["meta-default"]["absent"] == [
        "bluetape.id",
        "bluetape.measure",
        "bluetape.money",
    ]
    assert environments["meta-dev"]["external_artifacts"]
    assert environments["meta-all"]["external_artifacts"]
    assert environments["meta-values"]["external_artifacts"] == []
