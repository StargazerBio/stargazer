"""Tests for `app.deploy`: building the notebook image and deploying a dashboard.

Serving is faked at `flyte.with_servecontext`, so nothing reaches a cluster.
"""

import os
import subprocess
from types import SimpleNamespace

import pytest

from app import config, deploy

ALICE = "387300641116005877"
CLUSTER = "arn:aws:dsql:us-west-2:111122223333:cluster/abc123"


@pytest.fixture(autouse=True)
def dsql_cluster(monkeypatch):
    """Deploys index on the org's DSQL cluster, as every Union deploy does."""
    monkeypatch.setattr(config, "DSQL_CLUSTER_ARN", CLUSTER)


def test_notebook_image_is_the_built_uri(monkeypatch):
    """Dashboards bake in the content-hashed URI the build returns, no retag."""
    monkeypatch.setattr(
        deploy.flyte, "build", lambda img: SimpleNamespace(uri="reg/notebook-app:h1")
    )
    assert deploy.build_notebook_image() == "reg/notebook-app:h1"


def test_dashboard_deploy_keeps_the_env_resolvable(monkeypatch, served_dashboard):
    """The served env is built where it's defined, with the owner's settings.

    Flyte resolves `include=` paths and the pod's loader from the frame the
    env was created in; a `clone_with` copy reports `dataclasses.py` instead,
    and the deploy fails on `templates/`.
    """
    monkeypatch.setattr(
        deploy, "get_init_config", lambda: SimpleNamespace(org="stargazerbio")
    )
    assert deploy.deploy_dashboard("u-jane", ALICE) == "https://u-jane.apps.example"
    assert served_dashboard["env"]._caller_frame.filename.endswith("app/admin_app.py")
    assert (served_dashboard["ctx"]["project"], served_dashboard["ctx"]["domain"]) == (
        "u-jane",
        "development",
    )
    assert served_dashboard["domain"].subdomain == "u-jane"
    assert {
        k: served_dashboard["env_vars"][k]
        for k in (
            "FLYTE_PROJECT",
            "SG_OWNER_SUBJECT",
            "STARGAZER_NOTEBOOK_IMAGE",
            "FLYTE_ORG",
        )
    } == {
        "FLYTE_PROJECT": "u-jane",
        "SG_OWNER_SUBJECT": ALICE,
        "STARGAZER_NOTEBOOK_IMAGE": "reg/notebook-app:h1",
        "FLYTE_ORG": "stargazerbio",
    }


def test_dashboard_deploy_carries_the_asset_store_and_owner(
    monkeypatch, served_dashboard
):
    """The dashboard stores under the workspace root and stamps its owner."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    monkeypatch.setattr(config, "ADMIN_SUBJECTS", frozenset({"391057331988775036"}))
    monkeypatch.setattr(config, "PUBLIC_ASSETS", False)
    deploy.deploy_dashboard("u-jane", ALICE)
    env_vars = served_dashboard["env_vars"]
    assert env_vars["STARGAZER_PUBLIC_ASSETS"] == "off"
    assert env_vars["STARGAZER_ADMIN_SUBJECTS"] == "391057331988775036"
    assert env_vars["STARGAZER_STORE_ROOT"] == "s3://bucket/stargazer"
    assert env_vars["STARGAZER_OWNER"] == ALICE


def test_dashboard_deploy_is_versioned_with_the_release(monkeypatch, served_dashboard):
    """The deploy's version is the commit it came from, on its page and in the console."""
    monkeypatch.setattr(deploy, "release_version", lambda: "18fbabe-dirty")
    deploy.deploy_dashboard("u-jane", ALICE)
    assert served_dashboard["env_vars"]["STARGAZER_VERSION"] == "18fbabe-dirty"
    assert served_dashboard["ctx"]["version"] == "18fbabe-dirty"


@pytest.fixture
def bare_git_env(monkeypatch):
    """No inherited `GIT_*` variables: a pre-commit hook's would point at this repo."""
    for name in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(name)


def test_release_version_is_the_checkout_commit(tmp_path, bare_git_env):
    """The deployer's commit, marked `-dirty` when tracked files have changed."""

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-q")
    (tmp_path / "notes.txt").write_text("one")
    git("add", "notes.txt")
    git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-qm", "c")
    sha = git("rev-parse", "--short", "HEAD")
    assert deploy.release_version(tmp_path) == sha
    (tmp_path / "notes.txt").write_text("two")
    assert deploy.release_version(tmp_path) == f"{sha}-dirty"


def test_release_version_outside_a_checkout_is_unknown(tmp_path, bare_git_env):
    """Deploying from something that isn't a git checkout still deploys."""
    assert deploy.release_version(tmp_path) == "unknown"


def test_dashboard_deploy_waits_out_a_stale_watch_failure(monkeypatch):
    """A watch error on a deploy that does come up is not reported as failure.

    Seen on the tenant: the watch tripped on an older failed revision while
    the new one became ready a few seconds later.
    """

    def failing_servecontext(**ctx):
        def serve(env):
            raise RuntimeError("App deployment for app dashboard has failed!")

        return SimpleNamespace(serve=serve)

    states = iter([False, False, True])

    class FakeApp:
        @staticmethod
        def get(name, project, domain):
            active = next(states)
            return SimpleNamespace(
                is_active=lambda: active, endpoint="https://u-jane.apps.example"
            )

    monkeypatch.setattr(deploy.flyte, "with_servecontext", failing_servecontext)
    monkeypatch.setattr(deploy, "App", FakeApp)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(deploy.time, "sleep", lambda s: None)
    assert deploy.deploy_dashboard("u-jane", ALICE) == "https://u-jane.apps.example"


def test_a_projects_index_login_is_a_plain_identifier():
    """`-` can't sit in an unquoted identifier, so it becomes `_`."""
    assert deploy.login_for("u-jane-2") == "u_jane_2"


def test_dashboard_deploy_indexes_in_the_users_dsql_table(served_dashboard):
    """The dashboard's index is the user's DSQL table, as `make_index` opens it."""
    deploy.deploy_dashboard("u-jane", ALICE)
    assert served_dashboard["env_vars"]["STARGAZER_INDEX_URL"] == (
        "dsql://u_jane@abc123.dsql.us-west-2.on.aws/assets.u_jane"
        "?role_arn=arn:aws:iam::111122223333:role/stargazer-index-u-jane"
    )


def test_dashboard_deploy_without_an_index_server_is_refused(
    monkeypatch, served_dashboard
):
    """No cluster and no index given: refused before anything is served.

    The dashboard would fall back to a file on its own disk, which its pods
    can't reach and scale-to-zero erases.
    """
    monkeypatch.setattr(config, "DSQL_CLUSTER_ARN", "")
    with pytest.raises(RuntimeError, match="STARGAZER_DSQL_CLUSTER_ARN"):
        deploy.deploy_dashboard("u-jane", ALICE)
    assert served_dashboard == {}


def test_dashboard_deploy_takes_a_given_index_without_a_cluster(
    monkeypatch, served_dashboard
):
    """The devbox's dashboard brings its Postgres URL and needs no cluster."""
    monkeypatch.setattr(config, "DSQL_CLUSTER_ARN", "")
    url = "postgresql://sg:pw@postgres.stargazer.svc.cluster.local:5432/stargazer"
    deploy.deploy_dashboard("u-jane", ALICE, extra_env={"STARGAZER_INDEX_URL": url})
    assert served_dashboard["env_vars"]["STARGAZER_INDEX_URL"] == url
