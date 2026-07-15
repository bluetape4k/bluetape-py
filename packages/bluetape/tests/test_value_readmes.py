import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
PACKAGES = ("id", "measure", "money")


def extract_example(path: Path) -> str:
    matched = re.search(
        r"<!-- value-example:start -->\n```python\n(.*?)\n```\n<!-- value-example:end -->",
        path.read_text(),
        re.DOTALL,
    )
    assert matched is not None, path
    return matched.group(1) + "\n"


def test_value_readme_examples_execute_from_installed_wheels(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    for package in PACKAGES:
        completed = subprocess.run(
            ["uv", "build", "--package", f"bluetape-{package}", "--out-dir", dist],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    environment = tmp_path / "environment"
    subprocess.run(
        ["uv", "venv", environment, "--python", "3.13.14"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    python = environment / "bin/python"
    wheels = sorted(dist.glob("*.whl"))
    completed = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            "--offline",
            "--no-index",
            "--no-deps",
            *wheels,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    for package in PACKAGES:
        english = ROOT / f"packages/bluetape-{package}/README.md"
        korean = ROOT / f"packages/bluetape-{package}/README.ko.md"
        english_example = extract_example(english)
        assert extract_example(korean) == english_example
        completed = subprocess.run(
            [python, "-I", "-c", english_example],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, f"{package}: {completed.stderr}"


def test_value_readme_locale_sections_and_links_match() -> None:
    required_sections = {
        "id": (
            ("## Install", "## 설치"),
            ("## Quickstart", "## 빠른 시작"),
            ("## IDs Are Not Secrets", "## ID는 비밀값이 아님"),
            ("## Generator State", "## 생성기 상태"),
            ("## Persistence and Rollback", "## 영속성과 롤백"),
            ("## Deferred Scope", "## 보류 범위"),
        ),
        "measure": (
            ("## Install", "## 설치"),
            ("## Quickstart", "## 빠른 시작"),
            ("## Custom Units", "## 사용자 정의 단위"),
            ("## Versionless Schema", "## 버전 없는 스키마"),
            ("## Persistence and Rollback", "## 영속성과 롤백"),
            ("## Deferred Scope", "## 보류 범위"),
        ),
        "money": (
            ("## Install", "## 설치"),
            ("## Quickstart", "## 빠른 시작"),
            ("## ISO 4217 Snapshot", "## ISO 4217 스냅샷"),
            ("## Rounding and Exchange Rates", "## 반올림과 환율"),
            ("## Versionless Schema", "## 버전 없는 스키마"),
            ("## Current, Not Historical", "## 현재 데이터와 비역사성"),
            ("## Deferred Scope", "## 보류 범위"),
        ),
    }
    for package, sections in required_sections.items():
        english = (ROOT / f"packages/bluetape-{package}/README.md").read_text()
        korean = (ROOT / f"packages/bluetape-{package}/README.ko.md").read_text()
        for english_heading, korean_heading in sections:
            assert english_heading in english
            assert korean_heading in korean

    for root_readme in (ROOT / "README.md", ROOT / "README.ko.md"):
        text = root_readme.read_text()
        assert "docs/images/readme-diagrams/value-packages-boundary.png" in text
        assert "docs/images/readme-diagrams/value-packages-boundary.svg" in text
        for package in PACKAGES:
            assert f"packages/bluetape-{package}/README.md" in text
            assert f"packages/bluetape-{package}/README.ko.md" in text

    assert (ROOT / "docs/images/readme-diagrams/value-packages-boundary.svg").is_file()
    assert (ROOT / "docs/images/readme-diagrams/value-packages-boundary.png").is_file()
