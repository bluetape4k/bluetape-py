"""Fast source-tree packaging checks for bluetape-jwt."""

import tomllib
from pathlib import Path

import bluetape.jwt as jwt

ROOT = Path(__file__).parents[4]
JWT_DEPENDENCY = "bluetape-jwt==0.1.0"
PUBLIC_EXPORTS = [
    "JWTError",
    "JWTConfigurationError",
    "JWTKeyError",
    "JWTKeyStateError",
    "JWTKeyUnavailableError",
    "JWTTokenError",
    "JWTMalformedTokenError",
    "JWTUnsupportedTokenError",
    "JWTSignatureError",
    "JWTExpiredError",
    "JWTNotYetValidError",
    "JWTClaimError",
    "JWTIssuancePolicyError",
    "JWTCacheError",
    "JWSAlgorithm",
    "KeyStatus",
    "JSONValue",
    "JWTKey",
    "KeyEntry",
    "KeySnapshot",
    "KeyRepository",
    "InMemoryKeyRepository",
    "TokenClaims",
    "VerifiedToken",
    "IssuanceProfile",
    "ValidationProfile",
    "TokenProvider",
    "IssuanceProfileProvider",
    "JWSProvider",
    "VerifiedTokenCacheOptions",
]


def load_pyproject(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_workspace_registers_jwt() -> None:
    root = load_pyproject(ROOT / "pyproject.toml")

    assert root["project"]["dependencies"].count(JWT_DEPENDENCY) == 1
    assert root["tool"]["uv"]["sources"]["bluetape-jwt"] == {"workspace": True}
    assert root["tool"]["uv"]["workspace"]["members"].count("packages/bluetape-jwt") == 1


def test_jwt_distribution_metadata_is_exact() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape-jwt/pyproject.toml")
    project = metadata["project"]

    assert project["name"] == "bluetape-jwt"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.13"
    assert project["dependencies"] == [
        "bluetape-cache==0.1.0",
        "joserfc>=1.7.4,<2",
    ]
    assert metadata["build-system"] == {
        "requires": ["uv_build>=0.11.28,<0.12"],
        "build-backend": "uv_build",
    }
    assert metadata["tool"]["uv"]["build-backend"]["module-name"] == "bluetape.jwt"


def test_meta_extra_includes_jwt_without_widening_default() -> None:
    metadata = load_pyproject(ROOT / "packages/bluetape/pyproject.toml")
    project = metadata["project"]

    assert project["dependencies"] == ["bluetape-core==0.1.0"]
    assert project["optional-dependencies"]["jwt"] == [JWT_DEPENDENCY]
    assert JWT_DEPENDENCY in project["optional-dependencies"]["dev"]
    assert JWT_DEPENDENCY in project["optional-dependencies"]["all"]
    assert metadata["tool"]["uv"]["sources"]["bluetape-jwt"] == {"workspace": True}


def test_namespace_and_typing_marker_are_packaged_without_root_initializer() -> None:
    package_root = ROOT / "packages/bluetape-jwt/src/bluetape"

    assert not (package_root / "__init__.py").exists()
    assert (package_root / "jwt/py.typed").is_file()


def test_public_surface_has_exact_reviewed_order() -> None:
    assert jwt.__all__ == PUBLIC_EXPORTS


def test_readmes_are_aligned_with_completed_sync_scope() -> None:
    english = (ROOT / "packages/bluetape-jwt/README.md").read_text()
    korean = (ROOT / "packages/bluetape-jwt/README.ko.md").read_text()

    assert "Implementation status: in progress" not in english
    assert "구현 상태: 진행 중" not in korean
    assert "JWSAlgorithm" in english and "JWSAlgorithm" in korean
    assert "JWSProvider(" in english and "JWSProvider(" in korean
