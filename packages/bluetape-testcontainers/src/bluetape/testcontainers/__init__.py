"""Ecosystem-owned Testcontainers wrappers for bluetape-py."""

from bluetape.testcontainers.localstack import (
    DEFAULT_LOCALSTACK_IMAGE,
    LocalStackConnectionDetails,
    LocalStackServer,
)
from bluetape.testcontainers.postgres import (
    DEFAULT_POSTGRES_IMAGE,
    PostgresConnectionDetails,
    PostgresServer,
)
from bluetape.testcontainers.redis import (
    DEFAULT_REDIS_IMAGE,
    RedisConnectionDetails,
    RedisServer,
    StartFailureKind,
    TestcontainerStartError,
)

__all__ = [
    "DEFAULT_LOCALSTACK_IMAGE",
    "DEFAULT_POSTGRES_IMAGE",
    "DEFAULT_REDIS_IMAGE",
    "LocalStackConnectionDetails",
    "LocalStackServer",
    "PostgresConnectionDetails",
    "PostgresServer",
    "RedisConnectionDetails",
    "RedisServer",
    "StartFailureKind",
    "TestcontainerStartError",
]
