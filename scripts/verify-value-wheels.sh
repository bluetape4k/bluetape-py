#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

exec uv run --locked --python 3.13.14 python - <<'PY'
from __future__ import annotations

import email
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path.cwd()
PYTHON_VERSION = "3.13.14"
VALUE_MODULES = ["bluetape.id", "bluetape.measure", "bluetape.money"]


def run(command: list[str], *, environment: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        rendered = " ".join(command)
        raise RuntimeError(f"command failed: {rendered}\n{completed.stderr}")
    return completed.stdout


def load_project(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def normalize_distribution(distribution: str) -> str:
    return re.sub(r"[-_.]+", "_", distribution).lower()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def requirement_name(requirement: str) -> str:
    matched = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
    if matched is None:
        raise ValueError("invalid local requirement")
    return matched.group().lower().replace("_", "-")


def parse_external_artifacts(text: str) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in text.splitlines():
        matched = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)", line)
        if matched is not None:
            current = {
                "name": matched.group(1).lower().replace("_", "-"),
                "version": matched.group(2),
                "hashes": [],
            }
            artifacts.append(current)
            continue
        hash_match = re.search(r"--hash=sha256:([0-9a-f]{64})", line)
        if hash_match is not None and current is not None:
            current["hashes"].append(hash_match.group(1))
    for artifact in artifacts:
        artifact["hashes"] = sorted(set(artifact["hashes"]))
        if not artifact["hashes"]:
            raise AssertionError(f"locked artifact has no hashes: {artifact['name']}")
    return artifacts


def inspect_focused_metadata(wheel: Path) -> dict[str, object]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_name))
    return {
        "requires_dist": metadata.get_all("Requires-Dist") or [],
        "root_namespace_initializer": "bluetape/__init__.py" in names,
    }


PROBE = r'''
import importlib.util
import json
import sys
from pathlib import Path

request = json.loads(sys.argv[1])

def find(name):
    try:
        return importlib.util.find_spec(name)
    except ModuleNotFoundError:
        return None

root = Path(sys.prefix).resolve()
origins = {}
for name in request["modules"]:
    specification = find(name)
    assert specification is not None and specification.origin is not None, name
    origin = Path(specification.origin).resolve()
    assert origin.is_relative_to(root), (name, origin, root)
    origins[name] = str(origin)
for name in request["absent"]:
    assert find(name) is None, name
print(json.dumps({"origins": origins}, separators=(",", ":"), sort_keys=True))
'''


