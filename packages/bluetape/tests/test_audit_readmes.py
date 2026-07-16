import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
PACKAGE_READMES = (
    ROOT / "packages/bluetape-audit/README.md",
    ROOT / "packages/bluetape-audit/README.ko.md",
)
ROOT_READMES = (ROOT / "README.md", ROOT / "README.ko.md")
SVG_PATH = ROOT / "docs/images/readme-diagrams/audit-contract-boundary.svg"
PNG_PATH = ROOT / "docs/images/readme-diagrams/audit-contract-boundary.png"


def extract_example(path: Path) -> str:
    matched = re.search(
        r"<!-- audit-example:start -->\n```python\n(.*?)\n```\n<!-- audit-example:end -->",
        path.read_text(),
        re.DOTALL,
    )
    assert matched is not None, path
    return matched.group(1) + "\n"


def test_audit_readme_example_executes_from_installed_focused_wheel(
    tmp_path: Path,
) -> None:
    english_example = extract_example(PACKAGE_READMES[0])
    assert extract_example(PACKAGE_READMES[1]) == english_example

    dist = tmp_path / "dist"
    completed = subprocess.run(
        ["uv", "build", "--package", "bluetape-audit", "--out-dir", dist],
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
    wheel = next(dist.glob("*.whl"))
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
            wheel,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    completed = subprocess.run(
        [python, "-I", "-c", english_example],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_audit_readme_sections_and_install_contracts_match() -> None:
    section_pairs = (
        ("## Install", "## 설치"),
        ("## Field Semantics", "## 필드 의미"),
        ("## Adapter Validation", "## 어댑터 검증"),
        ("## Safe Error Handling", "## 안전한 오류 처리"),
        ("## Redaction Boundary", "## 비식별화 경계"),
        ("## Payload Dispatch", "## 페이로드 디스패치"),
        ("## Incremental Adoption", "## 점진적 도입"),
        ("## Removal and Rollback", "## 제거와 롤백"),
        ("## Accepted and Rejected Ownership", "## 소유하는 것과 소유하지 않는 것"),
        ("## Testing Helpers", "## 테스트 도우미"),
    )
    english = PACKAGE_READMES[0].read_text()
    korean = PACKAGE_READMES[1].read_text()
    for english_heading, korean_heading in section_pairs:
        assert english_heading in english
        assert korean_heading in korean

    for text in (english, korean):
        assert "pip install bluetape-audit" in text
        assert 'pip install "bluetape[audit]"' in text
        assert "pip uninstall bluetape-audit" in text
        assert "pip uninstall bluetape" in text
        assert "(content_type, schema_version)" in text
        assert "validate_audit_event" in text
        assert "first side effect" in text
        assert "field_category" in text
        assert "limit_name" in text
        assert "make_audit_event" in text
        assert "assert_audit_event_preserved" in text


def test_audit_readmes_pin_security_rollout_and_ownership_boundaries() -> None:
    required_literals = (
        "untrusted caller assertion",
        "adapter allowlist",
        "before parser selection",
        "before header emission",
        "rejected before parsing",
        "versioned adapter-owned limits",
        "replay compatibility",
        "producer compatibility",
        "external bounded policy ID",
        "not event metadata",
        "never log rejected values",
        "new writes",
        "explicit caller migration",
        "never rewrites history",
        "preserve unknown payload bytes",
        "no package-owned data migration",
        "core-only default install",
        "bluetape.audit is absent",
        "validation is not durable capture",
        "upstream allocation limits",
        "reuse the event ID",
        "every field may be sensitive",
        "repository, history, and outbox remain external",
        "value assertion, not durable history",
    )
    for path in PACKAGE_READMES:
        text = path.read_text()
        for literal in required_literals:
            assert literal in text, f"{literal!r} missing from {path}"


def test_audit_readmes_reference_the_same_svg_and_png_assets() -> None:
    package_svg = "../../docs/images/readme-diagrams/audit-contract-boundary.svg"
    package_png = "../../docs/images/readme-diagrams/audit-contract-boundary.png"
    root_svg = "docs/images/readme-diagrams/audit-contract-boundary.svg"
    root_png = "docs/images/readme-diagrams/audit-contract-boundary.png"

    for path in PACKAGE_READMES:
        text = path.read_text()
        assert package_svg in text
        assert package_png in text
    for path in ROOT_READMES:
        text = path.read_text()
        assert root_svg in text
        assert root_png in text

    assert SVG_PATH.is_file()
    assert PNG_PATH.is_file()
