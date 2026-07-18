import psycopg
import pytest
from bluetape.testcontainers import DEFAULT_POSTGRES_IMAGE, PostgresServer

from ._support import assert_container_removed, published_host_ips

pytestmark = pytest.mark.testcontainers


def test_postgres_18_query_loopback_binding_and_cleanup() -> None:
    server = PostgresServer()
    with server:
        provider = server._container
        assert provider is not None
        wrapped = provider.get_wrapped_container()
        container_id = wrapped.id

        assert DEFAULT_POSTGRES_IMAGE == "postgres:18-alpine"
        host_ips = published_host_ips(provider, 5432)
        assert host_ips
        assert host_ips <= {"127.0.0.1", "::1"}
        with psycopg.connect(server.details.url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select current_setting('server_version_num')")
                version = int(cursor.fetchone()[0])
        assert version >= 180000
        assert server.details.connection_url(driver="psycopg").startswith("postgresql+psycopg://")

    assert_container_removed(container_id)
