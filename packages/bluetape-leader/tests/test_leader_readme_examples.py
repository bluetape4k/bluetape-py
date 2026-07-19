from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

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


def test_manual_lifecycle_example_surfaces_terminal_renewal_outcomes_without_release() -> None:
    namespace: dict[str, object] = {}
    exec(snippet(ENGLISH.read_text(), "manual-lifecycle-example"), namespace)
    leader = __import__("bluetape.leader", fromlist=["bluetape"])

    class SyncHandle:
        def __init__(self, outcome: object) -> None:
            self.outcome = outcome
            self.release_calls = 0

        def assert_held(self) -> None:
            return None

        def renew(self) -> object:
            return self.outcome

        def release(self) -> None:
            self.release_calls += 1

    class SyncLock:
        def __init__(self, handle: SyncHandle) -> None:
            self.handle = handle

        def try_acquire(self, _name: str, _options: object) -> SyncHandle:
            return self.handle

    not_held = SyncHandle(leader.NotHeld())
    with pytest.raises(leader.LeaderLeaseLostError):
        namespace["run_manual"](SyncLock(not_held), object(), object())
    assert not_held.release_calls == 0

    class AsyncHandle:
        def __init__(self, outcome: object) -> None:
            self.outcome = outcome
            self.release_calls = 0

        async def assert_held(self) -> None:
            return None

        async def renew(self) -> object:
            return self.outcome

        async def release(self) -> None:
            self.release_calls += 1

    class AsyncLock:
        def __init__(self, handle: AsyncHandle) -> None:
            self.handle = handle

        async def try_acquire(self, _name: str, _options: object) -> AsyncHandle:
            return self.handle

    failure = leader.LeaderBackendError()
    backend_failed = AsyncHandle(leader.RenewBackendFailure(failure))
    with pytest.raises(leader.LeaderBackendError) as caught:
        asyncio.run(namespace["run_manual_async"](AsyncLock(backend_failed), object(), object()))
    assert caught.value is failure
    assert backend_failed.release_calls == 0


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
