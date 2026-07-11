import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
CONFORMANCE = ROOT / "packages/bluetape-serde/conformance/fory"
CLI = CONFORMANCE / "python/conformance_cli.py"
MANIFEST = CONFORMANCE / "verify_manifest.py"


def run(*args: str) -> None:
    subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        timeout=30,
        env={**os.environ, "LC_ALL": "C.UTF-8", "TZ": "UTC"},
    )


def test_python_fixture_is_fresh_process_deterministic_and_verifiable(tmp_path: Path) -> None:
    first = tmp_path / "python.first"
    second = tmp_path / "python.second"

    run(sys.executable, str(CLI), "generate", str(first))
    run(sys.executable, str(CLI), "generate", str(second))

    assert first.read_bytes() == second.read_bytes()
    run(sys.executable, str(CLI), "verify", str(first))


def test_manifest_validator_checks_complete_four_producer_inputs(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    artifacts = {name: fixtures / f"{name}.bin" for name in ("python", "go", "rust", "kotlin")}
    run(sys.executable, str(CLI), "generate", str(artifacts["python"]))
    for name in ("go", "rust", "kotlin"):
        artifacts[name].write_bytes(artifacts["python"].read_bytes())
    manifest = tmp_path / "manifest.json"
    command = [
        sys.executable,
        str(MANIFEST),
        "--manifest",
        str(manifest),
        "--python",
        str(artifacts["python"]),
        "--go",
        str(artifacts["go"]),
        "--rust",
        str(artifacts["rust"]),
        "--kotlin",
        str(artifacts["kotlin"]),
    ]

    run(*command, "--write")
    run(*command)
