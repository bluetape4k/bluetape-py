from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[3]
ENGLISH = ROOT / "packages/bluetape-leader/README.md"
KOREAN = ROOT / "packages/bluetape-leader/README.ko.md"


def snippet(text: str, name: str) -> str:
    match = re.search(
        rf"<!-- {re.escape(name)} -->\n```python\n(?P<code>.*?)\n```",
        text,
        re.DOTALL,
    )
    assert match is not None, f"missing {name}"
    return match.group("code")


def test_bilingual_precise_result_example_is_identical_and_executes() -> None:
    english = snippet(ENGLISH.read_text(), "precise-result-example")
    korean = snippet(KOREAN.read_text(), "precise-result-example")

    assert english == korean
    namespace: dict[str, object] = {}
    exec(english, namespace)
    assert namespace["classify"](namespace["sample_result"]) == "elected:none"


def test_bilingual_manual_lifecycle_example_is_identical_and_compiles() -> None:
    english = snippet(ENGLISH.read_text(), "manual-lifecycle-example")
    korean = snippet(KOREAN.read_text(), "manual-lifecycle-example")

    assert english == korean
    compile(english, "<manual-lifecycle-example>", "exec")


def test_core_readmes_record_public_result_and_lifecycle_contracts() -> None:
    for path in (ENGLISH, KOREAN):
        text = path.read_text()
        for required in (
            "pip install bluetape-leader",
            'pip install "bluetape[leader]"',
            "run_if_leader()",
            "run_if_leader_result()",
            "Elected",
            "Skipped",
            "ActionFailed",
            "try_acquire()",
            "auto_renew=True",
            "fencing_token",
            "is_held",
            "TOCTOU",
            "CancelledError",
            "caller",
        ):
            assert required in text, f"{required!r} missing from {path}"
