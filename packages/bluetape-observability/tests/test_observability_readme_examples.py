from __future__ import annotations

import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1]
ENGLISH = PACKAGE_ROOT / "README.md"
KOREAN = PACKAGE_ROOT / "README.ko.md"


def extract(path: Path, marker: str) -> str:
    text = path.read_text()
    pattern = re.compile(
        rf"<!-- {re.escape(marker)}:start -->\n"
        rf"```python\n(.*?)\n```\n<!-- {re.escape(marker)}:end -->",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"missing {marker} in {path}"
    return match.group(1)


def test_package_readme_examples_are_source_equivalent() -> None:
    for marker in (
        "api-only-example",
        "sdk-example",
        "resilience-composition",
        "redis-composition",
    ):
        english = extract(ENGLISH, marker)
        korean = extract(KOREAN, marker)
        assert english == korean
        compile(english, f"{ENGLISH}:{marker}", "exec")


def test_api_only_example_executes_without_sdk() -> None:
    source = extract(ENGLISH, "api-only-example")
    namespace: dict[str, object] = {}
    exec(compile(source, str(ENGLISH), "exec"), namespace)


@pytest.mark.observability_sdk
def test_sdk_example_executes_with_application_owned_lifecycle() -> None:
    source = extract(ENGLISH, "sdk-example")
    namespace: dict[str, object] = {}
    exec(compile(source, str(ENGLISH), "exec"), namespace)
    assert namespace["shutdown_order"] == ["tracer", "meter"]


def test_composition_examples_pin_order_and_failure_policy() -> None:
    for marker in ("resilience-composition", "redis-composition"):
        namespace: dict[str, object] = {}
        exec(compile(extract(ENGLISH, marker), str(ENGLISH), "exec"), namespace)
        assert namespace["calls"] == ["audit", "otel"]

    for path in (ENGLISH, KOREAN):
        text = path.read_text()
        assert "fail-stop" in text
        assert "fail-continue" in text
        assert "replaces the previous observer" in text
        assert "restores the prior observer" in text


def test_package_readmes_pin_ownership_privacy_and_prerequisites() -> None:
    required = (
        "pip install bluetape-observability",
        "bluetape-observability + bluetape-resilience",
        "bluetape-observability + bluetape-cache-redis",
        "OpenTelemetryPolicyObserver",
        "OpenTelemetryRedisObserver",
        "OpenTelemetryRedisCoordinationObserver",
        "bluetape.resilience.policy.events",
        "bluetape.redis.operations",
        "bluetape.redis.coordination.operations",
        "no mutable health",
        "application-owned",
        "raw threads",
        "run_in_executor",
        "detached",
        "baggage",
        "trace ID",
        "rollback",
    )
    for path in (ENGLISH, KOREAN):
        text = path.read_text()
        assert all(value in text for value in required)
        assert "bluetape[observability]" not in text

    assert ENGLISH.read_text().splitlines()[1] == ""
    assert ENGLISH.read_text().splitlines()[2] == "English | [한국어](README.ko.md)"
    assert KOREAN.read_text().splitlines()[1] == ""
    assert KOREAN.read_text().splitlines()[2] == "[English](README.md) | 한국어"
