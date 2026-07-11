#!/usr/bin/env python3
"""Verify deterministic four-language Apache Fory conformance artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
SCHEMA = ROOT / "schema.json"
PYTHON_VERIFIER = ROOT / "python/conformance_cli.py"
PRODUCER_CONTRACTS = {
    "go": {
        "dependency": "github.com/apache/fory/go/fory v1.3.0",
        "toolchain": "go1.26.5",
    },
    "kotlin": {
        "dependency": "org.apache.fory:fory-kotlin:1.3.0",
        "toolchain": "Kotlin 2.3.20; Temurin 21.0.11+10",
    },
    "python": {
        "dependency": "pyfory==1.3.0",
        "toolchain": "CPython 3.13.14",
    },
    "rust": {
        "dependency": "fory=1.3.0",
        "toolchain": "rustc 1.96.1",
    },
}


def canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(artifacts: dict[str, Path]) -> dict[str, Any]:
    schema_bytes = SCHEMA.read_bytes()
    return {
        "format": "apache-fory-xlang",
        "manifest_version": 1,
        "producers": {
            name: {
                **PRODUCER_CONTRACTS[name],
                "fixture": f"fixtures/{name}.bin",
                "sha256": sha256(path.read_bytes()),
                "size": path.stat().st_size,
            }
            for name, path in sorted(artifacts.items())
        },
        "schema": {
            "path": "schema.json",
            "sha256": sha256(schema_bytes),
        },
    }


def verify_manifest(manifest_path: Path, artifacts: dict[str, Path]) -> None:
    raw_manifest = manifest_path.read_text()
    manifest = json.loads(raw_manifest)
    if raw_manifest != canonical_json(manifest):
        raise ValueError("manifest must use canonical sorted JSON")
    expected = build_manifest(artifacts)
    if manifest != expected:
        raise ValueError("manifest fields, hashes, sizes, or toolchain pins do not match")

    for name, artifact in artifacts.items():
        fixture = manifest_path.parent / manifest["producers"][name]["fixture"]
        if fixture.read_bytes() != artifact.read_bytes():
            raise ValueError(f"{name} artifact differs from its committed fixture")
        if name != "python":
            subprocess.run(
                [sys.executable, str(PYTHON_VERIFIER), "verify", str(artifact)],
                check=True,
                timeout=30,
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--python", required=True, dest="python_artifact", type=Path)
    parser.add_argument("--go", required=True, type=Path)
    parser.add_argument("--rust", required=True, type=Path)
    parser.add_argument("--kotlin", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    artifacts = {
        "python": arguments.python_artifact,
        "go": arguments.go,
        "rust": arguments.rust,
        "kotlin": arguments.kotlin,
    }
    if arguments.write:
        arguments.manifest.write_text(canonical_json(build_manifest(artifacts)))
    verify_manifest(arguments.manifest, artifacts)


if __name__ == "__main__":
    main()
