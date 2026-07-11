import json
import os
import subprocess
import sys
import timeit
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pyfory
import pytest
from bluetape.serde import PayloadMetadata, TrustProfile
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyLimits,
    ForyRegistration,
)


@dataclass(slots=True)
class PerformanceRecord:
    record_id: pyfory.Int64
    name: str
    scores: list[pyfory.Int32]


def metadata() -> PayloadMetadata:
    return PayloadMetadata(
        format=FORY_FORMAT,
        version=FORY_VERSION,
        content_type=FORY_CONTENT_TYPE,
        trust_profile=TrustProfile.TRUSTED_INTERNAL,
    )


def adapter() -> ForyAdapter[PerformanceRecord]:
    return ForyAdapter(
        registration=ForyRegistration(
            python_type=PerformanceRecord,
            schema_id=0x42545046,
            schema_version=1,
            type_id=1101,
            logical_name="io.bluetape.serde.PerformanceRecord",
        ),
        limits=ForyLimits(max_concurrency=4),
    )


def measure_case(name: str, value: PerformanceRecord) -> dict[str, int | float | str]:
    active_adapter = adapter()
    policy = metadata()
    payload = active_adapter.serialize(value, metadata=policy)
    assert active_adapter.deserialize(payload, expected_metadata=metadata()) == value

    serialize_seconds = timeit.timeit(
        lambda: active_adapter.serialize(value, metadata=policy),
        number=1000,
    )
    deserialize_seconds = timeit.timeit(
        lambda: active_adapter.deserialize(payload, expected_metadata=policy),
        number=1000,
    )
    tracemalloc.start()
    active_adapter.serialize(value, metadata=policy)
    active_adapter.deserialize(payload, expected_metadata=policy)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "case": name,
        "encoded_bytes": len(payload.data),
        "serialize_1000_seconds": serialize_seconds,
        "deserialize_1000_seconds": deserialize_seconds,
        "tracemalloc_peak_bytes": peak_bytes,
    }


def test_fory_smoke_measurements_are_structurally_bounded() -> None:
    small = PerformanceRecord(pyfory.Int64(1), "small", [pyfory.Int32(1)])
    large = PerformanceRecord(
        pyfory.Int64(2),
        "large",
        [pyfory.Int32(index) for index in range(4096)],
    )

    observations = [measure_case("small", small), measure_case("large", large)]

    assert observations[0]["encoded_bytes"] < observations[1]["encoded_bytes"]
    assert all(observation["encoded_bytes"] <= 16 * 1024 * 1024 for observation in observations)
    print("FORY_PERFORMANCE=" + json.dumps(observations, sort_keys=True))


def test_fory_post_contention_adapter_reuse() -> None:
    active_adapter = adapter()
    policy = metadata()
    values = [
        PerformanceRecord(pyfory.Int64(index), f"record-{index}", [pyfory.Int32(index)])
        for index in range(32)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        payloads = list(
            executor.map(lambda value: active_adapter.serialize(value, metadata=policy), values)
        )
    results = [
        active_adapter.deserialize(payload, expected_metadata=policy) for payload in payloads
    ]
    after = active_adapter.serialize(values[0], metadata=policy)

    assert results == values
    assert active_adapter.deserialize(after, expected_metadata=policy) == values[0]
    print(
        "FORY_CONTENTION="
        + json.dumps(
            {
                "operations": len(values),
                "max_concurrency": active_adapter.limits.max_concurrency,
                "post_contention_encoded_bytes": len(after.data),
            },
            sort_keys=True,
        )
    )


_RSS_SCRIPT = r"""
import json
import resource
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import pyfory
from bluetape.serde import PayloadMetadata, TrustProfile
from bluetape.serde.fory import (
    FORY_CONTENT_TYPE,
    FORY_FORMAT,
    FORY_VERSION,
    ForyAdapter,
    ForyLimits,
    ForyRegistration,
)

@dataclass(slots=True)
class R:
    record_id: pyfory.Int64
    scores: list[pyfory.Int32]

metadata = PayloadMetadata(
    format=FORY_FORMAT,
    version=FORY_VERSION,
    content_type=FORY_CONTENT_TYPE,
    trust_profile=TrustProfile.TRUSTED_INTERNAL,
)
adapter = ForyAdapter(
    registration=ForyRegistration(
        python_type=R,
        schema_id=1112819270,
        schema_version=1,
        type_id=1201,
        logical_name="io.bluetape.serde.RssRecord",
    ),
    limits=ForyLimits(max_concurrency=4),
)
scenario = sys.argv[1]
count = 1 if scenario == "small" else 4096
value = R(pyfory.Int64(1), [pyfory.Int32(i) for i in range(count)])
if scenario == "contention":
    with ThreadPoolExecutor(max_workers=8) as executor:
        payloads = list(
            executor.map(lambda _: adapter.serialize(value, metadata=metadata), range(32))
        )
    for payload in payloads:
        assert adapter.deserialize(payload, expected_metadata=metadata) == value
else:
    for _ in range(100):
        payload = adapter.serialize(value, metadata=metadata)
        assert adapter.deserialize(payload, expected_metadata=metadata) == value
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
rss_bytes = rss if sys.platform == "darwin" else rss * 1024
print(
    json.dumps(
        {
            "scenario": scenario,
            "rss_bytes": rss_bytes,
            "encoded_bytes": len(adapter.serialize(value, metadata=metadata).data),
        },
        sort_keys=True,
    )
)
"""


@pytest.mark.parametrize("scenario", ["small", "large", "contention"])
def test_fory_native_rss_high_water_is_recorded_in_isolated_process(scenario: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _RSS_SCRIPT, scenario],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "LC_ALL": "C.UTF-8", "TZ": "UTC"},
    )
    observation = json.loads(completed.stdout)

    assert observation["scenario"] == scenario
    assert observation["rss_bytes"] > 0
    assert 20 < observation["encoded_bytes"] <= 16 * 1024 * 1024
    print("FORY_RSS=" + json.dumps(observation, sort_keys=True))
