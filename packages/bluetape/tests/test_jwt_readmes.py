from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[3]
READMES = (
    ROOT / "packages/bluetape-jwt/README.md",
    ROOT / "packages/bluetape-jwt/README.ko.md",
)
SCENARIOS = {
    "install",
    "profile-provider",
    "issuance-policy",
    "rotation-revocation",
    "cache-boundary",
    "security-boundary",
    "follow-ups",
}


def scenario_ids(path: Path) -> set[str]:
    return set(re.findall(r"<!-- jwt-scenario:([a-z-]+) -->", path.read_text()))


def test_bilingual_jwt_readmes_have_exact_scenario_parity() -> None:
    assert scenario_ids(READMES[0]) == scenario_ids(READMES[1]) == SCENARIOS


def test_bilingual_jwt_readmes_keep_api_examples_aligned() -> None:
    calls = re.compile(
        r"(?:JWTKey\.from_hmac_secret|InMemoryKeyRepository|ValidationProfile|"
        r"VerifiedTokenCacheOptions|JWSProvider|IssuanceProfile|"
        r"IssuanceProfileProvider)\([^\n]*"
    )

    def example_calls(path: Path) -> list[str]:
        blocks = re.findall(r"```python\n(.*?)```", path.read_text(), flags=re.DOTALL)
        return calls.findall("\n".join(blocks))

    assert example_calls(READMES[0]) == example_calls(READMES[1])


def test_jwt_readmes_record_install_algorithms_and_operational_limits() -> None:
    required = (
        'pip install "bluetape[jwt]"',
        "pip install bluetape-jwt",
        "HS256",
        "HS384",
        "HS512",
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ACTIVE",
        "RETIRED",
        "REVOKED",
        "typ",
        "issuer",
        "audience",
        "default_ttl=None",
        "VerifiedTokenCacheOptions",
        "#88",
        "#89",
        "#90",
    )
    for path in READMES:
        text = path.read_text()
        assert all(value in text for value in required), path
