"""Ecosystem-owned Testcontainers wrappers for bluetape-py."""

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
    "DEFAULT_POSTGRES_IMAGE",
    "DEFAULT_REDIS_IMAGE",
    "PostgresConnectionDetails",
    "PostgresServer",
    "RedisConnectionDetails",
    "RedisServer",
    "StartFailureKind",
    "TestcontainerStartError",
]