with tempfile.TemporaryDirectory(prefix="bluetape-value-wheels-") as temporary:
    temporary_root = Path(temporary)
    dist = temporary_root / "dist"
    dist.mkdir()
    run(["uv", "build", "--all-packages", "--out-dir", str(dist)])

    projects = {
        load_project(path)["project"]["name"]: load_project(path)
        for path in sorted((ROOT / "packages").glob("*/pyproject.toml"))
    }
    workspace_distributions = sorted(projects)
    wheels: dict[str, Path] = {}
    wheel_counts: dict[str, int] = {}
    for distribution in workspace_distributions:
        matches = sorted(dist.glob(f"{normalize_distribution(distribution)}-*.whl"))
        wheel_counts[distribution] = len(matches)
        if len(matches) != 1:
            raise AssertionError(
                f"expected one wheel for {distribution}, found {len(matches)}"
            )
        wheels[distribution] = matches[0]

    meta_project = projects["bluetape"]["project"]
    meta_extras = meta_project["optional-dependencies"]
    core_and_meta = ["bluetape-core", "bluetape"]

    def meta_local(extra: str) -> list[str]:
        dependencies = [requirement_name(item) for item in meta_extras[extra]]
        return [*core_and_meta, *dependencies]

    configurations = [
        {
            "name": "focused-id",
            "export_package": "bluetape-id",
            "extra": None,
            "local": ["bluetape-id"],
            "modules": ["bluetape.id"],
            "absent": VALUE_MODULES[1:],
        },
        {
            "name": "focused-measure",
            "export_package": "bluetape-measure",
            "extra": None,
            "local": ["bluetape-measure"],
            "modules": ["bluetape.measure"],
            "absent": [VALUE_MODULES[0], VALUE_MODULES[2]],
        },
        {
            "name": "focused-money",
            "export_package": "bluetape-money",
            "extra": None,
            "local": ["bluetape-money"],
            "modules": ["bluetape.money"],
            "absent": VALUE_MODULES[:2],
        },
        *[
            {
                "name": f"meta-{extra}",
                "export_package": "bluetape",
                "extra": extra,
                "local": meta_local(extra),
                "modules": [f"bluetape.{extra}"],
                "absent": [module for module in VALUE_MODULES if module != f"bluetape.{extra}"],
            }
            for extra in ("id", "measure", "money")
        ],
        {
            "name": "meta-values",
            "export_package": "bluetape",
            "extra": "values",
            "local": meta_local("values"),
            "modules": VALUE_MODULES,
            "absent": [],
        },
        {
            "name": "meta-dev",
            "export_package": "bluetape",
            "extra": "dev",
            "local": meta_local("dev"),
            "modules": VALUE_MODULES,
            "absent": [],
        },
        {
            "name": "meta-all",
            "export_package": "bluetape",
            "extra": "all",
            "local": meta_local("all"),
            "modules": VALUE_MODULES,
            "absent": [],
        },
        {
            "name": "meta-default",
            "export_package": "bluetape",
            "extra": None,
            "local": core_and_meta,
            "modules": ["bluetape.core"],
            "absent": VALUE_MODULES,
        },
    ]

    environments: dict[str, dict[str, object]] = {}
    for configuration in configurations:
        name = configuration["name"]
        environment_root = temporary_root / name
        requirements = temporary_root / f"{name}-requirements.txt"
        export_command = [
            "uv",
            "export",
            "--locked",
            "--package",
            configuration["export_package"],
            "--no-dev",
            "--no-emit-local",
        ]
        if configuration["extra"] is not None:
            export_command.extend(["--extra", configuration["extra"]])
        export_command.extend(["-o", str(requirements)])
        run(export_command)
        requirement_text = requirements.read_text()

        run(["uv", "venv", str(environment_root), "--python", PYTHON_VERSION])
        python = environment_root / "bin/python"
        run(
            [
                "uv",
                "pip",
                "sync",
                "--python",
                str(python),
                "--require-hashes",
                "--allow-empty-requirements",
                str(requirements),
            ]
        )

        offline_environment = os.environ.copy()
        offline_environment["UV_OFFLINE"] = "1"
        local_wheels = [str(wheels[distribution]) for distribution in configuration["local"]]
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--offline",
                "--no-index",
                "--find-links",
                str(dist),
                "--no-deps",
                *local_wheels,
            ],
            environment=offline_environment,
        )
        run(["uv", "pip", "check", "--python", str(python)], environment=offline_environment)
        request = {
            "modules": configuration["modules"],
            "absent": configuration["absent"],
        }
        probe = run(
            [str(python), "-I", "-c", PROBE, json.dumps(request, sort_keys=True)],
            environment=offline_environment,
        )
        origins = json.loads(probe)["origins"]
        environments[name] = {
            "extra": configuration["extra"],
            "modules": configuration["modules"],
            "absent": configuration["absent"],
            "origins": origins,
            "external_artifacts": parse_external_artifacts(requirement_text),
            "requirements_sha256": sha256(requirements),
            "preparation": "uv-export-locked+uv-pip-sync-require-hashes",
            "installation": "uv-offline+no-index+no-deps+local-wheels",
            "network_free": True,
            "pip_check": True,
            "python_isolated": True,
        }

    focused_metadata = {
        distribution: inspect_focused_metadata(wheels[distribution])
        for distribution in ("bluetape-id", "bluetape-measure", "bluetape-money")
    }
    if any(value["requires_dist"] for value in focused_metadata.values()):
        raise AssertionError("focused value wheels must have no runtime dependencies")
    if any(value["root_namespace_initializer"] for value in focused_metadata.values()):
        raise AssertionError("focused value wheels must not own bluetape/__init__.py")

    summary = {
        "schema_version": 1,
        "lock_sha256": sha256(ROOT / "uv.lock"),
        "workspace_distributions": workspace_distributions,
        "wheel_counts": wheel_counts,
        "local_wheels": [
            {"distribution": distribution, "filename": wheel.name, "sha256": sha256(wheel)}
            for distribution, wheel in sorted(wheels.items())
        ],
        "focused_metadata": focused_metadata,
        "environments": environments,
    }
    print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
PY
