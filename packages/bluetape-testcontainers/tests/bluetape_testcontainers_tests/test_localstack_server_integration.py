import pytest
from bluetape.testcontainers import DEFAULT_LOCALSTACK_IMAGE, LocalStackServer

from ._support import assert_container_removed, published_host_ips

pytestmark = pytest.mark.testcontainers


def test_localstack_s3_round_trip_loopback_binding_and_cleanup() -> None:
    boto3 = pytest.importorskip(
        "boto3",
        reason="LocalStack integration tests require the package test dependency group",
    )

    server = LocalStackServer(services=("s3",))
    with server:
        provider = server._container
        assert provider is not None
        wrapped = provider.get_wrapped_container()
        container_id = wrapped.id
        details = server.details

        assert DEFAULT_LOCALSTACK_IMAGE == "localstack/localstack:4.14.0"
        assert details.services == ("s3",)
        host_ips = published_host_ips(provider, 4566)
        assert host_ips
        assert host_ips <= {"127.0.0.1", "::1"}
        client = boto3.client(
            "s3",
            endpoint_url=details.endpoint_url,
            region_name=details.region_name,
            aws_access_key_id=details.access_key_id,
            aws_secret_access_key=details.secret_access_key,
        )
        try:
            client.create_bucket(Bucket="bluetape-issue-15")
            buckets = {bucket["Name"] for bucket in client.list_buckets()["Buckets"]}
            assert "bluetape-issue-15" in buckets
        finally:
            client.close()

    assert_container_removed(container_id)
