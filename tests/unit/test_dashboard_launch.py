"""Tests for the dashboard launcher: when Litestream runs, and what it replicates."""

from app.dashboard_launch import SERVER, replica_url


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


def test_replica_url_carries_the_region():
    """The bucket's region rides on the replica URL: AWS_REGION, then
    AWS_DEFAULT_REGION, then the deploy's own setting.

    It has to be given: Litestream's lookup needs s3:GetBucketLocation, which
    the tenant's role doesn't grant (measured on the tenant).
    """
    env = {"STARGAZER_STORE_ROOT": "s3://bucket/stargazer", "SG_OWNER_SUBJECT": "u1"}
    base = "s3://bucket/stargazer/users/u1/index"
    assert (
        replica_url({**env, "AWS_REGION": "us-west-2", "AWS_DEFAULT_REGION": "x"})
        == f"{base}?region=us-west-2"
    )
    assert (
        replica_url({**env, "AWS_DEFAULT_REGION": "eu-west-1"})
        == f"{base}?region=eu-west-1"
    )
    assert (
        replica_url({**env, "STARGAZER_STORE_REGION": "us-east-2"})
        == f"{base}?region=us-east-2"
    )


def test_server_is_the_dashboard():
    """The process Litestream wraps is the dashboard's uvicorn."""
    assert SERVER[:2] == ["uvicorn", "app.admin_app:asgi_app"]
