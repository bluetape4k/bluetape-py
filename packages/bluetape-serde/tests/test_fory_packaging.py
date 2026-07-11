import subprocess
import zipfile
from email import message_from_bytes
from email.message import Message
from pathlib import Path
from typing import NamedTuple

import pytest

ROOT = Path(__file__).parents[3]


class Wheels(NamedTuple):
    serde: Path
    meta: Path
    core: Path


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="session")
def wheels(tmp_path_factory: pytest.TempPathFactory) -> Wheels:
    wheelhouse = tmp_path_factory.mktemp("fory-wheels")
    for package in ("bluetape-serde", "bluetape", "bluetape-core"):
        run("uv", "build", "--package", package, "--wheel", "--out-dir", str(wheelhouse))
    return Wheels(
        serde=next(wheelhouse.glob("bluetape_serde-*.whl")),
        meta=next(wheelhouse.glob("bluetape-*.whl")),
        core=next(wheelhouse.glob("bluetape_core-*.whl")),
    )


def new_venv(path: Path, python: str) -> Path:
    run("uv", "venv", "--python", python, str(path))
    return path / "bin/python"


def wheel_metadata(wheel: Path) -> Message:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        return message_from_bytes(archive.read(metadata_name))


_ROUND_TRIP = r"""
from dataclasses import dataclass
import pyfory
from bluetape.serde import PayloadMetadata, TrustProfile
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyRegistration,
)

@dataclass(slots=True)
class Record:
    value: pyfory.Int64

metadata = PayloadMetadata(
    format=FORY_FORMAT,
    version=FORY_VERSION,
    content_type=FORY_CONTENT_TYPE,
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
adapter = ForyAdapter(
    registration=ForyRegistration(
        python_type=Record,
        schema_id=1,
        schema_version=1,
        type_id=1001,
        logical_name="Record",
    )
)
value = Record(pyfory.Int64(7))
payload = adapter.serialize(value, metadata=metadata)
assert adapter.deserialize(payload, expected_metadata=metadata) == value
"""


def test_meta_package_forwards_only_explicit_fory_extra() -> None:
    metadata = (ROOT / "packages/bluetape/pyproject.toml").read_text()

    assert 'fory = ["bluetape-serde[fory]==0.1.0"]' in metadata
    assert (ROOT / ".python-version").read_text() == "3.13.14\n"


def test_wheel_metadata_keeps_existing_meta_extras_provider_free(wheels: Wheels) -> None:
    metadata = wheel_metadata(wheels.meta)
    requirements = metadata.get_all("Requires-Dist") or []

    assert any("bluetape-serde[fory]==0.1.0" in requirement for requirement in requirements)
    assert all(
        "bluetape-serde[fory]" not in requirement
        for requirement in requirements
        if 'extra == "fory"' not in requirement
    )
    assert all("pyfory" not in requirement for requirement in requirements)


def test_cpython313_base_wheel_imports_without_provider(wheels: Wheels, tmp_path: Path) -> None:
    python = new_venv(tmp_path / "base-313", "3.13.14")
    run("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheels.serde))
    script = r"""
import bluetape.serde
try:
    import bluetape.serde.fory
except ModuleNotFoundError as error:
    assert error.name == "pyfory"
    assert str(error) == "Install bluetape-serde[fory] with CPython 3.13 to use Apache Fory."
else:
    raise AssertionError("provider module unexpectedly imported")
"""
    run(str(python), "-c", script)


def test_cpython313_serde_extra_round_trips(wheels: Wheels, tmp_path: Path) -> None:
    python = new_venv(tmp_path / "extra-313", "3.13.14")
    run("uv", "pip", "install", "--python", str(python), f"{wheels.serde}[fory]")
    run(str(python), "-c", _ROUND_TRIP)


def test_cpython314_base_imports_but_fory_extra_has_no_artifact(
    wheels: Wheels,
    tmp_path: Path,
) -> None:
    python = new_venv(tmp_path / "base-314", "3.14")
    run("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheels.serde))
    run(str(python), "-c", "import bluetape.serde; assert bluetape.serde.json_serialize")

    completed = run(
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        f"{wheels.serde}[fory]",
        check=False,
    )
    assert completed.returncode != 0
    assert "pyfory" in completed.stderr


def test_meta_fory_extra_installs_from_seeded_offline_wheelhouse(
    wheels: Wheels,
    tmp_path: Path,
) -> None:
    wheelhouse = wheels.serde.parent
    run(
        "uv",
        "run",
        "--with",
        "pip",
        "--python",
        "3.13.14",
        "pip",
        "download",
        "--only-binary=:all:",
        "--dest",
        str(wheelhouse),
        "pyfory==1.3.0",
    )
    python = new_venv(tmp_path / "offline-313", "3.13.14")
    run(
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "bluetape[fory]==0.1.0",
    )
    run(str(python), "-c", _ROUND_TRIP)
