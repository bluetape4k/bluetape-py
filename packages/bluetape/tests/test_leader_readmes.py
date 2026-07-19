from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[3]
CORE = (
    ROOT / "packages/bluetape-leader/README.md",
    ROOT / "packages/bluetape-leader/README.ko.md",
)
ADAPTER = (
    ROOT / "packages/bluetape-leader-redis/README.md",
    ROOT / "packages/bluetape-leader-redis/README.ko.md",
)
ROOT_READMES = (ROOT / "README.md", ROOT / "README.ko.md")
META_READMES = (
    ROOT / "packages/bluetape/README.md",
    ROOT / "packages/bluetape/README.ko.md",
)
SCENARIOS = {
    "install",
    "constructor",
    "contention",
    "precise-result",
    "identity",
    "fencing",
    "cancellation",
    "manual-lifecycle",
    "unsupported-topology",
    "migration",
    "rollback",
    "operator-actions",
    "deployment-checklist",
}


def scenario_ids(path: Path) -> set[str]:
    return set(re.findall(r"<!-- leader-scenario:([a-z-]+) -->", path.read_text()))


def test_bilingual_leader_docs_have_the_same_stable_scenario_contract() -> None:
    english = scenario_ids(CORE[0]) | scenario_ids(ADAPTER[0])
    korean = scenario_ids(CORE[1]) | scenario_ids(ADAPTER[1])
    assert english == korean == SCENARIOS


def test_bilingual_leader_docs_keep_normalized_api_calls_aligned() -> None:
    calls = re.compile(
        r"(?:LeaderElectionOptions|RedisDistributedLock|AsyncRedisDistributedLock|"
        r"RedisLeaderElector|AsyncRedisLeaderElector|try_acquire|run_if_leader_result)\([^\n]*"
    )
    assert calls.findall(CORE[0].read_text()) == calls.findall(CORE[1].read_text())
    assert calls.findall(ADAPTER[0].read_text()) == calls.findall(ADAPTER[1].read_text())


def test_leader_docs_record_ordered_migration_loss_and_rollback_contracts() -> None:
    ordered_by_path = {
        ADAPTER[0]: (
            "stop every old and new contender",
            "prove the old lease absent",
            "downstream resource high-watermark",
            "strictly above",
            "identical prefix",
            "restart all contenders",
        ),
        ADAPTER[1]: (
            "기존 contender와 신규 contender를 모두 중지",
            "기존 lease가 없음을 증명",
            "downstream resource high-watermark",
            "엄격히 큰 값",
            "동일한 prefix",
            "모든 contender를 다시 시작",
        ),
    }
    required_by_path = {
        ADAPTER[0]: (
            "block new protected work",
            "never deletes",
            "never prints",
            "expired lease keys intact",
            "atomic downstream fencing",
        ),
        ADAPTER[1]: (
            "새 protected work를 차단",
            "절대 삭제하지",
            "절대 출력하지",
            "만료된 lease key를 그대로",
            "atomic downstream fencing",
        ),
    }
    for path, ordered_steps in ordered_by_path.items():
        normalized = " ".join(path.read_text().split()).casefold()
        positions = [normalized.index(step.casefold()) for step in ordered_steps]
        assert positions == sorted(positions)
        for required in required_by_path[path]:
            assert required.casefold() in normalized, f"{required!r} missing from {path}"


def test_root_meta_layout_and_status_docs_register_leader_packages() -> None:
    for path in ROOT_READMES + META_READMES:
        text = path.read_text()
        assert 'pip install "bluetape[leader]"' in text
        assert 'pip install "bluetape[leader-redis]"' in text
        assert "core-only" in text
    layout = (ROOT / "docs/package-layout.md").read_text()
    assert "`bluetape-leader`" in layout
    assert "`bluetape-leader-redis`" in layout
    for path in (ROOT / "WIP.md", ROOT / "CHANGELOG.md"):
        assert "Issue #17" in path.read_text()
