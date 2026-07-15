#!/usr/bin/env bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
mkdir -p "$tmp_dir/dist"

packages=(
  bluetape-core
  bluetape
  bluetape-observability
  bluetape-resilience
  bluetape-cache
  bluetape-compression
  bluetape-serde
  bluetape-cache-redis
)
for package in "${packages[@]}"; do
  uv build --package "$package" --out-dir "$tmp_dir/dist" >/dev/null
done

one_wheel() {
  local distribution="$1"
  local normalized="${distribution//-/_}"
  local wheels=("$tmp_dir"/dist/"${normalized}"-*.whl)
  if [[ ${#wheels[@]} -ne 1 || ! -f "${wheels[0]}" ]]; then
    echo "expected one wheel for $distribution, found ${#wheels[@]}" >&2
    return 1
  fi
  printf '%s\n' "${wheels[0]}"
}

core_wheel="$(one_wheel bluetape-core)"
meta_wheel="$(one_wheel bluetape)"
observability_wheel="$(one_wheel bluetape-observability)"
resilience_wheel="$(one_wheel bluetape-resilience)"
cache_wheel="$(one_wheel bluetape-cache)"
compression_wheel="$(one_wheel bluetape-compression)"
serde_wheel="$(one_wheel bluetape-serde)"
redis_wheel="$(one_wheel bluetape-cache-redis)"

uv export --locked --package bluetape-observability --no-dev --no-emit-local \
  -o "$tmp_dir/requirements.txt" >/dev/null
uv venv "$tmp_dir/focused" --python 3.13.14 >/dev/null
uv pip sync --python "$tmp_dir/focused/bin/python" --require-hashes \
  "$tmp_dir/requirements.txt" >/dev/null
uv pip install --python "$tmp_dir/focused/bin/python" --no-deps \
  "$observability_wheel" >/dev/null
uv pip check --python "$tmp_dir/focused/bin/python" >/dev/null

(
  cd "$tmp_dir"
  "$tmp_dir/focused/bin/python" -I -c '
import importlib.metadata
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from bluetape.observability.redis import (
    OpenTelemetryRedisCoordinationObserver,
    OpenTelemetryRedisObserver,
)
from bluetape.observability.resilience import OpenTelemetryPolicyObserver

class EnumValue:
    def __init__(self, value):
        self.value = value

policy = SimpleNamespace(
    policy_type=EnumValue("retry"), kind=EnumValue("succeeded"),
    outcome=EnumValue("success"), failure_category=EnumValue("none"),
    attempt=1, delay=None, timeout=None, state=None, previous_state=None,
    in_flight=None, waiters=None,
)
redis = SimpleNamespace(
    mode=EnumValue("sync"), operation=EnumValue("get"),
    outcome=EnumValue("success"), error_code=None, elapsed_ns=1,
)
coordination = SimpleNamespace(
    mode=EnumValue("async"), operation=EnumValue("get-or-load"),
    outcome=EnumValue("loaded"), error_code=None, attempts=1, polls=0,
    cleanup_failed=False, elapsed_ns=1,
)
OpenTelemetryPolicyObserver()(policy)
OpenTelemetryRedisObserver().on_event(redis)
OpenTelemetryRedisCoordinationObserver().on_event(coordination)

def absent(name):
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:
        return True

api = importlib.util.find_spec("opentelemetry.metrics")
bridge = importlib.util.find_spec("bluetape.observability")
assert api and api.origin and bridge and bridge.origin
root = Path(__import__("sys").prefix).resolve()
assert Path(api.origin).resolve().is_relative_to(root)
assert Path(bridge.origin).resolve().is_relative_to(root)
assert absent("opentelemetry.sdk")
assert absent("bluetape.resilience")
assert absent("bluetape.cache.redis")
result = {
    "opentelemetry_api_version": importlib.metadata.version("opentelemetry-api"),
    "opentelemetry_origin": api.origin,
    "observability_origin": bridge.origin,
    "sdk_absent": True,
    "domains_absent": True,
    "api_probe": True,
}
Path("focused-probe.json").write_text(json.dumps(result, sort_keys=True))
'
)

python3 - "$observability_wheel" "$tmp_dir/wheel-metadata.json" <<'PY'
import email
import json
import sys
import zipfile
from pathlib import Path

wheel = Path(sys.argv[1])
with zipfile.ZipFile(wheel) as archive:
    metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
    metadata = email.message_from_bytes(archive.read(metadata_name))
requirements = metadata.get_all("Requires-Dist") or []
assert requirements == ["opentelemetry-api>=1.43,<2"]
Path(sys.argv[2]).write_text(json.dumps({"requires_dist": requirements}, sort_keys=True))
PY

uv venv "$tmp_dir/default" --python 3.13.14 >/dev/null
uv pip install --python "$tmp_dir/default/bin/python" --no-index \
  --find-links "$tmp_dir/dist" bluetape==0.1.0 >/dev/null
uv pip check --python "$tmp_dir/default/bin/python" >/dev/null
(
  cd "$tmp_dir"
  "$tmp_dir/default/bin/python" -I -c '
import importlib.util
import json
from pathlib import Path

def absent(name):
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:
        return True

assert absent("opentelemetry")
assert absent("bluetape.observability")
core = importlib.util.find_spec("bluetape.core")
assert core and core.origin
result = {
    "core_origin": core.origin,
    "opentelemetry_absent": True,
    "observability_absent": True,
    "default_probe": True,
}
Path("default-probe.json").write_text(json.dumps(result, sort_keys=True))
'
)

uv export --locked --package bluetape-observability --no-dev --no-emit-local \
  -o "$tmp_dir/observability-requirements.txt" >/dev/null
uv export --locked --package bluetape-cache-redis --no-dev --no-emit-local \
  -o "$tmp_dir/redis-requirements.txt" >/dev/null
uv venv "$tmp_dir/readme" --python 3.13.14 >/dev/null
uv pip sync --python "$tmp_dir/readme/bin/python" --require-hashes \
  "$tmp_dir/observability-requirements.txt" "$tmp_dir/redis-requirements.txt" >/dev/null
uv pip install --python "$tmp_dir/readme/bin/python" --no-deps \
  "$resilience_wheel" "$cache_wheel" "$compression_wheel" "$serde_wheel" \
  "$redis_wheel" "$observability_wheel" >/dev/null
uv pip check --python "$tmp_dir/readme/bin/python" >/dev/null

python3 - "$tmp_dir/api-only-example.py" <<'PY'
import re
import sys
from pathlib import Path

text = Path("packages/bluetape-observability/README.md").read_text()
match = re.search(
    r"<!-- api-only-example:start -->\n```python\n(.*?)\n```\n<!-- api-only-example:end -->",
    text,
    re.DOTALL,
)
assert match is not None
Path(sys.argv[1]).write_text(match.group(1) + "\n")
PY
(
  cd "$tmp_dir"
  "$tmp_dir/readme/bin/python" -I -c '
import importlib.util
import json
from pathlib import Path

assert importlib.util.find_spec("opentelemetry.sdk") is None
modules = {
    name: importlib.util.find_spec(name)
    for name in (
        "bluetape.observability",
        "bluetape.resilience",
        "bluetape.cache.redis",
    )
}
assert all(spec and spec.origin for spec in modules.values())
root = Path(__import__("sys").prefix).resolve()
assert all(Path(spec.origin).resolve().is_relative_to(root) for spec in modules.values())
result = {
    "origins": {name: spec.origin for name, spec in modules.items()},
    "sdk_absent": True,
    "readme_probe": True,
}
Path("readme-probe.json").write_text(json.dumps(result, sort_keys=True))
'
  "$tmp_dir/readme/bin/python" -I "$tmp_dir/api-only-example.py"
)

export VERIFY_TMP_DIR="$tmp_dir"
export VERIFY_PACKAGES="${packages[*]}"
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["VERIFY_TMP_DIR"])
expected = os.environ["VERIFY_PACKAGES"].split()
wheels = []
counts = {}
for distribution in expected:
    normalized = distribution.replace("-", "_")
    matches = sorted((root / "dist").glob(f"{normalized}-*.whl"))
    counts[distribution] = len(matches)
    for path in matches:
        wheels.append(
            {
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
focused = json.loads((root / "focused-probe.json").read_text())
default = json.loads((root / "default-probe.json").read_text())
readme = json.loads((root / "readme-probe.json").read_text())
metadata = json.loads((root / "wheel-metadata.json").read_text())
summary = {
    "schema_version": 1,
    "wheels": sorted(wheels, key=lambda item: item["filename"]),
    "wheel_counts": counts,
    "opentelemetry_api_version": focused["opentelemetry_api_version"],
    "focused": focused,
    "default": default,
    "readme": readme,
    "metadata": metadata,
    "verdicts": {
        "focused": focused["api_probe"],
        "default": default["default_probe"],
        "readme": readme["readme_probe"],
    },
}
assert all(count == 1 for count in counts.values())
assert all(summary["verdicts"].values())
print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
PY
