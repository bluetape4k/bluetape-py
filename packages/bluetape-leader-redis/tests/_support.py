from __future__ import annotations

from collections.abc import Callable
from typing import Any

import redis
import redis.asyncio as async_redis
from redis.backoff import NoBackoff
from redis.maint_notifications import MaintNotificationsConfig
from redis.retry import Retry


def safe_sync_client(**overrides: Any) -> redis.Redis:
    options: dict[str, Any] = {
        "host": "127.0.0.1",
        "socket_connect_timeout": 0.05,
        "socket_timeout": 0.05,
        "health_check_interval": 0,
        "retry": Retry(NoBackoff(), 0),
        "retry_on_error": [],
        "maint_notifications_config": MaintNotificationsConfig(
            enabled=False,
            proactive_reconnect=False,
            relaxed_timeout=-1,
        ),
    }
    options.update(overrides)
    return redis.Redis(**options)


def safe_async_client(**overrides: Any) -> async_redis.Redis:
    from redis.asyncio.retry import Retry as AsyncRetry

    options: dict[str, Any] = {
        "host": "127.0.0.1",
        "socket_connect_timeout": 0.05,
        "socket_timeout": 0.05,
        "health_check_interval": 0,
        "retry": AsyncRetry(NoBackoff(), 0),
        "retry_on_error": [],
    }
    options.update(overrides)
    return async_redis.Redis(**options)


class HostileCallback:
    def __init__(self, callback: Callable[[], Any]) -> None:
        self._callback = callback

    def get_credentials(self) -> Any:
        return self._callback()

    async def get_credentials_async(self) -> Any:
        return self._callback()
