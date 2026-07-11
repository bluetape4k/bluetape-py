import pytest
from bluetape.testcontainers import DEFAULT_REDIS_IMAGE, RedisServer

from ._support import redis_command


@pytest.mark.testcontainers
def test_redis_8_server_supports_dynamic_port_and_resp_round_trip() -> None:
    with RedisServer() as server:
        assert DEFAULT_REDIS_IMAGE == "redis:8"
        assert server.port > 0
        assert server.url == f"redis://{server.host}:{server.port}"
        assert redis_command(server.host, server.port, "PING") == b"PONG"
        assert redis_command(server.host, server.port, "SET", "issue:57", "ok") == b"OK"
        assert redis_command(server.host, server.port, "GET", "issue:57") == b"ok"

    assert server.running is False
    with pytest.raises(RuntimeError, match="not running"):
        _ = server.details
