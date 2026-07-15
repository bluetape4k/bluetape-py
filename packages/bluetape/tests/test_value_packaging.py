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
