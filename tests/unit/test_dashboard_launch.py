"""Tests for the dashboard launcher: when Litestream runs, and what it replicates."""

from pathlib import Path

from app.dashboard_launch import SERVER, litestream_config, replica_url, store_region


def test_replica_lives_under_the_owner_in_the_store():
    """The index replicates to <store root>/users/<owner>/index."""
    env = {"STARGAZER_STORE_ROOT": "s3://bucket/stargazer/", "SG_OWNER_SUBJECT": "u1"}
    assert replica_url(env) == "s3://bucket/stargazer/users/u1/index"


def test_no_durable_store_means_no_litestream():
    """Without a bucket root or an owner, the dashboard just serves."""
    assert replica_url({"SG_OWNER_SUBJECT": "u1"}) is None
    assert (
        replica_url({"STARGAZER_STORE_ROOT": "/tmp/store", "SG_OWNER_SUBJECT": "u1"})
        is None
    )
    assert replica_url({"STARGAZER_STORE_ROOT": "s3://bucket/stargazer"}) is None


def test_config_replicates_the_index_file():
    """The Litestream config names the index file, the replica and its region."""
    text = litestream_config(
        Path("/home/flyte/.stargazer/index.db"),
        "s3://bucket/stargazer/users/u1/index",
        "us-west-2",
    )
    assert "path: /home/flyte/.stargazer/index.db" in text
    assert "url: s3://bucket/stargazer/users/u1/index" in text
    assert "region: us-west-2" in text


def test_region_comes_from_the_pod_first():
    """AWS_REGION, then AWS_DEFAULT_REGION, then the deploy's own setting.

    The region has to be given: Litestream's lookup needs s3:GetBucketLocation,
    which the tenant's role doesn't grant (measured on the tenant).
    """
    assert (
        store_region({"AWS_REGION": "us-west-2", "AWS_DEFAULT_REGION": "x"})
        == "us-west-2"
    )
    assert store_region({"AWS_DEFAULT_REGION": "eu-west-1"}) == "eu-west-1"
    assert store_region({"STARGAZER_STORE_REGION": "us-east-2"}) == "us-east-2"
    assert store_region({}) is None


def test_server_is_the_dashboard():
    """The process Litestream wraps is the dashboard's uvicorn."""
    assert SERVER[:2] == ["uvicorn", "app.admin_app:asgi_app"]
