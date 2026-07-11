import pytest
from bluetape.testcontainers import DEFAULT_REDIS_IMAGE, RedisServer

from ._support import redis_command


@pytest.mark.testcontainers
def test_redis_8_server_supports_dynamic_port_and_resp_round_trip() -> None:
    with RedisServer() as first_server:
        assert DEFAULT_REDIS_IMAGE == "redis:8"
        assert first_server.port > 0
        assert first_server.url == f"redis://{first_server.host}:{first_server.port}"
        assert redis_command(first_server.host, first_server.port, "PING") == b"PONG"
        assert (
            redis_command(first_server.host, first_server.port, "SET", "issue:57", "first") == b"OK"
        )
        assert redis_command(first_server.host, first_server.port, "GET", "issue:57") == b"first"
        first_details = first_server.details

    assert first_server.running is False
    with pytest.raises(RuntimeError, match="not running"):
        _ = first_server.details

    with RedisServer() as second_server:
        second_details = second_server.details
        assert second_details is not first_details
        assert redis_command(second_server.host, second_server.port, "GET", "issue:57") is None
        assert (
            redis_command(second_server.host, second_server.port, "SET", "issue:57", "second")
            == b"OK"
        )
        assert redis_command(second_server.host, second_server.port, "GET", "issue:57") == b"second"

    assert second_server.running is False
