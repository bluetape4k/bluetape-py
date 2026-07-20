from bluetape.jwt import JWSAlgorithm
from bluetape.jwt._algorithms import _AlgorithmFamily


def test_algorithm_values_are_exact() -> None:
    assert [(algorithm.name, algorithm.value) for algorithm in JWSAlgorithm] == [
        ("HS256", "HS256"),
        ("HS384", "HS384"),
        ("HS512", "HS512"),
        ("RS256", "RS256"),
        ("RS384", "RS384"),
        ("RS512", "RS512"),
        ("PS256", "PS256"),
        ("PS384", "PS384"),
        ("PS512", "PS512"),
    ]


def test_algorithm_family_and_strength_helpers_are_internal_and_exact() -> None:
    assert {
        algorithm: (algorithm._family, algorithm._minimum_key_bits) for algorithm in JWSAlgorithm
    } == {
        JWSAlgorithm.HS256: (_AlgorithmFamily.HMAC, 256),
        JWSAlgorithm.HS384: (_AlgorithmFamily.HMAC, 384),
        JWSAlgorithm.HS512: (_AlgorithmFamily.HMAC, 512),
        JWSAlgorithm.RS256: (_AlgorithmFamily.RSA, 2048),
        JWSAlgorithm.RS384: (_AlgorithmFamily.RSA, 2048),
        JWSAlgorithm.RS512: (_AlgorithmFamily.RSA, 2048),
        JWSAlgorithm.PS256: (_AlgorithmFamily.RSA, 2048),
        JWSAlgorithm.PS384: (_AlgorithmFamily.RSA, 2048),
        JWSAlgorithm.PS512: (_AlgorithmFamily.RSA, 2048),
    }
