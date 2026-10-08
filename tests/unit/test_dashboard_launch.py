"""Tests for the dashboard launcher: when Litestream runs, and what it replicates."""

from app.dashboard_launch import SERVER, litestream_env, replica_url


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


def test_replica_url_names_an_s3_compatible_endpoint():
    """A store that isn't AWS S3 (the devbox's) rides on the URL as endpoint=,
    taken from the FLYTE_AWS_ENDPOINT Flyte gives its pods there.

    Without it Litestream tries AWS and fails looking up the bucket's region
    (measured on the devbox).
    """
    env = {
        "STARGAZER_STORE_ROOT": "s3://flyte-data/stargazer",
        "SG_OWNER_SUBJECT": "u1",
        "FLYTE_AWS_ENDPOINT": "http://rustfs-svc.flyte:9000",
    }
    base = "s3://flyte-data/stargazer/users/u1/index"
    endpoint = "endpoint=http%3A%2F%2Frustfs-svc.flyte%3A9000"
    assert replica_url(env) == f"{base}?{endpoint}"
    assert (
        replica_url({**env, "AWS_REGION": "us-east-1"})
        == f"{base}?region=us-east-1&{endpoint}"
    )


def test_litestream_gets_the_stores_credentials():
    """Flyte hands the devbox store's keys to pods as FLYTE_AWS_*; Litestream
    reads AWS_*, so the launcher copies them across. Keys already set win."""
    env = {
        "PATH": "/usr/bin",
        "FLYTE_AWS_ACCESS_KEY_ID": "rustfs",
        "FLYTE_AWS_SECRET_ACCESS_KEY": "rustfsstorage",
    }
    assert litestream_env(env) == {
        **env,
        "AWS_ACCESS_KEY_ID": "rustfs",
        "AWS_SECRET_ACCESS_KEY": "rustfsstorage",
    }
    mine = {**env, "AWS_ACCESS_KEY_ID": "a", "AWS_SECRET_ACCESS_KEY": "b"}
    assert litestream_env(mine) == mine


def test_without_flyte_keys_litestream_env_is_unchanged():
    """On Union the pod role supplies credentials; nothing is added."""
    env = {"PATH": "/usr/bin", "AWS_REGION": "us-west-2"}
    assert litestream_env(env) == env


def test_server_is_the_dashboard():
    """The process Litestream wraps is the dashboard's uvicorn."""
    assert SERVER[:2] == ["uvicorn", "app.admin_app:asgi_app"]
